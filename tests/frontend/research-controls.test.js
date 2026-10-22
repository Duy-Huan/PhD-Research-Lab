'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {boot,fixtures,R}=require('./harness');
const tid='topic-controls', base='/api/research/topics/'+tid;
const topic={id:tid,title:'Human-authored topic',description:'Original research',sources:['arxiv'],cadence:'manual',enabled:false,pdf_limit:10};
const paper={id:'p',title:'Original paper',year:0,venue:'',sources:['arxiv'],level:0,state:'candidate',oa_locations:[],flags:[],association:{review_reset:{reason:'new evidence'}},abstract:'',versions:[{id:'v1',source:'arxiv',version:1},{id:'v2',source:'arxiv',version:2,document:{status:'ready',sha256:'digest'}}]};
async function page(routes={},lang='en') {
  const h=await boot({storage:{'pl.lang':lang},hash:'#/chat/'+fixtures.meta.session,routes:{
    'GET /api/config':()=>({...fixtures.get('GET /api/config'),ui:{language:lang}}),
    'GET /api/chat/sessions/:id':()=>({...fixtures.get('GET /api/chat/sessions/:id'),topic_id:tid}),
    'GET /api/research/topics':()=>({topics:[topic],schedules:{[tid]:{last_run:'2026-10-21',next_run:'2026-10-23',last_status:'completed'}}}),
    ['GET '+base+'/papers']:()=>({papers:[paper],total:1}),
    ['GET '+base+'/workspaces']:()=>({workspaces:[]}),
    ['GET '+base+'/artifacts']:()=>({artifacts:[]}),
    ['GET '+base+'/provenance']:()=>({events:[]}),
    ['GET '+base+'/findings']:()=>({findings:[]}),
    ['GET '+base+'/missions']:()=>({missions:[]}),
    ['GET '+base+'/protocols']:()=>({protocols:[],runs:[]}),
    ['GET '+base+'/claims']:()=>({claims:[]}),
    'GET /api/research/os-settings':()=>({enabled:true,team_enabled:true,multi_team_enabled:true}),
    'GET /api/research/charters':()=>({charters:[]}),
    'GET /api/research/jobs':()=>({jobs:[]}),
    ...routes
  }}); return h;
}
const click=(h,text)=>h.clickText('.research-body button',text,25);
const save=(h,text='Save')=>h.clickText('.dialog-f button',text,30);
const field=(h,text)=>h.byText('.dialog label.field',text).querySelector('input,textarea,select');
const close=async h=>{if(h.$('.dialog'))await h.key('.dialog','Escape');};

test('stale research requests cannot overwrite a newly selected drawer',async()=>{
  const h=await page(); const PL=h.w.PL;
  const cases=[['papers',base+'/papers',{papers:[],total:0}],['workspaces',base+'/workspaces',{workspaces:[]}],['artifacts',base+'/artifacts',{artifacts:[]}],['jobs','/api/research/jobs',{jobs:[]}],['missions',base+'/missions',{missions:[]}],['monitor',base+'/missions',{missions:[]}],['teams',base+'/missions',{missions:[]}],['workstreams',base+'/missions',{missions:[]}],['protocols',base+'/protocols',{protocols:[],runs:[]}],['claims',base+'/claims',{claims:[]}]];
  for(const [mode,url,result] of cases){
    let release,seen=false;
    h.server.on('GET '+url,()=>{seen=true;return new Promise(resolve=>{release=()=>resolve(result);});});
    const opening=PL.research.open(mode); await h.until(()=>seen);
    await PL.research.open('topics');release();await opening;
    assert.equal(h.$('.research-body').dataset.mode,'topics',mode);
    h.server.on('GET '+url,()=>result);
  }
  let release,seen=false;
  h.server.on('GET /api/research/topics',()=>{if(seen)return {topics:[topic]};seen=true;return new Promise(resolve=>{release=()=>resolve({topics:[topic]});});});
  const opening=PL.research.open('papers');await h.until(()=>seen);await PL.research.open('topics');release();await opening;assert.equal(h.$('.research-body').dataset.mode,'topics');
  const collaboration={id:'m',payload:{spec:{collaboration:{workstreams:[]}}}};
  h.server.on('GET /api/research/topics',()=>({topics:[topic]}));
  h.server.on('GET '+base+'/missions',()=>({missions:[collaboration]}));seen=false;
  h.server.on('GET '+base+'/missions/m/workstreams',()=>{seen=true;return new Promise(resolve=>{release=()=>resolve({});});});
  const multi=PL.research.open('workstreams');await h.until(()=>seen);await PL.research.open('topics');release();await multi;assert.equal(h.$('.research-body').dataset.mode,'topics');
  assert.ok(h.server.last('GET',base+'/missions/m/workstreams'));
});

