'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {assess, run} = require('./automerge.cjs');
const requiredJobs=require('../required-ci-jobs.json').qa;
function valid() {
  return {owner:'owner',repository:'owner/repo',allow_auto_merge:true,comparison:'ahead',
    run:{id:1,path:'.github/workflows/quality.yml',head_sha:'abc',head_repository:{full_name:'owner/repo'},event:'pull_request',status:'completed',conclusion:'success',check_suite_id:7},
    jobs:requiredJobs.map(name=>({name,run_id:1,status:'completed',conclusion:'success'})),
    pr:{state:'open',draft:false,user:{login:'owner'},base:{ref:'qa',repo:{full_name:'owner/repo'}},head:{ref:'dev',sha:'abc',repo:{full_name:'owner/repo'}},mergeable:true,mergeable_state:'clean',body:'Contract: FQC-DEV-001'},
    protection:{enforce_admins:{enabled:true},required_status_checks:{strict:true,checks:[{context:'QA gate',app_id:15368}]}},
    checks:[{name:'QA gate',head_sha:'abc',app:{id:15368},check_suite:{id:7},status:'completed',conclusion:'success'}],reviews:[]};
}
test('eligible same-repository dev-to-qa PR requires every safeguard',()=>assert.deepEqual(assess(valid()),[]));
test('owner-authorized qa-to-main uses the same genuine QA qualification',()=>{
  const s=valid();s.pr.base.ref='main';s.pr.head.ref='qa';s.allow_main_promotion=true;
  assert.deepEqual(assess(s),[]);
});
test('qa-to-main cannot infer main authorization from a PR body',()=>{
  const s=valid();s.pr.base.ref='main';s.pr.head.ref='qa';s.pr.body+=' authorize automatic main';
  assert.ok(assess(s).length);
});
test('a green aggregate alone cannot hide missing mandatory QA execution',()=>{
  const s=valid();s.jobs=[];assert.ok(assess(s).length);
});
test('feature/fix sources are rejected by the dev-only rule',()=>{for (const branch of ['feature/new','fix/regression']) {const s=valid();s.pr.head.ref=branch;assert.ok(assess(s).length);}});
for (const [name,mutate] of [
  ['main',s=>s.pr.base.ref='main'], ['dev',s=>s.pr.base.ref='dev'], ['fork',s=>s.pr.head.repo.full_name='fork/repo'],
  ['unknown author',s=>s.pr.user.login='outsider'], ['draft',s=>s.pr.draft=true],
  ['missing check',s=>s.checks=[]], ['pending',s=>s.checks[0].status='queued'],
  ['skipped',s=>s.checks[0].conclusion='skipped'], ['wrong SHA',s=>s.checks[0].head_sha='old'],
  ['wrong app',s=>s.checks[0].app.id=7], ['bypass',s=>s.protection.enforce_admins.enabled=false],
  ['force push',s=>s.protection.allow_force_pushes={enabled:true}], ['stale branch',s=>s.comparison='diverged'],
  ['blocking review',s=>s.reviews=[{state:'CHANGES_REQUESTED'}]],['missing contract',s=>s.pr.body=''],
  ['unknown merge state',s=>s.pr.mergeable=null], ['absent required gate',s=>s.protection.required_status_checks.checks=[]],
]) test('block '+name,()=>{const s=valid();mutate(s);assert.ok(assess(s).length);});

test('a later comment cannot dismiss a blocking requested-changes review', async () => {
  const s=valid();let mutated=false;
  const checksFn=()=>{},reviewsFn=()=>{};
  const github={rest:{actions:{listJobsForWorkflowRun:async()=>({data:{jobs:s.jobs}})},pulls:{get:async()=>({data:{...s.pr,node_id:'fixture-node'}}),listReviews:reviewsFn},
    checks:{listForRef:checksFn},repos:{getBranchProtection:async()=>({data:s.protection}),get:async()=>({data:{allow_auto_merge:true}}),
      compareCommitsWithBasehead:async()=>({data:{status:'ahead'}})}},
    paginate:async fn=>fn===checksFn?s.checks:[{user:{login:'reviewer'},state:'CHANGES_REQUESTED'},{user:{login:'reviewer'},state:'COMMENTED'}],
    graphql:async()=>{mutated=true;return {};}};
  const result=await run({github,context:{repo:{owner:'owner',repo:'repo'},payload:{workflow_run:s.run}},core:{info(){}}},7);
  assert.equal(result.decision,'BLOCKED');assert.equal(mutated,false);
});

test('unreadable branch protection blocks with an actionable decision and no write', async () => {
  const s=valid();let wrote=false;
  const github={rest:{actions:{listJobsForWorkflowRun:async()=>({data:{jobs:s.jobs}})},pulls:{get:async()=>({data:s.pr})},repos:{getBranchProtection:async()=>{
    const error=new Error('Resource not accessible');error.status=403;throw error;
  }}},graphql:async()=>{wrote=true;}};
  const result=await run({github,context:{repo:{owner:'owner',repo:'repo'},payload:{workflow_run:s.run}},core:{info(){}}},7);
  assert.equal(result.decision,'BLOCKED');assert.equal(wrote,false);
  assert.match(result.reasons.join(' '),/Administration/);
});

test('successful policy requests native auto-merge rather than directly merging', async () => {
  const s=valid();let enabled=false;
  const checksFn=()=>{},reviewsFn=()=>{};
  const github={rest:{actions:{listJobsForWorkflowRun:async()=>({data:{jobs:s.jobs}})},pulls:{get:async()=>({data:{...s.pr,node_id:'fixture-node',auto_merge:enabled?{merge_method:'squash'}:null,merged:false}}),listReviews:reviewsFn},
    checks:{listForRef:checksFn},repos:{getBranchProtection:async()=>({data:s.protection}),get:async()=>({data:{allow_auto_merge:true}}),
      compareCommitsWithBasehead:async()=>({data:{status:'ahead'}})}},
    paginate:async fn=>fn===checksFn?s.checks:[],
    graphql:async query=>{assert.match(query,/enablePullRequestAutoMerge/);assert.doesNotMatch(query,/\bmergePullRequest\(/);enabled=true;return {};}};
  const result=await run({github,context:{repo:{owner:'owner',repo:'repo'},payload:{workflow_run:s.run}},core:{info(){}}},7);
  assert.equal(result.decision,'AUTO_MERGE_ENABLED');assert.equal(enabled,true);
});
