"""Official preparedness data; no scraping of river.go.jp operational endpoints."""
import csv,io,json,math,re,calendar
from pathlib import Path
from datetime import datetime,timedelta
import requests,storage,weather
ROOT=Path(__file__).parent/'data'
STATIONS=json.loads((ROOT/'heat-stations51.json').read_text(encoding='utf-8'))['items']
CAPITALS=json.loads((ROOT/'principal-cities51.json').read_text(encoding='utf-8'))

def principal_city(region,items):
 name=({'01-north':'旭川','01-east':'釧路','01-central':'札幌','01-south':'函館'}).get(region,CAPITALS.get(region))
 if region.startswith('01-'):
  import meteo
  region_name=next((f['properties']['name'] for f in meteo.REGIONS['features'] if f['properties']['code']==region),'')
  for part,city in [('道北','旭川'),('道東','釧路'),('道央','札幌'),('道南','函館')]:
   if part in region_name:name=city
 if not name:return items[0]['code'] if items else None
 exact=next((c for c in items if c['name'] in (name+'市',name+'区')),None)
 return (exact or next((c for c in items if c['name'].startswith(name)),None) or (items[0] if items else {})).get('code')

def finite(value):
 try:n=float(value)
 except (ValueError,TypeError):return None
 return n if math.isfinite(n) else None

def csv_text(url):
 response=requests.get(url,timeout=(3,15))
 if response.status_code==404:return None
 response.raise_for_status();return response.content.decode('utf-8-sig')

def wbgt_time(day,hour):
 h,m=map(int,hour.split(':')[:2]);return (datetime.strptime(day,'%Y/%m/%d').replace(tzinfo=storage.JST)+timedelta(hours=h,minutes=m)).isoformat()

def parse_observed(text):
 rows=[]
 for r in list(csv.reader(io.StringIO(text)))[1:]:
  if len(r)<3 or finite(r[2]) is None:continue
  try:rows.append({'time':wbgt_time(r[0],r[1]),'value':finite(r[2])})
  except (ValueError,TypeError):continue
 return rows

def parse_forecast(text,station):
 rows=list(csv.reader(io.StringIO(text)));out=[]
 if len(rows)<2:raise ValueError('Invalid heat forecast')
 row=next((r for r in rows[1:] if r and r[0].strip()==station),None)
 if row is None:raise ValueError('Station not found')
 for stamp,value in zip(rows[0][2:],row[2:]):
  value=finite(value)
  if value is None or not re.fullmatch(r'\d{10}',stamp.strip()):continue
  stamp=stamp.strip();at=datetime.strptime(stamp[:8],'%Y%m%d').replace(tzinfo=storage.JST)+timedelta(hours=int(stamp[8:]))
  out.append({'time':at.isoformat(),'value':value/10})
 return {'issued':row[1].strip(),'items':out}

def parse_alert(text):
 rows=list(csv.reader(io.StringIO(text)));header=next((i for i,r in enumerate(rows) if r and r[0]=='府県予報区'),None)
 if header is None:raise ValueError('Invalid alert header')
 meta={r[0]:r[1] for r in rows[:header] if len(r)>1};items=[]
 for raw in rows[header+1:]:
  d=dict(zip(rows[header],raw))
  for idx in [1,2]:
   flag=d.get('TargetDate'+str(idx)+'フラグ');day=meta.get('TargetDate'+str(idx))
   if not day or flag not in ('0','1','2','3','9'):continue
   items.append({'office':d.get('府県予報区等コード'),'name':d.get('府県予報区'),'date':day,'flag':int(flag),'label':{'0':'発表なし','1':'熱中症警戒アラート','2':'特別警戒情報の判定段階（正式発表前）','3':'熱中症特別警戒アラート','9':'発表時間外'}[flag]})
 return {'items':items,'issued':meta.get('ReportDate','')+' '+meta.get('ReportTime','')}

def heat(lat,lon,month=None):
 lat=float(lat);lon=float(lon)
 if not math.isfinite(lat+lon) or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Invalid coordinate')
 now=storage.now();month=month or now.strftime('%Y%m')
 if not re.fullmatch(r'\d{6}',month) or not 1<=int(month[4:])<=12 or not 2025<=int(month[:4])<=now.year or month>now.strftime('%Y%m'):raise ValueError('Invalid month')
 station=min(STATIONS,key=lambda s:(s['coords'][0]-lat)**2+((s['coords'][1]-lon)*math.cos(math.radians(lat)))**2);code=station['id']
 def load():
  observed_url=f'https://www.wbgt.env.go.jp/est15WG/dl/wbgt_{code}_{month}.csv';forecast_url=f'https://www.wbgt.env.go.jp/prev15WG/dl/yohou_{code}.csv'
  errors=[];observed=[];forecast={'items':[]};alerts=[];sources=[observed_url,forecast_url]
  try:
   text=csv_text(observed_url)
   if text is not None:observed=parse_observed(text)
  except (requests.RequestException,ValueError):errors.append('実況値')
  current_observed=observed
  if month!=now.strftime('%Y%m'):
   current_url=f'https://www.wbgt.env.go.jp/est15WG/dl/wbgt_{code}_{now:%Y%m}.csv';sources.append(current_url)
   try:
    text=csv_text(current_url);current_observed=parse_observed(text) if text is not None else []
   except (requests.RequestException,ValueError):current_observed=[];errors.append('現在の実況値')
  valid_observed=[p for p in current_observed if datetime.fromisoformat(p['time'])<=now]
  latest_observation=max(valid_observed,key=lambda p:p['time'],default=None)
  try:
   text=csv_text(forecast_url)
   if text is not None:forecast=parse_forecast(text,code)
  except (requests.RequestException,ValueError):errors.append('予測値')
  # Only actual issuance files; never treat the 10:00 preliminary flag as a warning.
  dates=[now] if now.hour>=5 else [now-timedelta(days=1)]
  for day in dates:
   for h in (['05','14','17'] if day.hour>=17 else ['05','14'] if day.hour>=14 else ['05']):
    url=f'https://www.wbgt.env.go.jp/alert/dl/{day.year}/alert_{day:%Y%m%d}_{h}.csv';sources.append(url)
    try:
     text=csv_text(url)
     if text is not None:alerts.extend(parse_alert(text)['items'])
    except (requests.RequestException,ValueError):errors.append('警戒情報')
  merged={}
  for item in alerts:
   key=(item['office'],item['date']);old=merged.get(key)
   if old is None or item['flag']==3 or old['flag']!=3:merged[key]=item
  active=[p for p in forecast['items'] if datetime.fromisoformat(p['time'])>=now]
  return {'station':station,'month':month,'observations':observed,'latestObservation':latest_observation,'forecast':forecast,'currentForecast':active,'alerts':list(merged.values()),'partialErrors':sorted(set(errors)),'source':'https://www.wbgt.env.go.jp/','sources':sources,'notice':'環境省熱中症予防情報サイトのCSVを表示用に加工。暑さ指数は気温とは異なり、実況推定値と予測値を区別します。低い値でも体調・環境によって熱中症のおそれがあります。警戒情報の正式発表は環境省で確認してください。','forecastExpired':bool(forecast['items']) and not active,'observedAvailable':bool(observed)}
 return weather.cached('heat52-'+code+'-'+month,1800,load)