test('paper search cancels stale responses and reports current errors only; live jobs stay project scoped',async()=>{
  const h=await page();const PL=h.w.PL;await PL.research.open('papers');
  let release,seen=false;
  h.server.on('GET '+base+'/papers',()=>{seen=true;return new Promise(resolve=>{release=resolve;});});
  await h.input('.research-filters input[type=search]','slow');await h.until(()=>seen);
  h.server.on('GET '+base+'/papers',()=>({papers:[],total:0}));await h.input('.research-filters input[type=search]','latest');await h.idle(30);
  release({papers:[paper],total:1});await h.idle(25);assert.match(h.$('.research-body').textContent,/No results/);
  h.server.on('GET '+base+'/papers',()=>R({detail:'Search unavailable'},503));await h.input('.research-filters input[type=search]','error');await h.idle(25);assert.match(h.$('.research-body').textContent,/Search unavailable/);
  h.server.on('GET '+base+'/papers',()=>{const e=new Error('cancelled');e.name='AbortError';return e;});await h.input('.research-filters input[type=search]','abort');await h.idle(25);assert.match(h.$('.research-body').textContent,/Search unavailable/);
  PL.store.set('panel',null);PL.emit({type:'research.updated'});
  PL.store.set('panel',{kind:'research',arg:'papers'});PL.emit({type:'research.updated'});
  PL.store.set('panel',{kind:'research',arg:'jobs'});h.$('#panel').hidden=true;PL.emit({type:'research.updated'});
  h.$('#panel').hidden=false;PL.emit({type:'research.updated',project_dir:'another-project'});
  PL.emit({type:'research.updated',project_dir:PL.state.project.data_dir});await h.idle(25);assert.equal(h.$('.research-body').dataset.mode,'jobs');
  PL.state=null;PL.emit({type:'research.updated'});await h.idle(25);assert.equal(h.$('.research-body').dataset.mode,'jobs');
  PL.state={project:null};PL.emit({type:'research.updated'});await h.idle(25);
  await h.clickText('.research-nav button','Topics');assert.equal(h.$('.research-body').dataset.mode,'topics');
  PL.research.flags=null;PL.research.tid='unknown-topic';await PL.research.open('papers');assert.equal(h.$('.research-context').textContent,'unknown-topic');
  PL.research.tid=tid;h.server.on('GET /api/research/topics',()=>({topics:[]}));await PL.research.open('monitor');await click(h,'New project charter');assert.match(h.$('.dialog textarea').value,/Research topic/);await close(h);
  PL.research.reset();assert.equal(PL.research.tid,'');
});

test('Topic create/edit validates persistence, semicolon fields, schedule and integration status',async()=>{
  let enabled=false, fail=false;
  const h=await page({
    'GET /api/research/topics':()=>({topics:[{...topic,enabled}],schedules:{}}),
    'POST /api/research/topics':()=>fail?R({detail:'Title required'},422):{id:tid},
    ['PUT '+base]:req=>{enabled=req.body.enabled;return {id:tid};},
    'GET /api/research/capabilities':()=>({plugins:[{id:'local',version:'1',status:'ready'},{id:'missing',status:'unavailable'}],retrieval:'offline'})
  });
  await h.w.PL.research.open('topics');
  await click(h,'New Topic'); field(h,'Title').value='New title'; field(h,'Keywords').value='MRI; ; noise';
  fail=true; await save(h); assert.match(h.toast(),/Title required/); assert.ok(h.$('.dialog'));
  fail=false; await save(h); assert.deepEqual(h.server.last('POST','/api/research/topics').body.keywords,['MRI','noise']);
  await click(h,'Edit'); field(h,'Title').value='Edited'; await save(h);
  assert.equal(h.server.last('PUT',base).body.title,'Edited');
  await click(h,'Enable schedule'); assert.equal(enabled,true);
  await click(h,'Pause'); assert.equal(enabled,false);
  await click(h,'Local integration'); assert.match(h.$('.dialog').textContent,/not installed/); await close(h);
  h.w.PL.research.flags={topic_scheduler_ui:false}; await h.w.PL.research.open('topics'); await click(h,'Edit');
  assert.equal(field(h,'Cadence').disabled,true); assert.equal(field(h,'Schedule enabled').disabled,true); await close(h);
  h.w.PL.chat.busy=true; await h.w.PL.research.switchTopic(tid); assert.match(h.toast(),/Stop or wait/);
  h.w.PL.chat.busy=false; await h.w.PL.research.switchTopic(''); assert.equal(h.server.last('POST','/api/chat/sessions').body.topic_id,'');
  h.w.PL.research.tid=tid; await h.w.PL.research.open('topics'); await click(h,'Open Topic'); assert.equal(h.server.last('POST','/api/chat/sessions').body.topic_id,tid);
  await h.w.PL.research.open('topics'); await click(h,'Project chat'); assert.equal(h.server.last('POST','/api/chat/sessions').body.topic_id,'');
});

