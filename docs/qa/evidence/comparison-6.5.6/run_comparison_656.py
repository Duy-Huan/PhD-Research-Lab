"""Execute the shared frozen harness serially; preserve failures and logs."""
from pathlib import Path
import hashlib,json,os,platform,subprocess,sys,time

HERE=Path(__file__).resolve().parent/'comparison-656'
prep=json.loads((HERE/'preparation.json').read_text())
python311=Path(sys.executable).parents[2]/'py311/Scripts/python.exe'
def capture(cmd):
 return subprocess.check_output(cmd,text=True,encoding='utf-8').strip()
environment={'python':sys.version,'python_executable':sys.executable,'python311':capture([str(python311),'--version']),
 'platform':platform.platform(),'node':capture(['node','--version']),
 'npm':capture(['npm.cmd','--version']),'packages':json.loads(capture([sys.executable,'-m','pip','list','--format=json'])),
 'node_modules':'D:/git-repo/PhD-Research-Lab-worktrees/local-ci-repair-supervisor/frontend/node_modules',
 'offline':'PHDLAB_QA_OFFLINE=1','execution':'Serial on the same host; no live model calls',
 'commands':[['scripts/verify.py','--profile','full','--component','backend'],
 ['scripts/verify.py','--profile','pr','--component','frontend'],
 ['-m','devtools.verification.browser','--profile','pr','--offline-all']]}
browser=capture(['node','-e',"const p=require('./frontend/node_modules/playwright'); process.stdout.write(JSON.stringify({executable:p.chromium.executablePath(),browserRevisions:require('./frontend/node_modules/playwright-core/browsers.json')}))"])
environment['chromium']=json.loads(browser)
environment['chromium']['executable_sha256']=hashlib.sha256(Path(environment['chromium']['executable']).read_bytes()).hexdigest()
environment['diagnostic_build']='npx --no-install vite build; node postbuild.js, same on both, never changes original mandatory build result'
environment['uat']='Canonical uat with unchanged exhausted task budget; no model invocation permitted'
environment_hash=hashlib.sha256(json.dumps(environment,sort_keys=True).encode()).hexdigest()
(HERE/'environment.json').write_text(json.dumps({'sha256':environment_hash,**environment},indent=2))
env=dict(os.environ,PHDLAB_QA_OFFLINE='1',PYTHONIOENCODING='utf-8')
for key in list(env):
 if (key.startswith('PHDLAB_') and 'LIVE' in key) or key.endswith(('_API_KEY','_API_TOKEN')) or key in ('GITHUB_TOKEN','GH_TOKEN','PHDLAB_ALLOW_LIVE_TESTS'):
  env.pop(key)
probe="import pathlib,json,sys; errors=[]\nfor p in pathlib.Path('backend').rglob('*.py'):\n try: compile(p.read_bytes(),str(p),'exec')\n except (SyntaxError,ValueError) as e: errors.append({'file':str(p),'error':str(e)})\nprint(json.dumps({'python':sys.version,'errors':errors}));sys.exit(bool(errors))"
results=[]
for name in ('main','candidate'):
 root=Path(prep[name+'_root']);out=root/'output/playwright/same-suite';out.mkdir(parents=True,exist_ok=True)
 commands=[('python311-compatibility',[str(python311),'-c',probe]),
 ('backend',[sys.executable,'scripts/verify.py','--profile','full','--component','backend','--base',prep['original']['main_head'],'--out',str(out/'backend')]),
 ('frontend',[sys.executable,'scripts/verify.py','--profile','pr','--component','frontend','--base',prep['original']['main_head'],'--out',str(out/'frontend')]),
 ('diagnostic-web-transpile',['npx.cmd','--no-install','vite','build']),
 ('diagnostic-web-index',['node','postbuild.js']),
 ('browser',[sys.executable,'-m','devtools.verification.browser','--profile','pr','--offline-all','--base',prep['original']['main_head'],'--out',str(out/'browser')]),
 ('uat',[sys.executable,'scripts/verify.py','--profile','uat','--repair-key','TASK-UAT-LOCAL-ADAPTER','--base',prep['original']['main_head'],'--out',str(out/'uat')])]
 transpile_ok=True
 for label,command in commands:
  log=HERE/(name+'-'+label+'.log')
  if log.exists():raise RuntimeError('Do not overwrite earlier execution: '+str(log))
  print('START '+name+' '+label,flush=True);start=time.time()
  if label=='browser' and not transpile_ok:
   results.append({'subject':name,'step':label,'status':'NOT_RUN','reason':'Fresh diagnostic bundle unavailable; never serve stale assets'})
   (HERE/'execution.json').write_text(json.dumps(results,indent=2));continue
  try:
   with log.open('w',encoding='utf-8') as stream:
    result=subprocess.run(command,cwd=root/'frontend' if label.startswith('diagnostic-web-') else root,env=dict(env,PHDLAB_DATA_DIR=str(out/'bootstrap-data')),stdout=stream,stderr=subprocess.STDOUT,timeout=1800)
   item={'subject':name,'step':label,'exit_code':result.returncode,'seconds':round(time.time()-start,2),'command':command,'log':str(log)}
  except subprocess.TimeoutExpired:
   item={'subject':name,'step':label,'status':'TIMEOUT','seconds':round(time.time()-start,2),'command':command,'log':str(log)}
  if label.startswith('diagnostic-web-') and item.get('exit_code')!=0:transpile_ok=False
  results.append(item);(HERE/'execution.json').write_text(json.dumps(results,indent=2))
  print(json.dumps(item),flush=True)
