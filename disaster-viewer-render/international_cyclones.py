"""Public JTWC/Fiji bulletin facts. No reuse of website API tokens or restricted feeds."""
from datetime import datetime,timedelta,timezone
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
from concurrent.futures import ThreadPoolExecutor
import re,requests,calendar
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import weather
UTC=timezone.utc;JST=timezone(timedelta(hours=9))
JTWC='https://www.metoc.navy.mil/jtwc/';FIJI='https://www.met.gov.fj/'
class Page(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.words=[];self.skip=0;self.main=False
 def handle_starttag(self,tag,attrs):
  data=dict(attrs)
  if tag=='a' and data.get('href'):self.links.append(data['href'])
  if tag in ('script','style'):self.skip+=1
  if tag=='main':self.main=True
  if self.main and tag in ('br','p','div','pre','h1','h2','h3'):self.words.append('\n')
 def handle_endtag(self,tag):
  if tag in ('script','style'):self.skip=max(0,self.skip-1)
  if tag=='main':self.main=False
 def handle_data(self,text):
  if self.main and not self.skip:self.words.append(text)
def fetch(url,limit=8_000_000):
 parsed=urlparse(url);host=parsed.hostname
 if parsed.scheme!='https' or parsed.username or parsed.port not in (None,443):raise ValueError('Invalid bulletin URL')
 if host not in ('www.metoc.navy.mil','www.met.gov.fj'):raise ValueError('Unsupported bulletin host')
 with requests.get(url,timeout=(4,16),stream=True,allow_redirects=False,headers={'User-Agent':'DisasterViewer/0.46'}) as response:
  response.raise_for_status()
  if 300<=response.status_code<400:raise ValueError('Unexpected redirect')
  if urlparse(response.url).hostname!=host:raise ValueError('Unexpected redirect')
  chunks=[];length=0
  for chunk in response.iter_content(65536):
   length+=len(chunk)
   if length>limit:raise ValueError('Bulletin too large')
   chunks.append(chunk)
 return b''.join(chunks)
def parse_fiji(text,now=None):
 now=now or datetime.now(UTC);text=' '.join(text.split());issue=re.search(r'\b([A-Z][a-z]{2})\s*(\d{2})(\d{2})(\d{2})\s*UTC',text)
 issued=None
 if issue:
  month=datetime.strptime(issue[1],'%b').month;options=[]
  for year in (now.year-1,now.year,now.year+1):
   try:options.append(datetime(year,month,int(issue[2]),int(issue[3]),int(issue[4]),tzinfo=UTC))
   except ValueError:pass
  if options:
   closest=min(options,key=lambda d:abs((d-now).total_seconds()))
   if abs((closest-now).total_seconds())<=7*86400:issued=closest.astimezone(JST).isoformat()
 items=[]
 pattern=r'(?:SEVERE\s+)?TROPICAL\s+(?:CYCLONE|DEPRESSION)\s+([A-Z][A-Z0-9-]{1,25})(.*?)(?=(?:SEVERE\s+)?TROPICAL\s+(?:CYCLONE|DEPRESSION)\s+[A-Z]|$)'
 for match in re.finditer(pattern,text,re.S):
  name,block=match.groups()
  if name in ('WARNING','WARNINGS','ACTIVITY','DEVELOPMENT','FORECAST','FORMATION'):continue
  pos=re.search(r'(?:CENTRE|CENTER|CENTRED|CENTERED|NEAR).{0,55}?([0-9]+(?:\.[0-9]+)?)\s*([NS])\s+([0-9]+(?:\.[0-9]+)?)\s*([EW])',block)
  if not pos or not issued:continue
  center=[float(pos[1])*(-1 if pos[2]=='S' else 1),float(pos[3])*(-1 if pos[4]=='W' else 1)]
  if abs(center[0])>90 or abs(center[1])>180:continue
  wind=re.search(r'(?:WINDS?|MAXIMUM WINDS?).{0,20}?(\d{1,3})\s*KNOTS?',block);pressure=re.search(r'(\d{3,4})\s*HPA',block)
  items.append({'id':'fiji-'+name+'-'+issued[:4],'name':name,'source':'フィジー気象局（RSMC Nadi）','provider':'fiji','issued':issued,'time':issued,'coords':center,'wind':int(wind[1]) if wind else None,'windUnit':'kt（ノット）','pressure':int(pressure[1]) if pressure else None,'category':'熱帯低気圧・サイクロン','url':FIJI+'fiji-weather/south-west-pacific-marine-bulletin/','forecast':[],'track':[],'history':[],'positionLabel':'公開海上速報に記載された位置'})
 return {'items':items,'issued':issued,'warningNil':bool(re.search(r'PART\s*1\s*:\s*WARNING\s*NIL',text,re.I))}
def fiji():
 url=FIJI+'fiji-weather/south-west-pacific-marine-bulletin/';page=Page();page.feed(fetch(url,2_000_000).decode('utf-8',errors='replace'));data=parse_fiji(' '.join(page.words));data.update(source=url,documents=[{'title':'南太平洋の海上速報（英語）','url':url},{'title':'Fijiの公式進路図','url':FIJI+'tropical-cyclone/tc-forecast-track-map/'}],notice='赤道～南緯25度、東経160度～西経120度の公開海上速報。'+('資料では海上警報はNILです。' if data['warningNil'] else '')+'位置付きの熱帯低気圧が読み取れない場合も、全海域で発生していないと断定しません。');return data

def wmo_time(value,reference):
 """DDHHMM is interpreted in the nearest adjacent UTC month, including year rollover."""
 day,hour,minute=int(value[:2]),int(value[2:4]),int(value[4:6]);candidates=[]
 for offset in (-1,0,1):
  index=reference.year*12+reference.month-1+offset;year,month=divmod(index,12);month+=1
  if day<=calendar.monthrange(year,month)[1]:candidates.append(datetime(year,month,day,hour,minute,tzinfo=UTC))
 if not candidates:raise ValueError('Invalid bulletin day')
 result=min(candidates,key=lambda d:abs((d-reference).total_seconds()))
 if abs((result-reference).total_seconds())>7*86400:raise ValueError('Ambiguous bulletin month')
 return result
def jtwc_fields(block):
 fields=[];wind=re.search(r'MAX SUSTAINED WINDS\s*-\s*(\d+)\s*KT(?:,\s*GUSTS\s*(\d+)\s*KT)?',block);radii=[]
 if wind:
  fields.append(['最大風速（1分平均）',wind[1]+' kt'])
  if wind[2]:fields.append(['最大瞬間風速',wind[2]+' kt'])
 for match in re.finditer(r'RADIUS OF\s+(\d+)\s*KT WINDS\s*-\s*((?:\d+\s+NM\s+(?:NORTHEAST|SOUTHEAST|SOUTHWEST|NORTHWEST) QUADRANT\s*)+)',block):
  quadrants={name:int(distance) for distance,name in re.findall(r'(\d+)\s+NM\s+(NORTHEAST|SOUTHEAST|SOUTHWEST|NORTHWEST) QUADRANT',match[2])};names={'NORTHEAST':'北東','SOUTHEAST':'南東','SOUTHWEST':'南西','NORTHWEST':'北西'}
  radii.append({'threshold':int(match[1]),'quadrants':quadrants});fields.append([str(int(match[1]))+' kt以上の風の範囲',' ／ '.join(names[name]+str(distance)+'海里' for name,distance in quadrants.items())])
 return fields,radii,int(wind[1]) if wind else None
def parse_jtwc(text,url,published):
 text=' '.join(text.split());subject=re.search(r'SUBJ/(.*?)\s+(\d{2}[WEPABSC])\s*\(([^)]+)\)\s+WARNING NR\s*(\d+)',text)
 if not subject:raise ValueError('JTWC subject unavailable')
 header=re.search(r'\b(?:PGTW|PHNC)\s+(\d{6})',text)
 if not header:raise ValueError('JTWC issue time unavailable')
 issued=wmo_time(header[1],published);position=re.search(r'WARNING POSITION:\s*(\d{6})Z\s*---\s*(?:NEAR\s*)?([0-9.]+)([NS])\s+([0-9.]+)([EW])',text)
 if not position:raise ValueError('JTWC position unavailable')
 def point(date,lat,ns,lon,ew,block,hours):
  at=wmo_time(date,issued);coords=[float(lat)*(-1 if ns=='S' else 1),float(lon)*(-1 if ew=='W' else 1)]
  if not -90<=coords[0]<=90 or not -180<=coords[1]<=180:raise ValueError('Invalid cyclone position')
  fields,radii,wind=jtwc_fields(block);return {'time':at.astimezone(JST).isoformat(),'coords':coords,'hours':hours,'fields':fields,'foreignWindRadii':radii,'wind':wind}
 current_block=text[position.end():].split('FORECASTS:',1)[0];first=point(*position.groups(),current_block,0);forecast=[first]
 pattern=r'(\d+)\s+HRS,\s+VALID AT:\s*(\d{6})Z\s*---\s*([0-9.]+)([NS])\s+([0-9.]+)([EW])(.*?)(?=\d+\s+HRS,\s+VALID AT:|REMARKS:|$)'
 for row in re.finditer(pattern,text):
  hours,date,lat,ns,lon,ew,block=row.groups();forecast.append(point(date,lat,ns,lon,ew,block,int(hours)))
 kind={'SUPER TYPHOON':'スーパー台風（JTWC区分）','TYPHOON':'台風（JTWC区分）','TROPICAL STORM':'熱帯暴風雨','TROPICAL DEPRESSION':'熱帯低気圧','TROPICAL CYCLONE':'サイクロン','SUBTROPICAL STORM':'亜熱帯暴風雨'}.get(subject[1],subject[1]);ident=re.search(r'/([a-z]{2}\d{4})web\.txt$',url,re.I)
 movement=re.search(r'MOVEMENT PAST SIX HOURS\s*-\s*(\d+) DEGREES AT\s*(\d+) KTS',text)
 return {'id':'jtwc-'+(ident[1].lower() if ident else subject[2]+'-'+str(issued.year)),'name':subject[3]+'（'+subject[2]+'）','source':'米軍合同台風警報センター（JTWC）','provider':'jtwc','issued':issued.astimezone(JST).isoformat(),'time':first['time'],'coords':first['coords'],'category':kind,'wind':first['wind'],'windUnit':'kt（1分平均）','advisoryNumber':int(subject[4]),'movementDir':int(movement[1]) if movement else None,'movementSpeed':int(movement[2]) if movement else None,'forecast':forecast,'history':[],'track':[],'url':url,'positionLabel':'JTWCの実況位置（時刻は日本時間）','description':'日本の台風番号・強さの区分とは異なります。風の範囲は34・50・64 ktの原文値です。'}
def jtwc_links(payload):
 root=ET.fromstring(payload);channel=root.find('channel')
 if channel is None:raise ValueError('Invalid JTWC feed')
 published=parsedate_to_datetime(channel.findtext('pubDate') or '');links=[];documents=[]
 for item in channel.findall('item'):
  page=Page();page.feed(item.findtext('description') or '')
  for url in page.links:
   if re.fullmatch(r'https://www\.metoc\.navy\.mil/jtwc/products/[a-z0-9_.-]+',url,re.I):
    if re.search(r'/[a-z]{2}\d{4}web\.txt$',url,re.I) and url not in links:links.append(url)
    if url.endswith(('web.txt','prog.txt','.gif','.kmz')):documents.append({'title':{'web.txt':'公式速報・概況','prog.txt':'予報の解説（英語）','.gif':'公式予報図','.kmz':'公式の位置・進路データ'}.get(next((s for s in ('web.txt','prog.txt','.gif','.kmz') if url.endswith(s)),''),'公式資料'),'url':url})
 return published,links,documents
def jtwc():
 published,links,documents=jtwc_links(fetch(JTWC+'rss/jtwc.rss',2_000_000));items=[];failures=0
 with ThreadPoolExecutor(max_workers=3) as pool:
  jobs=[(url,pool.submit(fetch,url,1_000_000)) for url in links[:12]]
  for url,job in jobs:
   try:items.append(parse_jtwc(job.result().decode('utf-8',errors='replace'),url,published))
   except Exception:failures+=1
 if failures and not items:raise ValueError('JTWC bulletin positions unavailable')
 return {'items':items,'documents':documents,'source':JTWC+'rss/jtwc.rss','issued':published.astimezone(JST).isoformat(),'notice':'JTWCの公開速報・予報です。風速は1分平均のkt。気象庁の強さの区分・台風番号とは異なります。'+(' 一部の速報を取得できません。公式資料も確認してください。' if failures else '')}
def listing(provider):
 if provider not in ('jtwc','fiji'):raise ValueError('Unsupported public cyclone provider')
 def load():
  import tc_history,storage
  data=(jtwc if provider=='jtwc' else fiji)()
  for item in data.get('items',[]):
   if not item.get('forecast') and item.get('time') and item.get('coords'):
    fields=[['種別',item.get('category','熱帯低気圧')]]
    if item.get('wind') is not None:fields.append(['最大風速',str(item['wind'])+' '+item['windUnit']])
    if item.get('pressure') is not None:fields.append(['中心気圧',str(item['pressure'])+' hPa'])
    storage.put('tc-step',item['id']+'|'+item['time'],{'storm':item['id'],'source':item['source'],'name':item['name'],'time':item['time'],'coords':item['coords'],'fields':fields})
   tc_history.observations(item)
   item['history']=sorted([r for r in storage.values('tc-step') if r.get('storm')==item['id'] and r.get('time','')<item.get('time','')],key=lambda r:r['time'])
  return data
 return weather.cached('international-cyclones46-'+provider,300,load)