test('paper details, evidence, bulk controls and filter states preserve scientific content',async()=>{
  let empty=false;
  const h=await page({['GET '+base+'/papers']:()=>({papers:empty?[]:[paper],total:empty?0:1}),['GET '+base+'/evidence']:()=>({evidence:[{id:'e',paper_id:'p',version_id:'v2',page:2,text:'Exact evidence'},{id:'other',paper_id:'other',text:'not included'}]})});
  const PL=h.w.PL;
  await PL.research.open();
  await click(h,'Versions & evidence'); assert.match(h.$('.dialog').textContent,/Abstract unavailable/); assert.equal(h.$('.dialog a').textContent,'Open PDF');
  await h.input('.dialog input','exact'); await h.clickText('.dialog button','Evidence'); assert.match(h.$('.dialog').textContent,/Exact evidence/); assert.doesNotMatch(h.$('.dialog').textContent,/not included/); await close(h);
  await click(h,'Dry run'); assert.equal(h.server.last('POST',base+'/discover').body.dry_run,true);
  await PL.research.open('papers'); await click(h,'Discover now'); assert.ok(h.server.last('POST',base+'/discover'));
  await PL.research.open('papers'); await click(h,'Import existing'); assert.ok(h.server.last('POST',base+'/papers/import-library'));
  await h.clickText('.research-bulk button','Accept'); assert.match(h.toast(),/Select papers/);
  await h.click('.research-card input');
  PL.prompt=async()=>null; await h.clickText('.research-bulk button','L4 attest'); assert.equal(h.server.last('POST',base+'/papers/bulk'),undefined);
  PL.prompt=async()=> 'Exact human note'; await h.clickText('.research-bulk button','L4 attest'); assert.equal(h.server.last('POST',base+'/papers/bulk').body.note,'Exact human note');
  PL.confirm=async()=>false; await h.clickText('.research-bulk button','Dismiss'); assert.equal(h.server.last('POST',base+'/papers/bulk').body.action,'verify');
  PL.confirm=async()=>true; await h.clickText('.research-bulk button','Dismiss'); assert.equal(h.server.last('POST',base+'/papers/bulk').body.action,'dismiss');
  PL.prompt=async()=>null; await h.clickText('.research-bulk button','Add to another');
  PL.prompt=async()=> 'target-topic'; await h.clickText('.research-bulk button','Add to another'); assert.equal(h.server.last('POST',base+'/papers/bulk').body.target_topic_id,'target-topic');
  await h.clickText('.research-bulk button','Compare with AI'); assert.match(h.$('#input').value,/^\/compare/);
  await h.clickText('.research-bulk button','Review with AI'); assert.match(h.$('#input').value,/^\/review/);
  await h.click('.research-card input'); assert.equal(PL.research.selected.size,0);
  PL.research.ai('review'); assert.match(h.toast(),/Select sources/);
  PL.research.flags={contextual_actions:false}; PL.research.ai('review'); assert.match(h.toast(),/disabled/);
  PL.research.flags={discovery_inbox:false}; await PL.research.open('papers'); assert.equal(h.$('.research-filters option[value=candidate]'),null);
  for(const el of h.$$('.research-filters select,.research-filters input:not([type=search])')) {el.dispatchEvent(new h.w.Event('change'));await h.idle();}
  empty=true; await PL.research.open('papers'); assert.match(h.$('.research-body').textContent,/No results/);
  await click(h,'→'); await click(h,'←');
  let upload;
  // h is captured by research.js: intercept the browser file chooser at the DOM level.
  const original=h.document.createElement.bind(h.document); h.document.createElement=(tag)=>{const node=original(tag);if(tag==='input'){upload=node;node.click=()=>{};}return node;};
  await click(h,'Import Zotero'); Object.defineProperty(upload,'files',{value:[],configurable:true}); upload.dispatchEvent(new h.w.Event('change')); await h.idle();
  Object.defineProperty(upload,'files',{value:h.files(['refs.json']),configurable:true}); upload.dispatchEvent(new h.w.Event('change')); await h.idle(30); assert.ok(h.server.last('POST',base+'/zotero/import'));
});

