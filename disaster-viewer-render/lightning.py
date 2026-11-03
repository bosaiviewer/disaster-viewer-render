"""JMA public LIDEN observations, separated by the provider's type field."""
from datetime import datetime,timezone
import re,requests,weather
BASE='https://www.jma.go.jp/bosai/'
def frames():
 def load():
  data=weather.get_json('jmatile/data/nowc/targetTimes_N3.json')
  return {'items':[r for r in data if 'liden' in r.get('elements',[]) and re.fullmatch(r'\d{14}',r.get('basetime','')) and re.fullmatch(r'\d{14}',r.get('validtime',''))]}
 return weather.cached('lightning-times32',60,load)
def observations(valid):
 if not re.fullmatch(r'\d{14}',valid):raise ValueError('Invalid time')
 moment=datetime.strptime(valid,'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
 catalog=frames()
 if catalog.get('error'):return {'items':[],'error':catalog['error']}
 rows=[]
 for row in catalog.get('items',[]):
  time=datetime.strptime(row['validtime'],'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
  if 0<=(moment-time).total_seconds()<=300:rows.append(row)
 if not rows:return {'items':[],'available':False,'notice':'この時刻の落雷・雲放電の観測データは提供範囲にありません。'}
 row=max(rows,key=lambda r:r['validtime']);base=row['basetime'];stamp=row['validtime']
 def load():
  url=BASE+f'jmatile/data/nowc/{base}/none/{stamp}/surf/liden/data.geojson'
  response=requests.get(url,timeout=(4,12));response.raise_for_status();raw=response.json()
  if raw.get('type')!='FeatureCollection' or not isinstance(raw.get('features'),list):raise ValueError('Invalid lightning GeoJSON')
  return {'items':parse_features(raw),'available':True,'time':stamp,'source':'https://www.jma.go.jp/bosai/nowc/','notice':'表示時刻までの前5分間に検知された放電です。検知した位置・種類には誤差があります。'}
 return weather.cached('lightning32-'+stamp,60,load)
def parse_features(raw):
 items=[]
 for feature in raw.get('features',[]):
  geom=feature.get('geometry') or {};props=feature.get('properties') or {};kind='ground' if props.get('type')==4 else 'cloud' if props.get('type') is not None else None
  if not kind:continue
  coords=[geom.get('coordinates')] if geom.get('type')=='Point' else geom.get('coordinates',[]) if geom.get('type')=='MultiPoint' else []
  for p in coords:
   if not isinstance(p,list) or len(p)<2 or not all(isinstance(v,(int,float)) for v in p[:2]) or not -180<=p[0]<=180 or not -90<=p[1]<=90:continue
   items.append({'coords':[p[1],p[0]],'kind':kind})
 return items
