"""Assemble recorded executions; never fabricate unavailable coverage or live evidence."""
import hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from devtools.verification.comparison import compare

folder=Path(sys.argv[1])
prep=json.loads((folder/'preparation.json').read_text(encoding='utf-8'))
environment=json.loads((folder/'environment.json').read_text(encoding='utf-8'))
def digest(files,root):
 data={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n') if p.suffix in ['.py','.ts','.tsx','.js','.cjs','.mjs','.json','.md','.txt','.lock','.yml','.toml'] or p.name=='.coveragerc' else p.read_bytes()).hexdigest() for p in sorted(files) if p.is_file()}
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),data
def production(root):
 paths=list((root/'backend').rglob('*.py'))
 paths += [p for p in (root/'frontend/src').rglob('*') if p.is_file() and not p.name.endswith(('.test.ts','.test.tsx','.pyc')) and '/src/test/' not in p.as_posix() and '__pycache__' not in p.parts]
 paths += [root/p for p in ['cli.py','start.py','frontend/react.html'] if (root/p).is_file()]
 return digest(paths,root)
def browser_cases(suite):
 cases=[]
 for spec in suite.get('specs',[]):
  for test in spec.get('tests',[]):
   results=test.get('results',[])
   status='PASS' if test.get('status')=='expected' and results and all(r['status']=='passed' for r in results) else 'SKIP' if test.get('status')=='skipped' else 'FAIL'
   cases.append({'id':'playwright.'+spec['title'],'status':status,'mode':'REAL_LOCAL_BROWSER','details':[r.get('error') for r in results if r.get('error')]})
 for child in suite.get('suites',[]):cases.extend(browser_cases(child))
 return cases
groups=[
 ('BASE-PDF-001','P1','Selected PDF loses results after page three','test_context_intelligence_audit.ContextIntelligenceAudit.test_expanded_selected_paper_includes_results_after_page_three'),
 ('BASE-REPLAY-001','P1','Reproducibility pack fabricates unexecuted metrics','test_evidence_integrity_regressions.EvidenceIntegrity.test_export_has_no_invented_metrics_and_replay_never_copies_expected'),
 ('BASE-CHECKSUM-001','P1','Empty checksum manifest is accepted','test_evidence_integrity_regressions.EvidenceIntegrity.test_empty_checksum_manifest_and_path_escape_fail_closed'),
 ('BASE-REMOTE-001','P1','Remote compute context raises missing-json NameError','test_latest_integration_regressions.LatestIntegration.test_remote_compute_context_preserves_record_identity_and_unverified_status'),
 ('BASE-METADATA-001','P1','Reference metadata is invented','test_evidence_integrity_regressions.EvidenceIntegrity.test_library_does_not_invent_authors_venue_year_or_ranking_from_hostname'),
 ('BASE-CLI-001','P2','CLI language/settings parity fails','test_cli_settings_parity.CLISettingsParity.test_language_switch_persists_in_web_and_new_terminal_and_keeps_session'),
 ('BASE-ACCESSIBILITY-001','P2','Workspace controls fail accessible-name requirements','playwright.UI-ACCESSIBLE-NAMES-001: WCAG automated scan of workspace and settings (en)'),
 ('LEGACY-RUN-PUBLISH-001','P1','Terminal status precedes metrics persistence','test_sandbox_completion_regressions.SandboxCompletion.test_terminal_status_is_published_only_after_metrics_are_persisted')]
def observed_states(cases):
 rank={'PASS':0,'SKIP':1,'NOT_RUN':2,'BLOCKED':3,'UNVERIFIED':3,'FAIL':4,'ERROR':5}
 result={}
 for c in cases:
  status=c.get('status','NOT_RUN')
  if rank.get(status,2)>=rank.get(result.get(c['id']),-1):result[c['id']]=status
 return result

subjects={}
for side in ('main','candidate'):
 root=Path(prep[side+'_root']);out=root/'output/playwright/same-suite';cases=[];coverage={};reports={}
 for component in ('backend','frontend','uat'):
  p=out/component/'report.json'
  if not p.exists():continue
  d=json.loads(p.read_text(encoding='utf-8'));reports[component]={'decision':d.get('decision'),'counts':d.get('counts'),'source':d.get('source',{}).get('sha256'),'source_stable':d.get('source_stable'),'steps':d.get('steps',[])}
  cases.extend(d.get('cases',[]));coverage.update(d.get('coverage',{}))
 p=out/'browser/results.json'
 browser=json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {}
 for suite in browser.get('suites',[]):cases.extend(browser_cases(suite))
 p=out/'browser/boundaries.json'
 if p.is_file():cases.extend(json.loads(p.read_text(encoding='utf-8')).get('cases',[]))
 probe=json.loads((folder/(side+'-python311-compatibility.log')).read_text(encoding='utf-8'))
 defects=[];states=observed_states(cases)
 for id,severity,description,case in groups:
  if states.get(case) in ('FAIL','ERROR'):
   defects.append({'id':id,'severity':severity,'description':description,'status':'CONFIRMED_UNRESOLVED','test_id':case,'evidence':str(out)})
 if probe['errors']:defects.append({'id':'LEGACY-PY311-001','severity':'P1','description':'Supported Python3.11 cannot compile production source','status':'CONFIRMED_UNRESOLVED','evidence':str(folder/(side+'-python311-compatibility.log'))})
 after=production(root);before=prep['production_before'][side]
 subjects[side]={'manifest':{k:prep[k] for k in ['suite_sha256','policy_sha256']},
  'source':{'head':prep['original'][side+'_head'],'production_sha256':after[0],'stable':list(after)==before,'instrumentation_scope':prep['scope']},
  'cases':cases,'coverage':coverage,'confirmed_defects':defects,'defect_inventory_complete':False,
  'full_research_acceptance':'BLOCKED: live/provider/research qualification unavailable; exhausted AI-UAT budget is not reset',
  'reports':reports,'browser_stats':browser.get('stats'),'python311':probe}
 subjects[side]['manifest']['environment_sha256']=environment['sha256']
 (folder/(side+'-subject.json')).write_text(json.dumps(subjects[side],indent=2)+'\n',encoding='utf-8')
critical=json.loads((ROOT/'docs/qa/CRITICAL_SOFTWARE_CHECKS.json').read_text(encoding='utf-8'))
result=compare(subjects['main'],subjects['candidate'],critical)
left=observed_states(subjects['main']['cases']);right=observed_states(subjects['candidate']['cases'])
result['observed_transitions']={'main_failure_candidate_pass':[k for k in left if left[k] in ['FAIL','ERROR'] and right.get(k)=='PASS'],
 'main_pass_candidate_failure':[k for k in right if right[k] in ['FAIL','ERROR'] and left.get(k)=='PASS'],
 'candidate_failures':[k for k in right if right[k] in ['FAIL','ERROR']],
 'candidate_skipped':[k for k in right if right[k]=='SKIP'],
 'classification':'Transitions are observations, not one confirmed defect per test; loader/API incompatibilities stay distinct'}
(folder/'comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({s:{k:result[s][k] for k in ['critical_pass_rate','known_confirmed_unresolved_defects','coverage','execution_counts']} for s in ['main','candidate']}))
