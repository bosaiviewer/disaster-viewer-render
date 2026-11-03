"""Additional public-information views. No fabricated live evacuation data."""
import math,re,os,json
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import requests
import weather,storage,meteo

def finite_coordinate(value,limit):
 try:value=float(value)
 except (TypeError,ValueError):raise ValueError('Invalid coordinate')
 if not math.isfinite(value) or not -limit<=value<=limit:raise ValueError('Invalid coordinate')
 return round(value,4)

def world_weather(lat,lon):
 lat=finite_coordinate(lat,90);lon=finite_coordinate(lon,180)
 def load():
  params={'latitude':lat,'longitude':lon,'current':'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,snowfall,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m','daily':'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,sunrise,sunset','timezone':'auto','forecast_days':7}
  r=requests.get('https://api.open-meteo.com/v1/forecast',params=params,timeout=(3,18));r.raise_for_status();d=r.json()
  if not isinstance(d.get('current'),dict) or not isinstance(d.get('daily'),dict):raise ValueError('Invalid forecast')
  d.update(source='https://open-meteo.com/',notice='Open-Meteoの気象モデルによる現在値・予報です。現地の実測や公式警報ではありません。選択地点の現地時間で表示します。無料APIは非商用利用向けです。公開・商用運用は利用条件を確認してください。')
  return d
 return weather.cached(f'world-{lat}-{lon}',600,load)

def world_search(query):
 query=str(query or '').strip()
 if not 2<=len(query)<=80:raise ValueError('Invalid search')
 def load():
  r=requests.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':query,'count':10,'language':'ja','format':'json'},timeout=(3,12));r.raise_for_status();doc=r.json()
  return {'results':[{'id':x['id'],'name':x['name'],'country':x.get('country',''),'region':x.get('admin1',''),'latitude':x['latitude'],'longitude':x['longitude']} for x in doc.get('results',[])],'source':'https://open-meteo.com/en/docs/geocoding-api'}
 return weather.cached('world-search-'+query,3600,load)

CAMERAS=[{'id':'kizu-C03121','name':'木津川 高山ダム下流','image':'https://www.seishiga.kkr.mlit.go.jp/kizujyo/pic/C03121.jpg','source':'https://www.kkr.mlit.go.jp/kizujyo/bousai/map/livecam/talayamadam.html','riverCodes':['860604037101','860604037102']}]

def cameras():
 return {'items':CAMERAS,'source':'https://www.ktr.mlit.go.jp/araike/kouji/livecamera.htm','notice':'国土交通省の公開静止画です。木津川の登録済み1地点のみです。現在画像を取得できなかった荒川の3地点は表示から削除しました。'}

def evacuation():
 # Optional trusted local export; do not treat absence of a feed as all-clear.
 file=os.environ.get('EV_EVACUATION_FILE')
 if not file:return {'available':False,'items':[],'notice':'全国の避難発令を取得する配信には未接続です。「発表なし」という意味ではありません。自治体の防災情報を確認してください。','source':'https://www.fmmc.or.jp/commons/faq/'}
 try:
  d=json.loads(Path(file).read_text(encoding='utf-8'))
  if not isinstance(d,dict) or not isinstance(d.get('items'),list):raise ValueError()
  parsed=datetime.fromisoformat(d['updatedAt'].replace('Z','+00:00'))
  if parsed.tzinfo is None:raise ValueError()
  items=[]
  for x in d['items']:
   if not isinstance(x,dict) or x.get('level') not in (3,4,5) or not re.fullmatch(r'(?:\d{5}|\d{7})',str(x.get('cityCode',''))):raise ValueError()
   item={k:x.get(k) for k in ['id','cityCode','municipality','region','reason','households','people','time','level','name','source']}
   item['id']=item.get('id') or str(item['cityCode'])+'-'+str(item.get('region'))
   items.append(item)
  age=(datetime.now(timezone.utc)-parsed.astimezone(timezone.utc)).total_seconds()
  return {'available':True,'stale':age>600 or age< -60,'updatedAt':d['updatedAt'],'items':items,'source':d.get('source',''),'notice':'ローカル連携ファイルの対象地域のみです。全国を網羅しません。最新性・対象範囲は連携元で確認してください。'}
 except (OSError,ValueError,KeyError,TypeError):return {'available':False,'items':[],'error':'避難情報の連携ファイルを読み取れません。','notice':'現在の避難発令状況は確認できません。'}

