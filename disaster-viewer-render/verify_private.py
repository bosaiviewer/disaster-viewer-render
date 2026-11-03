"""Offline regression gate before PRIVATE_START deploys. Never uses Cloudflare credentials."""
from pathlib import Path
import os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent

def checks():
 node=shutil.which('node');ps=shutil.which('powershell.exe')
 if not node:raise RuntimeError('Node.jsが見つかりません。初回準備を確認してください。')
 commands=[[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_private*.py','-q'],[node,'--test',str(ROOT/'cloudflare-private/worker.test.mjs'),str(ROOT/'tests/quake_pairs.test.mjs'),str(ROOT/'tests/priority44.test.mjs'),str(ROOT/'tests/event_merge45.test.mjs'),str(ROOT/'tests/presentation46.test.mjs')]]
 if os.name=='nt':
  if not ps:raise RuntimeError('Windows PowerShellが見つかりません。')
  commands.append([ps,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'cloudflare-private/startup.tests.ps1')])
 commands.insert(1,[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_v45.py','-q'])
 commands.insert(2,[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_v46.py','-q'])
 for command in commands:subprocess.run(command,cwd=ROOT,check=True)
 print('起動・認証・地震対応の自動検査に合格しました。',flush=True)

def main():
 if '--runtime-ready' not in sys.argv:
  from launcher import prepare,runtime_path
  python=prepare(ROOT,runtime_path())
  return subprocess.call([str(python),str(Path(__file__).resolve()),'--runtime-ready'],cwd=ROOT)
 try:checks();return 0
 except (OSError,RuntimeError,subprocess.CalledProcessError) as exc:
  print('自動検査に失敗したため、配置を停止します。ZIPを完全に展開し直し、PRIVATE_UPDATE_GUIDE.mdを確認してください。',flush=True);print(str(exc),flush=True);return 1
if __name__=='__main__':raise SystemExit(main())
