"""Read-only official JMA/NHC and GDACS tropical cyclone feeds, cached 5 min."""
import math,re,time,io,zipfile
from datetime import datetime,timezone
from threading import Lock
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests

JMA='https://www.jma.go.jp/bosai/typhoon/data/'
URLS={'jma':JMA+'targetTc.json','nhc':'https://www.nhc.noaa.gov/CurrentStorms.json','gdacs':'https://www.gdacs.org/xml/rss.xml'}
cache={};locks={k:Lock() for k in URLS}

def get(url):
    r=requests.get(url,timeout=(4,16));r.raise_for_status();return r

def coords(value):
    try:
        a,b=map(float,value)
        return [a,b] if math.isfinite(a) and math.isfinite(b) and -90<=a<=90 and -180<=b<=180 else None
    except (TypeError,ValueError):return None

def safe_url(value):
    return value if isinstance(value,str) and urlparse(value).scheme=='https' else None

def annotate_transition(q):
    """Only numbered former typhoons; an unnumbered developing depression is not a transition."""
    number=str(q.get('number') or '')
    category=q.get('category') or ''
    if not category:
        observations=[row for row in q.get('history',[]) if row.get('time') and not row.get('routeOnly')]
        latest=max(observations,key=lambda row:row['time'],default={})
        category=next((str(value) for key,value in latest.get('fields',[]) if key in ('種別','種類','熱帯擾乱種類','階級')), '')
    category=category.get('jp','') if isinstance(category,dict) else str(category)
    q['transitionTo']=next((kind for kind in ('温帯低気圧','熱帯低気圧') if kind in category),'') if re.fullmatch(r'\d{4}',number) else ''
    q['transitionMessage']=f"台風{int(number[-2:])}号は{q['transitionTo']}に変わりました。" if q['transitionTo'] else ''
    if q['transitionTo']:q['ongoing']=False
    return q

def parse_jma(target,forecast,spec):
    title=next((r for r in spec if r.get('part')=='title'),{})
    analysis=next((r for r in spec if r.get('advancedHours')==0),{})
    steps=[]
    for row in forecast:
        if not isinstance(row.get('advancedHours'),(int,float)):continue
        point=coords(row.get('center'))
        if not point:continue
        hours=row['advancedHours'];detail=next((r for r in spec if r.get('advancedHours')==hours),{})
        radius=(row.get('probabilityCircle') or {}).get('radius')
        steps.append({'hours':hours,'coords':point,'time':row.get('validtime',{}).get('JST'),
                      'radius':radius if isinstance(radius,(int,float)) and radius>0 else None,
                      'pressure':detail.get('pressure'),'wind':detail.get('maximumWind',{}).get('sustained',{}).get('m/s'),
                      'raw':detail,'geometry':row})
    observed=next((r for r in forecast if r.get('advancedHours')==0),{})
    track=observed.get('track') or {}
    number=target.get('typhoonNumber','');jp=title.get('name',{}).get('jp','');en=title.get('name',{}).get('en','').upper();name=en+('（'+jp+'）' if jp else '')
    label=f'台風{int(number[-2:])}号' if re.fullmatch(r'\d{4}',number) else '熱帯低気圧'+number.lower() if re.fullmatch(r'[a-zA-Z]',number) else '熱帯低気圧（識別記号未提供）'
    return annotate_transition({'id':target['tropicalCyclone'],'number':number,'name':label+(' '+name if name else ''),'source':'気象庁',
            'coords':coords(observed.get('center')) or coords(analysis.get('position',{}).get('deg')),
            'issued':title.get('issue',{}).get('JST') or target.get('issue'),'time':analysis.get('validtime',{}).get('JST'),
            'category':analysis.get('category',{}).get('jp',''),'intensity':analysis.get('intensity',''),'scale':analysis.get('scale',''),
            'hourlyUpdate':any(r.get('advancedHours')==1 for r in forecast),
            'pressure':analysis.get('pressure'),'wind':analysis.get('maximumWind',{}).get('sustained',{}).get('m/s'),'windUnit':'m/s',
            'location':analysis.get('location',''),'track':[c for v in track.values() if isinstance(v,list) for x in v if (c:=coords(x))],
            'forecast':sorted(steps,key=lambda r:r['hours']),'url':'https://www.jma.go.jp/bosai/map.html#contents=typhoon&typhoon='+target['tropicalCyclone'],
            'positionLabel':'実況の中心位置'})