def atom_entries(raw):
 root=ET.fromstring(raw);ns={'a':'http://www.w3.org/2005/Atom'};items=[]
 for e in root.findall('a:entry',ns):
  title=e.findtext('a:title',namespaces=ns) or '';summary=e.findtext('a:content',namespaces=ns) or '';link=e.find('a:link',ns);url=link.get('href','') if link is not None else ''
  if not url.startswith('https://www.data.jma.go.jp/developer/xml/data/'):continue
  if any(k in title for k in ['噴火','台風','南海トラフ','津波']):
   category='火山' if '噴火' in title else '台風' if '台風' in title else '南海トラフ' if '南海トラフ' in title else '津波'
   items.append({'id':url,'category':category,'title':title,'text':summary,'time':e.findtext('a:updated',namespaces=ns),'source':url,'view':{'火山':'volcanoes','台風':'cyclones','南海トラフ':'nankai','津波':'tsunami'}[category]})
 return items

def japanese_quake_name(q):
 name=q.get('anm') or '';regions=[]
 if not name or '遠地' in q.get('ttl',''):
  try:
   file=q.get('json','')
   if re.fullmatch(r'[A-Za-z0-9_-]+\.json',file):
    import jma
    d=weather.cached('news-name-v29-'+file,86400,lambda:jma.extract(weather.get_json('quake/data/'+file),file))
    name=d.get('displayName') or name;regions=[r.get('name') for r in d.get('regions',[]) if r.get('name')]
  except (requests.RequestException,ValueError,KeyError,TypeError):pass
 if name:return name
 if '震度速報' not in q.get('ttl',''):return '震源名は発表原文を確認してください'
 if regions:return '・'.join(regions)+'の震度速報（震源の発表前）'
 prefs=[]
 for item in q.get('int',[]):
  code=str(item.get('code',''));office=weather.AREAS['offices'].get(code+'0000',{})
  if office.get('name') and office['name'] not in prefs:prefs.append(office['name'])
 return ('・'.join(prefs)+'の震度速報（震源の発表前）') if prefs else '震源の発表前の速報'

def tsunami_news_levels46():
 """Use already received official forecasts, by exact event ID; never infer from magnitude."""
 latest={}
 for row in storage.values('tsunami'):
  event=str(row.get('eventId') or '')
  if not re.fullmatch(r'\d{14}',event):continue
  areas=row.get('areas') or []
  if not areas and not any(word in str(row.get('text') or '') for word in ('解除','発表なし')):continue
  level=max((2 if '津波警報' in str(a.get('kind')) else 1 if '津波注意報' in str(a.get('kind')) else 0 for a in areas),default=0)
  try:at=datetime.fromisoformat(str(row.get('time')).replace('Z','+00:00')).timestamp()
  except (ValueError,TypeError):continue
  if event not in latest or at>latest[event][0]:latest[event]=(at,level)
 return {event:value[1] for event,value in latest.items()}

