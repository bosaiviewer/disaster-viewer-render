"""Public JMA map products. No fabricated observation/forecast frames."""
import re,json,time,math
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests
import weather,storage
BASE=weather.BASE
ROOT=Path(__file__).parent
REGIONS=json.loads((ROOT/'static/weather-regions.geojson').read_text(encoding='utf-8'))
LAYERS={
 'current-weather':('天気（推計気象分布）','suikeikishou','wthr',['targetTimes.json'],'推計','suikei/'),
 'current-temp':('気温（推計気象分布）','suikeikishou','temp',['targetTimes.json'],'℃・推計','suikei/'),
 'rain':('雨雲レーダー','nowc','hrpns',['targetTimes_N1.json','targetTimes_N2.json'],'mm/h','nowc/'),
 'thunder':('雷の活動度','nowc','thns',['targetTimes_N3.json'],'活動度','nowc/'),
 'snow-depth':('積雪深','snow','snowd',['targetTimes.json'],'cm','snow/'),
 'snow-fall':('3時間降雪量','snow','snowf03h',['targetTimes.json'],'cm / 3時間','snow/'),
 'landslide':('土砂キキクル','risk','land',['targetTimes.json'],'危険度','risk/'),
 'inundation':('浸水キキクル','risk','inund',['targetTimes.json'],'危険度','risk/'),
 'flood':('洪水キキクル','risk','flood_mesh',['targetTimes.json'],'危険度','risk/'),
 'rain-risk':('大雨キキクル','risk','rain_mesh',['targetTimes.json'],'危険度','risk/'),
 'dist-wm':('天気分布予報・天気','wdist','wm',['targetTimes.json'],'天気','wdist/'),
 'dist-temp':('天気分布予報・気温','wdist','temp',['targetTimes.json'],'℃','wdist/'),
 'dist-r3':('天気分布予報・3時間降水量','wdist','r3',['targetTimes.json'],'mm / 3時間','wdist/'),
 'dist-s3':('天気分布予報・3時間降雪量','wdist','s3',['targetTimes.json'],'cm / 3時間','wdist/'),
 'satellite':('気象衛星・赤外画像','himawari','ir',[], '赤外画像','map.html#contents=himawari&elem=ir')}

LAYERS['line-rain']=('線状降水帯予測マップ','rasrf','sjfcstmap',['targetTimes.json'],'大雨のおそれ','kaikotan/#elements:sjfcstmap')
LAYERS['satellite-wide']=LAYERS['satellite']
for hours in (6,12,24,48,72):
 LAYERS['snow-fall-'+str(hours)]=(str(hours)+'時間降雪量','snow','snowf'+str(hours).zfill(2)+'h',['targetTimes.json'],'cm / '+str(hours)+'時間','snow/')

def raster_index(key):
 if key not in LAYERS:raise ValueError('Unknown layer')
 name,group,element,files,unit,source=LAYERS[key]
 def load():
  if key in ('satellite','satellite-wide'):raw=weather.get_json('himawari/data/satimg/targetTimes_'+('fd' if key=='satellite-wide' else 'jp')+'.json')
  else:
   raw=[]
   for filename in files:raw.extend(weather.get_json('jmatile/data/'+group+'/'+filename))
  frames={}
  for row in raw:
   if not isinstance(row,dict) or key not in ('satellite','satellite-wide') and element not in row.get('elements',[]):continue
   base=row.get('basetime','');valid=row.get('validtime','');member=row.get('member','none')
   if not re.fullmatch(r'\d{14}',base) or not re.fullmatch(r'\d{14}',valid) or not re.fullmatch(r'[A-Za-z0-9]+',member):continue
   if key in ('satellite','satellite-wide'):url=BASE+f"himawari/data/satimg/{base}/{'fd' if key=='satellite-wide' else 'jp'}/{valid}/B13/TBB/"+'{z}/{x}/{y}.jpg'
   else:url=BASE+f'jmatile/data/{group}/{base}/{member}/{valid}/surf/{element}/'+'{z}/{x}/{y}.png'
   interval=3 if key in ('dist-wm','dist-r3','dist-s3','snow-fall') else int(key.rsplit('-',1)[-1]) if key.startswith('snow-fall-') else 0
   frame={'base':base,'valid':valid,'member':member,'url':url,'forecast':valid>base,'intervalHours':interval,'product':name,'unit':unit}
   # A valid time may be present in several forecast runs: use newest run.
   if valid not in frames or base>frames[valid]['base']:frames[valid]=frame
  issues=[]
  if key=='rain':
   # The short-range product is one-hour precipitation, not instantaneous rain rate.
   try:
    coarse=weather.get_json('jmatile/data/rasrf/targetTimes.json')
    lo=min(frames) if frames else '';hi=max(frames) if frames else ''
    for row in coarse:
     base=row.get('basetime','');valid=row.get('validtime','');member=row.get('member','none')
     if 'rasrf' not in row.get('elements',[]) or not re.fullmatch(r'\d{14}',base) or not re.fullmatch(r'\d{14}',valid) or not re.fullmatch(r'[A-Za-z0-9]+',member):continue
     if lo<=valid<=hi:continue
     frame={'base':base,'valid':valid,'member':member,'url':BASE+f'jmatile/data/rasrf/{base}/{member}/{valid}/surf/rasrf/'+'{z}/{x}/{y}.png','forecast':valid>base,'intervalHours':1,'product':'1時間降水量','unit':'mm / 1時間','coarse':True}
     if valid not in frames or base>frames[valid]['base']:frames[valid]=frame
   except (requests.RequestException,ValueError,TypeError,KeyError):issues.append('1時間降水量の時刻一覧を取得できません。5分ごとの情報を表示しています。')
  values=sorted(frames.values(),key=lambda r:r['valid'])
  if key in ('satellite','satellite-wide'):values=values[::4]+values[-1:] if len(values)>500 else values
  values=list({v['valid']:v for v in values}.values())[-600:]
  if not values:raise ValueError('No frames')
  return {'name':name,'key':key,'unit':unit,'frames':values,'source':BASE+source,'issues':issues,'notice':'提供元の時刻一覧に含まれる範囲のみです。予想は観測値ではありません。'+(' 前後の時間帯は1時間降水量を表示します。雨の強さ（mm/h）とは異なる情報です。' if key=='rain' else '')+' '.join(issues)}
 return weather.cached('raster-v38-'+key,60,load)

