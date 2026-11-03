"""防災情報ビューアー 0.51 — localhost only."""
from datetime import datetime, timezone, timedelta
from threading import Lock
import math
import hashlib
import json
from pathlib import Path
import time
import requests
from flask import Flask, jsonify, render_template,send_file,request
import jma
import usgs

app = Flask(__name__)
import asset_delivery48
asset_delivery48.install(app)
URL = 'https://api.p2pquake.net/v2/history'
SCALES = {0: "0",10:'1',20:'2',30:'3',40:'4',45:'5弱',50:'5強',55:'6弱',60:'6強',70:'7'}
TYPES = {'ScalePrompt':'震度速報','Destination':'震源に関する情報','ScaleAndDestination':'震源・震度情報','DetailScale':'震源・震度情報','Foreign':'遠地地震に関する情報','Other':'その他'}
lock = Lock()
cache = {'items': [], 'lastSuccess': None, 'error': None}
last_attempt = None
PAGE_SIZE = 100
MAX_PAGES = 5
TARGET_EVENTS = 100
CITY_NAMES = json.loads((Path(__file__).parent / 'data/municipalities.json').read_text(encoding='utf-8'))
SEISMIC_NAMES = json.loads((Path(__file__).parent / 'data/seismic_names.json').read_text(encoding='utf-8'))
DOMESTIC = {
    'None': 'この地震による日本への津波の心配はありません。',
    'Unknown': '日本への津波の影響は不明です。',
    'Checking': '日本への津波の影響について調査中です。',
    'NonEffective': 'この地震により、日本の沿岸では若干の海面変動があるかもしれませんが、被害の心配はありません。',
    'Watch': 'この発表時点では、日本に津波注意報が発表されています。',
    'Warning': 'この発表時点では、日本に津波予報が発表されています（種類はこのデータでは不明です）。',
}
FOREIGN = {
    'None': '海外での津波の心配はありません。',
    'Unknown': '海外での津波の影響は不明です。',
    'Checking': '海外での津波の影響について調査中です。',
    'NonEffectiveNearby': '震源の近傍で小さな津波が発生する可能性がありますが、被害の心配はありません。',
    'WarningNearby': '震源の近傍で津波発生の可能性があります。',
    'WarningPacific': '太平洋で津波発生の可能性があります。',
    'WarningPacificWide': '太平洋の広域で津波発生の可能性があります。',
    'WarningIndian': 'インド洋で津波発生の可能性があります。',
    'WarningIndianWide': 'インド洋の広域で津波発生の可能性があります。',
    'Potential': '一般に、この規模の地震では津波発生の可能性があります。',
}

def group_points(points):
    groups = {}
    for point in points:
        pref, addr = point['pref'], point['addr']
        # Longest official municipality prefix; never guess by the first 市/町 character.
        alias = next((name for name in sorted(SEISMIC_NAMES.get(pref, {}),key=len,reverse=True) if addr.startswith(name)), None)
        identity = SEISMIC_NAMES.get(pref,{}).get(alias,{})
        city = identity.get('city') or next((name for name in CITY_NAMES.get(pref, []) if addr.startswith(name)), None)
        ward = identity.get('ward')
        area = point['isArea']
        label = addr if area or not city else city
        key = (pref, label, ward, area)
        group = groups.setdefault(key, {'name': f'{pref} {label}'.strip(), 'isArea': area,
                                       'pref':pref, 'city':label, 'ward':ward,
                                       'matched': bool(city) and not area, 'scaleCode': -1, 'points': []})
        group['points'].append(point)
        group['scaleCode'] = max(group['scaleCode'], point['scaleCode'])
    for g in groups.values():
        g['scale'] = SCALES.get(g['scaleCode'], '不明')
        g['points'].sort(key=lambda p: (-p['scaleCode'], p['addr']))
    return sorted(groups.values(), key=lambda g: (-g['scaleCode'], g['name']))

