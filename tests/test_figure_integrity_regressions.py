"""REAL_LOCAL software integrity with actual synthetic CPU experiments.

Fixture approvals are test inputs, never human scientific endorsement of a release.
"""
import _env
import asyncio
import json
from pathlib import Path
import statistics
import time
import unittest

from backend.agent import missions
from backend.core import config
from backend.execution import protocols
from backend.execution.protocol_contracts import ExperimentProtocol
from backend.figures import store, verifier
from backend.figures.contracts import FigureSpec
from backend.knowledge import research_store, verification
from backend.paper import results


class FigureIntegrity(unittest.TestCase):
    def setUp(self):
        started=time.monotonic()
        _env.isolate_config(self)
        _env.fresh_project('figure-raw-integrity',code_project=None)
        self.tid=research_store.save_topic(research_store.TopicInput(title='Synthetic denoising integrity fixture'))['id']
        protocol=protocols.create(ExperimentProtocol(topic_id=self.tid,hypothesis='A fixed smoothing filter affects generated image noise',seeds=[11]))
        protocol=protocols.approve(self.tid,protocol['id'],protocol['digest'],'Test fixture approval of synthetic CPU inputs, not scientific review')
        mission=protocols.mission_draft(self.tid,protocol['id'])
        missions.approve(self.tid,mission['id'],mission['payload']['plan_digest'],'Run the fixed CPU verification fixture')
        for _ in range(4):asyncio.run(missions.tick())
        completed=missions.get(mission['id'])
        self.assertEqual(completed['status'],'completed')
        self.reasoning_calls=completed['payload']['reasoning_calls']
        self.run=protocols.runs(self.tid)[0]
        self.series,self.labels,_=verifier.extract_experiment_metrics(self.tid,self.run['id'])
        self.cpu_validation_seconds=time.monotonic()-started

    def test_bounded_cpu_fixture_finishes_without_research_reasoning_calls(self):
        self.assertLess(self.cpu_validation_seconds,60,'The tiny CPU validation fixture must stay within its declared test budget')
        self.assertEqual(self.run['status'],'completed')
        self.assertEqual(self.reasoning_calls,0)
        self.assertTrue(all(trial['status']=='completed' for trial in self.run['trials']))

    def figure(self, **overrides):
        body={'topic_id':self.tid,'title':'Measured synthetic validation data','x_label':'Method','x_unit':'condition',
              'y_label':'PSNR','y_unit':'dB','source':{'kind':'experiment_artifact','experiment_id':self.run['id']},
              'outputs':['svg','png','pdf']}
        return store.create_or_regenerate(FigureSpec.model_validate({**body,**overrides}))

    def test_mse_is_recomputed_from_validation_not_invented_zeros(self):
        self.assertTrue(all(v>0 for v in self.series['mean_mse']))
        expected=[]
        expected_labels=[]
        for trial in self.run['trials']:
            if trial['payload']['request']['split']!='validation':continue
            expected_labels.append('alpha='+str(trial['payload']['request']['alpha']))
            actual=[m['mse'] for m in trial['payload']['summary']['per_seed'].values()]
            expected.append(round(statistics.mean(actual),8))
        self.assertEqual(self.labels,expected_labels)
        self.assertEqual(self.series['mean_mse'],expected)

    def test_alias_and_unknown_series_cannot_hide_wrong_metrics(self):
        for label in ('mean_psnr_db','Validation Mean PSNR (dB)','Unsupported invented metric'):
            figure=self.figure(source={'kind':'experiment_artifact','experiment_id':self.run['id'],
                'series':{label:[v+1000 for v in self.series['mean_psnr_db']]},'x_values':self.labels})
            self.assertEqual(figure['verification']['overall_status'],'failed')
            self.assertEqual(figure['verification']['tests']['numerical_values'],'fail')

    def test_forged_method_labels_cannot_pass_even_when_numbers_match(self):
        figure=self.figure(source={'kind':'experiment_artifact','experiment_id':self.run['id'],
            'series':{'mean_psnr_db':self.series['mean_psnr_db']},'x_values':['forged-'+str(i) for i in range(len(self.labels))]})
        self.assertEqual(figure['verification']['tests']['numerical_values'],'fail')

    def test_raw_artifact_tamper_invalidates_existing_figure_and_paper_use(self):
        figure=self.figure()
        artifact=Path(self.run['trials'][0]['payload']['artifact']['path'])
        if not artifact.is_absolute():artifact=research_store.store_dir()/artifact
        artifact.write_bytes(artifact.read_bytes()+b'\nTAMPERED')
        self.assertEqual(verification.verify_run(self.tid,self.run['id'])['status'],'failed')
        self.assertEqual(store.validate_figure_version(self.tid,figure['id'])['overall_status'],'failed')
        with self.assertRaisesRegex(ValueError,'changed'):
            store.attach_to_paper(self.tid,figure['id'])

    def test_approval_is_bound_to_exact_version_and_does_not_approve_another(self):
        first=self.figure()
        second=store.update_style(self.tid,first['id'],{'font_size_pt':10})
        store.approve_figure(self.tid,first['id'],2,'Fixture review of version2 only')
        self.assertIsNone(store.get_figure(self.tid,first['id'],1)['approval'])
        self.assertIsNotNone(store.get_figure(self.tid,first['id'],2)['approval'])
        with self.assertRaisesRegex(ValueError,'approval'):store.attach_to_paper(self.tid,first['id'],version=1)
        store.validate_figure_version(self.tid,first['id'],1)
        self.assertEqual(store.get_figure(self.tid,first['id'],2)['status'],'approved')
        self.assertEqual(second['current_version'],2)

    def test_tampered_approved_pdf_cannot_be_attached_or_exported(self):
        figure=self.figure()
        store.approve_figure(self.tid,figure['id'],1,'Fixture approval of unchanged bytes')
        pdf=store.export_file_path(self.tid,figure['id'],'pdf',1)
        pdf.write_bytes(pdf.read_bytes()+b'\nTAMPERED')
        with self.assertRaises(ValueError):store.attach_to_paper(self.tid,figure['id'])
        with self.assertRaises(ValueError):store.export_file_path(self.tid,figure['id'],'pdf',1)

    def test_paper_exports_include_real_approved_pdf_and_escape_caption(self):
        figure=self.figure(caption='Measured 5% change & validation_error')
        store.approve_figure(self.tid,figure['id'],1,'Fixture exact-version review')
        attached=store.attach_to_paper(self.tid,figure['id'])
        snippet=attached['latex_snippet']
        self.assertIn(r'5\% change \& validation\_error',snippet)
        files=results.figure_files([snippet])
        self.assertEqual(len(files),1)
        self.assertEqual(files[0][0].read_bytes()[:4],b'%PDF')
        self.assertEqual(files[0][1],f"figures/{figure['id']}_v0001.pdf")
        copied=results.copy_figures([snippet],config.data_dir()/'paper-build')
        self.assertEqual(copied,[files[0][1]])


if __name__=='__main__':unittest.main()