test('workspace create, open, sync, relink and provenance/findings controls use scoped endpoints',async()=>{
  let fail=true;
  const workspace={id:'w',engine:'openscience',path:'C:/saved',artifact_count:1,capabilities:{binary_available:true},checkpoint:{status:'partial',at:'today',error:'Partial read'}};
  const h=await page({
    ['GET '+base+'/workspaces']:()=>({workspaces:[workspace,{...workspace,id:'w2',engine:'feynman',capabilities:{binary_available:false},checkpoint:null}]}),
    ['POST '+base+'/workspaces']:()=>fail?R({detail:'Folder missing'},422):{id:'w'},
    'POST /api/research/workspaces/w/open':()=>({status:'opened',detail:'CLI ready',command:'openscience',log:'started'}),
    ['GET '+base+'/artifacts']:()=>({artifacts:[{id:'a',path:'report.md',engine:'openscience',version:1,available:true,bytes:10,sha256:'digest'},{id:'b',path:'old.md',engine:'feynman',version:2,available:false,bytes:0}]}),
    ['GET '+base+'/provenance']:()=>({events:[{type:'observed',observed:'today',payload:{file:'report.md'}}]}),
    ['GET '+base+'/findings']:()=>({findings:[{id:'f',status:'pending',text:'Human source text',source_evidence_ids:['artifact:a']},{id:'f2',status:'approved',text:'Previous review',source_evidence_ids:[]}]})
  }); const PL=h.w.PL;
  await PL.research.open('workspaces'); await click(h,'Create / link'); await save(h,'Link'); assert.match(h.toast(),/Folder missing/);
  fail=false; await save(h,'Link'); assert.equal(h.server.last('POST',base+'/workspaces').body.sync_interval_minutes,0);
  await click(h,'Open openscience'); assert.match(h.$('.dialog').textContent,/CLI ready/); await close(h);
  h.server.on('POST /api/research/workspaces/w/open',()=>({status:'unavailable'}));await click(h,'Open openscience');assert.match(h.$('.dialog').textContent,/unavailable/);await close(h);
  h.server.on('PUT /api/research/workspaces/w',()=>R({detail:'Relink failed'},422));await click(h,'Relink / schedule');await save(h);assert.match(h.toast(),/Relink failed/);await close(h);
  h.server.on('PUT /api/research/workspaces/w',()=>({ok:true}));
  await click(h,'Relink / schedule'); await save(h); assert.equal(h.server.last('PUT','/api/research/workspaces/w').body.path,'C:/saved');
  await click(h,'Sync Now'); assert.ok(h.server.last('POST','/api/research/workspaces/w/sync'));
  await PL.research.open('workspaces'); await click(h,'View changes');
  await h.click('.research-card input'); assert.equal(PL.research.sources()[0],'artifact:a');
  await click(h,'Review with AI'); assert.match(h.$('#input').value,/^\/review/);
  await h.input('.research-body > input','feynman'); assert.match(h.$('.research-body').textContent,/old.md/); assert.doesNotMatch(h.$('.research-body > div article').textContent,/report.md/);
  PL.prompt=async()=>null; await click(h,'Propose finding'); await click(h,'Approve');
  PL.prompt=async()=> 'Review evidence'; await click(h,'Propose finding'); assert.equal(h.server.last('POST',base+'/findings').body.text,'Review evidence');
  await click(h,'Approve'); assert.equal(h.server.last('POST',base+'/findings/f/review').body.approve,true);
  await click(h,'Reject'); assert.equal(h.server.last('POST',base+'/findings/f/review').body.approve,false);
  await h.input('.research-body > input',''); await h.click('.research-card input'); assert.equal(PL.research.selected.size,0);
});