def point_tree(groups):
    prefs={}
    for g in groups:
        pref=prefs.setdefault(g['pref'],{'name':g['pref'],'scaleCode':-1,'children':{}})
        label=g['city']+('（地域情報）' if g['isArea'] else '' if g['matched'] else '（観測点）')
        city=pref['children'].setdefault(label,{'name':label,'scaleCode':-1,'children':{},'points':[]})
        dest=city
        if g['ward']:
            dest=city['children'].setdefault(g['ward'],{'name':g['ward'],'scaleCode':-1,'children':{},'points':[]})
        dest['points'].extend(g['points'])
        for node in (pref,city,dest): node['scaleCode']=max(node['scaleCode'],g['scaleCode'])
    def finish(nodes):
        values=sorted(nodes.values(),key=lambda n:(-n['scaleCode'],n['name']))
        for n in values:
            n['scale']=SCALES.get(n['scaleCode'],'不明')
            n['children']=finish(n['children'])
        return values
    return finish(prefs)

def messages(quake, comments):
    return {'domestic': DOMESTIC.get(quake.get('domesticTsunami'), '日本への津波に関する情報は、この発表にはありません。'),
            'foreign': FOREIGN.get(quake.get('foreignTsunami'), '海外の津波に関する情報は、この発表にはありません。'),
            'comment': str(comments.get('freeFormComment') or '').strip()}

def event_groups(rows):
    """551 has report IDs, not earthquake IDs. Use conservative exact-time matching."""
    reports = {r['id']: r for r in (normalize(row) for row in rows if row.get('code') == 551)}
    groups = []
    for report in sorted(reports.values(), key=lambda r: (r['issued'], r['received']), reverse=True):
        candidates = [g for g in groups if report['time'] != '不明' and g[0]['time'] == report['time']
                      and g[0]['source'] == report['source'] and g[0]['name'] == report['name']]
        if len(candidates) == 1:
            candidates[0].append(report)
        else:
            groups.append([report])
    # A source's epicenter-less preliminary report can be attached only when the
    # exact origin time identifies a single named event in the fetched window.
    for g in list(groups):
        if g[0]['name'] != '震源情報なし' or g[0]['time'] == '不明':
            continue
        candidates = [x for x in groups if x[0]['name'] != '震源情報なし' and x[0]['time'] == g[0]['time'] and x[0]['source'] == g[0]['source']]
        if len(candidates) == 1:
            candidates[0].extend(g)
            groups.remove(g)
    result = []
    for history in groups:
        history.sort(key=lambda r: (r['issued'], r['received']), reverse=True)
        for i,report in enumerate(history):
            if report['type']=='震源に関する情報' and report['scaleCode']==-1:
                prompt=next((r for r in history[i+1:] if r['type']=='震度速報' and r['issued']<report['issued']),None)
                if prompt:
                    for field in ('scale','scaleCode','points','pointGroups','pointTree'):
                        report[field]=prompt[field]
                    report['intensitySource']={'issued':prompt['issued'],'reportId':prompt['reportId']}
        latest = dict(history[0])
        identity = next((r for r in history if r['name'] != '震源情報なし'), latest)
        key = f"{identity['source']}|{identity['time']}|{identity['name']}" if identity['time'] != '不明' else identity['id']
        latest['id'] = hashlib.sha256(key.encode()).hexdigest()[:24]
        latest['history'] = history[1:]
        latest['historyCount'] = len(history)-1
        latest['reportCount'] = len(history)
        result.append(latest)
    return sorted(result, key=lambda r: (r['issued'], r['received']), reverse=True)

def stamp():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')

def fetch_events():
    """Fetch reports until 100 events AND their initial report boundary are covered."""
    raw = {}
    items = []
    exhausted = False
    covered = False
    for page in range(MAX_PAGES):
        params={'codes':551,'limit':PAGE_SIZE}
        if page: params['offset']=page*PAGE_SIZE
        response=requests.get(URL,params=params,timeout=(3,5),headers={'User-Agent':'EarthquakeViewer/0.7'})
        response.raise_for_status()
        batch=response.json()
        if not isinstance(batch,list) or any(not isinstance(r,dict) for r in batch):
            raise ValueError('Invalid API payload')
        for row in batch:
            if row.get('code')==551:
                raw[str(row.get('id') or row.get('time'))]=row
        items=event_groups(raw.values())
        if len(batch)<PAGE_SIZE:
            exhausted=True
            break
        if len(items)>=TARGET_EVENTS:
            origins=[q['time'] for q in items[:TARGET_EVENTS] if q['time']!='不明']
            issued=[(r.get('issue') or {}).get('time') for r in batch]
            issued=[v for v in issued if isinstance(v,str)]
            # Read beyond the oldest selected origin so its earlier bulletins
            # cannot be accidentally cut off at a page boundary.
            if origins and issued and min(issued)<min(origins):
                covered=True
                break
    notice=''
    if len(items)<TARGET_EVENTS:
        notice=f'取得できた地震は{len(items)}件です。配信元の提供範囲または取得上限により100件に届いていません。'
    elif not (covered or exhausted):
        notice='地震は100件表示しています。取得上限（500発表）のため、一部の古い履歴が含まれない可能性があります。'
    import quake_revisions
    items=quake_revisions.enrich(items)
    return items[:TARGET_EVENTS],len(raw),notice

