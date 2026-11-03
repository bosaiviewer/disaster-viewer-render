"""JMA published Asian dust image catalog; no downloaded JavaScript is executed."""
import re
from datetime import datetime,timedelta,timezone
import requests,storage,weather

BASE='https://www.data.jma.go.jp/env/kosa/fcst/'

PRODUCTS={
 'surface':('黄砂解析予測図（地表付近の黄砂の濃度）','地表から上空1kmまでの黄砂の濃さを、数値モデルで解析・予測した図です。地上で観測された濃度そのものではありません。'),
 'column':('黄砂解析予測図（大気中の黄砂の総量）','地表から大気の上端までに含まれる黄砂の総量を、数値モデルで解析・予測した図です。地表付近の濃度とは異なります。'),
 'true':('ひまわり黄砂監視画像（トゥルーカラー再現画像）','可視・近赤外・赤外の観測を組み合わせ、人の目に近い色を再現します。日中は黄砂や雲の広がりを確認できます。夜間は赤外画像になり、黄砂を直接識別しにくくなります。'),
 'satdust':('ひまわり黄砂監視画像（ダスト画像）','衛星の赤外観測を組み合わせ、黄砂や火山灰などを識別しやすくした合成画像です。砂じんは主にマゼンタ系に見えますが、雲に隠れることもあり、色だけで黄砂と断定できません。'),
 'observed':('黄砂観測実況図','観測地点で目視により黄砂等を観測した結果を、視程（見通せる距離）で区分した日別の図です。当日は更新時点までの速報で、その日の各地点の最小の視程を示します。未表示の場所に黄砂がないとは限りません。')
}

def catalog_url(product,area):
    if product not in PRODUCTS or area not in ('jp','as'):raise ValueError('黄砂の種類・範囲を確認してください。')
    if product in ('surface','column'):return BASE+'list_js/'+('s' if product=='surface' else 'c')+'_jp'+area+'_list.js'
    if product in ('true','satdust'):return BASE.replace('fcst/','himawari/')+'kosa_js/'+('TRM' if product=='true' else 'DST')+'Time.js'
    return BASE.replace('fcst/','obs/')+'list_js/jp'+area+'_list.js'

def parse_catalog(text,product='surface',area='jp'):
    catalog_url(product,area)
    rows={}
    pattern=r'\b(imgFcst|imgAnly|imgSat|imgObs)\s*\[\s*[in]\s*\+\+\s*\]\s*=\s*["\x27](\d{8}(?:\d{4})?)["\x27]'
    for variable,stamp in re.findall(pattern,text):
        if variable not in ({'imgFcst','imgAnly'} if product in ('surface','column') else {'imgSat'} if product in ('true','satdust') else {'imgObs'}):continue
        try:
            if variable=='imgObs':at=datetime.strptime(stamp,'%Y%m%d').replace(tzinfo=storage.JST)
            elif variable=='imgSat':at=(datetime.strptime(stamp,'%Y%m%d%H%M').replace(tzinfo=timezone.utc)+timedelta(minutes=10)).astimezone(storage.JST)
            else:at=datetime.strptime(stamp,'%Y%m%d%H%M').replace(tzinfo=storage.JST)
        except ValueError:continue
        if product in ('surface','column'):
            code,folder=('s','surf') if product=='surface' else ('c','colu')
            url=BASE+'img/'+folder+'/'+area+'/'+stamp+'_kosafcst-'+code+'_jp_'+area+'.png';kind='解析' if variable=='imgAnly' else '予測'
        elif variable=='imgSat':
            code='TRM' if product=='true' else 'DST';url=BASE.replace('fcst/','himawari/')+'img/'+code+'/'+stamp+'_'+code+('_as' if area=='as' else '')+'.jpg';kind='衛星観測'
        else:url=BASE.replace('fcst/','obs/')+'img/'+area+'/'+stamp+'_kosaobs_jp_'+area+'.png';kind='観測日'
        rows[stamp]={'id':stamp,'time':at.isoformat(),'kind':kind,'url':url,'dayOnly':variable=='imgObs'}
    if not rows:raise ValueError('黄砂の時刻一覧を確認できません。')
    return sorted(rows.values(),key=lambda r:r['time'])

def dust(product='surface',area='jp'):
    url=catalog_url(product,area)
    def load():
        response=requests.get(url,timeout=(3,15));response.raise_for_status()
        if product in ('surface','column'):source=BASE+'fcst-'+('s' if product=='surface' else 'c')+'_'+area+'.html'
        elif product in ('true','satdust'):source=BASE.replace('fcst/','himawari/')+'himawari-'+('TRM' if product=='true' else 'DST')+('_as' if area=='as' else '')+'.html'
        else:source=BASE.replace('fcst/','obs/')+('japan' if area=='jp' else 'asia')+'.html'
        return {'items':parse_catalog(response.text,product,area),'source':source,'product':product,'area':area,'title':PRODUCTS[product][0],'description':PRODUCTS[product][1],'notice':'出典：気象庁。解析・予測・衛星観測・日別観測を区別して表示します。画像内の時刻・凡例も確認してください。','credits':'JMA / NOAA/NESDIS / CSU/CIRA' if product=='true' else '気象庁','updateNote':'毎日午前6時頃に更新' if product in ('surface','column') else '1時間ごとに更新' if product in ('true','satdust') else '毎時10分・40分頃に当日の速報を更新'}
    return weather.cached('dust-images53-'+product+'-'+area,1800 if product in ('surface','column') else 600,load)
