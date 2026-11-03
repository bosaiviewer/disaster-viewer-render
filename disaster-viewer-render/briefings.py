"""Public JMA briefings, forecast outlooks and bulletin views."""
import math,re,json,html
from datetime import datetime,timedelta,timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import requests
import weather,meteo,storage,updates
BASE=weather.BASE
WEEK_AREAS=json.loads((Path(__file__).parent/'data/probability_week_areas.json').read_text(encoding='utf-8'))
def probability_name(code):
 known=(weather.AREAS['offices'].get(code) or weather.AREAS['class10s'].get(code) or {}).get('name')
 if known:return known
 names=[weather.AREAS['class10s'].get(k,{}).get('name') for k,v in WEEK_AREAS.items() if code in v]
 return '・'.join(dict.fromkeys(n for n in names if n)) or '地域名未提供'


def parse_time(value):
 try:
  at=datetime.fromisoformat(str(value).replace('Z','+00:00'))
  return at if at.tzinfo else None
 except (ValueError,TypeError):return None

def bulletins():
 def load():
  data=weather.get_json('information/data/r8/information.json')
  if not isinstance(data,list):raise ValueError('Invalid bulletin list')
  cutoff=datetime.now(timezone.utc)-timedelta(days=7);saved={r['id']:r for r in storage.values('weather-bulletins')}
  for r in data:
   at=parse_time(r.get('reportDatetime'));title=r.get('controlTitle','')
   if not at or at<cutoff or not any(t in title for t in ['気象防災速報','気象解説情報']):continue
   name=r.get('jsonName','')
   if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',name):continue
   item={'id':name,'title':r.get('headTitle') or title,'type':'気象防災速報' if '速報' in title else '気象解説情報','time':r['reportDatetime'],'office':r.get('publishingOffice'),'areaType':r.get('areaType'),'areaCodes':r.get('areaCodes',[]),'format':r.get('dataType'),'source':BASE+'information/'}
   if saved.get(name)!=item:storage.put('weather-bulletins',name,item)
   saved[name]=item
  items=sorted([r for r in saved.values() if (parse_time(r.get('time')) or datetime.min.replace(tzinfo=timezone.utc))>=cutoff],key=lambda r:parse_time(r['time']),reverse=True)
  return {'items':items,'source':BASE+'information/','notice':'発表日時が過去7日以内の気象防災速報・気象解説情報です。配信一覧と保存済み発表の範囲で表示します。'}
 return weather.cached('weather-bulletins-v27',300,load)

def bulletin_detail(name):
 if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',name):raise ValueError('Invalid bulletin')
 def load():
  doc=weather.get_json('information/data/r8/denbun/'+name+'.json');texts=[]
  for key,value in meteo.leaves(doc):
   if key in ('headlineText','commentText','textHonbun','text','Text') and value.strip():
    text=html.unescape(re.sub('<[^>]+>','\n',value)).strip()
    if text not in texts:texts.append(text)
  return {'title':doc.get('headTitle'),'time':doc.get('reportDatetime'),'texts':texts,'raw':doc,'source':BASE+'information/'}
 return weather.cached('weather-bulletin-'+name,3600,load)

def outlook():
 def load():
  d=weather.get_json('warning_timeline/data/center.json')
  if not isinstance(d,dict) or not isinstance(d.get('timeSeries'),list):raise ValueError('Invalid outlook')
  return dict(d,source=BASE+'warning_timeline/',notice='全国の地方ごとの明日までの警報等の見通しです。地域内の最大区分の見通しで、個々の市町村への発表ではありません。')
 return weather.cached('national-outlook',300,load)

def early():
 def load():
  raw=weather.get_json('probability/data/probability/r8/map.json');rows=[]
  if not isinstance(raw,list):raise ValueError('Invalid probability')
  for group in raw:
   for d in group if isinstance(group,list) else [group]:
    for series in d.get('timeSeries',[]):
     for area in series.get('areas',[]):
      rows.append({'code':area['code'],'name':probability_name(area['code']),'issued':d.get('reportDatetime'),'times':series.get('timeDefines',[]),'properties':area.get('properties',[])})
  return {'items':rows,'source':BASE+'map.html#contents=probability','notice':'「高」「中」は警報級となる可能性です。現在の警報や発生確率の数値とは異なります。空欄は高・中の発表がない区分です。'}
 return weather.cached('early-warning',300,load)

