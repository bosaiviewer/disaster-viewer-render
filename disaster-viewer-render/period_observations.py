"""Official long-period class CSV, including class zero, with validated event IDs."""
import csv,io,re,time,math
from threading import Lock
from urllib.parse import urljoin
import requests,publications
from html.parser import HTMLParser
from urllib.parse import parse_qs,urlparse
BASE='https://www.data.jma.go.jp/eew/data/ltpgm/'
_cache={};_lock=Lock()
class ObservationTable(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.items={};self.cells=[];self.cell=None;self.station=None
 def handle_starttag(self,tag,attrs):
  if tag=='tr':self.cells=[];self.station=None
  if tag=='td':self.cell=[]
  if tag=='a':
   code=parse_qs(urlparse(dict(attrs).get('href','')).query).get('stNo5',[''])[0]
   if re.fullmatch(r'\d{5}',code):self.station=code
 def handle_data(self,text):
  if self.cell is not None:self.cell.append(text)
 def handle_endtag(self,tag):
  if tag=='td' and self.cell is not None:self.cells.append(''.join(self.cell).strip());self.cell=None
  if tag=='tr' and self.station and len(self.cells)>=5:
   pref,area,name,scale=self.cells[:4]
   if pref and area:self.items[self.station]={'pref':pref,'area':area,'scale':scale if scale in ('0','1','2','3','4','5弱','5強','6弱','6強','7','5-','5+','6-','6+') else None}

def page_observations(html):
 parser=ObservationTable();parser.feed(html);return parser.items

def parse_csv(text,metadata=None):
 metadata=metadata or {}
 stations=[]
 for row in csv.reader(io.StringIO(text)):
  if len(row)<15 or not re.fullmatch(r'\d{5}',row[0]):continue
  try:level=int(row[5]);lat=float(row[13]);lon=float(row[14])
  except (ValueError,TypeError):continue
  if level not in range(5) or not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180:continue
  pref=re.match(r'^(北海道|東京都|.{2,3}[府県])',row[2]);bands=[int(v) if v in ('0','1','2','3','4') else None for v in row[6:13]]
  stations.append({'id':row[0],'name':row[1],'area':row[2],'pref':metadata.get(row[0],{}).get('pref') or (pref[1] if pref else ('伊豆諸島' if row[2] in ('伊豆大島','新島','三宅島','八丈島','神津島') else row[2])), 'scale':metadata.get(row[0],{}).get('scale'),'level':level,'coords':[lat,lon],'start':row[3],'minutes':row[4],'bands':bands})
 if not stations:raise ValueError('No recognized observations')
 return stations

def details(event_id):
 if not re.fullmatch(r'\d{14}',event_id):raise ValueError('Invalid event ID')
 known=next((r for r in publications.index('period').get('items',[]) if 'eventId='+event_id in r['url']),None)
 if not known:raise ValueError('Event outside published list')
 with _lock:
  old=_cache.get(event_id)
  if old and time.monotonic()-old[0]<60:return old[1]
  try:
   page=requests.get(known['url'],timeout=(4,12));page.raise_for_status();page.encoding='utf-8'
   parts=[]
   for key in ('dir1','dir2'):
    found=re.search(r"const\s+"+key+r"\s*=\s*['\"]([0-9/]*)['\"]",page.text)
    if not found:raise ValueError('CSV location unavailable')
    parts.append(found[1].strip('/'))
   path='/'.join(x for x in [parts[0],event_id,parts[1],'data','level.csv'] if x)
   response=requests.get(BASE+path,timeout=(4,12));response.raise_for_status()
   stations=parse_csv(response.content.decode('cp932'),page_observations(page.text))
   result={'eventId':event_id,'stations':stations,'url':known['url'],'max':max(p['level'] for p in stations),'error':None}
   _cache[event_id]=(time.monotonic(),result);return result
  except (requests.RequestException,ValueError,UnicodeError):
   if old:return {**old[1],'error':'観測情報の更新を確認できません。前回取得した値です。'}
   return {'eventId':event_id,'stations':[],'error':'長周期地震動の観測点データを取得できません。','url':known['url']}
