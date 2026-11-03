"""USGS catalog and all publicly returned product versions."""
from datetime import datetime,timezone,timedelta
from threading import Lock
from urllib.parse import urlparse
import math,re,time
import requests

API='https://earthquake.usgs.gov/fdsnws/event/1/query'
JST=timezone(timedelta(hours=9))
lock=Lock()
cache={'items':[],'lastSuccess':None,'error':None}
attempt=-1000
details={}

def numeric(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError):return None

def date(value):
    try:return datetime.fromtimestamp(float(value)/1000,JST).strftime('%Y/%m/%d %H:%M:%S')
    except (ValueError,TypeError,OverflowError,OSError):return '不明'

def safe_url(value):
    return value if isinstance(value,str) and urlparse(value).scheme=='https' and urlparse(value).netloc else None

def normalize(feature):
    p=feature.get('properties') or {};c=(feature.get('geometry') or {}).get('coordinates') or []
    lat=numeric(c[1]) if len(c)>1 else None;lon=numeric(c[0]) if c else None
    depth=numeric(c[2]) if len(c)>2 else None;mag=numeric(p.get('mag'))
    return {'id':str(feature['id']),'reportId':str(feature['id']),'provider':'usgs',
        'name':p.get('place') or 'Location not provided','time':date(p.get('time')),
        'issued':date(p.get('updated')),'updated':p.get('updated'),
        'coords':[lat,lon] if lat is not None and lon is not None and -90<=lat<=90 and -180<=lon<=180 else None,
        'magnitude':f'{mag:.1f}' if mag is not None else '不明','magValue':mag,
        'depth':f'{depth:.1f} km' if depth is not None else '不明','magType':p.get('magType') or '不明',
        'type':'USGS '+{'earthquake':'地震','explosion':'爆発','quarry blast':'採石場の発破','nuclear explosion':'核爆発','ice quake':'氷震','rock burst':'山はね','mining explosion':'鉱山の爆発','other event':'その他のイベント'}.get(p.get('type'),p.get('type') or 'イベント'), 'eventType':p.get('type'),'source':p.get('net') or 'USGS','url':safe_url(p.get('url')),
        'status':p.get('status'),'felt':p.get('felt'),'cdi':p.get('cdi'),'mmi':p.get('mmi'),
        'alert':p.get('alert'),'tsunamiFlag':p.get('tsunami'),'scale':'不明','scaleCode':-1,
        'historyCount':0,'history':[],'isForeign':False}

def listing():
    global attempt
    with lock:
        if time.monotonic()-attempt>=60:
            attempt=time.monotonic()
            try:
                r=requests.get(API,params={'format':'geojson','limit':500,'orderby':'time'},timeout=(4,12));r.raise_for_status()
                data=r.json();features=data.get('features')
                if not isinstance(features,list):raise ValueError('Invalid catalog')
                items=[normalize(f) for f in features[:500]]
                cache.update(items=items,lastSuccess=datetime.now(JST).isoformat(),error=None)
            except (requests.RequestException,ValueError,TypeError,KeyError,AttributeError):
                cache['error']='USGSの地震情報を取得できませんでした。取得済みの表示を保持しています。'
        return dict(cache,stale=bool(cache['error']),notice='' if len(cache['items'])==500 else 'USGSから取得できた地震は500件未満です。')

def product_data(document):
    versions=[]
    for kind,products in (document.get('properties',{}).get('products') or {}).items():
        for product in products:
            properties=product.get('properties') or {}
            links=[]
            for name,content in (product.get('contents') or {}).items():
                url=safe_url(content.get('url'))
                if url:links.append({'name':name or '原文','url':url})
            for key in ('url','link','review-url'):
                url=safe_url(properties.get(key))
                if url:links.append({'name':key,'url':url})
            versions.append({'kind':kind,'source':product.get('source',''),'code':product.get('code',''),
                'updateTime':product.get('updateTime',0),'time':date(product.get('updateTime')),
                'status':product.get('status',''),'weight':numeric(product.get('preferredWeight')) or 0,
                'properties':properties,'links':links})
    versions.sort(key=lambda v:v['updateTime'],reverse=True)
    seen=set();current=[];history=[]
    for v in versions:
        identity=(v['kind'],v['source'],v['code'])
        if identity in seen:history.append(v)
        else:seen.add(identity);current.append(v)
    return {'current':current,'history':history,'total':len(versions),
            'event':normalize(document),'status':'ok'}

def detail(event_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',event_id):return {'status':'error','message':'地震IDが不正です。'}
    with lock:
        prior=details.get(event_id)
        if prior and time.monotonic()-prior[0]<60:return prior[1]
        try:
            r=requests.get(API,params={'format':'geojson','eventid':event_id,'includesuperseded':'true'},timeout=(4,20));r.raise_for_status()
            result=product_data(r.json())
            details[event_id]=(time.monotonic(),result)
            if len(details)>100:details.pop(next(iter(details)))
            return result
        except (requests.RequestException,ValueError,TypeError,KeyError,AttributeError):
            if prior:return dict(prior[1],stale=True,message='詳細の再取得に失敗しました。前回の取得内容です。')
            return {'status':'error','message':'USGSの関連情報・更新履歴を取得できませんでした。地震を選び直して再試行してください。'}
