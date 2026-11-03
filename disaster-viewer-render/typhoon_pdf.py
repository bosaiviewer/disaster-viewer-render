"""Read JMA's provisional per-storm position tables when annual CSV is not ready."""
from io import BytesIO
import re
from datetime import datetime
from pypdf import PdfReader
import cyclones as net
import storage

ROW=re.compile(r'^(?P<prefix>(?:\d{1,2}\s+){1,3})(?P<lat>\d{1,2}\.\d+)\s*(?P<ns>[NS])?\s+(?P<lon>\d{1,3}\.\d+)\s*(?P<ew>[EW])?\s+(?P<pressure>\d{3,4}|---)\s+(?P<wind>\d{1,3}|--)(?:\s+|$)(?P<other>.*)$')

def parse(raw, year, number):
    reader=PdfReader(BytesIO(raw));first=reader.pages[0].extract_text() or ''
    if f'({number})' not in first:raise ValueError('Wrong storm table')
    name=re.search(r'\b([A-Z][A-Z -]+)\s*\('+number+r'\)',first)
    month=day=None;points=[]
    for page in reader.pages:
        for line in (page.extract_text() or '').splitlines():
            row=ROW.match(line.strip())
            if not row:continue
            tokens=[int(x) for x in row['prefix'].split()]
            if len(tokens)==3:month,day,hour=tokens
            elif len(tokens)==2:day,hour=tokens
            else:hour=tokens[0]
            if month is None or day is None or hour>23:continue
            try:when=datetime(year,month,day,hour,tzinfo=storage.JST).isoformat()
            except ValueError:continue
            lat=float(row['lat'])*(-1 if row['ns']=='S' else 1)
            lon=float(row['lon'])*(-1 if row['ew']=='W' else 1)
            pressure=row['pressure'];wind=row['wind'];other=row['other'].strip()
            fields=[['中心気圧',pressure+' hPa' if pressure!='---' else '未提供'],['最大風速',wind+' m/s' if wind!='--' else '未提供']]
            if other:fields.append(['暴風域・強風域・強さ等（位置表の表記）',other])
            points.append({'time':when,'coords':[lat,lon],'fields':fields,'source':'気象庁 台風位置表（PDF）'})
    if not points:raise ValueError('No positions in PDF')
    return {'name':name[1].strip() if name else None,'points':points}

def get(number,year):
    cached=storage.get('typhoon-pdf',number)
    if cached:return cached
    url=f'https://www.data.jma.go.jp/typhoon/data/T{number}.pdf'
    result=parse(net.get(url).content,year,number)
    result['url']=url
    storage.put('typhoon-pdf',number,result)
    return result
