"""Read-only check of the disabled shared-service preparation. Never prints secrets."""
from pathlib import Path
from contextlib import closing
import argparse,os,sqlite3
REQUIRED={'users','user_preferences','snapshots','changes'}
def inspect(directory):
 database=Path(directory).resolve()/'shared-service.sqlite3'
 if not database.is_file():return {'prepared':False,'schemaVersion':None,'missing':sorted(REQUIRED)}
 with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as db:
  tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")};version=db.execute('PRAGMA user_version').fetchone()[0]
 return {'prepared':REQUIRED<=tables and version==1,'schemaVersion':version,'missing':sorted(REQUIRED-tables)}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--directory',default=str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'EarthquakeViewer'/'shared-service'));args=parser.parse_args()
 try:state=inspect(args.directory)
 except (OSError,sqlite3.Error,ValueError):print('保存基盤を確認できません。保存先とアクセス権を確認してください。');return 1
 print('保存基盤：'+('準備済み' if state['prepared'] else '未準備（PREPARE_SHARED.batで準備できます）'))
 print('全閲覧者への共通ライブ配信：未実装・無効');print('アカウント登録：未実装・無効');print('外部への配置・メール送信・秘密情報の表示は行っていません。')
 return 0
if __name__=='__main__':raise SystemExit(main())
