"""Official volcano observations and current/archived tsunami bulletins."""
import re,html,time,calendar,json
from pathlib import Path
from datetime import datetime,timedelta
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
import cyclones as net,storage

BASE='https://www.jma.go.jp/bosai/'
VOL='https://www.data.jma.go.jp/vois/data/report/volinfo/'
CAM='https://www.data.jma.go.jp/vois/data/obs/volcam/'
_cache={}
def cached(key,loader,ttl=300):
    old=_cache.get(key)
    if old and time.monotonic()-old[0]<ttl:return old[1]
    try:result=loader();result.update(lastSuccess=storage.now().isoformat(),error=None);storage.put('hazard-cache',key,result)
    except (net.requests.RequestException,ValueError,TypeError,KeyError,ET.ParseError):
        result=dict(storage.get('hazard-cache',key,{}),error='取得に失敗しました。保存済み情報がある場合は古い内容です。最新状態は公式サイトで確認してください。',stale=True)
    _cache[key]=(time.monotonic(),result);return result

def volcanoes():
    def load():
        points=net.get(BASE+'volcano/const/volcano_list.json').json();warnings=net.get(BASE+'volcano/data/warning.json').json();byid={w['eventId']:w for w in warnings}
        camera_page=net.get(CAM+'volcam.php').content.decode('utf-8')
        cameras=[{'id':m[0],'name':html.unescape(re.sub('<[^>]+>','',m[1]))} for m in re.findall(r"href=['\"]\./volcam.php\?VC=(\d+)['\"][^>]*>(.*?)</a>",camera_page,re.I|re.S)]
        def local_forecast(point):
            code=point['code'];saved=storage.get('volcano-forecast',code)
            if saved and time.time()-saved.get('checked',0)<3600:return saved['label']
            try:
                page=net.get('https://www.data.jma.go.jp/vois/data/report/activity_info/'+code+'.html').content.decode('utf-8')
                match=re.search(r'class=["\']level-keyword[^"\']*["\'][^>]*>\s*<strong>(.*?)</strong>',page,re.I|re.S)
                label=html.unescape(re.sub('<[^>]+>','',match[1])).strip() if match else None
                if label:storage.put('volcano-forecast',code,{'label':label,'checked':time.time()})
                return label
            except net.requests.RequestException:return saved['label'] if saved else None
        forecast={}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for point,label in zip(points,pool.map(local_forecast,[p for p in points])):forecast[point['code']]=label
        result=[]
        for p in points:
            if p['name_jp'] in ('その他の活火山','新たな活火山'):continue
            warning=byid.get(p['code'],{});info=next((v for v in warning.get('volcanoInfos',[]) if v['type']=='噴火警報・予報（対象火山）'),{})
            names=[v['name'] for v in info.get('items',[])];label=' / '.join(names) or forecast.get(p['code']) or '噴火警報・予報を確認できません'
            level=re.search(r'レベル([1-5１-５])',label)
            result.append({'id':p['code'],'name':p['name_jp'],'coords':net.coords(p.get('latlon')),'level':int(level[1]) if level else None,'warning':label,'issued':warning.get('reportDatetime'),'raw':warning,'cameras':[c for c in cameras if c['id'].startswith(p['code'])], 'url':VOL+'volinfo.php?id='+p['code']+'&info=ALL'})
        return {'items':result}
    return cached('volcanoes',load)

def one_month_ago():
    n=storage.now();month=n.month-1;year=n.year
    if month<=0:month+=12;year-=1
    return n.replace(year=year,month=month,day=min(n.day,calendar.monthrange(year,month)[1]))

def volcano_history(code):
    if not re.fullmatch(r'\d{3}',code):raise ValueError('Invalid volcano')
    def load():
        page=net.get(VOL+'volinfo.php?id='+code+'&info=VG').content.decode('utf-8')
        items=[];cut=one_month_ago()
        for filename,stamp,title in re.findall(r'href=["\']\./(VG(\d{14})_\d+\.html)["\'][^>]*>(.*?)</a>',page,re.I|re.S):
            dt=datetime.strptime(stamp,'%Y%m%d%H%M%S').replace(tzinfo=storage.JST)
            if cut<=dt<=storage.now():items.append({'id':filename,'time':dt.isoformat(),'name':html.unescape(re.sub('<[^>]+>','',title)),'url':VOL+filename})
        return {'items':sorted(items,key=lambda x:x['time'],reverse=True),'since':cut.isoformat(),'notice':'気象庁の公開一覧に掲載された噴火・爆発等の火山観測報（過去1か月）です。'}
    return cached('vol-history-month42-'+code,load,600)

