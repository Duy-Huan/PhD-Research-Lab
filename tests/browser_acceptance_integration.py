"""REAL_LOCAL disposable HTTP/browser/worker fences; no model calls. Run in the browser CI job."""
import json
from pathlib import Path
import unittest
import urllib.error
import urllib.request
import tempfile
import subprocess
import sys
import shutil
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]


class OwnedServerCapability(unittest.TestCase):
    def test_project_journey_has_owned_creation_but_cannot_switch_provider_or_launch_tools(self):
        """Actual HTTP/preflight only: no turn is submitted and no model qualification is implied."""
        from devtools.verification.browser import application
        from devtools.verification.uat import run_space
        from devtools.verification.uat_journeys import CHAT_PROMPT
        out=run_space(ROOT/'output/playwright/uat-journey-selftest')
        with application(out,browser_uat=True,uat_journey='project-and-chat') as env:
            def call(path,body=None):
                request=urllib.request.Request(env['PHDLAB_E2E_URL']+path,
                    data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(request,timeout=10) as response:return response.status,json.load(response)
                except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
            state=call('/api/qa/uat-state')[1];name=state['lease']['project_name']
            self.assertFalse(state['in_owned_project'])
            self.assertEqual(call('/api/projects',{'name':name,'data_dir':str(out.parent/'escape')})[0],403)
            self.assertEqual(call('/api/projects',{'name':name})[0],200)
            self.assertTrue(call('/api/qa/uat-state')[1]['in_owned_project'])
            self.assertEqual(call('/api/projects',{'name':name})[0],403)
            status,session=call('/api/chat/sessions',{'title':CHAT_PROMPT[:48],'topic_id':'','chat_project':'','settings':{}})
            self.assertEqual(status,200)
            self.assertEqual(call('/api/chat/sessions/'+session['id']+'/turns',{'text':CHAT_PROMPT,'overrides':{'provider':'app:openai'}})[0],403)
            self.assertEqual(call('/api/terminal/execute',{'command':'echo forbidden'})[0],403)
            self.assertEqual(call('/api/chat/sessions/'+session['id'])[1]['turns'],[])
            cfg=call('/api/config')[1]
            self.assertFalse(cfg['aiws']['mcp_auto']);self.assertEqual(cfg['aiws']['mcp_tools'],['-'])
            self.assertEqual(cfg['aiws']['memory_mode'],'off');self.assertFalse(cfg['fallback_to_cloud'])

    def _browser_journey_without_model(self,journey,actions):
        """Deterministic Playwright validates the oracle only, never an AI action history."""
        from devtools.verification.browser import application
        from devtools.verification.uat import run_space
        from devtools.verification.uat_gate import unexpected_events,validate_run
        out=run_space(ROOT/'output/playwright/uat-journey-selftest')
        with application(out,browser_uat=True,uat_journey=journey) as env:
            options=out/'options.json';options.write_text(json.dumps({'url':env['PHDLAB_E2E_URL'],'out':str(out),
                'journey':journey,'source_sha256':'SELFTEST-NO-MODEL'}),encoding='utf-8')
            with (out/'browser.log').open('wb') as log:
                browser=subprocess.Popen([shutil.which('node') or 'node','devtools/verification/uat_browser.mjs',str(options)],
                    cwd=ROOT,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True,env=env)
                try:
                    for _ in range(120):
                        if (out/'browser-lease.json').is_file():break
                        if browser.poll() is not None:self.fail('Owned browser exited; see '+str(out/'browser.log'))
                        time.sleep(.25)
                    self.assertTrue((out/'browser-lease.json').is_file())
                    script="""const fs=require('node:fs');const {chromium,expect}=require('@playwright/test');
(async()=>{const lease=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));const browser=await chromium.connectOverCDP(lease.cdp_url);
const page=browser.contexts()[0].pages()[0];"""+actions+"\nprocess.exit(0);})().catch(e=>{console.error(e);process.exit(1)});"
                    actor=subprocess.run([shutil.which('node') or 'node','-e',script,str(out/'browser-lease.json')],
                        cwd=ROOT/'frontend',env=env,capture_output=True,text=True,timeout=100)
                    (out/'deterministic-actor.log').write_text(actor.stdout+actor.stderr,encoding='utf-8')
                    self.assertEqual(actor.returncode,0,'Deterministic browser actor failed; see '+str(out))
                    finishing=time.monotonic()
                    browser.communicate('{"action":"finish"}\n',timeout=30)
                    self.assertEqual(browser.returncode,0,'See '+str(out/'browser.log'))
                    # Bounded teardown: lingering proxied SSE upstreams must not keep the owned browser alive near the 30s limit.
                    self.assertLess(time.monotonic()-finishing,10,'Owned browser teardown exceeded 10s; see '+str(out))
                finally:
                    if browser.poll() is None:browser.terminate();browser.wait(timeout=15)
            evidence=json.loads((out/'browser-evidence.json').read_text(encoding='utf-8'))
            self.assertEqual(evidence['confirmation'],'PASS',str(out))
            self.assertEqual(unexpected_events(evidence),[],str(out))
            self.assertTrue(validate_run(out,'SELFTEST-NO-MODEL',journey),
                'Deterministic browser oracle PASS without a model action history must not become AI-UAT')

    def test_failure_recovery_browser_oracle_requires_observed_fault_and_real_reload(self):
        self._browser_journey_without_model('failure-recovery',"""
await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/config')&&r.status()===503),page.reload()]);
await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/config')&&r.status()===200),page.reload()]);
await page.getByRole('button',{name:'System Settings',exact:true}).click();
await expect(page.locator('.settings-studio-content')).toBeVisible();
""")

    def test_native_workflow_browser_oracle_retains_actual_cpu_artifacts_without_model(self):
        self._browser_journey_without_model('workflow-operations',"""
await page.locator('#topic-btn').click();await page.locator('#panel').getByText(lease.setup.topic_title,{exact:true}).click();
await page.locator('#drawer-close-btn').click();
await page.getByRole('button',{name:'Autonomous Missions',exact:true}).click();
await page.getByRole('button',{name:'Workflows L1–L4',exact:true}).click();
const card=page.locator('article').filter({has:page.getByRole('heading',{name:/L3.*Synthetic CPU UAT mission/})});
await card.getByText('Plan and results',{exact:true}).click();
await card.getByRole('textbox',{name:'Review note',exact:true}).fill('Disposable synthetic UAT technical fixture only; no scientific approval.');
await card.getByRole('button',{name:'Approve plan and run',exact:true}).click();
await expect(card.getByRole('status')).toContainText('awaiting_review',{timeout:45000});
await card.getByRole('button',{name:'Complete review',exact:true}).click();
await expect(card.getByRole('status')).toContainText('completed');
""")

    def test_python_worker_denies_file_mutation_and_processes_outside_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'lease';out.mkdir();secret=root/'private.txt';secret.write_text('canary',encoding='utf-8')
            program='''import json,sys,subprocess,socket
from pathlib import Path
from devtools.verification.browser_use_worker import restrict_worker
out=Path(sys.argv[1]);secret=Path(sys.argv[2]);restrict_worker(out,{1234})
blocked=[]
for name,action in [('read',lambda: secret.read_text()),('write',lambda: secret.write_text('bad')),('remove',lambda: secret.unlink()),('spawn',lambda: subprocess.run([sys.executable,'-V'])),('socket',lambda: socket.create_connection(('127.0.0.1',1),timeout=1))]:
 try:action()
 except PermissionError:blocked.append(name)
(out/'allowed.txt').write_text('lease-only')
print(json.dumps(blocked))
'''
            result=subprocess.run([sys.executable,'-c',program,str(out),str(secret)],cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),['read','write','remove','spawn','socket'])
            self.assertEqual(secret.read_text(encoding='utf-8'),'canary')
            self.assertEqual((out/'allowed.txt').read_text(encoding='utf-8'),'lease-only')

    def test_owned_browser_origin_proxy_and_finish_without_model(self):
        from devtools.verification.browser import application
        from devtools.verification.uat import run_space
        out=run_space(ROOT/'output/playwright/browser-lease-selftest')
        with application(out,browser_uat=True) as env:
            options=out/'options.json';options.write_text(json.dumps({'url':env['PHDLAB_E2E_URL'],'out':str(out)}),encoding='utf-8')
            with (out/'browser.log').open('wb') as log:
                browser=subprocess.Popen([shutil.which('node') or 'node','devtools/verification/uat_browser.mjs',str(options)],
                    cwd=ROOT,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True,env=env)
                try:
                    for _ in range(120):
                        if (out/'browser-lease.json').is_file():break
                        if browser.poll() is not None:self.fail('Owned browser exited; see '+str(out/'browser.log'))
                        time.sleep(.25)
                    self.assertTrue((out/'browser-lease.json').is_file())
                    browser.communicate('{"action":"finish"}\n',timeout=30)
                    self.assertEqual(browser.returncode,0)
                finally:
                    if browser.poll() is None:
                        browser.terminate();browser.wait(timeout=15)
            lease=json.loads((out/'browser-lease.json').read_text(encoding='utf-8'))
            evidence=json.loads((out/'browser-evidence.json').read_text(encoding='utf-8'))
            self.assertFalse(lease['personal_profile'])
            self.assertEqual(lease['egress_canary'],'BLOCKED')
            self.assertEqual(evidence['confirmation'],'UNCONFIRMED')
            self.assertTrue((out/'trace.zip').is_file())
            self.assertTrue((out/'final.png').read_bytes().startswith(b'\x89PNG'))

    def test_actual_uat_server_allows_language_and_denies_other_writes(self):
        """REAL_LOCAL HTTP integration; no model, account or browser credentials."""
        from devtools.verification.browser import application
        from devtools.verification.uat import run_space
        out = run_space(ROOT / 'output/playwright/capability-selftest')
        observations = []
        with patch.dict('os.environ',{'OPENAI_API_KEY':'QA_CANARY_ONLY','GITHUB_TOKEN':'QA_TOKEN_ONLY'}), application(out, browser_uat=True) as env:
            self.assertFalse('OPENAI_API_KEY' in env,'Disposable child must not inherit provider keys')
            self.assertFalse('GITHUB_TOKEN' in env,'Disposable child must not inherit GitHub credentials')
            def call(path, body=None, raw=None):
                payload = raw if raw is not None else json.dumps(body).encode() if body is not None else None
                request = urllib.request.Request(env['PHDLAB_E2E_URL'] + path, data=payload,
                    headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        status, result = response.status, json.load(response)
                except urllib.error.HTTPError as exc:
                    status, result = exc.code, json.load(exc)
                observations.append({'path': path, 'status': status})
                return status, result
            for language in ['vi', 'en']:
                self.assertEqual(call('/api/config', {'ui': {'language': language}})[0], 200)
                self.assertEqual(call('/api/config')[1]['ui']['language'], language)
            for path, body in [('/api/config', {'api_key': 'forbidden'}),
                               ('/api/config', {'ui': {'language': 'vi', 'theme': 'dark'}}),
                               ('/api/terminal/execute', {'command': 'echo forbidden'}),
                               ('/api/chat/sessions', {'title': 'forbidden'})]:
                self.assertEqual(call(path, body)[0], 403)
            self.assertEqual(call('/api/config', raw=b'{broken')[0], 403)
            self.assertEqual(call('/api/config')[1]['ui']['language'], 'en')
        (out / 'capability-result.json').write_text(json.dumps({'mode': 'REAL_LOCAL',
            'observations': observations, 'scope': 'Owned settings-only HTTP capability fence'}, indent=2), encoding='utf-8')


if __name__=='__main__':unittest.main()
