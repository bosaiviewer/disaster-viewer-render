"""Small current-state snapshot, separate from yearly archives and existing collectors.

Clients read every second. One shared background HTTP check per >=10 seconds
supplements immediate P2P WebSocket delivery; it is not a 1 Hz JMA feed.
"""
from threading import Lock,Thread
from datetime import datetime
import time,re
import hazards,storage

_lock=Lock()
_worker=None
_attempt=None
_state=None
_documents={}

def at(value):
    d=datetime.fromisoformat(value)
    return d if d.tzinfo else d.replace(tzinfo=storage.JST)

def fetch_current():
    listing=hazards.net.get(hazards.BASE+'tsunami/data/list.json').json()
    clear=hazards.net.get(hazards.BASE+'tsunami/data/clearweb.json').json()
    if not isinstance(listing,list) or not all(k in clear for k in ('w','f')):raise ValueError('津波の現在状態を確認できません。')
    limits={k:at(clear[k]) for k in ('w','f')};rows=[]
    for row in listing:
        name=row.get('json','')
        if not re.fullmatch(r'[\w]+\.json',name) or '_K' in row.get('ift',''):continue
        kind='f' if row.get('ttl') in ('津波情報','沖合の津波観測に関する情報') else 'w'
        if at(row['rdt'])<=limits[kind]:continue
        if name not in _documents:
            doc=storage.get('tsu-doc',name)
            if doc is None:
                doc=hazards.net.get(hazards.BASE+'tsunami/data/'+name).json()
                storage.put('tsu-doc',name,doc)
            parsed=hazards.parse_tsunami(doc)
            parsed.update(id=name,eventId=doc.get('Head',{}).get('EventID'),url=hazards.BASE+'tsunami/data/'+name)
            _documents[name]=parsed
            while len(_documents)>100:_documents.pop(next(iter(_documents)))
        result=_documents[name]
        if result.get('validUntil') and at(result['validUntil'])<=storage.now():continue
        rows.append(result)
    current=[];seen=set()
    for row in sorted(rows,key=lambda r:r.get('time') or '',reverse=True):
        event=row.get('eventId') or row['id']
        if row.get('areas') or row.get('infoType')=='取消':
            if event in seen:continue
            seen.add(event)
        current.append(row)
    return {'current':current,'history':[],'error':None,'stale':False,'checkedAt':storage.now().isoformat(),'upstreamIntervalSeconds':10}

def _refresh():
    global _state
    try:
        result=fetch_current()
        with _lock:
            changed=_state is None or result['current']!=_state.get('current')
            _state=result
        if changed:storage.put('live-tsunami52','current',result)
    except Exception:
        # Failure keeps known state and must never be presented as all-clear.
        with _lock:_state=dict(_state or {},error='津波の最新状態を確認できません。前回の情報を保持しています。',stale=True)

def snapshot():
    global _worker,_attempt,_state
    with _lock:
        if _state is None:
            saved=storage.get('live-tsunami52','current') or storage.get('hazard-cache','tsunami',{})
            _state={'current':saved.get('current',[]),'history':[],'error':'最新状態を確認中です。','stale':True,'checkedAt':saved.get('checkedAt') or saved.get('lastSuccess'),'upstreamIntervalSeconds':10}
        if (_worker is None or not _worker.is_alive()) and (_attempt is None or time.monotonic()-_attempt>=10):
            _attempt=time.monotonic();_worker=Thread(target=_refresh,daemon=True);_worker.start()
        return dict(_state)