def news():
 def load():
  failures=[];items=[]
  previous_quakes={r.get('eventId') for r in merge_saved_quakes(storage.values('news-history')) if r.get('category')=='地震'}
  def fetch_feed(name):
   r=requests.get('https://www.data.jma.go.jp/developer/xml/feed/'+name+'_l.xml',timeout=(3,15));r.raise_for_status();return atom_entries(r.content)
  with ThreadPoolExecutor(max_workers=2) as pool:
   futures={name:pool.submit(fetch_feed,name) for name in ['eqvol','extra']}
   for name,future in futures.items():
    try:items.extend(future.result())
    except (requests.RequestException,ValueError,ET.ParseError):failures.append(name)
  try:
   rows=weather.get_json('quake/data/list.json')
   for q in consolidate_quake_announcements(rows):
    try:mag=float(q.get('mag') or -1);scale=str(q.get('maxi') or '')
    except (ValueError,TypeError):continue
    if mag<6 and scale not in ('3','4','5-','5+','6-','6+','7') and q['_eventId'] not in previous_quakes:continue
    file=q.get('json','')
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.json',file):continue
    title=(q.get('ttl') or '地震情報')+'：'+japanese_quake_name(q)
    items.append({'regionCodes':[str(a.get('code','')).ljust(6,'0') for a in q.get('int',[])],'eventId':q['_eventId'],'quake':{'time':q.get('at') or q.get('atime'),'name':q.get('anm'),'eventId':q['_eventId']},'intensitySource':q.get('_intensitySource'),'id':'quake-event-'+q['_eventId'],'category':'地震','title':title,'text':'発生 '+str(q.get('at') or q.get('atime') or '未提供')+' ／ '+('M'+str(q.get('mag')) if mag>=0 else '規模未提供')+' ／ 最大震度 '+({'5-':'5弱','5+':'5強','6-':'6弱','6+':'6強'}.get(scale,scale) or '未提供'),'time':q.get('rdt'),'source':'https://www.jma.go.jp/bosai/quake/','view':'earthquakes'})
  except (requests.RequestException,ValueError,TypeError,KeyError):failures.append('quake')
  warnings=meteo.national_warnings()
  if warnings.get('error'):failures.append('warnings')
  else:
   for c in warnings.get('items',[]):
    for w in c.get('warnings',[]):
     if w['level']<5:continue
     items.append({'regionCodes':[c['code']],'id':'warning-'+c['code']+'-'+w['code']+'-'+str(w['time']),'category':'特別警報','title':c['name']+'：'+w['name'],'text':'命に危険が及ぶ状況に備え、自治体の避難情報と原文を確認してください。','time':w['time'],'source':'https://www.jma.go.jp/bosai/warning/','view':'warnings'})
  import briefings
  bulletin_data=briefings.bulletins()
  if bulletin_data.get('error'):failures.append('bulletins')
  for row in bulletin_data.get('items',[]):
   if row.get('type')!='気象防災速報':continue
   items.append({'regionCodes':row.get('areaCodes',[]),'areaType':row.get('areaType'),'office':row.get('office'),'id':'bulletin-'+row['id'],'category':'気象防災速報','title':row['title'],'text':row.get('office') or '本文は気象防災速報の画面で確認してください。','time':row['time'],'source':row['source'],'view':'bulletins'})
  saved_before={x['id']:x for x in storage.values('news-history')}
  for item in items:
   if item.get('time') and saved_before.get(item['id'])!=item:storage.put('news-history',item['id'],item)
  def order(x):
   try:return datetime.fromisoformat(x.get('time','').replace('Z','+00:00')).timestamp()
   except (ValueError,TypeError):return 0
  saved=sorted([r for r in recent_news51(merge_saved_quakes(storage.values('news-history'))) if r.get('category')!='地震' or (re.search(r'[一-龯ぁ-んァ-ヶ]',r.get('title','').split('：')[-1]) and '震源地未提供' not in r.get('title',''))],key=order,reverse=True)
  tsunami_levels=tsunami_news_levels46()
  saved=[dict(row,tsunamiSeverity=tsunami_levels[row['eventId']]) if row.get('category')=='地震' and row.get('eventId') in tsunami_levels else row for row in saved]
  if not items and failures and not saved:raise ValueError('No feeds available')
  return {'items':saved,'source':'https://www.jma.go.jp/','partialErrors':failures,'notice':'過去1か月（取得・保存できた発表）の履歴です。取得できた気象庁の発表を新しい順に掲載します。地震は気象庁発表のみ。初回掲載は最大震度3以上またはM6.0以上とし、掲載後は同じ地震の最新の続報へ更新します。噴火・津波・台風・特別警報・南海トラフ関連・気象防災速報を掲載します。過去の投稿は現在の警報ではありません。アプリを閉じている間の全発表の保存は保証しません。'}
 result=weather.cached('latest-news-v51',60,load)
 return dict(result,items=recent_news51(result.get('items',[])))


