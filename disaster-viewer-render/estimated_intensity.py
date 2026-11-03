"""JMA published raster meshes, matched to one earthquake; no fabricated estimates."""
import re,math
from datetime import datetime,timedelta,timezone
import weather
BASE='https://www.jma.go.jp/bosai/estimated_intensity_map/'
def epoch(value):
 try:
  d=datetime.fromisoformat(str(value).replace('/','-').replace('Z','+00:00'))
  if d.tzinfo is None:d=d.replace(tzinfo=timezone(timedelta(hours=9)))
  return d.timestamp()
 except (ValueError,TypeError):return None
def mesh_bounds(code,datum=2):
 if not re.fullmatch(r'\d{4}',str(code)):raise ValueError('Invalid mesh')
 south=int(str(code)[:2])/1.5;west=int(str(code)[2:])+100;north=south+2/3;east=west+1
 if datum!=2:
  south=south-.00010695*south+.000017464*west+.0046017;west=west-.0000046038*south-.000083043*west+.010040
  north=north-.00010695*north+.000017464*east+.0046017;east=east-.0000046038*north-.000083043*east+.010040
 return [[south,west],[north,east]]
def match(rows,time,name='',coords=None):
 at=epoch(time)
 if at is None:raise ValueError('Invalid origin time')
 candidates=[]
 for row in rows:
  if not isinstance(row,dict):continue
  hypo=row.get('hypo') or {}
  if not isinstance(hypo,dict):continue
  origin=epoch(hypo.get('at'))
  if origin is None or abs(origin-at)>60 or hypo.get('kun') not in (0,None):continue
  if not re.fullmatch(r'\d{12}_\d{3}',str(row.get('url',''))):continue
  same_name=hypo.get('epi')==name or name.startswith(str(hypo.get('epi',''))+'（')
  near=False
  if coords:
   try:near=math.hypot((float(hypo['lat'])-coords[0])*111,(float(hypo['lon'])-coords[1])*90)<=80
   except (KeyError,TypeError,ValueError):pass
  if same_name or near:candidates.append(row)
 if len(candidates)!=1:return None
 row=candidates[0];images=[{'url':BASE+'data/'+row['url']+'/'+str(code)+'.png','bounds':mesh_bounds(code,row.get('datum',1))} for code in row.get('mesh_num',[]) if re.fullmatch(r'\d{4}',str(code))]
 if not images:return None
 return {'id':row['url'],'images':images,'bounds':row.get('bounds'),'issued':row['hypo'].get('it'),'origin':row['hypo'].get('at'),'name':row['hypo'].get('epi'),'comment':row.get('comment',''),'source':'https://www.jma.go.jp/bosai/map.html#contents=estimated_intensity_map&id='+row['url'][:12]}
def lookup(time,name,coords=None):
 if epoch(time) is None:raise ValueError('Invalid origin time')
 data=weather.cached('estimated-index46',60,lambda:{'items':weather.get_json('estimated_intensity_map/data/list.json')})
 if data.get('error'):return {'available':False,'error':'推計震度分布の提供状況を確認できません。'}
 item=match(data.get('items',[]),time,name,coords)
 return {'available':bool(item),'item':item,'source':BASE}
