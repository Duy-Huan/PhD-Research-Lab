"""Explicit offline controller fixtures; never proof of GitHub merging or AI execution."""
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class PromotionController(unittest.TestCase):
    def test_same_tree_native_merge_fast_forwards_only_dev_and_preserves_dirty_work(self):
        from devtools.verification.promotion import sync_dev,git
        with tempfile.TemporaryDirectory(prefix='phdlab-sync-fixture-') as directory:
            root=Path(directory)
            subprocess.run(['git','init','-q','--initial-branch=dev',str(root)],check=True,capture_output=True)
            for key,value in [('user.name','Fixture'),('user.email','fixture@example.invalid')]:git(root,'config',key,value)
            (root/'source.txt').write_text('Same tested source')
            git(root,'add','source.txt');git(root,'commit','-qm','Private fixture baseline')
            before=git(root,'rev-parse','HEAD');tree=git(root,'rev-parse','HEAD^{tree}')
            merge=subprocess.check_output(['git','commit-tree',tree,'-p',before,'-m','Observed same-tree merge fixture'],cwd=root,text=True).strip()
            git(root,'remote','add','origin','https://github.com/Duy-Huan/PhD-Research-Lab.git')
            git(root,'update-ref','refs/remotes/origin/qa',merge)
            mutations=[]
            def fixture_git(path,*args):
                if args[0] in ('fetch','push'):mutations.append(args);return ''
                return git(path,*args)
            with patch('devtools.verification.promotion.git',side_effect=fixture_git):
                result=sync_dev(root,'qa',merge)
                self.assertEqual(result['dev_head'],merge);self.assertEqual(git(root,'rev-parse','HEAD^{tree}'),tree)
                self.assertEqual(mutations,[('fetch','--no-tags','origin','qa'),('push','origin','dev')])
                (root/'source.txt').write_text('Owner uncommitted work')
                with self.assertRaises(ValueError):sync_dev(root,'qa',merge)
                self.assertEqual((root/'source.txt').read_text(),'Owner uncommitted work')
                self.assertEqual(len(mutations),2)

    def test_native_request_uses_only_the_qualifying_run_and_never_bypasses_failed_jobs(self):
        from devtools.verification.promotion import ensure_native
        names=json.loads((ROOT/'.github/required-ci-jobs.json').read_text())['qa']
        repo='Duy-Huan/PhD-Research-Lab'
        pr={'number':1,'node_id':'unit-fixture','state':'open','draft':False,'user':{'login':'Duy-Huan'},
            'base':{'ref':'qa','repo':{'full_name':repo}},'head':{'ref':'dev','sha':'head','repo':{'full_name':repo}},
            'mergeable':True,'mergeable_state':'clean','body':'Contract: FQC-AUTO-PROMOTION-001'}
        run={'id':1,'head_sha':'head','head_branch':'dev','head_repository':{'full_name':repo},'workflow_id':5,
             'event':'pull_request','path':'.github/workflows/quality.yml','status':'completed','conclusion':'success','check_suite_id':7}
        class FixtureAPI:
            def __init__(self):
                self.jobs=[{'name':name,'run_id':1,'status':'completed','conclusion':'success'} for name in names]
                self.mutations=[]
            def request(self,path,body=None):
                if path=='/graphql':self.mutations.append(body);return {'data':{}}
                if path=='/actions/workflows/quality.yml':return {'id':5}
                if path.startswith('/actions/workflows/quality.yml/runs?'):return {'workflow_runs':[run]}
                if path=='/branches/qa/protection':return {'enforce_admins':{'enabled':True},'required_status_checks':{
                    'strict':True,'checks':[{'context':'QA gate','app_id':15368}]}}
                if path.startswith('/compare/'):return {'status':'ahead'}
                if path=='':return {'allow_auto_merge':True}
                if path=='/pulls/1':return pr
                raise AssertionError('Unexpected API operation: '+path)
            def pages(self,path,field):
                if '/jobs?' in path:return self.jobs
                if '/check-runs?' in path:return [
                    {'name':'QA gate','head_sha':'head','app':{'id':15368},'check_suite':{'id':7},'status':'completed','conclusion':'success'},
                    {'name':'QA gate','head_sha':'head','app':{'id':15368},'check_suite':{'id':99},'status':'completed','conclusion':'skipped'}]
                if path.endswith('/reviews'):self.assert_array_pagination=field is None;return []
                raise AssertionError(path)
        api=FixtureAPI();policy={'authorize_native_main':True}
        self.assertEqual(ensure_native(api,ROOT,pr,policy,False)['phase'],'ELIGIBLE')
        self.assertTrue(api.assert_array_pagination);self.assertEqual(api.mutations,[])
        api.jobs[-1]['conclusion']='skipped'
        self.assertEqual(ensure_native(api,ROOT,pr,policy,True)['phase'],'BLOCKED')
        self.assertEqual(api.mutations,[])
        api.jobs[-1]['conclusion']='success'
        self.assertEqual(ensure_native(api,ROOT,pr,policy,True)['phase'],'NATIVE_AUTO_MERGE_REQUESTED')
        self.assertEqual(len(api.mutations),1)
        self.assertIn('enablePullRequestAutoMerge',api.mutations[0]['query'])
        self.assertNotIn('mergePullRequest(',api.mutations[0]['query'])

    def test_existing_api_pagination_supports_array_review_responses(self):
        from devtools.verification.ci_repair import GitHub
        class FixtureAPI:
            def request(self,path):return [{'state':'CHANGES_REQUESTED'}]
        self.assertEqual(GitHub.pages(FixtureAPI(),'/pulls/1/reviews',None),[{'state':'CHANGES_REQUESTED'}])

    def test_latest_matching_run_cannot_fall_back_to_an_older_success(self):
        from devtools.verification.promotion import latest_run
        def run(number,**patch):
            return {'id':number,'head_sha':'head','head_branch':'dev','event':'pull_request',
                    'path':'.github/workflows/quality.yml','workflow_id':5,
                    'head_repository':{'full_name':'Duy-Huan/PhD-Research-Lab'},'conclusion':'success'} | patch
        runs=[run(1),run(2,conclusion='failure'),run(3,head_sha='other'),run(4,event='push')]
        self.assertEqual(latest_run(runs,'head','dev',5)['id'],2)
        self.assertIsNone(latest_run(runs,'unknown','dev',5))
        self.assertIsNone(latest_run([run(8,head_repository={'full_name':'external/fork'})],'head','dev',5))

    def test_explicit_owner_policy_and_unchanged_trusted_controller_are_required(self):
        from devtools.verification.promotion import policy_errors,code_digests
        policy={'repository':'Duy-Huan/PhD-Research-Lab','root':str(ROOT.resolve()),
                'authorize_native_main':True,'code':code_digests(ROOT)}
        self.assertEqual(policy_errors(ROOT,policy),[])
        for patch in [{'authorize_native_main':False},{'root':'C:/untrusted'},
                      {'repository':'external/fork'},{'code':{}}]:
            self.assertTrue(policy_errors(ROOT,policy | patch))

    def test_persistent_state_is_atomic_and_corruption_never_resets_authority(self):
        from devtools.verification.promotion import save_state,read_state
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            first={'stopped':True,'merges':[{'pr':7,'merge_sha':'actual-fixture-value'}]}
            save_state(path,first);self.assertEqual(read_state(path),first)
            path.write_text('{corrupt')
            with self.assertRaises(ValueError):read_state(path)

    def test_shared_node_policy_never_qualifies_a_merged_flag_or_skipped_qa(self):
        from devtools.verification.promotion import assess
        names=json.loads((ROOT/'.github/required-ci-jobs.json').read_text())['qa']
        snapshot={'repository':'Duy-Huan/PhD-Research-Lab','expected_head_sha':'head',
                  'run':{'id':1,'head_sha':'head','head_repository':{'full_name':'Duy-Huan/PhD-Research-Lab'},
                         'event':'pull_request','path':'.github/workflows/quality.yml','status':'completed','conclusion':'success'},
                  'jobs':[{'name':name,'run_id':1,'status':'completed','conclusion':'success'} for name in names]}
        self.assertEqual(assess(ROOT,snapshot,'qualification')['decision'],'ELIGIBLE')
        for status in ['skipped','failure','cancelled',None]:
            data=json.loads(json.dumps(snapshot));data['jobs'][-1]['conclusion']=status
            self.assertEqual(assess(ROOT,data,'qualification')['decision'],'BLOCKED')
        self.assertEqual(assess(ROOT,{'merged':True},'qualification')['decision'],'BLOCKED')

