"""Read delayed official publication indexes; never interpret absence as no EEW."""
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
from threading import Lock
import re,time,unicodedata
import requests
URLS={'period':'https://www.data.jma.go.jp/eew/data/ltpgm/eq_list.php','eew':'https://www.data.jma.go.jp/eew/data/nc/fc_hist/index.html'}
JST=timezone(timedelta(hours=9));_cache={};_lock=Lock()
class Table(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
 def handle_starttag(self,tag,attrs):
  if tag=='tr':self.row=[]
  elif tag=='td' and self.row is not None:self.cell={'text':'','links':[]}
  elif tag=='a' and self.cell is not None:
   href=dict(attrs).get('href')
   if href:self.cell['links'].append(href)
 def handle_data(self,data):
  if self.cell is not None:self.cell['text']+=data
 def handle_endtag(self,tag):
  if tag=='td' and self.cell is not None and self.row is not None:self.row.append(self.cell);self.cell=None
  elif tag=='tr' and self.row is not None:
   if self.row:self.rows.append(self.row)
   self.row=None;self.cell=None

def epoch(value):
 try:
  d=datetime.fromisoformat(str(value).replace('/','-').replace('Z','+00:00'))
  return d.replace(tzinfo=d.tzinfo or JST).timestamp()
 except (ValueError,TypeError):return None

def parse(html,kind):
 parser=Table();parser.feed(html);result=[]
 for row in parser.rows:
  text=[unicodedata.normalize('NFKC',c['text']).strip() for c in row]
  if len(text)<5:continue
  digits=re.findall(r'\d+',text[0])
  if len(digits)!=5:continue
  try:origin=datetime(*map(int,digits),tzinfo=JST).isoformat()
  except ValueError:continue
  links=[urljoin(URLS[kind],href) for c in row for href in c['links']]
  links=[u for u in links if u.startswith('https://www.data.jma.go.jp/eew/data/')]
  if not links:continue
  mag=float(text[2]) if re.fullmatch(r'\d+(?:\.\d+)?',text[2]) else None
  item={'time':origin,'name':text[1].strip('()（）'),'mag':mag,'url':links[0]}
  if kind=='period':
   level=re.search(r'階級\s*([0-4])',text[3])
   if not level:continue
   item['level']=int(level[1])
  else:
   item['warning']=bool(text[4]);item['cancelled']=bool(re.search(r'取消|取り消|キャンセル',' '.join(text)))
  result.append(item)
 if not result:raise ValueError('Official index format not recognized')
 return result

def index(kind):
 with _lock:
  previous=_cache.get(kind,{})
  if time.monotonic()-previous.get('checked',-1000)<60:return previous
  try:
   r=requests.get(URLS[kind],timeout=(4,15));r.raise_for_status();r.encoding='utf-8'
   result={'checked':time.monotonic(),'items':parse(r.text,kind),'error':None}
  except (requests.RequestException,ValueError):result={**previous,'checked':time.monotonic(),'error':'気象庁の掲載状況を取得できません。'}
  _cache[kind]=result;return result

def match(rows,origin,name,mag):
 t=epoch(origin)
 if t is None:return None
 name=unicodedata.normalize('NFKC',name).strip()
 candidates=[]
 for r in rows:
  if r['name']!=name or abs(epoch(r['time'])-t)>90:continue
  if mag is not None and r['mag'] is not None and abs(mag-r['mag'])>.6:continue
  candidates.append(r)
 return candidates[0] if len(candidates)==1 else None

def lookup(origin,name,mag=None):
 result={}
 for kind in URLS:
  data=index(kind);matched=match(data.get('items',[]),origin,name,mag)
  if kind=='eew' and not matched:matched=event_identity_match(data.get('items',[]),origin,name,mag)
  if kind=='eew' and matched:
   matched=dict(matched)
   try:
    detail=eew_details(matched['url'],matched['time']);detail['cancelled']=bool(detail.get('cancelled') or matched.get('cancelled'));matched.update(detail)
   except (requests.RequestException,ValueError):matched['detailError']=True
  result[kind]={'match':matched,'error':data.get('error'),'source':URLS[kind]}
 return result

_detail_cache={};_detail_lock=Lock()
def eew_details(url,origin):
 with _detail_lock:
  prior=_detail_cache.get(url)
  if prior and time.monotonic()-prior[0]<60:return prior[1]
  if not re.fullmatch(r'https://www\.data\.jma\.go\.jp/eew/data/nc/fc_hist/\d{4}/\d{2}/\d{14}/index\.html',url):raise ValueError('Invalid EEW detail')
  r=requests.get(url,timeout=(4,12));r.raise_for_status();r.encoding='utf-8'
  table=table_section(r.text,'information_list')
  if not table:raise ValueError('EEW table unavailable')
  parser=Table();parser.feed(table);cancelled=bool(re.search(r'取消|取り消|キャンセル',unescape(re.sub('<[^>]*>',' ',table))))
  result={'cancelled':cancelled}
  first=next((row for row in parser.rows if row and row[0]['text'].strip()=='1'),None)
  if first:
   values=re.findall(r'\d+(?:\.\d+)?',first[1]['text'])
   if len(values)>=3:
    date=datetime.fromtimestamp(epoch(origin),JST);hour,minute=int(values[0]),int(values[1]);second=float(values[2]);issued=date.replace(hour=hour,minute=minute,second=int(second),microsecond=int((second%1)*1e6))
    if (issued-date).total_seconds() < -43200:issued+=timedelta(days=1)
    elif (issued-date).total_seconds()>43200:issued-=timedelta(days=1)
    result['firstIssued']=issued.isoformat()
  _detail_cache[url]=(time.monotonic(),result);return result

def table_section(html,identity):
 start=re.search(r'<table[^>]*id=["\']'+re.escape(identity)+r'["\'][^>]*>',html,re.I)
 if not start:return ''
 depth=1
 for tag in re.finditer(r'<(/?)table\b[^>]*>',html[start.end():],re.I):
  depth+=-1 if tag[1] else 1
  if depth==0:return html[start.start():start.end()+tag.end()]
 return ''

def event_identity_match(rows,origin,name,mag):
 import jma
 try:
  identities=set()
  for report in jma.get_index():
   if jma.minute(report.get('at'))!=jma.minute(origin) or report.get('anm')!=name:continue
   if mag is not None:
    try:
     if abs(float(report.get('mag'))-mag)>.6:continue
    except (ValueError,TypeError):continue
   found=re.search(r'^\d{14}_(\d{14})_',report.get('json',''))
   if found:identities.add(found[1])
  if len(identities)!=1:return None
  identity=next(iter(identities));matches=[r for r in rows if '/'+identity+'/' in r.get('url','')]
  return matches[0] if len(matches)==1 else None
 except (requests.RequestException,ValueError,TypeError):return None