test('job cancel/retry and research settings/dispatch failures are explicit',async()=>{
  const h=await page({'GET /api/research/jobs':()=>({jobs:[{id:'queued',kind:'sync',status:'queued',updated:'today',payload:{}},{id:'partial',kind:'download',status:'partial',updated:'today',payload:{error:'network'}}]})}); const PL=h.w.PL;
  await PL.research.open('jobs'); await click(h,'Cancel'); assert.ok(h.server.last('POST','/api/research/jobs/queued/cancel'));
  await click(h,'Retry'); assert.ok(h.server.last('POST','/api/research/jobs/partial/retry')); await click(h,'Refresh');
  await PL.research.dispatch({availability:'available',route_or_component_key:'settings'});assert.ok(h.$('.settings'));await close(h);
  await PL.research.dispatch({availability:'available',route_or_component_key:'library'});assert.equal(h.$('#panel').hidden,false);
  PL.research.flags={paper_explorer_v2:false};await PL.research.open('papers');assert.match(h.toast(),/disabled/);
  PL.research.tid='';await PL.research.open('claims');assert.match(h.$('.research-body').textContent,/Choose or create/);await click(h,'Topics');
  h.server.on('GET /api/research/topics',()=>({topics:[]}));await PL.research.open('topics');assert.match(h.$('.research-body').textContent,/No Topics yet/);
  h.server.on('GET /api/research/topics',()=>R({detail:'Failed topic load'},500));await PL.research.open('topics');assert.match(h.$('.research-body').textContent,/Failed topic load/);await click(h,'Retry');
  assert.deepEqual(h.errors,[]);
});

test('mission drafts, approvals, retries and cancellation require explicit controls',async()=>{
  let fail=true;
  const h=await page({
    ['GET '+base+'/missions']:()=>({missions:[{id:'draft',status:'draft',payload:{spec:{objective:'Human objective',permissions:['workspace_write']},reasoning_calls:0,active_seconds:0,plan_digest:'exact'},tasks:[{id:'inspect',status:'failed',payload:{error:'failed'}},{id:'done',status:'completed',payload:{result:'Human evidence'}}]}]}),
    ['POST '+base+'/missions']:()=>fail?R({detail:'Invalid draft'},422):{id:'draft'}
  }); const PL=h.w.PL;
  await PL.research.open('missions'); await click(h,'New mission'); await save(h,'Create draft'); assert.match(h.toast(),/Invalid draft/);
  fail=false;await save(h,'Create draft'); assert.equal(h.server.last('POST',base+'/missions').body.topic_id,tid);
  PL.prompt=async()=>null;await click(h,'Draft with AI');await click(h,'Approve this plan');await click(h,'Reconcile');
  PL.prompt=async()=> 'Human approval';await click(h,'Draft with AI');assert.equal(h.server.last('POST',base+'/missions/plan').body.allow_reasoning,true);
  await click(h,'Approve this plan');assert.equal(h.server.last('POST',base+'/missions/draft/approve').body.plan_digest,'exact');
  await click(h,'Reconcile');assert.equal(h.server.last('POST',base+'/missions/draft/retry').body.task_id,'inspect');
  await click(h,'Cancel');assert.ok(h.server.last('POST',base+'/missions/draft/cancel'));await click(h,'Refresh');
  PL.research.selected.set('paper:p','Paper');await click(h,'New mission');assert.match(h.$('.dialog textarea').value,/"p"/);await close(h);
});

