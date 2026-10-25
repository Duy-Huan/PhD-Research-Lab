'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {qualify}=require('./release_provenance.cjs');
function fixture(){
 const sha='a'.repeat(40),head='b'.repeat(40);const prsFn=()=>{},checksFn=()=>{};
 const s={protected:true,main:sha,prs:[{number:9,merged_at:'now',merge_commit_sha:sha,base:{ref:'main'},head:{ref:'qa',sha:head,repo:{full_name:'owner/repo'}}}],
  checks:['Development gate','QA gate'].map(name=>({name,head_sha:head,app:{id:15368},status:'completed',conclusion:'success'})),sameTree:true};
 const github={rest:{repos:{getBranch:async()=>({data:{protected:s.protected,commit:{sha:s.main}}}),listPullRequestsAssociatedWithCommit:prsFn,
  getCommit:async({ref})=>({data:{commit:{tree:{sha:!s.sameTree && ref===sha?'different':'tree'}}}})},checks:{listForRef:checksFn}},
  paginate:async fn=>fn===prsFn?s.prs:s.checks};
 return {s,args:{github,context:{repo:{owner:'owner',repo:'repo'},ref:'refs/heads/main',sha}},sha};
}
test('qualified exact main source needs no second publication approval',async()=>{const f=fixture();assert.equal((await qualify(f.args,f.sha)).sha,f.sha);});
for(const [name,change] of [
 ['unprotected',f=>f.s.protected=false],['wrong ref',f=>f.args.context.ref='refs/heads/dev'],
 ['stale commit',f=>f.s.main='c'.repeat(40)],['absent promotion',f=>f.s.prs=[]],
 ['wrong source branch',f=>f.s.prs[0].head.ref='feature/direct'],['fork',f=>f.s.prs[0].head.repo.full_name='outside/repo'],
 ['missing gate',f=>f.s.checks.pop()],['skipped gate',f=>f.s.checks[1].conclusion='skipped'],
 ['wrong app',f=>f.s.checks[0].app.id=7],['wrong tested SHA',f=>f.s.checks[1].head_sha='old'],
 ['changed merge tree',f=>f.s.sameTree=false]
])test('reject '+name,async()=>{const f=fixture();change(f);await assert.rejects(qualify(f.args,f.sha));});