@app.get('/api/event-names')
def event_names():
    with lock:
        reports=list(cache['items'])
    response=jsonify(jma.event_names(reports));response.headers['Cache-Control']='no-store'
    return response

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def normalize(row):
    quake = row.get('earthquake') or {}
    hypo = quake.get('hypocenter') or {}
    issue = row.get('issue') or {}
    lat, lon = hypo.get('latitude'), hypo.get('longitude')
    coords = [lat, lon] if number(lat) and number(lon) and -90 <= lat <= 90 and -180 <= lon <= 180 else None
    depth, mag = hypo.get('depth'), hypo.get('magnitude')
    points = []
    for p in row.get('points') or []:
        if not isinstance(p, dict):
            continue
        scale = p.get('scale') if p.get('scale') in SCALES else -1
        pref, addr = str(p.get('pref') or ''), str(p.get('addr') or '')
        points.append({'name': f'{pref} {addr}'.strip(), 'pref': pref, 'addr': addr,
                       'scale': SCALES.get(scale, '不明'), 'scaleCode': scale, 'isArea': bool(p.get('isArea'))})
    return {'id': str(row.get('id') or row.get('time') or ''),
            'reportId':str(row.get('id') or row.get('time') or ''),
            'isForeign':issue.get('type') == 'Foreign',
            'received': row.get('time') or '',
            'time': quake.get('time') or '不明', 'issued': issue.get('time') or '不明',
            'type': issue.get('title') or TYPES.get(issue.get('type'), 'その他の地震情報'),
            'eventId':row.get('eventId'),'serial':issue.get('serial'),
            'correction': issue.get('correct') or 'None',
            'name': hypo.get('name') or '震源情報なし', 'coords': coords,
            'scale': SCALES.get(quake.get('maxScale'), '不明'),
            'scaleCode': quake.get('maxScale', -1),
            'depth': ('ごく浅い' if depth == 0 else f'{depth:g} km') if number(depth) and depth >= 0 else '不明',
            'magnitude': f'{mag:.1f}' if number(mag) and mag >= 0 else '不明',
            'source': issue.get('source') or '発表元情報なし',
            'messages': messages(quake, row.get('comments') or {}),
            'points': points, 'pointGroups': group_points(points), 'pointTree':point_tree(group_points(points))}

@app.get('/api/reports/<report_id>/supplement')
def report_supplement(report_id):
    if report_id.endswith('.json'):
        import news_quakes
        try:return jsonify(news_quakes.supplement(report_id))
        except (ValueError,requests.RequestException):return jsonify(status='unavailable'),404
    with lock:
        report=next((r for item in cache['items'] for r in [item,*item['history']] if r['reportId']==report_id),None)
    if report is None: return jsonify(status='unavailable',message='表示対象が更新されました。地震一覧を更新してください。'),404
    response=jsonify(jma.supplement(report));response.headers['Cache-Control']='no-store'
    return response

@app.get('/api/realtime/eew')
def realtime_eew_snapshot():
    import realtime
    return jsonify(realtime.eew_snapshot())

@app.get('/api/realtime/stations/<report_id>')
def realtime_stations(report_id):
    """Official station coordinates when JMA has published the matching bulletin."""
    import re
    import realtime
    if not re.fullmatch(r'[a-fA-F0-9]{24}',report_id):
        return jsonify(status='invalid',stations=[]),400
    row=next((item for item in realtime.recent().get('items',[])
              if item.get('id')==report_id and item.get('code')==551),None)
    if not row:return jsonify(status='unavailable',stations=[]),404
    info=jma.supplement(normalize(row))
    return jsonify(status=info.get('status'),stations=info.get('stations',[]),regions=info.get('regions',[]),url=info.get('url'))

