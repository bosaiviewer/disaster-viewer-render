"""On-demand supplement from the JMA website; never mix different reports."""
import re
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
import requests

BASE = 'https://www.jma.go.jp/bosai/quake/data/'
_lock = Lock()
_index = []
_checked = -1000
_documents = {}

def minute(value):
    try:
        dt = datetime.fromisoformat(value.replace('/', '-').replace('Z', '+00:00'))
        if dt.tzinfo:
            dt = dt.astimezone(timezone(timedelta(hours=9)))
        return dt.strftime('%Y/%m/%d %H:%M')
    except (ValueError, TypeError, AttributeError):
        return None

def get_index():
    global _index, _checked
    if time.monotonic() - _checked >= 60:
        _checked = time.monotonic()
        res = requests.get(BASE+'list.json', timeout=(3, 5))
        res.raise_for_status()
        data = res.json()
        if not isinstance(data, list):
            raise ValueError('Invalid JMA index')
        _index = data
    return _index

def match(report, index):
    # Origin minute AND report minute AND magnitude. A single unambiguous report only.
    candidates = []
    for row in index:
        if not isinstance(row, dict): continue
        if minute(row.get('at')) != minute(report['time']) or not minute(report['time']): continue
        if minute(row.get('rdt')) != minute(report['issued']): continue
        if report['magnitude'] != '不明':
            try:
                if float(row.get('mag')) != float(report['magnitude']): continue
            except (ValueError, TypeError): continue
        coords = re.findall(r'[+-]\d+(?:\.\d+)?', row.get('cod') or '')
        if report['coords'] and len(coords) >= 2:
            if any(abs(float(v)-c) > 0.11 for v,c in zip(coords[:2],report['coords'])): continue
        elif report.get('type')=='震度速報':
            if row.get('ttl')!='震度速報': continue
        elif row.get('anm') != report['name']: continue
        if re.fullmatch(r'[A-Za-z0-9_]+\.json', row.get('json') or ''):
            candidates.append(row)
    return candidates[0] if len(candidates)==1 else None

def event_names(reports):
    """Resolve all broad names up front using one cached index request."""
    with _lock:
        try:
            index=get_index()
            names={}
            for report in reports:
                row=match(report,index)
                if not row or not row.get('anm'): continue
                broad=row['anm'];detail=report['name']
                names[report['reportId']]=f'{broad}（{detail}）' if broad!=detail and detail!='震源情報なし' else broad
            return {'names':names,'status':'ok'}
        except (requests.RequestException,ValueError,TypeError,AttributeError):
            return {'names':{},'status':'error'}

def station_points(document):
    def rows(value):return value if isinstance(value,list) else [value] if isinstance(value,dict) else []
    points=[]
    codes={'0':0,'1':10,'2':20,'3':30,'4':40,'5-':45,'5+':50,'6-':55,'6+':60,'7':70}
    for pref in rows(document.get('Body',{}).get('Intensity',{}).get('Observation',{}).get('Pref')):
        for area in rows(pref.get('Area')):
            for city in rows(area.get('City')):
                for station in rows(city.get('IntensityStation')):
                    pos=station.get('latlon') or {};lat,lon=pos.get('lat'),pos.get('lon')
                    if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)) or not -90<=lat<=90 or not -180<=lon<=180:continue
                    raw=station.get('Int');label={'5-':'5弱','5+':'5強','6-':'6弱','6+':'6強'}.get(raw,raw or station.get('Condition') or '不明')
                    points.append({'id':station.get('Code'),'name':station.get('Name','').replace('＊','').replace('*',''),
                                   'areaCode':area.get('Code'),'areaName':area.get('Name'),'pref':pref.get('Name',''),'city':city.get('Name',''),'coords':[lat,lon],'scale':label,'scaleCode':codes.get(raw,-1)})
    return points

def region_points(document):
    def rows(value):return value if isinstance(value,list) else [value] if isinstance(value,dict) else []
    codes={'0':0,'1':10,'2':20,'3':30,'4':40,'5-':45,'5+':50,'6-':55,'6+':60,'7':70};out=[]
    for pref in rows(document.get('Body',{}).get('Intensity',{}).get('Observation',{}).get('Pref')):
        for area in rows(pref.get('Area')):
            value=area.get('MaxInt');code=codes.get(value,-1)
            if code>=0:out.append({'code':str(area.get('Code','')),'name':area.get('Name'),'scaleCode':code,'scale':{'5-':'5弱','5+':'5強','6-':'6弱','6+':'6強'}.get(value,value)})
    return out

def extract(document, filename):
    if document.get('Control',{}).get('Status') != '通常':
        raise ValueError('Not an operational report')
    body=document.get('Body') or {}
    area=((body.get('Earthquake') or {}).get('Hypocenter') or {}).get('Area') or {}
    name,detail=area.get('Name'),area.get('DetailedName')
    comments=[]
    for key,value in (body.get('Comments') or {}).items():
        text=value.get('Text') if isinstance(value,dict) else value if isinstance(value,str) else None
        if text: text=text.replace('＊印は気象庁以外の震度観測点についての情報です。','').strip()
        if text and text.strip() not in comments: comments.append(text.strip())
    title=document.get('Head',{}).get('Title','')
    return {'displayName':f'{name}（{detail}）' if name and detail and name!=detail else name,
            'comments':comments,'regions':region_points(document),'stations':station_points(document),'url':BASE+filename,'eventId':document.get('Head',{}).get('EventID'),
            'isForeign': '遠地' in title or bool(detail),
            'issued':document.get('Head',{}).get('ReportDateTime')}

def supplement(report):
    with _lock:
        try:
            row=match(report,get_index())
            if not row:
                return {'status':'unavailable','message':'この発表と一致する気象庁の補足データは取得範囲内にありません。'}
            filename=row['json']
            if filename not in _documents:
                res=requests.get(BASE+filename,timeout=(3,5));res.raise_for_status()
                doc=res.json()
                if not isinstance(doc,dict): raise ValueError('Invalid JMA document')
                _documents[filename]=extract(doc,filename)
                if len(_documents)>200: _documents.pop(next(iter(_documents)))
            return dict(_documents[filename],status='ok')
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            return {'status':'error','message':'気象庁の補足情報を取得できませんでした。表示中のP2P地震情報は引き続き利用できます。'}
