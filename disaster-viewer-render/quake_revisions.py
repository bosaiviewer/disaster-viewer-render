"""Official immutable bulletins; preserve observations across source-only revisions."""
import copy,re,math
from datetime import datetime
import requests,weather,jma
BASE='https://www.jma.go.jp/bosai/quake/data/'
SCALES={'0':0,'1':10,'2':20,'3':30,'4':40,'5-':45,'5+':50,'6-':55,'6+':60,'7':70}
def epoch(value):
 try:return datetime.fromisoformat(str(value).replace('/','-').replace('Z','+00:00')).replace(tzinfo=None).timestamp()
 except (ValueError,TypeError):return 0
def document(filename):
 if not re.fullmatch(r'\d{14}_\d{14}_[A-Za-z0-9_]+\.json',filename):raise ValueError('Invalid bulletin filename')
 return weather.cached('quake-document45-'+filename,86400,lambda:weather.get_json('quake/data/'+filename))
def catalog():
 result=weather.cached('quake-catalog45',10,lambda:{'items':weather.get_json('quake/data/list.json')})
 if not isinstance(result.get('items'),list):raise ValueError('Official catalog unavailable')
 return result['items']
def raw_report(row,doc):
 if doc.get('Control',{}).get('Status')!='通常':raise ValueError('Not operational')
 body=doc.get('Body') or {};eq=body.get('Earthquake') or {};head=doc.get('Head') or {};area=(eq.get('Hypocenter') or {}).get('Area') or {};title=head.get('Title') or row.get('ttl') or '地震情報'
 if not eq and not body.get('Intensity'):raise ValueError('Not earthquake information')
 coords=re.findall(r'[+-]\d+(?:\.\d+)?',area.get('Coordinate') or '')
 pos=area.get('latlon') or {};lat,lon=pos.get('lat'),pos.get('lon');depth=None
 if len(coords)>=2:
  lat,lon=map(float,coords[:2])
  if len(coords)>=3:depth=abs(float(coords[2]))/1000
 precise=re.findall(r'[+-]\d+(?:\.\d+)?',area.get('Coordinate_WGS') or '')
 if len(precise)>=2:
  def degrees(value,limit):
   n=float(value);absolute=abs(n)
   return math.copysign(int(absolute//100)+(absolute%100)/60,n) if absolute>limit else n
  lat,lon=degrees(precise[0],90),degrees(precise[1],180)
  if len(precise)>=3:depth=abs(float(precise[2]))/1000
 if lat is not None and (not math.isfinite(float(lat)) or abs(float(lat))>90):lat=None
 if lon is not None and (not math.isfinite(float(lon)) or abs(float(lon))>180):lon=None
 value=eq.get('Magnitude');value=value.get('value') if isinstance(value,dict) else value
 try:mag=float(value)
 except (ValueError,TypeError):mag=None
 coordinate_text=None
 if len(precise)>=2:
  def label(value,limit,positive,negative):
   n=float(value);absolute=abs(n);degrees=int(absolute//100) if absolute>limit else int(absolute);minutes=absolute%100 if absolute>limit else (absolute-degrees)*60
   minute_text=format(minutes,'.6f').rstrip('0').rstrip('.')
   return (negative if n<0 else positive)+str(degrees)+'度'+minute_text+'分'
  coordinate_text=label(precise[0],90,'北緯','南緯')+'/'+label(precise[1],180,'東経','西経')
 stations=jma.station_points(doc);regions=jma.region_points(doc);obs=(body.get('Intensity') or {}).get('Observation') or {}
 points=[{'pref':p['pref'],'addr':p['name'],'scale':p['scaleCode'],'isArea':False} for p in stations] or [{'pref':'','addr':p['name'],'scale':p['scaleCode'],'isArea':True} for p in regions]
 maximum=SCALES.get(str(obs.get('MaxInt')),-1);maximum=max(maximum,max((p['scale'] for p in points),default=-1))
 kind='HypocenterUpdate' if '震源要素更新' in title else 'IntensityUpdate' if '震度情報更新' in title else 'ScalePrompt' if title=='震度速報' else 'Destination' if title=='震源に関する情報' else 'Foreign' if '遠地' in title else 'ScaleAndDestination'
 comments=jma.extract(doc,row['json'])['comments']
 return {'id':'jma-update-'+row['json'],'reportFile':row['json'],'coordinateText':coordinate_text,'eventId':head.get('EventID') or row.get('eid'),'code':551,'time':head.get('ReportDateTime') or row.get('rdt'),'issue':{'type':kind,'title':title,'time':head.get('ReportDateTime') or row.get('rdt'),'source':'気象庁','serial':head.get('Serial') or row.get('ser')},'earthquake':{'time':eq.get('OriginTime') or row.get('at'),'maxScale':maximum,'hypocenter':{'name':area.get('Name'),'latitude':lat,'longitude':lon,'magnitude':mag,'depth':depth}},'points':points,'stations':stations,'regions':regions,'comments':{'freeFormComment':'\n'.join(comments)},'hasIntensity':bool(body.get('Intensity'))}
def series(rows,loader=None):
 import app
 loader=loader or document
 result=[];previous=None
 for row in sorted(rows,key=lambda r:epoch(r.get('rdt'))):
  raw=raw_report(row,loader(row['json']));report=app.normalize(raw);report.update(reportId=row['json'],eventId=raw['eventId'],type=raw['issue']['title'],serial=raw['issue']['serial'],intensityReportId=row['json'],coordinateText=raw.get('coordinateText'))
  if previous:
   if not raw['hasIntensity']:
    for key in ('scale','scaleCode','points','pointGroups','pointTree','intensityReportId'):report[key]=copy.deepcopy(previous[key])
    report['intensitySource']={'issued':previous['issued'],'reportId':previous['reportId']}
    for key in ('domestic','foreign'):report['messages'][key]=previous['messages'][key]
    report['isForeign']=previous.get('isForeign',False)
    before=previous['messages'].get('comment','');after=report['messages'].get('comment','')
    if before and before not in after:report['messages']['comment']='\n'.join(x for x in (before,after) if x)
   for key in ('coords','depth','magnitude'):
    if report[key] in (None,'不明'):report[key]=copy.deepcopy(previous[key])
   if report['name']=='震源情報なし':report['name']=previous['name']
   if not (loader(row['json']).get('Body') or {}).get('Comments'):report['messages']=copy.deepcopy(previous['messages'])
  result.append(report);previous=report
 return result
def enrich(items):
 """Only revise an existing, unambiguously identified event; never add guessed events."""
 try:rows=catalog()
 except (requests.RequestException,ValueError,TypeError):return items
 if not isinstance(rows,list):return items
 grouped={}
 for row in rows:
  if isinstance(row,dict) and row.get('eid') and row.get('json'):grouped.setdefault(row['eid'],[]).append(row)
 result=[dict(q) for q in items]
 by_publication={}
 for row in rows:
  if isinstance(row,dict):by_publication.setdefault((jma.minute(row.get('at')),jma.minute(row.get('rdt')),row.get('anm') or ''),[]).append(row)
 for item in result:
  if 'history' in item:item['history']=[dict(h) for h in item['history']]
  for report in [item,*item.get('history',[])]:
   key=(jma.minute(report.get('time')),jma.minute(report.get('issued')),'' if report.get('name')=='震源情報なし' else report.get('name'))
   matches=by_publication.get(key,[])
   if len(matches)==1 and matches[0].get('ttl'):
    row=matches[0];report.update(type=row['ttl'],serial=row.get('ser'),eventId=row.get('eid'))
 for event,reports in grouped.items():
  if not any('更新' in r.get('ttl','') for r in reports):continue
  named=next((r for r in reports if r.get('anm')),None)
  if not named:continue
  names={r.get('anm') for r in reports if r.get('anm')};origins={jma.minute(r.get('at')) for r in reports if jma.minute(r.get('at'))}
  matches=[q for q in result if q.get('eventId')==event or jma.minute(q.get('time')) in origins and q.get('name') in names]
  if len(matches)!=1:continue
  old=matches[0]
  try:history=series(reports)
  except (requests.RequestException,ValueError,TypeError,KeyError):continue
  if not history or epoch(history[-1]['issued'])<epoch(old['issued']):continue
  latest=copy.deepcopy(history[-1]);latest.update(id=old['id'],history=list(reversed(history[:-1])),historyCount=len(history)-1,reportCount=len(history),provider='jma')
  result[result.index(old)]=latest
 return result
def supplement(filename):
 rows=catalog()
 if not any(r.get('json')==filename for r in rows if isinstance(r,dict)):raise ValueError('Bulletin outside published catalog')
 current=document(filename);data=jma.extract(current,filename)
 if not data['stations'] and not data['regions']:
  event=current.get('Head',{}).get('EventID');issued=current.get('Head',{}).get('ReportDateTime')
  rows=[r for r in rows if r.get('eid')==event and epoch(r.get('rdt'))<=epoch(issued)]
  for row in sorted(rows,key=lambda r:epoch(r.get('rdt')),reverse=True):
   previous=jma.extract(document(row['json']),row['json'])
   if previous['stations'] or previous['regions']:
    data.update(stations=previous['stations'],regions=previous['regions'],intensitySourceURL=previous['url'],comments=list(dict.fromkeys(previous['comments']+data['comments'])));break
 return dict(data,status='ok')
