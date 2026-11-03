"""Disabled-by-default storage foundations. No registration or public endpoint."""
from pathlib import Path
import argparse,hashlib,json,os,sqlite3
from contextlib import closing
from datetime import datetime,timezone
SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email_normalized TEXT UNIQUE,password_hash TEXT,verified_at TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_preferences(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,value_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(channel TEXT PRIMARY KEY,value_json TEXT NOT NULL,digest TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS changes(cursor INTEGER PRIMARY KEY AUTOINCREMENT,channel TEXT NOT NULL,value_json TEXT NOT NULL,created_at TEXT NOT NULL);
'''
def prepare(directory):
 path=Path(directory).resolve();path.mkdir(parents=True,exist_ok=True)
 database=path/'shared-service.sqlite3'
 with closing(sqlite3.connect(database)) as db, db:
  db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA journal_mode=WAL');db.executescript(SCHEMA);db.execute('PRAGMA user_version=1')
 return database
def record_snapshot(database,channel,value):
 if channel not in ('earthquakes','realtime','tsunami','volcanoes','cyclones'):raise ValueError('Unsupported channel')
 body=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);digest=hashlib.sha256(body.encode()).hexdigest();now=datetime.now(timezone.utc).isoformat()
 with closing(sqlite3.connect(database)) as db, db:
  db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT digest FROM snapshots WHERE channel=?',(channel,)).fetchone()
  if old and old[0]==digest:return None
  db.execute('INSERT INTO snapshots VALUES(?,?,?,?) ON CONFLICT(channel) DO UPDATE SET value_json=excluded.value_json,digest=excluded.digest,updated_at=excluded.updated_at',(channel,body,digest,now))
  cursor=db.execute('INSERT INTO changes(channel,value_json,created_at) VALUES(?,?,?)',(channel,body,now)).lastrowid
  db.execute('DELETE FROM changes WHERE cursor < ?',(max(0,cursor-1000),));return cursor
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--directory',default=str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'EarthquakeViewer'/'shared-service'));args=parser.parse_args();database=prepare(args.directory)
 print('共通配信・アカウント向けの保存基盤を準備しました。');print(database);print('ユーザー登録・公開配信・メール送信は有効化していません。外部の公開フォルダーへ置かないでください。')
if __name__=='__main__':main()
