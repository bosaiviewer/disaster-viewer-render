"""One-click setup. Reuse a per-user environment across extracted versions."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys

def runtime_path():
    base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))
    return base/'EarthquakeViewer'/f'python-{sys.version_info.major}.{sys.version_info.minor}'

def prepare(root, runtime):
    python=runtime/'Scripts'/'python.exe'
    requirements=root/'requirements.txt'
    digest=hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker=runtime/'requirements.sha256'
    if not python.exists():
        print('初回の準備をしています。この処理は通常1回だけです。',flush=True)
        subprocess.run([sys.executable,'-m','venv',str(runtime)],check=True)
    installed=marker.read_text().strip() if marker.exists() else ''
    if installed!=digest:
        print('必要なライブラリーを準備しています…',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(requirements)],check=True)
        marker.write_text(digest,encoding='ascii')
    return python

def main():
    if sys.version_info<(3,11):
        print('Python 3.11以降をインストールしてください。');return 1
    root=Path(__file__).resolve().parent
    try:
        python=prepare(root,runtime_path())
        return subprocess.call([str(python),str(root/'app.py'),'--port','0','--open-browser'],cwd=root)
    except (OSError,subprocess.CalledProcessError) as exc:
        print(f'起動準備に失敗しました。ネット接続とPythonのインストールを確認してください。\n{exc}')
        return 1
    except KeyboardInterrupt:
        return 0

if __name__=='__main__':
    raise SystemExit(main())
