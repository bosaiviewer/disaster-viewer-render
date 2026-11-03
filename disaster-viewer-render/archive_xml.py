"""Original JMA XML archived by NII; no values reconstructed from news articles."""
import html,re,time,json,threading,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import requests

BASE='https://agora.ex.nii.ac.jp/cgi-bin/cps/'
SOURCE='気象庁防災情報XMLデータベース（国立情報学研究所）'
TSUNAMI_TYPES=('津波警報・注意報・予報a','津波警報・注意報・予報','津波情報a','津波情報','沖合の津波観測に関する情報')
ID_PATTERN=r'\d{14}_\d+_[A-Z0-9]+_\d+'
def get(url,params=None):
    response=requests.get(url,params=params,timeout=(5,35));response.raise_for_status()
    return response.content.decode('utf-8')
def index_ids(page):
    ids=list(dict.fromkeys(re.findall(r'report_each\.pl\?id=('+ID_PATTERN+r')',html.unescape(page))))
    match=re.search(r'全\s*([\d,]+)\s*件中',page)
    if not match:raise ValueError('Archive index has no total')
    expected=int(match[1].replace(',',''))
    if len(ids)!=expected:raise ValueError(f'Incomplete archive index: {len(ids)}/{expected}')
    return ids
def extract_xml(page):
    match=re.search(r'<pre[^>]*>(.*?)</pre>',page,re.S|re.I)
    raw=html.unescape(match[1]) if match else page
    root=ET.fromstring(raw)
    if root.tag.split('}')[-1]!='Report':raise ValueError('Not a JMA report')
    return raw
def document(raw):
    def convert(node):
        children=list(node)
        if not children:
            text=(node.text or '').strip()
            if node.tag.split('}')[-1] in ('TsunamiHeight','Magnitude') and node.attrib:
                return dict(node.attrib,value=text)
            return text
        result={}
        for child in children:
            key=child.tag.split('}')[-1];value=convert(child)
            if key in result:
                if not isinstance(result[key],list):result[key]=[result[key]]
                result[key].append(value)
            else:result[key]=value
        return result
    return convert(ET.fromstring(raw))
def tsunami_report(raw,xml_id):
    from hazards import parse_tsunami
    doc=document(raw);result=parse_tsunami(doc)
    result.update(id='nii-'+xml_id,xmlId=xml_id,eventId=doc.get('Head',{}).get('EventID'),
                  archiveSource='nii',source=SOURCE,url=BASE+'report_xml.pl?id='+xml_id)
    return result
def fetch_report(xml_id):
    if not re.fullmatch(ID_PATTERN,xml_id):raise ValueError('Invalid XML id')
    return extract_xml(get(BASE+'report_xml.pl',{'id':xml_id}))
def list_tsunami(year):
    ids=[];counts={}
    for kind in TSUNAMI_TYPES:
        params={'type':kind,'year':year};page=get(BASE+'report_list.pl',params)
        match=re.search(r'全\s*([\d,]+)\s*件中',page)
        if not match:raise ValueError('Missing archive total')
        expected=int(match[1].replace(',',''))
        pages=[page]+[get(BASE+'report_list.pl',dict(params,page=n)) for n in range(2,math.ceil(expected/100)+1)]
        batch=list(dict.fromkeys(re.findall(r'report_each\.pl\?id=('+ID_PATTERN+r')',html.unescape(''.join(pages)))))
        if len(batch)!=expected:raise ValueError('Incomplete archive pagination')
        ids.extend(batch);counts[kind]=len(batch)
    return sorted(set(ids)),counts

_lock=threading.Lock();_running=set()
def start_tsunami_sync(year):
    """Refresh the source index at most daily; never block the current-status API."""
    import storage
    with _lock:
        state=storage.get('xml-archive-state',str(year),{})
        included=bundled(year).get('manifest',{})
        if included.get('completeIndex') and time.time()-included.get('checked',0)<86400:return
        if year in _running or time.time()-state.get('attempt',0)<86400:return
        _running.add(year)
    def worker():
        state=dict(attempt=time.time(),running=True,source=SOURCE)
        storage.put('xml-archive-state',str(year),state)
        try:
            ids,counts=list_tsunami(year);included_reports={r.get('xmlId'):r for r in bundled(year).get('reports',[])}
            state.update(expected=len(ids),counts=counts,xmlIds=ids)
            def fetch(xml_id):
                old=storage.get('tsunami-original',xml_id)
                if old:return True
                try:
                    report=included_reports.get(xml_id) or tsunami_report(fetch_report(xml_id),xml_id)
                    storage.put('tsunami-original',xml_id,report);return True
                except (requests.RequestException,ValueError,ET.ParseError,TypeError):return False
            with ThreadPoolExecutor(max_workers=3) as pool:done=sum(pool.map(fetch,ids))
            cross_events={r.get('eventId') for r in storage.values('tsunami-original') if r.get('xmlId') in ids and r.get('eventId') and r['eventId'][:4].isdigit() and int(r['eventId'][:4])<year}
            for event in cross_events:
                page=get(BASE+'event_list.pl',{'eventid':event})
                more=set(re.findall(r'report_each\.pl\?id=('+ID_PATTERN+r')',html.unescape(page)))
                for xml_id in sorted(more):
                    if re.search(r'_VTSE(?:41|51|52)_',xml_id) and xml_id not in ids:
                        ids.append(xml_id);done+=bool(fetch(xml_id))
            state.update(expected=len(ids),xmlIds=ids)
            state.update(fetched=done,completeIndex=done==len(ids),checked=time.time(),error=None if done==len(ids) else '一部の原文を取得できませんでした。')
        except (requests.RequestException,ValueError,ET.ParseError,TypeError):state.update(error='原文アーカイブの一覧を取得できませんでした。',completeIndex=False)
        finally:
            state['running']=False;storage.put('xml-archive-state',str(year),state)
            with _lock:_running.discard(year)
    threading.Thread(target=worker,daemon=True).start()
def bundled(year):
    path=Path(__file__).parent/'data'/f'tsunami_{year}_original.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'reports':[],'manifest':{}}