def world_cities():
 def load():
  cities=json.loads((Path(__file__).parent/'data/world_cities.json').read_text(encoding='utf-8'))
  params={'latitude':','.join(str(c['lat']) for c in cities),'longitude':','.join(str(c['lon']) for c in cities),'current':'temperature_2m,weather_code','timezone':'GMT','forecast_days':1}
  r=requests.get('https://api.open-meteo.com/v1/forecast',params=params,timeout=(3,25));r.raise_for_status();raw=r.json()
  if not isinstance(raw,list) or len(raw)!=len(cities):raise ValueError('Invalid city weather batch')
  items=[]
  for c,d in zip(cities,raw):
   current=d.get('current') or {};temp=current.get('temperature_2m');code=current.get('weather_code')
   if not isinstance(temp,(int,float)) or not math.isfinite(temp):continue
   items.append(dict(c,temperature=round(temp,1),weatherCode=code,time=current.get('time')))
  if not items:raise ValueError('No city weather available')
  return {'items':items,'source':'https://open-meteo.com/','notice':'主な54都市の天気・気温（気象モデルの推計）。拡大すると表示都市が増えます。地図の都市情報は30分間共有キャッシュします。都市や地図上の地点を押すと詳細を表示します。'}
 return weather.cached('world-city-overview-v28',1800,load)

def catalog_event_id(row):
 filename=row.get('json','');found=re.search(r'^\d{14}_(\d{14})_',filename)
 return str(row.get('eid') or (found[1] if found else ''))

def consolidate_quake_announcements(rows):
 groups={}
 for row in rows:
  if not isinstance(row,dict):continue
  identity=catalog_event_id(row) or '|'.join([str(row.get('at') or row.get('atime') or row.get('json')),str(row.get('anm',''))])
  groups.setdefault(identity,[]).append(row)
 out=[]
 for identity,reports in groups.items():
  reports.sort(key=lambda r:r.get('rdt') or '',reverse=True);latest=dict(reports[0]);latest['_eventId']=identity
  if str(latest.get('maxi','')) not in ('0','1','2','3','4','5-','5+','6-','6+','7'):
   prompt=next((r for r in reports[1:] if str(r.get('maxi','')) in ('0','1','2','3','4','5-','5+','6-','6+','7') and r.get('rdt','')<=latest.get('rdt','')),None)
   if prompt:
    latest['maxi']=prompt.get('maxi');latest['int']=prompt.get('int',[]);latest['_intensitySource']=prompt.get('rdt')
  out.append(latest)
 return sorted(out,key=lambda r:r.get('rdt') or '',reverse=True)

def merge_saved_quakes(rows):
 others=[];quakes={}
 for row in rows:
  if row.get('category')!='地震':others.append(row);continue
  identity=row.get('eventId')
  if not identity:
   found=re.search(r'quake-\d{14}_(\d{14})_',row.get('id',''));identity=found[1] if found else row.get('id')
  if not identity:continue
  item=dict(row);item['eventId']=identity
  if 'quake' not in item:
   origin=re.search(r'発生\s+([^／]+)',item.get('text',''))
   if origin:item['quake']={'time':origin[1].strip(),'name':item.get('title','').split('：',1)[-1],'eventId':identity}
  if identity not in quakes or (str(item.get('time','')),item.get('id','').startswith('quake-event-'))>(str(quakes[identity].get('time','')),quakes[identity].get('id','').startswith('quake-event-')):quakes[identity]=item
 return others+list(quakes.values())


def recent_news51(rows,now=None):
 now=now or storage.now();cut=month_before51(now)
 result=[]
 for row in rows:
  try:
   at=datetime.fromisoformat(str(row.get('time','')).replace('Z','+00:00'))
   if at.tzinfo is None:at=at.replace(tzinfo=storage.JST)
  except (ValueError,TypeError):continue
  if cut<=at<=now:result.append(row)
 return result

def month_before51(now):
 import calendar
 year=now.year-(now.month==1);month=12 if now.month==1 else now.month-1
 return now.replace(year=year,month=month,day=min(now.day,calendar.monthrange(year,month)[1]))