def office_for_city(code):
 key=code
 for kind in ['class20s','class15s','class10s']:
  a=weather.AREAS[kind].get(key)
  if not a:return None
  key=a.get('parent')
 return key

def national_warnings():
 def load():
  docs=weather.get_json('warning/data/r8/map.json')
  if not isinstance(docs,list) or not docs:raise ValueError('Invalid warnings')
  groups={}
  for d in docs:
   towns=(d.get('warning') or {}).get('class20Items',[])
   if not towns:continue
   code=office_for_city(towns[0].get('areaCode'))
   if code:groups.setdefault(code,[]).append(d)
  if not groups:raise ValueError('No offices')
  cities=[];bulletins=[]
  for office,rows in groups.items():
   parsed=weather.parse_warnings(rows)
   cities.extend([dict(c,office=office) for c in parsed['items']]);bulletins.extend([dict(b,officeCode=office) for b in parsed['bulletins']])
  river_error=None
  try:
   flood=weather.get_json('flood/data/r8/flood_xml.json')
   if not isinstance(flood,list):raise ValueError('Invalid flood list')
   by_city={c['code']:c for c in cities}
   for report in flood:
    item=report.get('item') or {};code=str(item.get('code',''));level=int(code[:1]) if code[:1].isdigit() else 0
    if level<2 or report.get('infoType')=='取消':continue
    for city in report.get('class20Codes',[]):
     if city not in by_city:continue
     town=by_city[city];name=item.get('name') or item.get('condition') or '氾濫に関する警報・注意報'
     town['warnings'].append({'name':name+'（'+report.get('riverName','河川')+'）','code':'river-'+str(report.get('riverCode','')),'level':level,'alertLevel':level,'status':'発表','time':report.get('reportDatetime'),'type':'指定河川洪水予報'})
     town['level']=max(town['level'],level);town['warnings'].sort(key=lambda w:-w['level'])
    bulletins.append({'type':'指定河川洪水予報','time':report.get('reportDatetime'),'office':report.get('publishingOffice'),'officeCode':(report.get('officeCodes') or [None])[0],'headline':report.get('riverName','')+'：'+item.get('name','')})
  except (requests.RequestException,ValueError,TypeError,KeyError):river_error='指定河川の氾濫警報・注意報を確認できません。気象庁の原文も確認してください。'
  regions=[]
  for feature in REGIONS['features']:
   prop=feature['properties'];items=[c for c in cities if c['office'] in prop['offices']];warnings=[w for c in items for w in c['warnings']]
   regions.append(dict(prop,level=max((w['level'] for w in warnings),default=0),active=sum(bool(c['warnings']) for c in items),available=bool(items),warnings=sorted({w['name'] for w in warnings})))
  return {'riverError':river_error,'regions':regions,'items':cities,'bulletins':bulletins,'source':BASE+'warning/','issued':max((b['time'] or '' for b in bulletins),default='')}
 return weather.cached('national-warnings-v26',60,load)

def warning_timeline(code):
 weather.validate_office(code)
 def load():
  doc=weather.get_json('warning_timeline/data/'+code+'.json')
  if not isinstance(doc,dict) or not isinstance(doc.get('timeSeries'),list):raise ValueError('Invalid timeline')
  return dict(doc,source=BASE+'warning_timeline/#area_type=offices&area_code='+code)
 return weather.cached('warning-timeline-'+code,60,load)