def parse_tide(raw,coverage):
 if not isinstance(raw,list) or not isinstance(coverage.get('class20s'),dict):raise ValueError('Invalid coastal forecast data')
 items=[]
 for d in raw:
  if d.get('dataTypeCode')!='VPWW57':continue
  for i,coast in enumerate(d.get('warning',{}).get('tidalItems',[])):
   warnings=[]
   for kind in coast.get('kinds',[]):
    named=weather.CODES.get(kind.get('code'),{})
    warnings.append(dict(kind,name=named.get('name') or kind.get('name') or '指定海岸高潮予報',level=named.get('level',0)))
   additions=d.get('tidalWarningAdditions',[])
   addition=additions[i] if isinstance(additions,list) and i<len(additions) else {}
   towns=addition.get('tidalArea',{}).get('subCityCodeList','').split()
   items.append({'code':coast.get('areaCode',str(i)),'name':coast.get('areaName','対象海岸'),'time':d.get('reportDatetime'),'warnings':warnings,'office':d.get('publishingOffice'),'headline':d.get('headlineText'),'cityCodes':towns,'properties':[p for k in coast.get('kinds',[]) for p in k.get('properties',[])],'addition':addition})
 active=[r for r in items if any(w.get('status') not in ('解除','発表警報・注意報はなし','発表なし','取消') and (w.get('code') or w.get('name')) for w in r['warnings'])]
 return {'items':items,'activeCount':len(active),'state':'active' if active else 'none','coverage':coverage,'source':BASE+'tide/','notice':'指定海岸専用の発表項目を確認しています。対象海岸は気象庁の指定一覧によります。高潮警報・注意報（通常の市町村向け）や全国の潮位観測とは別の情報です。'}

def tide():
 def load():return parse_tide(weather.get_json('warning/data/r8/map.json'),weather.get_json('warning/const/with_tidal_area.json'))
 return weather.cached('designated-coast-tide-v28',300,load)

def earthquake_followup():
 def load():
  raw=weather.get_json('quake/data/list.json');items=[]
  for row in raw:
   if not any(k in row.get('ttl','') for k in ['北海道・三陸沖後発','北海道・三陸沖地震']):continue
   name=row.get('json','')
   if not re.fullmatch(r'[A-Za-z0-9_-]+\.json',name):continue
   doc=weather.get_json('quake/data/'+name);texts=[]
   for key,value in meteo.leaves(doc.get('Body',{})):
    if key in ('Text','Comment','Notice') and value not in texts:texts.append(value)
   items.append({'id':name,'title':row['ttl'],'time':row.get('rdt'),'texts':texts,'source':BASE+'nceq/'})
  return {'items':items,'source':BASE+'nceq/','notice':'公開一覧に掲載されている発表です。取得した一覧にない過去の発表は補完しません。日頃の備えと自治体の案内も確認してください。'}
 return weather.cached('nceq-followup',300,load)

def ashfall():
 def load():
  r=requests.get('https://www.data.jma.go.jp/developer/xml/feed/eqvol_l.xml',timeout=(3,18));r.raise_for_status();root=ET.fromstring(r.content);ns={'a':'http://www.w3.org/2005/Atom'};items=[]
  for e in root.findall('a:entry',ns):
   title=e.findtext('a:title',namespaces=ns) or ''
   if '降灰予報' not in title:continue
   link=e.find('a:link',ns);url=link.get('href','') if link is not None else '';name=url.rsplit('/',1)[-1]
   if not re.fullmatch(r'\d{14}_\d+_VFVO5[345]_\d{6}\.xml',name):continue
   text=e.findtext('a:content',namespaces=ns) or '';m=re.search(r'火山名[\s　]+(.+?)[\s　]+降灰予報',text)
   items.append({'id':name,'title':title,'volcano':m[1] if m else '', 'text':text,'time':e.findtext('a:updated',namespaces=ns),'source':url})
  return {'items':items,'source':BASE+'map.html#contents=ashfall','notice':'定時・速報・詳細の降灰予報です。定時予報には「噴火した場合」の予想が含まれ、噴火の発生を示すものではありません。'}
 return weather.cached('ashfall-feed',300,load)

def public_xml(name):
 if not re.fullmatch(r'\d{14}_\d+_(?:VFVO5[345]|VXKO\d{2}|VXSE\d{2}|V[FP][A-Z][A-Z]\d{2})_\d{6}\.xml',name):raise ValueError('Invalid XML')
 def load():
  url='https://www.data.jma.go.jp/developer/xml/data/'+name;r=requests.get(url,timeout=(3,15));r.raise_for_status();root=ET.fromstring(r.content);texts=[];fields=[];polygons=[]
  for e in root.iter():
   tag=meteo.local_name(e.tag)
   if tag in ['Text','HeadlineText'] and e.text and e.text not in texts:texts.append(e.text)
   if tag in ['Polygon','Line'] and e.text:
    coords=meteo.parse_coordinates(e.text)
    if coords:polygons.append(coords)
   if tag in ['Name','DateTime','WaterLevel','Stage','FlowRate','Level','Condition','Description','ArrivalTime'] and e.text:fields.append({'name':e.attrib.get('type') or tag,'value':e.text,'unit':e.attrib.get('unit','')})
  result={'title':meteo.first_text(root,'Title'),'time':meteo.first_text(root,'ReportDateTime'),'texts':texts,'fields':fields,'polygons':polygons,'source':url}
  if '_VFVO5' in name:result.update(parse_ashfall(r.content))
  return result
 return weather.cached('public-xml-v28-'+name,3600,load)

