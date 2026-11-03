"""Persistent public-data cache. No secrets are stored here."""
import os,json,sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone,timedelta
JST=timezone(timedelta(hours=9))
def now():return datetime.now(JST)
@contextmanager
def db():
    root=Path(os.environ.get('EV_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA',Path.home()))/'EarthquakeViewer'/'data')
    root.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(root/'history.sqlite3',timeout=20)
    c.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT,key TEXT,body TEXT, PRIMARY KEY(kind,key))')
    try:
        with c:yield c
    finally:c.close()
def put(kind,key,value):
    with db() as c:c.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(kind,key,json.dumps(value,ensure_ascii=False)))
def get(kind,key,default=None):
    with db() as c:r=c.execute('SELECT body FROM records WHERE kind=? AND key=?',(kind,key)).fetchone()
    return json.loads(r[0]) if r else default
def values(kind):
    with db() as c:return [json.loads(r[0]) for r in c.execute('SELECT body FROM records WHERE kind=?',(kind,))]
