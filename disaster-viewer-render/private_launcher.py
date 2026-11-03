"""Use the same reusable Windows runtime as START.bat, without opening a public origin."""
from pathlib import Path
import subprocess,sys
from launcher import prepare,runtime_path
if __name__=='__main__':
 root=Path(__file__).resolve().parent;python=prepare(root,runtime_path())
 if '--prepare-only' in sys.argv:
  print('PRIVATE_PYTHON='+str(python),flush=True);raise SystemExit(0)
 raise SystemExit(subprocess.call([str(python),str(root/'private_runner.py'),'--port','8000'],cwd=root))