def amedas():
 def load():
  response=requests.get(BASE+'amedas/data/latest_time.txt',timeout=(3,10));response.raise_for_status();at=datetime.fromisoformat(response.text.strip())
  if at.tzinfo is None:raise ValueError('Missing zone')
  path=at.astimezone(timezone(timedelta(hours=9))).strftime('%Y%m%d%H%M%S')
  table=weather.get_json('amedas/const/amedastable.json');data=weather.get_json('amedas/data/map/'+path+'.json')
  if not isinstance(table,dict) or not isinstance(data,dict):raise ValueError('Invalid AMeDAS')
  items=[]
  for code,values in data.items():
   station=table.get(code)
   if not station or len(station.get('lat',[]))!=2 or len(station.get('lon',[]))!=2:continue
   obs={}
   for key,val in values.items():
    if isinstance(val,list) and len(val)>=2:obs[key]={'value':val[0] if val[1]==0 and isinstance(val[0],(int,float)) and math.isfinite(val[0]) else None,'quality':val[1]}
   items.append({'id':code,'name':station.get('kjName',code),'coords':[station['lat'][0]+station['lat'][1]/60,station['lon'][0]+station['lon'][1]/60],'values':obs})
  if not items:raise ValueError('No stations')
  return {'time':at.isoformat(),'items':items,'source':BASE+'amedas/','notice':'最新のアメダス観測値です。地点により観測項目が異なります。品質フラグが正常でない値は表示しません。空の天気現象（晴れ・雨など）は推測しません。'}
 return weather.cached('amedas-current',60,load)

def leaves(node):
 if isinstance(node,dict):
  for k,v in node.items():
   if isinstance(v,(list,dict)):yield from leaves(v)
   elif isinstance(v,str) and v.strip():yield (k,v)
 elif isinstance(node,list):
  for v in node:yield from leaves(v)

def nankai():
 def load():
  rows=weather.get_json('quake/data/list.json')
  matched=[r for r in rows if str(r.get('ttl','')).startswith('南海トラフ地震') and '_K' not in r.get('ift','')]
  items=[]
  for row in matched[:15]:
   filename=row.get('json','')
   if not re.fullmatch(r'[A-Za-z0-9_-]+\.json',filename):continue
   doc=weather.get_json('quake/data/'+filename);texts=[]
   for key,value in leaves(doc.get('Body',{})):
    if key in ('Text','Comment','Notice','Reason','ForecastComment') and value not in texts:texts.append(value)
   items.append({'id':filename,'title':row.get('ttl'),'time':row.get('rdt'),'texts':texts,'source':BASE+'nteq/'})
  return {'items':items,'source':BASE+'nteq/','notice':'気象庁の公開一覧にある南海トラフ関連の発表です。発表日時を確認してください。'}
 return weather.cached('nankai',300,load)

def rivers():
 def load():
  data=weather.get_json('flood/data/r8/flood_xml.json')
  if not isinstance(data,list):raise ValueError('Invalid river information')
  return {'items':data,'source':BASE+'flood/','notice':'指定河川洪水予報など、公開一覧に含まれる情報です。各河川の全観測所の水位を網羅するものではありません。'}
 return weather.cached('rivers',60,load)

def local_name(tag):return tag.rsplit('}',1)[-1]
def first_text(node,name):return next((e.text for e in node.iter() if local_name(e.tag)==name and e.text),'')
def parse_coordinates(text):
 result=[]
 for part in (text or '').split('/'):
  nums=re.findall(r'[+-]\d+(?:\.\d+)?',part)
  if len(nums)>=2:
   lat,lon=map(float,nums[:2])
   if -90<=lat<=90 and -180<=lon<=360:result.append([lat,lon])
 return result

def chart_target_time(filename):
 """Read only the XML prefix through its first forecast/analysis target, then close the response."""
 saved=storage.get('weather-chart-time',filename)
 if saved:return saved
 parser=ET.XMLPullParser(events=('start','end'));stack=[]
 with requests.get('https://www.data.jma.go.jp/developer/xml/data/'+filename,timeout=(3,8),stream=True) as response:
  response.raise_for_status()
  size=0
  for chunk in response.iter_content(4096):
   size+=len(chunk)
   if size>262144:break
   parser.feed(chunk)
   for event,node in parser.read_events():
    tag=local_name(node.tag)
    if event=='start':stack.append(tag)
    else:
     if tag=='DateTime' and len(stack)>1 and stack[-2]=='MeteorologicalInfo' and node.text:
      value=node.text.strip();datetime.fromisoformat(value.replace('Z','+00:00'));storage.put('weather-chart-time',filename,value);return value
     stack.pop()
 return None

