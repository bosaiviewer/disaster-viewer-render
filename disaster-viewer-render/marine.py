"""Selected MSIL public API layers. Keys stay server-side; provider HTML is never rendered."""
import os,re,time,math,html
from html.parser import HTMLParser
from threading import Lock
from urllib.parse import urlsplit
import requests
import weather

SOURCE='https://portal.msil.go.jp/msil-api-list'
LAYERS={
 'volcano':('海域火山','marine-volcano-DB',(1,),86400),
 'geodesy':('海底地殻変動観測点','seabed-crust-deformation-info',(1,),86400),
 'tides':('潮汐推算の地点','tide-prediction',(),86400),
 'ocean':('海洋速報・黒潮','quick-bulletin',(6,),3600),
 'navigation':('海上の航行警報','navigational-warnings',(1,2,3),600),
}
_key_lock=Lock();_trial=('',0.0)

def api_key():
    configured=os.environ.get('MSIL_API_KEY','').strip()
    if configured:return configured,False
    global _trial
    with _key_lock:
        if not _trial[0] or time.monotonic()-_trial[1]>86400:
            response=requests.get('https://portal.msil.go.jp/howtouse',timeout=(3,15));response.raise_for_status()
            keys=re.findall(r'\b[a-f0-9]{32}\b',response.text)
            if not keys:raise ValueError('Public trial key unavailable')
            _trial=(keys[0],time.monotonic())
        return _trial[0],True

class Text(HTMLParser):
    def __init__(self):super().__init__();self.text=[];self.links=[]
    def handle_data(self,data):self.text.append(data)
    def handle_starttag(self,tag,attrs):
        if tag in ('br','hr','p','div'):self.text.append('\n')
        if tag=='a':
            value=dict(attrs).get('href','');parts=urlsplit(value)
            if parts.scheme=='https' and parts.hostname and not parts.username and not parts.password:self.links.append(value)

def readable(value):
    parser=Text();parser.feed(str(value));text=re.sub(r'[ \t\r\f\v]+',' ',''.join(parser.text))
    return text.strip(),list(dict.fromkeys(parser.links))

def normalize_feature(feature,kind,index):
    geometry=feature.get('geometry');props=feature.get('properties') or {}
    if not isinstance(geometry,dict) or geometry.get('type') not in ('Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon'):return None
    def valid(node):
        if not isinstance(node,list) or not node:return False
        if isinstance(node[0],(int,float)):
            return len(node)>=2 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in node[:2]) and -180<=node[0]<=180 and -90<=node[1]<=90
        return all(valid(x) for x in node)
    if not valid(geometry.get('coordinates')):return None
    fields=[];links=[]
    for name,value in props.items():
        if value is None or isinstance(value,(dict,list)) or str(name).lower() in ('objectid','shape_length','shape_area'):continue
        text,found=readable(value);links.extend(found)
        parts=urlsplit(str(value))
        if parts.scheme=='https' and parts.hostname and not parts.username and not parts.password:links.append(str(value));continue
        if str(name).lower()=='url':continue
        if text:fields.append([str(name),text])
    name=next((str(props[k]) for k in ('火山名','観測地点名','nameJa','name','海流の種類') if props.get(k)),LAYERS[kind][0])
    return {'type':'Feature','geometry':geometry,'properties':{'id':kind+'-'+str(index),'name':readable(name)[0],'fields':fields,'links':list(dict.fromkeys(links))}}

def load(kind):
    if kind not in LAYERS:raise ValueError('Unsupported marine layer')
    title,path,layers,ttl=LAYERS[kind]
    def fetch():
        key,trial=api_key();headers={'Ocp-Apim-Subscription-Key':key};features=[]
        targets=[f'https://api.msil.go.jp/{path}/v2/MapServer/{layer}/query' for layer in layers] if layers else ['https://api.msil.go.jp/tide-prediction/v3/station']
        for url in targets:
            offset=0
            for _ in range(5):
                params={'f':'geojson','where':'1=1','outFields':'*','outSR':'4326','returnGeometry':'true','resultOffset':offset} if layers else None
                response=requests.get(url,params=params,headers=headers,timeout=(3,20));response.raise_for_status();data=response.json()
                if data.get('type')!='FeatureCollection' or not isinstance(data.get('features'),list):raise ValueError('Invalid marine data')
                rows=data['features'];features.extend(rows)
                if not data.get('exceededTransferLimit'):
                    break
                if not rows:raise ValueError('Empty incomplete page')
                offset+=len(rows)
            else:raise ValueError('Marine paging limit')
        cleaned=[r for i,f in enumerate(features) if (r:=normalize_feature(f,kind,i))]
        notes={'volcano':'海域火山の位置と資料への案内です。現在の噴火警報ではありません。','geodesy':'観測点の設置位置です。現在の揺れや地殻変動の実測値ではありません。','tides':'潮汐推算の対象地点です。数値・基準面は公式の推算画面で確認してください。津波の観測情報ではありません。','ocean':'海洋速報の黒潮の範囲です。データの発行日・解析対象日は地点の詳細で確認してください。','navigation':'海しるに掲載されている航行警報です。船舶の航行には原文の最新情報を確認してください。'}
        return {'kind':kind,'name':title,'features':cleaned,'source':SOURCE,'trial':trial,'notice':notes[kind]+(' 公開の試用キーで接続しています。継続公開には個別キーを設定してください。' if trial else ''),'attribution':'このサービスは、海しるAPIを利用して取得した情報をもとに作成していますが、サービスの内容は海上保安庁によって保証されたものではありません。'}
    return weather.cached('marine-v38-'+kind,ttl,fetch)