test('monitor contracts, exact-plan controls, bounded pause and human review preserve payloads',async()=>{
  const statuses=['draft','awaiting_approval','paused','running','queued','scheduled','awaiting_review','completed'];
  const missions=statuses.map((status,i)=>({id:'m'+i,status,payload:{spec:{objective:status,control:{}},plan_digest:'exact'+i,reasoning_calls:0,active_seconds:1,blocking_reason:i===1?'Human blocker':''},tasks:[]}));
  const h=await page({['GET '+base+'/missions']:()=>({missions:[...missions,{id:'ordinary',payload:{spec:{}}}]}),'GET /api/research/charters':()=>({charters:[{payload:{goal:'Human charter'}}]})}); const PL=h.w.PL;PL.research.selected.set('paper:p','Selected paper');PL.research.selected.set('artifact:a','Artifact');
  await PL.research.open('monitor');assert.match(h.$('.research-body').textContent,/Human charter/);
  await click(h,'Disable Research OS');assert.equal(h.server.last('PUT','/api/research/os-settings').body.enabled,false);
  await click(h,'New project charter');await save(h,'Save draft');assert.ok(h.server.last('POST','/api/research/charters'));
  await click(h,'New supervised mission');await save(h,'Save draft');assert.equal(h.server.last('POST',base+'/missions').body.control.allow_api_billing,false);
  await click(h,'Request approval');assert.ok(h.server.last('POST',base+'/missions/m0/request-approval'));
  PL.prompt=async()=>null;await click(h,'Approve / resume');await click(h,'Pause');await click(h,'Complete human');
  PL.prompt=async()=> 'Reviewed';await click(h,'Approve / resume');assert.equal(h.server.last('POST',base+'/missions/m0/approve').body.plan_digest,'exact0');
  await click(h,'Pause');assert.equal(h.server.last('POST',base+'/missions/m3/pause').body.note,'Reviewed');
  await click(h,'Complete human');assert.equal(h.server.last('POST',base+'/missions/m6/review').body.note,'Reviewed');
  await click(h,'Cancel');assert.ok(h.server.last('POST',base+'/missions/m0/cancel'));await click(h,'Refresh');
  PL.research.editContract('Invalid JSON',{x:1},()=>({}));h.$('.dialog textarea').value='bad';await save(h,'Save draft');assert.ok(h.$('.dialog'));await close(h);
  PL.research.editContract('Failed save',{},async()=>null);await save(h,'Save draft');assert.ok(h.$('.dialog'));await close(h);
});

test('team and workstream proposals remain editable drafts and scoped output updates are versioned',async()=>{
  let produced=true;
  const mission={id:'multi',status:'failed',payload:{spec:{objective:'Owned evidence',team:{mode:'adaptive',agents:[{id:'worker',purpose:'Inspect'}],assignments:[{task_id:'inspect',owner:'worker',verifier:'verifier'},{task_id:'absent',owner:'worker'}]},collaboration:{rationale:'Human rationale',workstreams:[{id:'stream',objective:'Inspect',task_ids:['inspect']}]}}},tasks:[{id:'inspect',status:'failed',payload:{result:{artifacts:['report.md']}}}]};
  const h=await page({
    ['GET '+base+'/missions']:()=>({missions:[mission,{payload:{spec:{}}}]}),
    'POST /api/research/teams/propose':()=>({spec:{...mission.payload.spec}}),
    'POST /api/research/workstreams/propose':()=>({spec:{...mission.payload.spec}}),
    'GET /api/research/team-capabilities':()=>({capabilities:['paper.inspect']}),
    ['GET '+base+'/missions/multi/team']:()=>({records:['handoff']}),
    ['GET '+base+'/missions/multi/workstreams']:()=>({usage:[{team_id:'stream'}],messages:[],receipts:[],canonical_outputs:[],disputes:[{id:'d',status:'open',revision:3,payload:{reason:'Conflict'}},{id:'closed',status:'resolved',payload:{reason:'Handled'}}]})
  }); const PL=h.w.PL;PL.research.selected.set('paper:p','Selected paper');
  await PL.research.open('teams');await click(h,'Refresh');await click(h,'Disable teams');assert.equal(h.server.last('PUT','/api/research/os-settings').body.team_enabled,false);
  await click(h,'Propose team');await save(h,'Save draft');await h.idle(20);assert.match(h.$('.dialog').textContent,/Review roles/);await save(h,'Save draft');assert.ok(h.server.last('POST',base+'/missions'));
  await PL.research.open('teams');await click(h,'Capability evidence');assert.match(h.$('.dialog').textContent,/paper.inspect/);await close(h);
  await click(h,'Propose bounded reassignment');await save(h,'Save draft');assert.equal(h.server.last('POST',base+'/missions/multi/replan').body.task_id,'inspect');
  await PL.research.open('teams');await click(h,'Inspect handoffs');assert.match(h.$('.dialog').textContent,/handoff/);await close(h);await click(h,'Mission approvals');assert.equal(h.$('.research-body').dataset.mode,'monitor');
  await PL.research.open('workstreams');await click(h,'Disable multi-team');assert.equal(h.server.last('PUT','/api/research/os-settings').body.multi_team_enabled,false);
  await click(h,'Propose workstreams');await save(h,'Save draft');await h.idle(20);assert.match(h.$('.dialog').textContent,/Review team charters/);await save(h,'Save draft');
  await PL.research.open('workstreams');PL.prompt=async()=>null;await click(h,'Resolve with PI note');PL.prompt=async()=> 'Exact decision';await click(h,'Resolve with PI note');assert.equal(h.server.last('POST',base+'/missions/multi/disputes/d/resolve').body.expected_revision,3);
  await click(h,'Register canonical output');await save(h,'Save draft');assert.equal(h.server.last('POST',base+'/missions/multi/outputs').body.source_task,'inspect');
  mission.tasks=[];await PL.research.open('workstreams');await click(h,'Register canonical output');await save(h,'Save draft');assert.equal(h.server.last('POST',base+'/missions/multi/outputs').body.team_id,'');
  await click(h,'Refresh');await click(h,'Mission approvals');assert.equal(h.$('.research-body').dataset.mode,'monitor');
  await PL.research.open('teams');await click(h,'Propose bounded reassignment');assert.match(h.$('.dialog textarea').value,/"task_id": ""/);await close(h);
});

