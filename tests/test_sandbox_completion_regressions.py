"""Deterministic software fault injection; not live experiment qualification."""
import _env
import json
import threading
import unittest
from unittest import mock

from backend.execution import sandbox as S


class SandboxCompletion(unittest.TestCase):
    def test_terminal_status_is_published_only_after_metrics_are_persisted(self):
        _env.fresh_project('completion-publication')
        job = S.Job('run', 'synthetic completed process')
        job.run_dir = S.runs_dir() / job.id
        job.run_dir.mkdir()
        job.status, job.started = 'running', 1
        job.proc = mock.Mock(returncode=0)
        job.proc.poll.return_value = 0
        entered, release = threading.Event(), threading.Event()
        errors = []

        def collect(_job):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test did not release metrics collection')
            return {'metrics': {'acc': 0.9}, 'metrics_source': 'synthetic fixture'}

        def wait():
            try:
                S._waiter(job, mock.Mock(), mock.Mock(), 10)
            except BaseException as error:
                errors.append(error)

        with mock.patch.object(S, 'collect_run', side_effect=collect), \
                mock.patch.object(S, '_after_run'), mock.patch.object(S, '_auto_clearml'), \
                mock.patch.dict(S.JOBS, {job.id: job}):
            worker = threading.Thread(target=wait)
            worker.start()
            try:
                self.assertTrue(entered.wait(5), 'Collector was never entered')
                self.assertEqual(job.status, 'running', 'Terminal status exposed incomplete evidence')
            finally:
                release.set()
                worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(job.status, 'done')
            saved = json.loads((job.run_dir / 'run.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['status'], 'done')
            self.assertEqual(saved['metrics']['acc'], 0.9)
            self.assertEqual(S.get_run(job.id)['metrics']['acc'], 0.9)