@app.get('/')
def index():
    from realtime import wolfx_authorized,wolfx_mode51
    return render_template('index.html',wolfx_enabled=wolfx_authorized(),wolfx_mode=wolfx_mode51())

@app.get('/api/archive-xml/<xml_id>')
def saved_original_xml(xml_id):
    import re
    if not re.fullmatch(r'\d{14}_\d+_[A-Z0-9]+_\d+',xml_id):return jsonify(error='対象外の識別子です。'),400
    path=Path(__file__).parent/'data'/'original-xml'/(xml_id+'.xml')
    if not path.is_file():return jsonify(error='この原文は同梱されていません。配信元のリンクをご確認ください。'),404
    return send_file(path,mimetype='text/plain; charset=utf-8')

@app.get('/api/cyclones/<source>')
def cyclone_list(source):
    import cyclones
    if source not in {*cyclones.URLS, 'jtwc', 'fiji'}:return jsonify(error='配信元が不正です。'),404
    response=jsonify(cyclones.listing(source));response.headers['Cache-Control']='no-store';return response

@app.get('/api/cyclone-history/<event_id>')
def cyclone_history(event_id):
    import tc_history,re
    if not re.fullmatch(r'TC\d+',event_id):return jsonify(error='対象外の識別子です。',items=[]),400
    return jsonify(tc_history.history(event_id))

@app.get('/api/cyclone-annual')
def cyclone_annual():
    import tc_history,storage,cyclones
    cyclones.listing('jma')
    return jsonify(tc_history.annual(storage.now().year))

@app.get('/api/hazards/<kind>')
def hazard_list(kind):
    import hazards
    if kind not in ['volcanoes','tsunami']:return jsonify(error='対象外です。'),404
    result=getattr(hazards,kind)()
    if kind=='tsunami':
        import archive_xml,storage
        archive_xml.start_tsunami_sync(storage.now().year)
    return jsonify(result)

@app.get('/api/volcano-history/<code>')
def volcano_history(code):
    import hazards
    try:return jsonify(hazards.volcano_history(code))
    except ValueError:return jsonify(error='火山コードが不正です。'),400

@app.get('/api/volcano-report/<filename>')
def volcano_report(filename):
    import hazards
    try:return jsonify(hazards.volcano_report(filename))
    except ValueError:return jsonify(error='識別子が不正です。'),400

@app.get('/api/volcano-camera/<code>')
def volcano_camera(code):
    import hazards
    try:return jsonify(hazards.cameras(code))
    except ValueError:return jsonify(error='カメラコードが不正です。'),400

@app.get('/api/usgs/earthquakes')
def usgs_list():
    response=jsonify(usgs.listing());response.headers['Cache-Control']='no-store';return response

@app.get('/api/usgs/events/<event_id>')
def usgs_detail(event_id):
    response=jsonify(usgs.detail(event_id));response.headers['Cache-Control']='no-store';return response

@app.get('/api/earthquakes')
def earthquakes():
    global last_attempt
    with lock:
        now = time.monotonic()
        # Share requests across browser tabs; throttle both successes and failures.
        if last_attempt is None or now - last_attempt >= 10:
            last_attempt = now
            try:
                items,report_count,notice = fetch_events()
                cache.update(items=items, lastSuccess=stamp(), error=None, reportCount=report_count, notice=notice)
            except (requests.RequestException, ValueError, TypeError, AttributeError):
                cache['error'] = '地震情報を取得できませんでした。通信環境を確認して、しばらくしてから再試行してください。'
        result = dict(cache, checkedAt=stamp(), stale=bool(cache['error']), retryAfter=max(0, 10 - int(time.monotonic() - last_attempt)))
    response = jsonify(result)
    response.headers['Cache-Control'] = 'no-store'
    return response, 200 if cache['lastSuccess'] else (503 if cache['error'] else 200)



@app.get("/api/realtime")
def realtime_feed():
    import realtime
    realtime.extra_snapshot()
    response=jsonify(realtime.snapshot());response.headers["Cache-Control"]="no-store";return response

@app.get('/api/lightning/<valid>')
def lightning_api(valid):
    import lightning
    try:response=jsonify(lightning.observations(valid))
    except ValueError:return jsonify(error='時刻が不正です。'),400
    response.headers['Cache-Control']='no-store';return response

