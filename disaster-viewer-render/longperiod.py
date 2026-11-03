"""Published JMA long-period observations; never derive them from seismic intensity."""
import re,time
from threading import Lock
import requests
BASE='https://www.jma.go.jp/bosai/ltpgm/data/'
_lock=Lock();_cache={'items':[],'checked':0,'error':None}
def level(value):
    return int(str(value)) if str(value) in ('0','1','2','3','4') else None

def extract(document,url):
    if document.get('Control',{}).get('Status')!='通常':raise ValueError('Not operational')
    body=document.get('Body') or {};observation=(body.get('Intensity') or {}).get('Observation') or {};maximum=level(observation.get('MaxLgInt'))
    if maximum is None:raise ValueError('No observed long-period class')
    areas=[];stations=[]
    def walk(node):
        if isinstance(node,list):
            for value in node:walk(value)
        elif isinstance(node,dict):
            if node.get('Name') and re.fullmatch(r'\d{3}',str(node.get('Code',''))) and level(node.get('MaxLgInt')) is not None:areas.append({'code':node['Code'],'name':node['Name'],'level':level(node['MaxLgInt'])})
            if node.get('Name') and level(node.get('LgInt')) is not None:stations.append({'name':node['Name'],'level':level(node['LgInt'])})
            for value in node.values():
                if isinstance(value,(dict,list)):walk(value)
    walk(observation.get('Pref') or [])
    return {'eventId':document.get('Head',{}).get('EventID'),'origin':(body.get('Earthquake') or {}).get('OriginTime'),'name':((body.get('Earthquake') or {}).get('Hypocenter') or {}).get('Area',{}).get('Name'),'issued':document.get('Head',{}).get('ReportDateTime'),'max':maximum,'areas':areas,'stations':stations,'url':url}

def recent():
    with _lock:
        now=time.monotonic()
        if _cache['checked'] and now-_cache['checked']<60:return dict(_cache)
        _cache['checked']=now
        try:
            response=requests.get(BASE+'list.json',timeout=(3,6));response.raise_for_status();index=response.json()
            if not isinstance(index,list):raise ValueError('Invalid list')
            result=[]
            for row in index[:10]:
                name=row.get('json')
                if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.json',name):continue
                response=requests.get(BASE+name,timeout=(3,6));response.raise_for_status()
                result.append(extract(response.json(),BASE+name))
            _cache.update(items=result,error=None)
        except (requests.RequestException,ValueError,TypeError,AttributeError):_cache['error']='長周期地震動の観測情報を取得できません。'
        return dict(_cache)
