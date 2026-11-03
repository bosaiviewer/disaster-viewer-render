import xml.etree.ElementTree as ET
"""JMA public website data. These website endpoints are not a guaranteed API."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from threading import RLock
import json,time,re
import requests
import storage
ROOT=Path(__file__).parent/'data'
AREAS=json.loads((ROOT/'weather_areas.json').read_text(encoding='utf-8'))
BOUNDS=json.loads((ROOT/'weather_city_bounds.json').read_text(encoding='utf-8'))
CODES=json.loads((ROOT/'weather_warning_codes.json').read_text(encoding='utf-8'))
TELOPS=json.loads((ROOT/'weather_telops.json').read_text(encoding='utf-8'))
BASE='https://www.jma.go.jp/bosai/'
_lock=RLock();_key_locks={};_cache={};_attempt={}

def stamp():return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
def get_json(path):
    r=requests.get(BASE+path,timeout=(3,12));r.raise_for_status();return r.json()
def cached(key,ttl,loader):
    with _lock:
        key_lock=_key_locks.setdefault(key,RLock())
    with key_lock:
        now=time.monotonic()
        if key in _cache and now-_attempt.get(key,0)<ttl:return dict(_cache[key])
        if key not in _cache:
            old=storage.get('weather-cache',key)
            if old:_cache[key]=dict(old,stale=True,error='保存された情報です。最新情報を確認中です。')
        _attempt[key]=now
        try:
            data=loader();data.update(checkedAt=stamp(),lastSuccess=stamp(),error=None,stale=False)
            _cache[key]=data;storage.put('weather-cache',key,data)
        except (requests.RequestException,ValueError,TypeError,AttributeError,KeyError,IndexError,ET.ParseError):
            old=_cache.get(key,{})
            _cache[key]=dict(old,checkedAt=stamp(),stale=True,error='情報を取得できません。前回の情報があれば保持しています。配信元の原文も確認してください。')
        return dict(_cache[key])
def validate_office(code):
    if code not in AREAS['offices']:raise ValueError('Unknown office')
    return code

def catalog():
    return {'offices':[dict(code=k,**v) for k,v in AREAS['offices'].items()], 'centers':AREAS['centers'],'telops':TELOPS}

def city_info(code):
    a=AREAS['class20s'].get(code) or AREAS['class10s'].get(code) or {}
    out={'code':code,'name':a.get('name',code)}
    b=BOUNDS.get(code)
    if b:
        out['bounds']=[b['sw'],b['ne']];out['coords']=[(b['sw'][i]+b['ne'][i])/2 for i in range(2)]
    return out

def parse_warnings(documents):
    if not isinstance(documents,list) or not documents:raise ValueError('Invalid warnings')
    # One bulletin per hazard; a cancellation must only replace its own hazard.
    latest={}
    for d in documents:
        if not isinstance(d,dict) or not isinstance(d.get('warning'),dict):raise ValueError('Invalid warning bulletin')
        kind=d.get('dataTypeCode')
        if not kind:raise ValueError('Missing type')
        if kind not in latest or d.get('reportDatetime','')>latest[kind].get('reportDatetime',''):latest[kind]=d
    towns={};bulletins=[]
    for kind,d in latest.items():
        bulletins.append({'type':kind,'time':d.get('reportDatetime'),'office':d.get('publishingOffice'),'headline':d.get('headlineText','')})
        for a in d['warning'].get('class20Items',[]):
            code=a.get('areaCode');town=towns.setdefault(code,dict(city_info(code),warnings=[],released=[]))
            for w in a.get('kinds',[]):
                if not w.get('code'):continue
                info=CODES.get(w['code'],{'name':'未対応の警報・注意報（'+str(w['code'])+'）','level':0,'alertLevel':None})
                item=dict(info,code=w['code'],status=w.get('status',''),time=d.get('reportDatetime'),type=kind)
                town['released' if w.get('status')=='解除' else 'warnings'].append(item)
    if not towns:raise ValueError('No municipalities')
    for t in towns.values():
        t['warnings'].sort(key=lambda w:(-w['level'],w['name']));t['level']=max([w['level'] for w in t['warnings']],default=0)
    return {'items':sorted(towns.values(),key=lambda t:(-t['level'],t['code'])),'bulletins':sorted(bulletins,key=lambda b:b['time'] or '',reverse=True),'issued':max((b['time'] or '' for b in bulletins),default='')}

def warnings(code):
    validate_office(code)
    return cached('warnings-'+code,60,lambda:dict(parse_warnings(get_json('warning/data/r8/'+code+'.json')),office=code,source=BASE+'warning/#area_type=offices&area_code='+code))

def forecast(code):
    validate_office(code)
    def load():
        source_code='460100' if code=='460040' else code
        data=get_json('forecast/data/forecast/'+source_code+'.json')
        if not isinstance(data,list) or not data or not data[0].get('timeSeries'):raise ValueError('Invalid forecast')
        for doc in data:
            for ts in doc.get('timeSeries',[]):
                if not isinstance(ts.get('timeDefines'),list) or not isinstance(ts.get('areas'),list):raise ValueError('Invalid time series')
        if code in ('460040','460100'):
            amami={'460040','88837','88971'}
            for doc in data:
                for ts in doc.get('timeSeries',[]):
                    ts['areas']=[a for a in ts['areas'] if (a.get('area',{}).get('code') in amami)==(code=='460040')]
                doc['timeSeries']=[ts for ts in doc.get('timeSeries',[]) if ts['areas']]
        overview=None;notice=None
        try:
            overview=get_json('forecast/data/overview_forecast/'+source_code+'.json')
            if not isinstance(overview,dict):raise ValueError()
        except (requests.RequestException,ValueError):notice='天気概況は取得できませんでした。予報は表示しています。'
        return {'documents':data,'overview':overview,'notice':notice,'source':BASE+'forecast/#area_type=offices&area_code='+code}
    return cached('forecast-v27-'+code,600,load)

def charts():
    def load():
        data=get_json('weather_map/data/list.json');groups=[]
        for region,label in [('near','日本付近'),('asia','アジア太平洋')]:
            for period,title in [('now','実況'),('ft24','24時間予想'),('ft48','48時間予想')]:
                rows=[]
                for filename in data.get(region,{}).get(period,[]):
                    if not re.fullmatch(r'[A-Za-z0-9_]+\.png',filename):continue
                    m=re.search(r'_010000_(\d{14})_',filename);base_time=None
                    if m:base_time=(datetime.strptime(m[1],'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=9)))).isoformat()
                    hours=0 if period=='now' else int(period[2:]);valid=(datetime.fromisoformat(base_time)+timedelta(hours=hours)).isoformat() if base_time else None
                    rows.append({'file':filename,'baseTime':base_time,'validTime':valid,'url':BASE+'weather_map/data/png/'+filename})
                if rows:groups.append({'id':region+'-'+period,'name':label+'・'+title,'items':list(reversed(rows))})
        if not groups:raise ValueError('No charts')
        return {'groups':groups,'source':BASE+'weather_map/'}
    return cached('charts',600,load)

def chart_image(filename):
    if not re.fullmatch(r'[A-Za-z0-9_]+\.png',filename):raise ValueError('Invalid file')
    index=charts()
    if not any(r['file']==filename for g in index.get('groups',[]) for r in g['items']):raise ValueError('Unknown file')
    response=requests.get(BASE+'weather_map/data/png/'+filename,timeout=(3,15));response.raise_for_status()
    if len(response.content)>8_000_000 or not response.content.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Invalid PNG')
    return response.content