@app.get('/api/marine/<kind>')
def marine_information(kind):
    import marine
    try:return jsonify(marine.load(kind))
    except ValueError:return jsonify(error='対象外の海の情報です。'),404

@app.get('/api/news-quakes/<event_id>')
def news_quake_detail(event_id):
    import news_quakes
    try:data=news_quakes.load(event_id)
    except ValueError:return jsonify(error='取得対象外の地震です。'),404
    return jsonify(data),200 if data.get('report') else 503

@app.get('/api/period-observations/<event_id>')
def period_observations_api(event_id):
    import period_observations
    try:response=jsonify(period_observations.details(event_id))
    except ValueError:return jsonify(error='公開されている地震ではありません。'),404
    response.headers['Cache-Control']='no-store';return response

@app.get('/api/quake-publications')
def quake_publications():
    from flask import request
    import publications
    origin=request.args.get('time','')[:40];name=request.args.get('name','')[:100]
    if publications.epoch(origin) is None:return jsonify(error='発生時刻が不正です。'),400
    try:mag=float(request.args.get('mag',''))
    except (ValueError,TypeError):mag=None
    if mag is not None and not math.isfinite(mag):mag=None
    response=jsonify(publications.lookup(origin,name,mag));response.headers['Cache-Control']='no-store';return response

@app.get('/api/long-period')
def api_long_period():
    import longperiod
    response=jsonify(longperiod.recent());response.headers['Cache-Control']='no-store';return response

@app.get('/api/weather/catalog')
def weather_catalog():
    import weather
    return jsonify(weather.catalog())

@app.get('/api/weather/<kind>/<code>')
def weather_information(kind,code):
    import weather
    if kind not in ('warnings','forecast'):return jsonify(error='情報の種類が不正です。'),404
    try:
        data=getattr(weather,kind)(code)
        return jsonify(data),200 if data.get('lastSuccess') else 503
    except ValueError:return jsonify(error='地域が不正です。'),400

@app.get('/api/weather/charts')
def weather_charts():
    import weather
    data=weather.charts()
    return jsonify(data),200 if data.get('lastSuccess') else 503

@app.get('/api/weather/chart-image/<filename>')
def weather_chart_image(filename):
    import weather,io
    try:return send_file(io.BytesIO(weather.chart_image(filename)),mimetype='image/png',max_age=3600)
    except ValueError:return jsonify(error='天気図が見つかりません。'),404
    except requests.RequestException:return jsonify(error='天気図画像を取得できません。'),502

@app.get('/api/meteo/<kind>')
def meteo_data(kind):
    import meteo
    funcs={'warnings':meteo.national_warnings,'amedas':meteo.amedas,'nankai':meteo.nankai,'rivers':meteo.rivers,'chart-catalog':meteo.chart_catalog}
    if kind not in funcs:return jsonify(error='情報の種類が不正です。'),404
    data=funcs[kind]()
    return jsonify(data),200 if data.get('lastSuccess') else 503

@app.get('/api/meteo/raster/<kind>')
def meteo_raster(kind):
    import meteo
    try:data=meteo.raster_index(kind)
    except ValueError:return jsonify(error='情報の種類が不正です。'),400
    return jsonify(data),200 if data.get('lastSuccess') else 503

@app.get('/api/meteo/timeline/<code>')
def meteo_timeline(code):
    import meteo
    try:data=meteo.warning_timeline(code)
    except ValueError:return jsonify(error='地域が不正です。'),400
    return jsonify(data),200 if data.get('lastSuccess') else 503

@app.get('/api/meteo/chart/<filename>')
def meteo_chart(filename):
    import meteo
    try:data=meteo.chart_detail(filename)
    except ValueError:return jsonify(error='天気図が不正です。'),400
    return jsonify(data),200 if data.get('lastSuccess') else 503

@app.get('/api/updates/<kind>')
def update_views(kind):
    import updates
    funcs={'news':updates.news,'cameras':updates.cameras}
    if kind not in funcs:return jsonify(error='情報の種類が不正です。'),404
    return jsonify(funcs[kind]())

@app.get('/api/world/weather')
def world_weather_view():
    import updates
    try:return jsonify(updates.world_weather(request.args.get('lat'),request.args.get('lon')))
    except ValueError:return jsonify(error='緯度・経度が不正です。'),400

@app.get('/api/world/cities')
def world_city_view():
    import updates
    return jsonify(updates.world_cities())