def chart_catalog():
 def load():
  response=requests.get('https://www.data.jma.go.jp/developer/xml/feed/regular_l.xml',timeout=(3,15));response.raise_for_status();root=ET.fromstring(response.content)
  items=[];ns={'a':'http://www.w3.org/2005/Atom'}
  for e in root.findall('a:entry',ns):
   title=e.findtext('a:title',namespaces=ns) or ''
   if title not in ['地上実況図','地上２４時間予想図','地上４８時間予想図']:continue
   link=e.find('a:link',ns)
   if link is None:continue
   url=link.attrib.get('href','');filename=url.rsplit('/',1)[-1]
   if not re.fullmatch(r'\d{14}_\d+_VZS[AF]\d{2}_\d{6}\.xml',filename):continue
   if urlparse(url).hostname!='www.data.jma.go.jp':continue
   row={'id':filename,'title':title,'issued':e.findtext('a:updated',namespaces=ns),'url':url}
   storage.put('weather-chart-index',filename,row)
  cutoff=(datetime.now(timezone.utc)-timedelta(days=5)).isoformat()
  for row in storage.values('weather-chart-index'):
   try:
    if datetime.fromisoformat(row['issued'].replace('Z','+00:00'))>=datetime.now(timezone.utc)-timedelta(days=5):items.append(row)
   except (ValueError,KeyError):continue
  items.sort(key=lambda r:r['issued'],reverse=True)
  from concurrent.futures import ThreadPoolExecutor
  def enrich(row):
   try:row['targetTime']=chart_target_time(row['id'])
   except (requests.RequestException,ValueError,ET.ParseError):pass
   return row
  with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(enrich,items))
  return {'items':items,'source':'https://www.jma.go.jp/bosai/weather_map/','notice':'公開XMLと、このアプリが取得・保存した過去5日以内の天気図です。配信元にない過去時刻は補完しません。'}
 return weather.cached('chart-vector-index-v40',600,load)

def chart_detail(filename):
 if not re.fullmatch(r'\d{14}_\d+_VZS[AF]\d{2}_\d{6}\.xml',filename):raise ValueError('Invalid chart')
 def load():
  url='https://www.data.jma.go.jp/developer/xml/data/'+filename
  r=requests.get(url,timeout=(3,15));r.raise_for_status();root=ET.fromstring(r.content)
  features=[]
  for index,item in enumerate(e for e in root.iter() if local_name(e.tag)=='Item'):
   props=[];coords=[];paths=[];kind='';details=[]
   for e in item.iter():
    tag=local_name(e.tag)
    if tag=='Type' and e.text and not kind:kind=e.text
    if tag in ['Line','Coordinate'] and e.text:
     found=parse_coordinates(e.text)
     if found:
      path=[]
      for lat,lon in found:
       if not -85<=lat<=85:
        if len(path)>1:paths.append(path)
        path=[];continue
       if path:
        lon+=360*round((path[-1][1]-lon)/360)
        if abs(lat-path[-1][0])>30 or abs(lon-path[-1][1])>90:
         if len(path)>1:paths.append(path)
         path=[]
       elif lon<0:lon+=360
       path.append([lat,lon])
      if path:paths.append(path)
      coords=paths[0] if paths else []
    if tag in ['Pressure','Direction','Speed','WindSpeed','Name','Class','TyphoonName','TyphoonNumber'] and e.text:details.append({'name':e.attrib.get('type') or tag,'value':e.text,'unit':e.attrib.get('unit','')})
   if coords:features.append({'id':str(index),'kind':kind,'coords':coords,'paths':paths,'details':details})
  if not features:raise ValueError('No chart geometry')
  target=next((first_text(e,'DateTime') for e in root.iter() if local_name(e.tag)=='MeteorologicalInfo'),'')
  return {'title':first_text(root,'Title'),'baseTime':first_text(root,'TargetDateTime'),'targetTime':target or first_text(root,'TargetDateTime'),'issued':first_text(root,'ReportDateTime'),'features':features,'source':url}
 return weather.cached('chart-vector-v26-'+filename,86400,load)

def quake_updates():
 def load():
  import quake_revisions
  rows=quake_revisions.catalog();items=[]
  for row in rows:
   if not isinstance(row,dict) or '更新' not in row.get('ttl',''):continue
   try:
    report=quake_revisions.raw_report(row,quake_revisions.document(row['json']));related=[r for r in rows if r.get('eid')==row.get('eid')];report['previousNames']=list({r.get('anm') for r in related if r.get('anm')});report['previousOrigins']=list({r.get('at') for r in related if r.get('at')});items.append(report)
   except (ValueError,KeyError,TypeError):continue
   if len(items)>=10:break
  return {'items':items}
 return weather.cached('quake-extra-updates-v45',15,load)