def volcano_report(filename):
    if not re.fullmatch(r'VG\d{14}_\d{3}\.html',filename):raise ValueError('Invalid report')
    def load():
        page=net.get(VOL+filename).content.decode('utf-8');match=re.search(r'<pre[^>]*>(.*?)</pre>',page,re.I|re.S)
        return {'text':html.unescape(re.sub('<[^>]+>','',match[1] if match else '原文の本文を抽出できませんでした。公式リンクを確認してください。')),'url':VOL+filename}
    return cached(filename,load,86400)

def cameras(code):
    if not re.fullmatch(r'\d{5}',code):raise ValueError('Invalid camera')
    def load():
        text=net.get(CAM+'volcam.php?VC='+code).content.decode('utf-8')
        files=re.findall(r"file_array(?:\[.*?\])?\s*(?:=|\.push\()\s*['\"]([^'\"]+)['\"]",text)
        return {'frames':[urljoin(CAM,f) for f in files if re.search(r'\.(jpg|png|gif)$',f,re.I)],'url':CAM+'volcam.php?VC='+code,
                'notice':'公開されているカメラ画像のコマ送りです。過去の噴火報の時刻の映像が残っているとは限りません。雲・夜間・欠測で火口が見えない場合があります。'}
    return cached('camera-'+code,load,60)

def parse_tsunami(doc):
    if doc.get('Control',{}).get('Status')!='通常':raise ValueError('Not operational')
    head=doc.get('Head',{});body=doc.get('Body',{});rows=body.get('Tsunami',{}).get('Forecast',{}).get('Item',[])
    if isinstance(rows,dict):rows=[rows]
    areas=[{'name':r.get('Area',{}).get('Name'),'code':r.get('Area',{}).get('Code'),'kind':r.get('Category',{}).get('Kind',{}).get('Name'),'height':r.get('MaxHeight',{}).get('TsunamiHeight'),'raw':r} for r in rows]
    if head.get('InfoType')=='取消':
        for area in areas:area['kind']='取消'
    observation=body.get('Tsunami',{}).get('Observation',{})
    return {'id':head.get('EventID','')+'|'+head.get('ReportDateTime',''),'time':head.get('ReportDateTime'),'validUntil':head.get('ValidDateTime'),'title':head.get('Title'),'infoType':head.get('InfoType'),'text':head.get('Headline',{}).get('Text'),'areas':areas,'observations':observation,'earthquakes':body.get('Earthquake'), 'raw':body}

def bundled_tsunami_history(year):
    """Use only complete original XML records; never merge article reconstructions."""
    from archive_xml import bundled
    return bundled(year).get('reports',[])