@app.get('/api/world/search')
def world_search_view():
    import updates
    try:return jsonify(updates.world_search(request.args.get('q')))
    except ValueError:return jsonify(error='都市名を2〜80文字で入力してください。'),400

@app.post('/api/speech')
def local_speech():
    import voice,io,subprocess
    data=request.get_json(silent=True) or {}
    try:return send_file(io.BytesIO(voice.synthesize(data.get('text'))),mimetype='audio/wav',max_age=0)
    except ValueError:return jsonify(error='読み上げ文が不正です。'),400
    except (RuntimeError,OSError,subprocess.TimeoutExpired):return jsonify(error='Windowsの日本語音声を生成できません。ブラウザー音声を使用します。'),503

@app.get('/api/briefings/<kind>')
def briefing_views(kind):
    import briefings
    funcs={'bulletins':briefings.bulletins,'outlook':briefings.outlook,'early':briefings.early,'tide':briefings.tide,'followup':briefings.earthquake_followup,'ashfall':briefings.ashfall}
    if kind not in funcs:return jsonify(error='情報の種類が不正です。'),404
    return jsonify(funcs[kind]())

@app.get('/api/briefings/bulletin/<name>')
def briefing_detail(name):
    import briefings
    try:return jsonify(briefings.bulletin_detail(name))
    except ValueError:return jsonify(error='発表の識別子が不正です。'),400

@app.get('/api/briefings/xml/<name>')
def briefing_xml(name):
    import briefings
    try:return jsonify(briefings.public_xml(name))
    except ValueError:return jsonify(error='発表の識別子が不正です。'),400

@app.get('/api/briefings/cities/<region>')
def brief_cities(region):
    import briefings
    try:return jsonify(briefings.city_catalog(region))
    except ValueError:return jsonify(error='地域が不正です。'),400

@app.get('/api/briefings/home/<code>')
def brief_home(code):
    import briefings
    try:return jsonify(briefings.home_brief(code))
    except ValueError:return jsonify(error='市町村が不正です。'),400

@app.get('/api/briefings/river-stations')
def river_station_view():
    import briefings
    return jsonify(briefings.river_stations())

@app.get('/api/briefings/river/<code>')
def river_briefing(code):
    import briefings
    try:return jsonify(briefings.river_detail(code))
    except ValueError:return jsonify(error='河川の識別子が不正です。'),400

@app.get('/api/estimated-intensity')
def estimated_intensity_lookup():
 import estimated_intensity
 try:
  origin=request.args.get('time','')[:64];name=request.args.get('name','')[:100];lat=request.args.get('lat');lon=request.args.get('lon');position=None
  if (lat is None)!=(lon is None):raise ValueError('Both coordinates required')
  if lat is not None and lon is not None:
   position=[float(lat),float(lon)]
   if not all(math.isfinite(v) for v in position) or not -90<=position[0]<=90 or not -180<=position[1]<=180:raise ValueError('Invalid coordinates')
  return jsonify(estimated_intensity.lookup(origin,name,position))
 except (ValueError,TypeError):return jsonify(available=False,error='地震の発生時刻・位置を確認できません。'),400

@app.get('/api/volcano-level-history/<code>')
def volcano_levels51(code):
 import hazards
 try:return jsonify(hazards.volcano_level_history51(code))
 except ValueError:return jsonify(error='火山の識別子を確認してください。'),400

@app.get('/api/preparedness/dust')
def preparedness_dust52():
 import environment52
 try:return jsonify(environment52.dust(request.args.get('product','surface'),request.args.get('area','jp')))
 except ValueError:return jsonify(error='黄砂の種類・範囲を確認してください。'),400

@app.get('/api/realtime/tsunami')
def realtime_tsunami52():
 import live_tsunami52
 return jsonify(live_tsunami52.snapshot())

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='総合地震ビューアー')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--open-browser', action='store_true')
    args = parser.parse_args()
    if args.open_browser:
        import webbrowser
        from werkzeug.serving import make_server
        server=make_server('127.0.0.1',args.port,app,threaded=True)
        address=f'http://127.0.0.1:{server.server_port}'
        print(f'総合地震ビューアー：{address}\n終了はこのウィンドウでCtrl+C。',flush=True)
        webbrowser.open(address)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
    else:
        app.run(host='127.0.0.1', port=args.port, debug=False)