test('protocol and claim drafting, source links, audit and decisions retain scientific review boundaries',async()=>{
  let fail=true;
  const h=await page({
    ['GET '+base+'/protocols']:()=>({protocols:[{id:'p1',revision:2,digest:'digest',payload:{spec:{hypothesis:'Human hypothesis'}},approval:{by:'researcher'}}],runs:[{id:'r1',status:'completed',payload:{metric:1},trials:[{trial_key:'seed1',status:'completed',payload:{metric:1}}]}]}),
    ['POST '+base+'/protocols']:()=>fail?R({detail:'Invalid protocol'},422):{id:'p1'},
    ['POST '+base+'/claims']:()=>fail?R({detail:'Invalid claim'},422):{id:'c1'},
    ['GET '+base+'/claims']:()=>({claims:[{id:'c1',status:'rejected',payload:{kind:'source_claim',text:'Human claim'},checks:[],evidence:[{payload:{source_id:'paper:p',provenance:{paper_id:'p',version_id:'v',page:2}}},{payload:{source_id:'experiment:r1'}},{payload:{source_id:'artifact:a'}}]}]}),
    ['GET '+base+'/audit']:()=>({project_chain_valid:false,errors:['Mismatch']})
  }); const PL=h.w.PL;
  await PL.research.open('protocols');await click(h,'New protocol');await save(h,'Create immutable');assert.match(h.toast(),/Invalid protocol/);fail=false;await save(h,'Create immutable');
  PL.prompt=async()=>null;await click(h,'Approve fixed');PL.prompt=async()=> 'Exact review';await click(h,'Approve fixed');assert.equal(h.server.last('POST',base+'/protocols/p1/approve').body.digest,'digest');
  await click(h,'Prepare execution');assert.ok(h.server.last('POST',base+'/protocols/p1/mission'));await PL.research.open('protocols');await click(h,'Refresh');
  PL.research.selected.set('paper:p','Paper');await PL.research.open('claims');await click(h,'Propose claim');fail=true;await save(h,'Propose (not approve)');assert.match(h.toast(),/Invalid claim/);fail=false;await save(h,'Propose (not approve)');assert.equal(h.server.last('POST',base+'/claims').body.evidence[0].source_id,'paper:p');
  PL.prompt=async()=>null;await click(h,'Resolve DOI');await click(h,'approve');PL.prompt=async()=> '10.1234/real';await click(h,'Resolve DOI');assert.equal(h.server.last('POST',base+'/citations/resolve').body.allow_network,true);
  await click(h,'approve');assert.equal(h.server.last('POST',base+'/claims/c1/decision').body.action,'approve');
  await click(h,'Audit');assert.match(h.$('.dialog').textContent,/Audit discrepancy/);await close(h);await click(h,'Refresh');
});
