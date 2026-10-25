import json,subprocess,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from devtools.verification.browser import application
from devtools.verification.runner import identity
out=root/'output/playwright/stabilization-audit/ui-baseline-3'
out.mkdir(exist_ok=False)
before=identity(root)
with application(out) as env:
 result=subprocess.run(['node',str(out.parent/'ui-baseline.cjs')],cwd=root,env=env,timeout=240,capture_output=True)
 (out/'node.log').write_bytes(result.stdout+result.stderr)
after=identity(root)
(out/'source.json').write_text(json.dumps({'source':before,'source_after':after,'source_stable':before==after,'exit_code':result.returncode},indent=2),encoding='utf-8')
print(result.stdout.decode('utf-8',errors='replace'));print('exit_code',result.returncode,'source_stable',before==after)