def city_catalog(region):
 feature=next((f for f in meteo.REGIONS['features'] if f['properties']['code']==region),None)
 if not feature:raise ValueError('Invalid region')
 offices=set(feature['properties']['offices']);items=[]
 for code in weather.AREAS['class20s']:
  office=meteo.office_for_city(code)
  if office in offices:
   parent=weather.AREAS['class20s'][code].get('parent')
   items.append(dict(weather.city_info(code),office=office,forecastArea=weather.AREAS['class15s'].get(parent,{}).get('parent')))
 from preparedness51 import principal_city
 return {'items':items,'region':feature['properties']['name'],'defaultCity':principal_city(region,items)}

def home_brief(code):
 if code not in weather.AREAS['class20s']:raise ValueError('Invalid city')
 def load():
  city=weather.city_info(code);coords=city.get('coords')
  if not coords:raise ValueError('No city coordinates')
  with ThreadPoolExecutor(max_workers=3) as pool:
   f_obs=pool.submit(meteo.amedas);f_warn=pool.submit(meteo.national_warnings);f_sky=pool.submit(updates.world_weather,*coords)
   obs=f_obs.result();warnings=f_warn.result();sky=f_sky.result()
  def distance(p):
   lat,lon=p['coords'];return 111*math.hypot(lat-coords[0],(lon-coords[1])*math.cos(math.radians(coords[0])))
  values={}
  for key in ['temp','humidity','precipitation1h']:
   valid=sorted([r for r in obs.get('items',[]) if r.get('values',{}).get(key,{}).get('value') is not None],key=distance)
   station=next((s for s in valid if distance(s)<=60),None)
   values[key]={'value':station['values'][key]['value'],'station':station['name'],'distanceKm':round(distance(station),1),'time':obs.get('time')} if station else {'value':None}
  town=next((c for c in warnings.get('items',[]) if c['code']==code),None)
  parent=weather.AREAS['class20s'][code].get('parent');forecast_area=weather.AREAS['class15s'].get(parent,{}).get('parent')
  return {'city':dict(city,office=meteo.office_for_city(code),forecastArea=forecast_area),'values':values,'weather':{'code':sky.get('current',{}).get('weather_code'),'time':sky.get('current',{}).get('time'),'timezone':sky.get('timezone'),'source':'https://open-meteo.com/','estimated':True},'warnings':town.get('warnings',[]) if town else None,'warningTime':warnings.get('lastSuccess'),'observationTime':obs.get('time'),'issues':[label for label,d in [('観測値',obs),('警報・注意報',warnings),('天気の推計',sky)] if d.get('error') or d.get('stale')],'source':BASE+'amedas/','notice':'気温・湿度・1時間降水量は60km以内の最寄りの有効なアメダス観測点です（項目ごとに異なる場合があります）。天気はOpen-Meteoのモデル推計で、選択した市町村全域の実測ではありません。'}
 return weather.cached('home-brief-'+code,300,load)

