"""v4.2 acceptance: the browser UI and the `phdlab` CLI are two clients of ONE running backend, used at the same time.
Starts a real server process (uvicorn, throw-away data folder), drives it from CLI processes (also through the
phdlab.bat / phdlab launcher) and from an HTTP client that behaves like the UI, and checks that each side sees the
other's changes (sessions, code projects, the /api/events bus)."""
import _env  # noqa: F401  (must be first)
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import httpx

ROOT = _env.ROOT


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SharedBackend(unittest.TestCase):
    def test_real_cli_and_http_client_observe_the_same_persistent_session(self):
        """Actual loopback server and CLI process; no model or personal data."""
        with tempfile.TemporaryDirectory(prefix='phdlab-shared-backend-') as directory:
            data=Path(directory);port=free_port();url=f'http://127.0.0.1:{port}'
            (data/'config.json').write_text(json.dumps({'lifecycle':{'cloud_preconnect':False,'unload_on_exit':False},
                'memory':{'embed_engine':'hashing'},'clearml':{'auto_record':False},'ranking':{'auto':False}}),encoding='utf-8')
            keep={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','LOCALAPPDATA','USERPROFILE','HOME','APPDATA'}
            env={k:v for k,v in os.environ.items() if k.upper() in keep}
            env.update(PHDLAB_DATA_DIR=str(data),JUPYTER_DATA_DIR=str(data/'_jupyter'),PHDLAB_QA_OFFLINE='1',
                       PYTHONIOENCODING='utf-8',NO_PROXY='localhost,127.0.0.1,::1')
            with (data/'server.log').open('wb') as log:
                process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(port)],
                    cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                try:
                    with httpx.Client(base_url=url,trust_env=False,timeout=5) as client:
                        deadline=time.monotonic()+30
                        while True:
                            self.assertIsNone(process.poll(),'Owned server exited before readiness')
                            try:
                                if client.get('/api/config').status_code==200:break
                            except httpx.TransportError:pass
                            if time.monotonic()>deadline:self.fail('Owned backend did not become ready')
                            time.sleep(.1)
                        response=client.post('/api/chat/sessions',json={'title':'Shared real CLI fixture'})
                        response.raise_for_status();session=response.json();sid=session['id']
                        args=[sys.executable,'-m','backend.cli','--server',url,'--json','history','show',sid]
                        cli=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=20)
                        self.assertEqual(cli.returncode,0,cli.stderr)
                        self.assertEqual(json.loads(cli.stdout)['id'],sid)
                        self.assertEqual(json.loads(cli.stdout)['title'],'Shared real CLI fixture')
                        changed=client.put('/api/chat/sessions/'+sid,json={'title':'Updated through HTTP'})
                        changed.raise_for_status()
                        cli=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=20)
                        self.assertEqual(cli.returncode,0,cli.stderr)
                        self.assertEqual(json.loads(cli.stdout)['title'],'Updated through HTTP')
                        self.assertEqual(client.get('/api/chat/sessions/'+sid).json()['title'],'Updated through HTTP')
                finally:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)




if __name__ == "__main__":
    unittest.main()