def tsunami():
    def load():
        listings=net.get(BASE+'tsunami/data/list.json').json();clear=net.get(BASE+'tsunami/data/clearweb.json').json()
        if not isinstance(listings,list) or not all(k in clear for k in ['w','f']):raise ValueError('Invalid current status')
        def fetch(row):
            filename=row.get('json','')
            if not re.fullmatch(r'[\w]+\.json',filename) or '_K' in row.get('ift',''):return None
            doc=storage.get('tsu-doc',filename)
            if not doc:
                doc=net.get(BASE+'tsunami/data/'+filename).json();storage.put('tsu-doc',filename,doc)
            result=parse_tsunami(doc);result['eventId']=doc.get('Head',{}).get('EventID');result['id']=filename;result['url']=BASE+'tsunami/data/'+filename;storage.put('tsunami',filename,result)
            kind='f' if row.get('ttl') in ['津波情報','沖合の津波観測に関する情報'] else 'w'
            issued=datetime.fromisoformat(row['rdt']);limit=datetime.fromisoformat(clear[kind]);limit=limit.replace(tzinfo=storage.JST) if not limit.tzinfo else limit
            valid=result.get('validUntil');active=issued>limit and (not valid or datetime.fromisoformat(valid)>storage.now())
            return dict(result,active=active)
        with ThreadPoolExecutor(max_workers=4) as pool:rows=[x for x in pool.map(fetch,listings) if x]
        current=[r for r in rows if r['active']];current.sort(key=lambda r:r['time'],reverse=True)
        # Observational updates must not erase a warning issued earlier.
        seen=set();active=[]
        for r in current:
            event=r.get('eventId')
            if (r['areas'] or r.get('infoType')=='取消') and event not in seen:active.append(r);seen.add(event)
        observations=[r for r in current if not r['areas'] and r.get('infoType')!='取消']
        kinds={a['kind'] for r in active for a in r['areas'] if a['kind']}
        priority=['大津波警報','津波警報','津波注意報','津波予報（若干の海面変動）']
        status=next((k for k in priority if k in kinds),'発表なし')
        if status=='発表なし' and any(k not in ['取消','津波なし','津波予報（津波なし）'] and '解除' not in k for k in kinds):
            status='発表状況を判定できません。原文を確認してください'
        year=storage.now().year
        combined=[r for r in bundled_tsunami_history(year) if r.get('time') and datetime.fromisoformat(r['time'])<=storage.now()]+[r for r in storage.values('tsunami') if (r.get('time') or '').startswith(str(year))]
        # A JMA original and a P2P relay of the same bulletin can differ by seconds.
        history=[]
        original_keys={(r.get('eventId'),r.get('time'),r.get('title')) for r in combined if r.get('archiveSource')=='nii'}
        for r in sorted(combined,key=lambda x:x.get('time') or '',reverse=True):
            if r.get('archiveSource')!='nii' and (r.get('eventId'),r.get('time'),r.get('title')) in original_keys:continue
            if not any(x['id']==r['id'] for x in history):history.append(r)
        return {'status':status,'current':sorted(active+observations,key=lambda r:r['time'],reverse=True),'history':history,'year':year,'notice':'現在状態は気象庁の掲載終了情報と有効期限を確認しています。履歴は気象庁XML原文を使用し、予報・解除・満潮や到達予想・沿岸観測・沖合観測を同じ原文アーカイブから取得しています。'}
    result=dict(cached('tsunami',load,60))
    result['year']=storage.now().year
    result.setdefault('status','発表状況を確認できません')
    result.setdefault('current',[])
    # Keep complete episodes in the year of their last recorded bulletin, even
    # when their first warning was issued in the preceding year.
    all_rows={r['id']:r for r in result.get('history',[]) if r.get('id') and r.get('time') and not r['id'].startswith(('p2p-','archive-observation-'))}
    for r in storage.values('tsunami'):
        if r.get('id') and r.get('time'):all_rows[r['id']]=r
    for archive_year in (result['year']-1,result['year']):
        for r in bundled_tsunami_history(archive_year):
            if r.get('id') and r.get('time') and datetime.fromisoformat(r['time'])<=storage.now():
                all_rows.setdefault(r['id'],r)
    from archive_xml import bundled,SOURCE
    for r in storage.values('tsunami-original'):
        if r.get('id') and r.get('time') and datetime.fromisoformat(r['time'])<=storage.now():all_rows[r['id']]=r
    original_keys={(r.get('eventId'),r.get('time'),r.get('title')) for r in all_rows.values() if r.get('archiveSource')=='nii'}
    all_rows={key:r for key,r in all_rows.items() if r.get('archiveSource')=='nii' or (r.get('eventId'),r.get('time'),r.get('title')) not in original_keys}
    included=bundled(result['year']).get('manifest',{})
    state=storage.get('xml-archive-state',str(result['year']),{})
    result['archive']=dict(included,**{k:v for k,v in state.items() if k!='source'},source=SOURCE)
    groups={}
    for r in all_rows.values():
        event=r.get('eventId') or r.get('id','').split('|')[0]
        if event:groups.setdefault(str(event),[]).append(r)
    episodes=[]
    for event,reports in groups.items():
        # A forecast may end at its published ValidDateTime without a separate
        # cancellation bulletin. Label that as an expiry, never as a JMA release.
        latest=max(reports,key=lambda r:r.get('time') or '')
        latest_forecast=next((r for r in sorted(reports,key=lambda x:x.get('time') or '',reverse=True)
                              if r.get('validUntil') and r.get('areas') and
                              all('海面変動' in (a.get('kind') or '') for a in r['areas'])),None)
        expiry=latest_forecast.get('validUntil') if latest_forecast else None
        superseded=bool(latest_forecast and any(
            (r.get('time') or '')>(latest_forecast.get('time') or '') and
            (r.get('infoType')=='取消' or
             ('解除' in (r.get('title') or '') and not r.get('areas')) or
             (r.get('areas') and not all('海面変動' in (a.get('kind') or '') for a in r['areas'])))
            for r in reports))
        if (expiry and latest_forecast and not superseded and expiry>(latest.get('time') or '') and
                datetime.fromisoformat(expiry)<=storage.now()):
            reports.append({'id':event+'|valid-until','eventId':event,'time':expiry,
                            'title':'津波予報（若干の海面変動）の有効期間終了',
                            'text':'発表電文に記された有効期間が終了しました。別途「解除」の電文を確認したという意味ではありません。',
                            'areas':[],'earthquakes':latest_forecast.get('earthquakes'),
                            'derivedExpiry':True,'url':latest_forecast.get('url')})

        ordered=sorted(reports,key=lambda r:r.get('time') or '')
        if not ordered or not (ordered[-1].get('time') or '').startswith(str(result['year'])):continue
        effective_areas=[];effective_quakes=[];enriched=[];seen=set()
        for report in ordered:
            key=report.get('id')
            if key in seen:continue
            seen.add(key)
            entry=dict(report)
            if report.get('areas'):
                if '_VTSE51_' in report.get('xmlId','') and effective_areas:
                    additions={str(a.get('code')):a for a in report['areas']}
                    effective_areas=[dict(a,**additions.get(str(a.get('code')),{})) for a in effective_areas]
                    entry['areas']=effective_areas
                else:effective_areas=report['areas']
            elif report.get('infoType')=='取消' or '解除' in (report.get('title') or ''):effective_areas=[]
            elif report.get('observationsList') or report.get('observations'):
                entry['areas']=effective_areas
                entry['observationReport']=True
            if report.get('earthquakes'):effective_quakes=report['earthquakes']
            elif effective_quakes:entry['earthquakes']=effective_quakes
            enriched.append(entry)
        if enriched:episodes.append({'id':event,'latest':next((r for r in reversed(enriched) if r.get('areas') or r.get('derivedExpiry') or '解除' in (r.get('title') or '') or r.get('infoType')=='取消'),enriched[-1]),
                                     'reports':list(reversed(enriched)),
                                     'start':enriched[0].get('time'),
                                     'end':enriched[-1].get('time')})
    episodes.sort(key=lambda e:e['end'] or '',reverse=True)
    result['episodes']=episodes
    result['history']=[r for e in episodes for r in e['reports']]
    return result


