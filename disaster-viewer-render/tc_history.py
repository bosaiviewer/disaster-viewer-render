import csv,io,re,json,time,html
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
import cyclones as tc,storage
NAMES=json.loads((Path(__file__).parent/'data/typhoon_names.json').read_text(encoding='utf-8'))

def observations(q):
    for step in q.get('forecast',[]):
        if step.get('hours')==0 and step.get('time'):storage.put('tc-step',q['id']+'|'+step['time'],dict(step,storm=q['id'],name=q['name'],source=q['source']))
    storage.put('tc',q['source']+'|'+q['id'],q)

def xml_observations(raw,include_forecast=False):
    root=ET.fromstring(raw)
    if root.findtext('./{*}Control/{*}Status')!='通常':return []
    eid=root.findtext('./{*}Head/{*}EventID');issued=root.findtext('./{*}Head/{*}ReportDateTime');result=[]
    for row in root.findall('.//{*}MeteorologicalInfo'):
        dt=row.find('{*}DateTime')
        if dt is None or (dt.get('type')!='実況' and not include_forecast):continue
        coordinate=next((e.text for e in row.iter() if e.tag.split('}')[-1] in ('Coordinate','BasePoint') and e.get('type')=='中心位置（度）'),None)
        nums=re.findall(r'[+-]\d+(?:\.\d+)?',coordinate or '')
        point=tc.coords(nums[:2])
        if not point:continue
        fields=[]
        for el in row.iter():
            if len(el) or not ((el.text or '').strip() or el.get('description')):continue
            tag=el.tag.split('}')[-1]
            label=el.get('type') or {'Location':'存在地域','Name':'名称','NameKana':'カタカナ名','Number':'台風番号','DateTime':'実況時刻'}.get(tag,tag)
            text=el.get('description') or ((el.text or '').strip()+(' '+el.get('unit') if el.get('unit') else ''))
            if [label,text] not in fields:fields.append([label,text])
        target=root.findtext('./{*}Head/{*}TargetDateTime')
        hours=max(0,round((datetime.fromisoformat(dt.text)-datetime.fromisoformat(target)).total_seconds()/3600)) if target else 0
        result.append({'storm':eid,'time':dt.text,'issued':issued,'coords':point,'hours':hours if dt.get('type')!='実況' else 0,'isObservation':dt.get('type')=='実況','fields':simplify_fields(fields),'rawXML':True,'source':'気象庁XML'})
    return result

def simplify_fields(fields):
    """Prefer human-readable metric values over repeated XML type/unit variants."""
    result=[];areas=[];wind_kind=None
    for label,value in fields:
        if label in ('実況','Type','名称','カタカナ名','台風番号','中心位置（度）','中心位置（度分）'):continue
        if label in ('移動速度','最大風速','最大瞬間風速') and not any(x in value for x in ('キロ','メートル')):continue
        if label=='移動方向':value=value.replace(' １６方位漢字','').replace(' ８方位漢字','')
        if label=='風速':
            if 'メートル' in value:wind_kind='暴風域' if '２５メートル' in value or '25メートル' in value else '強風域'
            continue
        if label=='半径':
            if wind_kind and value=='なし':areas.append([wind_kind,'なし']);wind_kind=None
            if wind_kind and 'キロ' in value:areas.append([wind_kind,value]);wind_kind=None
            continue
        if label=='７０パーセント確率半径':
            if 'キロ' in value:result.append(['予報円の半径',value])
            continue
        if [label,value] not in result:result.append([label,value])
    return result+areas

_history_checked=0
def recent_xml():
    global _history_checked
    if time.monotonic()-_history_checked<300:return
    feed=ET.fromstring(tc.get('https://www.data.jma.go.jp/developer/xml/feed/extra_l.xml').content)
    urls=[e.get('href') for e in feed.findall('.//{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}link') if re.fullmatch(r'https://www\.data\.jma\.go\.jp/developer/xml/data/[\w]+_VPTW60_[\w]+\.xml',e.get('href',''))]
    def fetch(url):
        if storage.get('xml-done',url):return
        try:
            for row in xml_observations(tc.get(url).content):
                key=row['storm']+'|'+row['time'];old=storage.get('tc-step',key)
                if not old or old.get('rawXML'):storage.put('tc-step',key,row)
            storage.put('xml-done',url,True)
        except (TypeError,ValueError,ET.ParseError,tc.requests.RequestException):pass
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,urls))
    _history_checked=time.monotonic()