def parse_nhc(document):
    if not isinstance(document.get('activeStorms'),list):raise ValueError('Invalid NHC feed')
    result=[]
    for s in document['activeStorms']:
        result.append({'id':s['id'],'name':s.get('name') or s['id'],'source':'NOAA / NHC',
            'coords':coords([s.get('latitudeNumeric',s.get('latitude_numeric')),s.get('longitudeNumeric',s.get('longitude_numeric'))]),
            'time':s.get('lastUpdate'),'issued':s.get('lastUpdate'),'category':{'HU':'ハリケーン','TS':'熱帯暴風雨','TD':'熱帯低気圧','SS':'亜熱帯暴風雨','SD':'亜熱帯低気圧'}.get(s.get('classification'),s.get('classification','')),
            'pressure':s.get('pressure'),'wind':s.get('intensity'),'windUnit':'kt（ノット）','movementDir':s.get('movementDir'),'movementSpeed':s.get('movementSpeed'),'forecast':[],'track':[],
            'advisoryNumber':s.get('publicAdvisory',{}).get('advNum'),'links':{label:url for label,key in [('公式の概況','publicAdvisory'),('予報の詳細','forecastAdvisory'),('予報の解説','forecastDiscussion'),('予報図','forecastGraphics'),('暴風域の見通し','windSpeedProbabilities')] if (url:=safe_url((s.get(key) or {}).get('url')))},
            'url':safe_url(s.get('publicAdvisory',{}).get('url')) or 'https://www.nhc.noaa.gov/',
            'positionLabel':'配信時点の中心位置'})
    return result

def nhc_routes(items):
    """Read the official active KMZ links; missing GIS products leave the bulletin intact."""
    root=ET.fromstring(get('https://www.nhc.noaa.gov/gis/kml/nhc_active.kml').content)
    ns={'k':'http://www.opengis.net/kml/2.2'}
    links={}
    for node in root.findall('.//k:NetworkLink',ns):
        label=node.findtext('k:name',default='',namespaces=ns)
        url=safe_url(node.findtext('k:Link/k:href',default='',namespaces=ns))
        if url and url.startswith('https://www.nhc.noaa.gov/') and label in ('Track Forecast','Past Track'):
            match=re.search(r'([a-z]{2}\d{6})',url,re.I)
            if match:links.setdefault(match.group(1).lower(),{})[label]=url
    for item in items:
        storm=links.get(str(item['id']).lower(),{})
        for label,key in [('Track Forecast','forecast'),('Past Track','track')]:
            url=storm.get(label)
            if not url:continue
            try:
                payload=get(url).content
                if len(payload)>2_000_000:continue
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    name=next(n for n in archive.namelist() if n.lower().endswith('.kml'))
                    source=ET.fromstring(archive.read(name))
                lines=[]
                for node in source.findall('.//k:LineString/k:coordinates',ns):
                    route=[]
                    for triple in (node.text or '').split():
                        a=triple.split(',')
                        if len(a)>=2 and (point:=coords([a[1],a[0]])):route.append(point)
                    if len(route)>1:lines.append(route)
                if lines:
                    route=max(lines,key=len)
                    if key=='forecast':item['forecast']=[{'coords':p,'hours':None,'time':None,'routeOnly':True} for i,p in enumerate(route)]
                    else:item['track']=route
                    item.setdefault('routeSources',{})[key]=url
            except (requests.RequestException,ValueError,KeyError,StopIteration,ET.ParseError,zipfile.BadZipFile):pass

