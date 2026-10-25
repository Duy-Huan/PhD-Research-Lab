"""A disposable worker must release process-owned SQLite handles before cleanup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class WorkerCleanup(unittest.TestCase):
    def test_process_exit_releases_database_before_owned_directory_cleanup(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='phdlab-worker-fixture-') as directory:
            fixture=Path(directory)
            (fixture/'held_connection_fixture.py').write_text('''import os,sqlite3,unittest
connection=sqlite3.connect(os.path.join(os.environ['PHDLAB_DATA_DIR'],'held.sqlite3'))
class Database(unittest.TestCase):
 def test_connection_stays_open_until_process_exit(self):
  connection.execute('create table measurements(value real)')
  connection.execute('insert into measurements values (42)')
  self.assertEqual(connection.execute('select value from measurements').fetchone()[0],42)
''',encoding='utf-8')
            report=fixture/'result.json'
            env=dict(os.environ,PYTHONPATH=str(fixture))
            child=subprocess.run([sys.executable,'-m','devtools.verification.unittest_worker',str(report),
                                  'held_connection_fixture'],cwd=root,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(child.returncode,0,child.stderr)
            result=json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(result['passed'])
            self.assertTrue(result['cleanup_complete'])
            self.assertFalse(Path(result['disposable_data']).exists())


if __name__=='__main__':unittest.main()