def history(eid):
    error=None
    try:recent_xml()
    except (TypeError,ValueError,ET.ParseError,tc.requests.RequestException):error='過去の公式XMLを取得できませんでした。保存済みの履歴です。'
    rows=sorted([s for s in storage.values('tc-step') if s['storm']==eid],key=lambda r:r.get('time',''),reverse=True)
    return {'items':rows,'error':error,'notice':'公開XMLの提供期間と、このアプリが保存した実況の範囲です。全発表が揃うとは限りません。'}

def bundled_depressions(year):
    path=Path(__file__).parent/'data'/f'td_{year}_original.json'
    return json.loads(path.read_text(encoding='utf-8')).get('items',[]) if path.exists() else []

def annual(year):
    key=str(year);cached=storage.get('annual',key)
    if cached and cached.get('schema')==7 and time.time()-cached.get('checked',0)<300:return cached
    storms={};notes=[];groups={}
    try:recent_xml()
    except (TypeError,ValueError,ET.ParseError,tc.requests.RequestException):notes.append('公開期間内の台風・熱帯低気圧XMLは取得できませんでした。')
    try:
        tracks=tc.get(tc.JMA+'pastTracks.json').json()
        for t in tracks:
            number=t.get('typhoonNumber') or '';number=number if re.fullmatch(r'\d{4}',number) else ''
            eid=t.get('tropicalCyclone') or ''
            if not (number.startswith(str(year)[-2:]) or (not number and eid.startswith('TC'+str(year)[-2:]))):continue
            route=[]
            for k,v in t.items():
                if k.startswith('track') and isinstance(v,dict):
                    for kind,points in v.items():
                        for point in points:
                            if tc.coords(point):route.append({'coords':point,'time':None,'fields':[['経路上の区分',{'preTyphoon':'台風になる前','typhoon':'台風','postTyphoon':'台風でなくなった後'}.get(kind,kind)]],'routeOnly':True})
            key=number or eid
            storms[key]={'id':eid,'name':f'台風{int(number[-2:])}号' if number else '熱帯低気圧（台風に発達しなかった・'+eid+'）','number':number,'source':'気象庁（年次履歴）','coords':route[-1]['coords'] if route else None,'track':[r['coords'] for r in route],'forecast':[],'history':route,'archive':True,'url':'https://www.jma.go.jp/bosai/map.html#contents=typhoon' if not number else f'https://www.data.jma.go.jp/typhoon/position_table/table{year}.html'}
    except (tc.requests.RequestException,ValueError):notes.append('年間経路の取得に失敗しました。')
    try:
        response=tc.get(f'https://www.data.jma.go.jp/typhoon/position_table/table{year}.csv')
        rows=list(csv.reader(io.StringIO(response.content.decode('cp932'))));groups={}
        for r in rows[1:]:
            if len(r)<18 or r[0]!=str(year):continue
            when=datetime(*map(int,r[:4]),tzinfo=timezone.utc).isoformat();number=r[4]
            grade={'2':'熱帯低気圧','3':'台風（TS）','4':'台風（STS）','5':'台風（TY）','6':'温帯低気圧','7':'域外の熱帯低気圧'}.get(r[6],r[6])
            fields=[['種別',grade],['中心気圧',r[9]+' hPa'],['最大風速','34 kt未満' if r[10]=='0' else r[10]+' kt'],['上陸・通過直前','該当' if r[17]=='1' else '記録なし']]
            for a,b,c,label in [(11,12,13,'暴風域（50kt）'),(14,15,16,'強風域（30kt）')]:fields.append([label,f'長径方向コード {r[a]} ／ 長半径 {r[b]}海里 ／ 短半径 {r[c]}海里'])
            groups.setdefault(number,[]).append({'time':when,'coords':tc.coords(r[7:9]),'fields':fields,'raw':dict(zip(rows[0],r))})
            if number not in storms:storms[number]={'id':'annual'+number,'number':number,'forecast':[],'track':[],'archive':True,'source':'気象庁（確定位置表）','url':f'https://www.data.jma.go.jp/typhoon/position_table/table{year}.html'}
            storms[number]['name']=f'台風{int(number[-2:])}号 '+r[5]+('（'+NAMES[r[5].upper()]+'）' if r[5].upper() in NAMES else '')
        for number,points in groups.items():storms[number].update(history=points,track=[s['coords'] for s in points if s['coords']],coords=points[-1]['coords'],time=points[-1]['time'],source='気象庁（確定位置表）')
    except (tc.requests.RequestException,ValueError,UnicodeError):notes.append('確定位置表は未取得です。')
    try:
        from typhoon_pdf import get as pdf_get
        page=tc.get(f'https://www.data.jma.go.jp/typhoon/position_table/table{year}.html').content.decode('utf-8')
        available=set(re.findall(r'\.\./data/T('+str(year)[-2:]+r'\d{2})\.pdf',page))
        missing=[number for number in storms if number in available and number not in groups]
        def read_pdf(number):
            try:return number,pdf_get(number,year)
            except (tc.requests.RequestException,ValueError):return number,None
        with ThreadPoolExecutor(max_workers=4) as pool:
            for number,report in pool.map(read_pdf,missing):
                if not report:notes.append(f'{int(number[-2:])}号の個別位置表は未取得です。');continue
                storm=storms[number];points=report['points'];storm.update(history=points,track=[p['coords'] for p in points],coords=points[-1]['coords'],time=points[-1]['time'],url=report['url'],source='気象庁（個別位置表）')
                name=report.get('name')
                if name:storm['name']=f'台風{int(number[-2:])}号 '+name+('（'+NAMES[name.upper()]+'）' if name.upper() in NAMES else '')
    except (tc.requests.RequestException,ValueError):notes.append('個別位置表の一覧を取得できませんでした。')
    for q in storage.values('tc'):
        if q.get('id') in storms and not q.get('number'):
            storms[q['id']].update(name=q['name'],time=q.get('time'),issued=q.get('issued'),category=q.get('category'),pressure=q.get('pressure'),wind=q.get('wind'),location=q.get('location'))
        elif q.get('number') in storms:
            storm=storms[q['number']];storm['name']=q['name'].replace('台風第','台風')
            if q.get('category') and (q.get('time') or '')>=(storm.get('time') or ''):
                for field in ('category','time','issued','forecast','pressure','wind','windUnit','location','coords','intensity','scale'): 
                    if field in q:storm[field]=q[field]
        elif (q.get('number') or '').startswith(str(year)[-2:]):storms[q['number']]=dict(q,archive=True,history=q.get('history',[]))
    for original in bundled_depressions(year):storms[original['id']]=dict(original)
    for q in storms.values():
        current=next((item for item in tc.cache.get('jma',{}).get('items',[]) if item['id']==q['id'] or q.get('number') and item.get('number')==q['number']),None)
        if current:
            for field in ('category','forecast','issued','time','coords','pressure','wind','windUnit','location','intensity','scale'):
                if field in current:q[field]=current[field]
        q['ongoing']=bool(current)
        tc.annotate_transition(q)
        detailed=[r for r in storage.values('tc-step') if r['storm']==q['id']]
        if detailed:
            old=q.get('history',[]);known={r.get('time') for r in old if r.get('time')}
            q['history']=[s for s in old if not(s.get('routeOnly') and any(r.get('coords')==s.get('coords') for r in detailed))]+[r for r in detailed if r.get('time') not in known]
            if not q.get('time'):q['time']=max((r['time'] for r in detailed if r.get('time')),default=None)
        if not q.get('number') and not q.get('time'):
            q['dataNotice']='気象庁の公開経路には時刻・気圧・風速がありません。発表時にこのアプリが保存した実況または公開期間内のXMLがある場合だけ詳細を表示します。'
    for q in storms.values():
        tc.annotate_transition(q)
        q['isTyphoon']=bool(re.fullmatch(r'\d{4}',q.get('number') or ''))
        q['historyGroup']='typhoon' if q['isTyphoon'] else 'developing' if q.get('ongoing') else 'undeveloped'
        entries=[r for r in q.get('history',[]) if not r.get('routeOnly')]
        q['historyCoverage']={'timed':sum(bool(r.get('time')) for r in entries),'routeOnly':sum(bool(r.get('routeOnly')) for r in q.get('history',[]))}
        if not q['isTyphoon']:q['archiveSearchUrl']='https://agora.ex.nii.ac.jp/cps/weather/typhoon/index.html.ja'
    result={'items':sorted(storms.values(),key=lambda q:q.get('number','') or q.get('id',''),reverse=True),'year':year,'checked':time.time(),'schema':7,
            'notice':'今年の気象庁の確定位置表・個別位置表・公開経路・保存した実況を表示します。台風に発達しなかった熱帯低気圧は公開経路にあるものを含めます。位置表未掲載の地点は時刻や強さを推測で補いません。個別PDFの速報値は後日修正される場合があります。 '+ ' '.join(notes)}
    if notes and cached:
        byid={q['id']:q for q in cached.get('items',[])};byid.update({q['id']:q for q in result['items']})
        result['items']=sorted(byid.values(),key=lambda q:q.get('number','') or q.get('id',''),reverse=True)
        result['error']=' '.join(notes)
    storage.put('annual',key,result);return result