def parse_river_xml(content):
 root=ET.fromstring(content);stations={};name=meteo.local_name
 for series in root.iter():
  if name(series.tag)!='TimeSeriesInfo':continue
  times={t.attrib.get('timeId'):{'time':meteo.first_text(t,'DateTime'),'label':meteo.first_text(t,'Name')} for t in series.iter() if name(t.tag)=='TimeDefine'}
  for item in series:
   if name(item.tag)!='Item':continue
   station=next((e for e in item.iter() if name(e.tag)=='Station'),None)
   if station is None:continue
   code=meteo.first_text(station,'Code');record=stations.setdefault(code,{'id':code,'name':meteo.first_text(station,'Name'),'location':meteo.first_text(station,'Location'),'points':[],'thresholds':[]})
   points={}
   for e in item.iter():
    if name(e.tag)!='WaterLevel':continue
    ref=e.attrib.get('refID');kind=e.attrib.get('type','');timing=times.get(ref,{})
    if not ref:continue
    point=points.setdefault(ref,dict(timing,value=None,level=None))
    try:value=float(e.text)
    except (TypeError,ValueError):value=None
    if value is not None and not math.isfinite(value):value=None
    if kind=='水位':point['value']=value if e.attrib.get('condition','正常')=='正常' else None;point['unit']=e.attrib.get('unit','m')
    elif kind=='レベル':point['level']=value
   record['points'].extend(points.values())
 for item in root.iter():
  if name(item.tag)!='Item':continue
  station=next((e for e in item if name(e.tag)=='Station'),None)
  if station is None:continue
  code=meteo.first_text(station,'Code')
  if code not in stations:continue
  for e in item.iter():
   if name(e.tag)=='WaterLevel' and not e.attrib.get('refID') and e.attrib.get('type','').startswith('レベル'):
    stations[code]['thresholds'].append({'name':e.attrib['type'],'value':e.text,'unit':e.attrib.get('unit','')})
 return {'title':meteo.first_text(root,'Title'),'time':meteo.first_text(root,'ReportDateTime'),'stations':list(stations.values()),'texts':list(dict.fromkeys(e.text for e in root.iter() if name(e.tag)=='Text' and e.text))}

RIVER_STATIONS=json.loads((Path(__file__).parent/'data/river_stations.json').read_text(encoding='utf-8'))

def river_detail(code):
 if not re.fullmatch(r'\d{12}',code):raise ValueError('Invalid river')
 geo=json.loads((Path(__file__).parent/'static/rivers.geojson').read_text(encoding='utf-8'));feature=next((f for f in geo['features'] if f['properties']['riverCode']==code),None)
 if not feature:raise ValueError('Unknown river')
 river_name=feature['properties']['fcstAreaNameJP']
 def load():
  def feed():
   r=requests.get('https://www.data.jma.go.jp/developer/xml/feed/extra_l.xml',timeout=(3,15));r.raise_for_status()
   return {'xml':r.content.decode('utf-8')}
  index=weather.cached('river-xml-index-v28',300,feed)
  if index.get('error'):raise ValueError('River bulletin index unavailable')
  root=ET.fromstring(index['xml']);ns={'a':'http://www.w3.org/2005/Atom'};candidates=[]
  for e in root.findall('a:entry',ns):
   if '指定河川洪水予報' not in (e.findtext('a:title',namespaces=ns) or ''):continue
   if river_name not in (e.findtext('a:content',namespaces=ns) or ''):continue
   link=e.find('a:link',ns);url=link.get('href','') if link is not None else ''
   if re.fullmatch(r'https://www\.data\.jma\.go\.jp/developer/xml/data/\d{14}_\d+_VXKO\d{2}_\d{6}\.xml',url):candidates.append(url)
  def fetch(url):
   def get():
    r=requests.get(url,timeout=(3,12));r.raise_for_status();doc=ET.fromstring(r.content)
    if not any(meteo.local_name(e.tag)=='Code' and (e.text or '').startswith(code) for e in doc.iter()):return {'match':False}
    return dict(parse_river_xml(r.content),source=url,match=True)
   return weather.cached('river-report-v28-'+code+'-'+url.rsplit('/',1)[-1],86400,get)
  with ThreadPoolExecutor(max_workers=4) as pool:reports=list(pool.map(fetch,candidates[:12]))
  valid=sorted([d for d in reports if d.get('match') and not d.get('error')],key=lambda d:parse_time(d.get('time')) or datetime.min.replace(tzinfo=timezone.utc),reverse=True)
  if not valid:
   if reports and any(d.get('error') for d in reports):raise ValueError('Water-level reports unavailable')
   return {'riverCode':code,'riverName':river_name,'stations':[],'texts':[],'source':BASE+'flood/','notice':'公開一覧に水位データがありません。平常時の全観測所・全カメラは未接続です。川の防災情報も確認してください。'}
  data=dict(valid[0]);stations={r['id']:dict(r,points=list(r['points'])) for r in data['stations']}
  for report in valid:
   for station in report['stations']:
    for point in station['points']:
     if point.get('label')=='現況' and point.get('time'):
      observed=dict(point,label='観測',issued=report['time'],source=report['source'])
      storage.put('river-observations-v28',station['id']+'-'+point['time'],dict(observed,stationId=station['id'],riverCode=code))
  cutoff=datetime.now(timezone.utc)-timedelta(days=7)
  saved=[r for r in storage.values('river-observations-v28') if r.get('riverCode')==code and (parse_time(r.get('time')) or datetime.min.replace(tzinfo=timezone.utc))>=cutoff]
  for station in stations.values():
   observations={r['time']:r for r in saved if r['stationId']==station['id']}
   for point in station['points']:
    if point.get('label')=='現況':observations[point['time']]=dict(point,label='観測')
   forecasts=[dict(r,label='予想') for r in station['points'] if r.get('label')!='現況' and r.get('time') not in observations]
   station['points']=sorted(list(observations.values())+forecasts,key=lambda r:r.get('time',''))
   metadata=next((r for r in RIVER_STATIONS if r['id']==station['id']),None)
   if metadata:station.update(coords=metadata['coords'],positionSource=metadata['source'])
   station['current']=next((r for r in reversed(station['points']) if r['label']=='観測'),None)
  data.update(stations=list(stations.values()),riverCode=code,riverName=river_name,reportCount=len(valid),partial=any(d.get('error') for d in reports),notice='公開一覧の直近12発表と取得済みの過去7日分の観測値です。実線は観測、破線は最新発表の予想。未取得の時刻は補間して観測値として表示しません。全国の平常時の全観測所は未接続です。')
  return data
 return weather.cached('river-detail-v28-'+code,300,load)

