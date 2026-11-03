"""Recent P2P quake warnings and evaluated shaking reports for reconnect recovery."""
from threading import Lock,Thread
from concurrent.futures import ThreadPoolExecutor,as_completed
import time
import os
import requests

URL='https://api.p2pquake.net/v2/history'
_lock=Lock()
_cache={'items':[],'checked':0.0,'error':None}
_refresh_lock=Lock()
_worker_lock=Lock()
_worker=None

def _history(code,limit):
    response=requests.get(URL,params=[('codes',code),('limit',limit)],timeout=(3,8))
    response.raise_for_status()
    rows=response.json()
    if not isinstance(rows,list):raise ValueError('Invalid history response')
    return [r for r in rows if isinstance(r,dict) and r.get('code')==code and r.get('id')]

def recent():
    # Never hold the cache lock while waiting for an upstream provider.
    if not _refresh_lock.acquire(blocking=False):
        with _lock:return dict(_cache)
    try:
        with _lock:
            if time.monotonic()-_cache['checked']<5:return dict(_cache)
            _cache['checked']=time.monotonic()
        errors=[]
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs={pool.submit(_history,code,limit):code for code,limit in ((551,100),(552,20),(556,20))}
            for future in as_completed(jobs):
                try:batch=future.result()
                except (requests.RequestException,ValueError,TypeError):errors.append(jobs[future]);continue
                # Publish successful streams immediately, even if another one is slow.
                with _lock:
                    merged={r['id']:r for r in _cache['items'] if r.get('code')!=jobs[future] or str(r.get('id','')).startswith('jma-update-')}
                    merged.update({r['id']:r for r in batch})
                    _cache['items']=sorted(merged.values(),key=lambda r:r.get('time') or '',reverse=True)[:250]
        with _lock:
            _cache['error']='一部の配信履歴を取得できません。受信済みの情報を保持しています。' if errors else None
            return dict(_cache)
    finally:_refresh_lock.release()

def snapshot():
    """Return immediately; at most one recovery fetch runs in the background."""
    global _worker
    with _worker_lock:
        with _lock:due=time.monotonic()-_cache['checked']>=5
        if due and (_worker is None or not _worker.is_alive()):
            _worker=Thread(target=recent,daemon=True,name='quake-recovery')
            _worker.start()
    with _lock:return dict(_cache,refreshing=bool(_worker and _worker.is_alive()))

_extra_last=0.0
_extra_worker=None
def extra_snapshot():
    """The slower official update bulletins never block the live recovery API."""
    global _extra_last,_extra_worker
    def update():
        try:
            import meteo
            rows=meteo.quake_updates().get('items',[])
            with _lock:
                merged={r['id']:r for r in _cache['items']}
                merged.update({r['id']:r for r in rows})
                _cache['items']=sorted(merged.values(),key=lambda r:r.get('time') or '',reverse=True)[:250]
        except (requests.RequestException,ValueError,TypeError,KeyError):pass
    with _worker_lock:
        if time.monotonic()-_extra_last>=15 and (_extra_worker is None or not _extra_worker.is_alive()):
            _extra_last=time.monotonic();_extra_worker=Thread(target=update,daemon=True,name='quake-extra-updates');_extra_worker.start()


def wolfx_mode51():
    if os.environ.get('EV_WOLFX_AUTHORIZED')=='1':return 'authorized'
    return 'private' if os.environ.get('EV_WOLFX_MODE','private')=='private' else 'off'

def wolfx_authorized():
    # Legacy name: private viewing is not an assertion that redistribution permission exists.
    return wolfx_mode51()!='off'

def eew_snapshot():
    if not wolfx_authorized():return {'enabled':False,'data':None}
    import weather
    def load():
        response=requests.get('https://api.wolfx.jp/jma_eew.json',timeout=(3,8));response.raise_for_status();raw=response.json()
        if not isinstance(raw,dict) or not raw.get('EventID') or not raw.get('AnnouncedTime'):raise ValueError('Invalid EEW snapshot')
        return {'data':raw,'source':'https://wolfx.jp/docs/open-api/'}
    return weather.cached('eew-snapshot-v51',60,load)