def parse_level_report51(raw):
 import unicodedata
 text=html.unescape(re.sub('<[^>]+>','',re.search(r'<pre[^>]*>(.*?)</pre>',raw,re.I|re.S)[1] if re.search(r'<pre[^>]*>(.*?)</pre>',raw,re.I|re.S) else raw))
 clean=unicodedata.normalize('NFKC',text);head=re.sub(r'\s+','',clean.split('**(本')[0])
 new=re.search(r'噴火警戒レベル\s*([1-5])',head)
 change=re.search(r'レベル(?:を)?\s*([1-5])[^\n]{0,22}?から\s*(?:レベル)?\s*([1-5])',head)
 return {'level':int(change[2]) if change else int(new[1]) if new else None,'previousLevel':int(change[1]) if change else None,'direction':'引き上げ' if re.search(r'引[き]?上げ|引上げ',head) else '引き下げ' if re.search(r'引[き]?下げ|引下げ',head) else '発表','text':text.strip()}

def volcano_level_history51(code):
 if not re.fullmatch(r'\d{3}',code):raise ValueError('Invalid volcano')
 def load():
  page=net.get(VOL+'volinfo.php?id='+code+'&info=VJ').content.decode('utf-8');cut=one_month_ago();rows=[]
  if '火山に関する情報の発表状況' not in page and 'VJ' not in page:raise ValueError('Invalid volcano history page')
  for file,stamp,title in re.findall(r'href=["\']\./(VJ(\d{14})_\d{3}\.html)["\'][^>]*>(.*?)</a>',page,re.I|re.S):
   if not file.endswith('_'+code+'.html'):continue
   at=datetime.strptime(stamp,'%Y%m%d%H%M%S').replace(tzinfo=storage.JST)
   if cut<=at<=storage.now():rows.append({'id':file,'time':at.isoformat(),'title':html.unescape(re.sub('<[^>]+>','',title)),'source':VOL+file})
  def detail(row):
   body=net.get(row['source']).content.decode('utf-8');return dict(row,**parse_level_report51(body))
  with ThreadPoolExecutor(max_workers=3) as pool:items=list(pool.map(detail,rows))
  return {'items':sorted(items,key=lambda x:x['time'],reverse=True),'since':cut.isoformat(),'source':VOL+'volinfo.php?id='+code+'&info=VJ','notice':'気象庁の公開一覧に掲載された過去1か月の噴火警報・予報です。引き上げ・引き下げが原文に明記された場合はその内容を表示し、同じレベルの更新も区別します。'}
 return cached('volcano-level51-'+code,load,900)
