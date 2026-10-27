'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {publish}=require('./publish_release.cjs');
function fixture(t){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'phdlab-release-test-'));
 t.after(()=>{const target=path.resolve(directory);if(!target.startsWith(path.resolve(os.tmpdir())+path.sep)||!path.basename(target).startsWith('phdlab-release-test-'))throw Error('Unsafe fixture cleanup');fs.rmSync(target,{recursive:true,force:true});});
 const sha='a'.repeat(40),head='b'.repeat(40),assets=[];
 const manifest={version:'1.2.3',source_sha:sha,assets:['source','web'].map(kind=>{
  const name=`phdlab-1.2.3-${kind}.zip`,bytes=Buffer.from('MOCKED archive bytes '+kind);fs.writeFileSync(path.join(directory,name),bytes);
  return {name,size:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')};})};
 fs.writeFileSync(path.join(directory,'manifest.json'),JSON.stringify(manifest));
 const prsFn=()=>{},checksFn=()=>{},assetsFn=()=>{},runsFn=()=>{};const s={release:null,tag:null,writes:0,main:sha};
 const notFound=()=>{const e=Error('Missing');e.status=404;throw e;};
 const github={rest:{repos:{getBranch:async()=>({data:{protected:true,commit:{sha:s.main}}}),listPullRequestsAssociatedWithCommit:prsFn,
  getCommit:async()=>({data:{commit:{tree:{sha:'same-tree'}}}}),
  getReleaseByTag:async()=>s.release?{data:s.release}:notFound(),
  createRelease:async()=>{s.writes++;s.release={id:1,draft:true,html_url:'https://example.invalid/release'};return {data:s.release};},listReleaseAssets:assetsFn,
  uploadReleaseAsset:async r=>{s.writes++;assets.push({name:r.name,digest:'sha256:'+crypto.createHash('sha256').update(r.data).digest('hex')});return {data:{}};},
  updateRelease:async()=>{s.writes++;s.release={...s.release,draft:false};return {data:s.release};}},
  actions:{getWorkflow:async()=>({data:{id:5}}),listWorkflowRuns:runsFn},
  checks:{listForRef:checksFn},git:{getRef:async()=>s.tag?{data:{object:{type:'commit',sha:s.tag}}}:notFound()}},
  paginate:async fn=>fn===prsFn?[{number:9,merged_at:'now',merge_commit_sha:sha,base:{ref:'main'},head:{ref:'qa',sha:head,repo:{full_name:'owner/repo'}}}]:fn===runsFn?[{id:1,workflow_id:5,path:'.github/workflows/quality.yml',event:'pull_request',head_sha:head,head_branch:'qa',head_repository:{full_name:'owner/repo'},status:'completed',conclusion:'success',check_suite_id:7}]:fn===checksFn?['Development gate','QA gate'].map(name=>({name,head_sha:head,app:{id:15368},check_suite:{id:7},status:'completed',conclusion:'success'})):assets};
 return {directory,sha,s,assets,manifest,args:{github,context:{repo:{owner:'owner',repo:'repo'},ref:'refs/heads/main',sha}}};
}
test('qualified release uploads validated assets before publishing',async t=>{
 const f=fixture(t),r=await publish(f.args,f.directory,f.sha);assert.equal(r.decision,'PUBLISHED');assert.equal(f.s.release.draft,false);assert.equal(f.assets.length,3);
});
test('repeat publishing is idempotent and performs no additional writes',async t=>{
 const f=fixture(t);await publish(f.args,f.directory,f.sha);const writes=f.s.writes;await publish(f.args,f.directory,f.sha);assert.equal(f.s.writes,writes);
});
test('modified package is rejected before creating a release',async t=>{
 const f=fixture(t);fs.writeFileSync(path.join(f.directory,f.manifest.assets[0].name),'corrupt');await assert.rejects(publish(f.args,f.directory,f.sha),/Modified/);assert.equal(f.s.writes,0);
});
test('manifest path traversal is rejected before reading outside artifact directory',async t=>{
 const f=fixture(t);f.manifest.assets[0].name='../outside';fs.writeFileSync(path.join(f.directory,'manifest.json'),JSON.stringify(f.manifest));await assert.rejects(publish(f.args,f.directory,f.sha),/Unexpected/);assert.equal(f.s.writes,0);
});
test('a version tag cannot be moved to a different commit',async t=>{
 const f=fixture(t);f.s.tag='c'.repeat(40);await assert.rejects(publish(f.args,f.directory,f.sha),/different commit/);assert.equal(f.s.writes,0);
});
test('published mismatched assets cannot be overwritten',async t=>{
 const f=fixture(t);await publish(f.args,f.directory,f.sha);const writes=f.s.writes;f.assets[0].digest='sha256:wrong';await assert.rejects(publish(f.args,f.directory,f.sha),/digest differs/);assert.equal(f.s.writes,writes);
});
test('a stale main commit never publishes',async t=>{
 const f=fixture(t);f.s.main='f'.repeat(40);await assert.rejects(publish(f.args,f.directory,f.sha),/current protected main/);assert.equal(f.s.writes,0);
});
test('omitting an archive checksum cannot bypass integrity validation',async t=>{
 const f=fixture(t);delete f.manifest.assets[0].sha256;fs.writeFileSync(path.join(f.directory,'manifest.json'),JSON.stringify(f.manifest));await assert.rejects(publish(f.args,f.directory,f.sha),/required archive checksum/);assert.equal(f.s.writes,0);
});
