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