def gdacs_routes(items):
    for item in items:
        if not re.fullmatch(r'\d+',str(item['id'])):continue
        url='https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype=TC&eventid='+str(item['id'])+'&episodeid='+str(item['episode'])
        try:
            features=get(url).json().get('features',[])
            segments=[]
            for feature in features:
                geometry=feature.get('geometry') or {}
                if geometry.get('type')!='LineString':continue
                points=[]
                for p in geometry.get('coordinates',[]):
                    if len(p)>=2 and (point:=coords([p[1],p[0]])):points.append(point)
                if len(points)>1:segments.append(points)
            if segments:item['routeSegments']=segments;item['routeSources']={'route':url}
        except (requests.RequestException,ValueError,TypeError,AttributeError):pass

def parse_gdacs(xml):
    ns={'g':'http://www.gdacs.org','geo':'http://www.w3.org/2003/01/geo/wgs84_pos#'}
    root=ET.fromstring(xml)
    if root.tag!='rss':raise ValueError('Invalid GDACS feed')
    rows={}
    for s in root.findall('./channel/item'):
        text=lambda key:s.findtext(key,default='',namespaces=ns)
        if text('g:eventtype')!='TC':continue
        eid=text('g:eventid');version=int(text('g:episodeid') or 0)
        if eid in rows and rows[eid]['version']>=version:continue
        rows[eid]={'id':eid,'episode':version,'version':version,'name':text('g:eventname'),'source':'GDACS（EC-JRC / 国連）',
            'coords':coords([text('geo:Point/geo:lat'),text('geo:Point/geo:long')]),
            'time':text('g:todate'),'issued':text('g:datemodified') or text('pubDate'),
            'category':'熱帯低気圧の報告','location':text('g:country'),
            'description':text('description'),'severity':text('g:severity'),'population':text('g:population'),'alertLevel':text('g:alertlevel'),'isCurrent':text('g:iscurrent')=='true','periodStart':text('g:fromdate'),'periodEnd':text('g:todate'),
            'url':safe_url(text('link')) or 'https://www.gdacs.org/','forecast':[],'track':[],
            'positionLabel':'報告位置（現在の中心位置とは限りません）'}
    return list(rows.values())

def listing(source):
    if source in ('jtwc','fiji'):
        import international_cyclones
        return international_cyclones.listing(source)
    if source not in URLS:raise ValueError('Unknown source')
    with locks[source]:
        previous=cache.get(source,{})
        if time.monotonic()-previous.get('attempt',-1000)<300:return previous
        result=dict(previous,attempt=time.monotonic(),error=None,stale=False)
        try:
            response=get(URLS[source])
            if source=='jma':
                targets=response.json()
                if not isinstance(targets,list):raise ValueError('Invalid JMA feed')
                items=[]
                for target in targets:
                    tc=target.get('tropicalCyclone','')
                    if not re.fullmatch(r'TC\d+',tc):raise ValueError('Invalid cyclone id')
                    items.append(parse_jma(target,get(JMA+tc+'/forecast.json').json(),get(JMA+tc+'/specifications.json').json()))
            elif source=='nhc':
                items=parse_nhc(response.json())
                try:nhc_routes(items)
                except (requests.RequestException,ET.ParseError,ValueError,TypeError):pass
            else:
                items=parse_gdacs(response.content)
                gdacs_routes(items)
            import tc_history
            for item in items:
                item['history']=[{'coords':p,'time':None,'routeOnly':True} for p in item.get('track',[]) if p!=item.get('coords')]
                tc_history.observations(item)
            result.update(items=items,lastSuccess=datetime.now(timezone.utc).isoformat())
        except (requests.RequestException,ValueError,KeyError,TypeError,AttributeError,ET.ParseError):
            result.update(error='情報を取得できませんでした。取得済みの情報がある場合は、古い内容を保持しています。',stale=True)
            result.setdefault('items',[])
        cache[source]=result
        return result