def river_stations():
 def load():
  index=meteo.rivers()
  if index.get('error'):raise ValueError('River index unavailable')
  codes=list(dict.fromkeys(r.get('riverCode') for r in index.get('items',[]) if re.fullmatch(r'\d{12}',str(r.get('riverCode','')))))
  with ThreadPoolExecutor(max_workers=4) as pool:reports=list(pool.map(river_detail,codes[:12]))
  stations=[];errors=[]
  for report in reports:
   if report.get('error'):errors.append(report.get('riverName') or report.get('error'))
   for station in report.get('stations',[]):stations.append(dict(station,riverCode=report['riverCode'],riverName=report['riverName'],issued=report.get('time')))
  return {'items':stations,'unmapped':sum(not r.get('coords') for r in stations),'partial':len(codes)>12 or bool(errors),'errors':errors,'source':BASE+'flood/','notice':'公開洪水予報に含まれる観測所です。位置を国土交通省の資料で確認できた地点のみ地図に表示します（登録済み2地点）。座標未登録の観測所は一覧で確認できます。全国の全観測所を網羅しません。'}
 return weather.cached('river-stations-v28',300,load)


def parse_ashfall(content):
 """Keep each forecast period, phenomenon and polygon together."""
 root=ET.fromstring(content);tag=meteo.local_name
 def child(node,key):return next((e for e in node if tag(e.tag)==key),None)
 head=child(root,'Head');body=child(root,'Body');periods=[];volcano={}
 if body is None:raise ValueError('Missing ashfall body')
 for info in body:
  if tag(info.tag)=='VolcanoInfo' and info.attrib.get('type')=='降灰予報（対象火山）':
   volcano={'name':meteo.first_text(info,'Name')}
   coord=next((e for e in info.iter() if tag(e.tag)=='Coordinate'),None)
   if coord is not None:
    nums=re.findall(r'[+-]\d+(?:\.\d+)?',coord.text or '')
    if len(nums)>=2:
     vals=list(map(float,nums[:2]));volcano['coords']=[(1 if v>=0 else -1)*(int(abs(v)//100)+(abs(v)%100)/60) for v in vals]
 for ash in body.iter():
  if tag(ash.tag)!='AshInfo':continue
  period={'start':meteo.first_text(ash,'StartTime'),'end':meteo.first_text(ash,'EndTime'),'items':[]}
  for item in ash:
   if tag(item.tag)!='Item':continue
   kind=child(item,'Kind');areas=child(item,'Areas')
   if kind is None:continue
   row={'phenomenon':meteo.first_text(kind,'Name'),'areas':[],'polygons':[]}
   if areas is not None:
    row['areas']=[{'name':meteo.first_text(a,'Name'),'code':meteo.first_text(a,'Code')} for a in areas if tag(a.tag)=='Area']
   for e in kind.iter():
    key=tag(e.tag)
    if key=='Polygon':
     coords=meteo.parse_coordinates(e.text)
     if coords:row['polygons'].append(coords)
    elif key=='PlumeDirection':row['direction']=e.attrib.get('description') or e.text
    elif key=='Distance':row['distanceKm']=e.text
    elif key=='Size':row['sizeCm']=e.text
   period['items'].append(row)
  periods.append(period)
 return {'ashfall':{'volcano':volcano,'start':meteo.first_text(head,'TargetDateTime') if head is not None else '', 'end':meteo.first_text(head,'ValidDateTime') if head is not None else '', 'conditional':'定時' in meteo.first_text(root,'Title'),'periods':periods},'fields':[]}
