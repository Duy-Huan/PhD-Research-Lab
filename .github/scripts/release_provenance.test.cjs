'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {qualify}=require('./release_provenance.cjs');
function fixture(){
 const sha='a'.repeat(40),head='b'.repeat(40);const prsFn=()=>{},checksFn=()=>{},runsFn=()=>{};
 const s={protected:true,main:sha,prs:[{number:9,merged_at:'now',merge_commit_sha:sha,base:{ref:'main'},head:{ref:'qa',sha:head,repo:{full_name:'owner/repo'}}}],
  runs:[{id:1,workflow_id:5,path:'.github/workflows/quality.yml',event:'pull_request',head_sha:head,head_branch:'qa',head_repository:{full_name:'owner/repo'},status:'completed',conclusion:'success',check_suite_id:7}],
  checks:['Development gate','QA gate'].map(name=>({name,head_sha:head,app:{id:15368},check_suite:{id:7},status:'completed',conclusion:'success'})),sameTree:true};
 const github={rest:{repos:{getBranch:async()=>({data:{protected:s.protected,commit:{sha:s.main}}}),listPullRequestsAssociatedWithCommit:prsFn,
  getCommit:async({ref})=>({data:{commit:{tree:{sha:!s.sameTree && ref===sha?'different':'tree'}}}})},checks:{listForRef:checksFn}},
  paginate:async fn=>fn===prsFn?s.prs:fn===runsFn?s.runs:s.checks};
 github.rest.actions={getWorkflow:async()=>({data:{id:5}}),listWorkflowRuns:runsFn};
 return {s,args:{github,sleep:async()=>{},context:{repo:{owner:'owner',repo:'repo'},ref:'refs/heads/main',sha}},sha};
}
test('qualified exact main source needs no second publication approval',async()=>{const f=fixture();assert.equal((await qualify(f.args,f.sha)).sha,f.sha);});
test('latest failed QA run cannot reuse older successful contexts',async()=>{const f=fixture();f.s.runs.push({...f.s.runs[0],id:2,conclusion:'failure'});await assert.rejects(qualify(f.args,f.sha));});
test('unrelated dev-push skipped context cannot replace actual QA result',async()=>{const f=fixture();f.s.checks.push({...f.s.checks[1],check_suite:{id:99},conclusion:'skipped'});assert.equal((await qualify(f.args,f.sha)).sha,f.sha);});
test('successful contexts from another workflow suite cannot qualify',async()=>{const f=fixture();f.s.checks.forEach(c=>c.check_suite.id=99);await assert.rejects(qualify(f.args,f.sha));});
for(const [name,change] of [
 ['unprotected',f=>f.s.protected=false],['wrong ref',f=>f.args.context.ref='refs/heads/dev'],
 ['stale commit',f=>f.s.main='c'.repeat(40)],['absent promotion',f=>f.s.prs=[]],
 ['wrong source branch',f=>f.s.prs[0].head.ref='feature/direct'],['fork',f=>f.s.prs[0].head.repo.full_name='outside/repo'],
 ['missing gate',f=>f.s.checks.pop()],['skipped gate',f=>f.s.checks[1].conclusion='skipped'],
 ['wrong app',f=>f.s.checks[0].app.id=7],['wrong tested SHA',f=>f.s.checks[1].head_sha='old'],
 ['changed merge tree',f=>f.s.sameTree=false]
])test('reject '+name,async()=>{const f=fixture();change(f);await assert.rejects(qualify(f.args,f.sha));});

test('delayed association is retried without weakening QA checks',async()=>{const f=fixture();const original=f.args.github.paginate;let calls=0,waits=[];f.args.sleep=async ms=>waits.push(ms);f.args.github.paginate=async(fn,...rest)=>fn===f.args.github.rest.repos.listPullRequestsAssociatedWithCommit && ++calls<3?[]:original(fn,...rest);assert.equal((await qualify(f.args,f.sha)).sha,f.sha);assert.deepEqual(waits,[1000,2000]);});
test('absent association stops after bounded six attempts',async()=>{const f=fixture();f.s.prs=[];let waits=[];f.args.sleep=async ms=>waits.push(ms);await assert.rejects(qualify(f.args,f.sha),/No confirmed/);assert.deepEqual(waits,[1000,2000,4000,8000,16000]);});
test('main moving during retry fails closed',async()=>{const f=fixture();f.s.prs=[];f.args.sleep=async()=>{f.s.main='c'.repeat(40)};await assert.rejects(qualify(f.args,f.sha),/main changed/);});
