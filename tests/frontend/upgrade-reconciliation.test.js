'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {boot, fixtures} = require('./harness');
const tid='audit-topic', base='/api/research/topics/'+tid;
const topic={id:tid,title:'MRI',sources:['arxiv'],cadence:'manual',pdf_limit:10,enabled:true,archived:false};
const paper={id:'p',title:'Original title',year:2025,venue:'CVPR',sources:['OpenAlex'],level:2,state:'candidate',oa_locations:[],flags:[],association:{tags:['baseline']},abstract:'Evidence',versions:[]};
async function page() {
  return boot({storage:{'pl.lang':'en'},hash:'#/chat/'+fixtures.meta.session,routes:{
    'GET /api/config':()=>({...fixtures.get('GET /api/config'),ui:{language:'en'}}),
    'GET /api/chat/sessions/:id':()=>({...fixtures.get('GET /api/chat/sessions/:id'),topic_id:tid}),
    'GET /api/research/topics':()=>({topics:[topic]}),
    ['GET '+base+'/papers']:()=>({papers:[paper],total:1}),
    ['POST '+base+'/papers/bulk']:()=>({updated:['p']}),
    ['PUT '+base]:req=>{topic.archived=req.body.archived;return topic;},
    'GET /api/research/jobs':()=>({jobs:[]})
  }});
}

test('advanced paper filters, tags and reprocessing are scoped deterministic actions', async()=>{
  const h=await page(); const PL=h.w.PL;
  await PL.research.open('papers');
  h.server.on('GET '+base+'/citation-graph',()=>({nodes:[],edges:[],limits:'Source-declared only'}));
  await h.clickText('.research-body button','Citation graph');
  assert.match(h.$('.dialog').textContent,/Source-declared only/);await h.key('.dialog','Escape');
  assert.match(h.$('.research-card').textContent,/baseline/);
  const filters={max_year:'2025',venue:'CVPR',publication_type:'article',tag:'baseline',flag:'preprint',pdf:'true'};
  for(const [key,value] of Object.entries(filters)) {
    const control=key==='pdf' ? h.$('.research-filters details select') : h.$$('.research-filters details input')[Object.keys(filters).indexOf(key)];
    control.value=value; control.dispatchEvent(new h.w.Event('change')); await h.idle();
    assert.equal(h.server.last('GET',base+'/papers').query[key],value);
  }
  const pdf=h.$('.research-filters details select');pdf.value='';pdf.dispatchEvent(new h.w.Event('change'));await h.idle();
  assert.equal(h.server.last('GET',base+'/papers').query.pdf,undefined);
  await h.click('.research-card input[type=checkbox]');
  PL.prompt=async()=>null;await h.clickText('.research-bulk button','Add tags');
  assert.equal(h.server.calledWith('POST',base+'/papers/bulk').length,0);
  PL.prompt=async()=> 'MRI; baseline; ;';await h.clickText('.research-bulk button','Add tags');
  assert.deepEqual(h.server.last('POST',base+'/papers/bulk').body.tags,['MRI','baseline']);
  assert.equal(h.server.last('POST',base+'/papers/bulk').body.action,'tag');
  await h.clickText('.research-bulk button','Remove tags');
  assert.equal(h.server.last('POST',base+'/papers/bulk').body.action,'untag');
  await h.clickText('.research-bulk button','Reprocess PDF');
  assert.equal(h.server.last('POST',base+'/papers/bulk').body.action,'index');
  assert.equal(h.$('.research-body').dataset.mode,'jobs');
  assert.equal(h.server.calledWith('POST','/api/chat/sessions/'+fixtures.meta.session+'/turns').length,0);
  assert.deepEqual(h.errors,[]);h.close();
});

test('archiving and restoring Topic keeps data and disables schedule',async()=>{
  topic.archived=false;const h=await page();await h.w.PL.research.open('topics');
  await h.clickText('.research-card button','Archive Topic');
  assert.equal(h.server.last('PUT',base).body.archived,true);
  assert.equal(h.server.last('PUT',base).body.enabled,false);
  await h.clickText('.research-card button','Restore Topic');
  assert.equal(h.server.last('PUT',base).body.archived,false);
  h.close();
});

test('paper evidence search targets exact paper and opens available page anchors',async()=>{
  const h=await page();let evidence=[{id:'e1',paper_id:'p',version_id:'v1',page:3,text:'Exact span'},
    {id:'e2',paper_id:'p',version_id:null,page:null,text:'Abstract only'},
    {id:'e3',paper_id:'p',version_id:'v1',page:null,text:'No page'},
    {id:'e4',paper_id:'another',version_id:'v2',page:4,text:'Different paper'}];
  h.server.on('GET '+base+'/evidence',()=>({evidence}));
  await h.w.PL.research.open('papers');await h.clickText('.research-card button','Versions & evidence');
  await h.clickText('.dialog button','Evidence');
  assert.equal(h.server.last('GET',base+'/evidence').query.paper_id,'p');
  assert.equal(h.$('.dialog a').getAttribute('href'),base+'/papers/p/pdf/v1#page=3');
  assert.match(h.$('.dialog').textContent,/Page location unavailable/);
  assert.doesNotMatch(h.$('.dialog').textContent,/Different paper/);
  h.close();
});

test('artifact snapshots and timeline filters retain original scoped evidence',async()=>{
  const h=await page();
  h.server.on('GET '+base+'/artifacts',()=>({artifacts:[{id:'a',path:'result.md',engine:'feynman',version:1,available:true,bytes:12,sha256:'hash'}]}));
  h.server.on('GET '+base+'/provenance',()=>({events:[{type:'artifact.changed',observed:'2026-10-22',payload:{source_engine:'feynman',session_id:'s1'}},{type:'artifact.changed',observed:'2026-10-21',payload:{source_engine:'openscience',session_id:'s2'}}]}));
  h.server.on('GET '+base+'/findings',()=>({findings:[]}));
  h.server.on('GET '+base+'/artifacts/a',()=>({title:'result.md',text:'Observed immutable version'}));
  await h.w.PL.research.open('artifacts');
  await h.clickText('.research-card button','Inspect artifact version');
  assert.match(h.$('.dialog').textContent,/Observed immutable version/);
  await h.key('.dialog','Escape');
  const filter=h.$('.research-body input[type=search]');
  filter.value='s1';filter.dispatchEvent(new h.w.Event('input'));
  assert.equal(h.$$('.provenance-events details').length,1);
  assert.match(h.$('.provenance-events').textContent,/feynman/);
  filter.value='2026-10-21';filter.dispatchEvent(new h.w.Event('input'));
  assert.match(h.$('.provenance-events').textContent,/openscience/);
  assert.deepEqual(h.errors,[]);h.close();
});

test('local Zotero read requires explicit confirmation and displays its actual receipt',async()=>{
  const h=await page(),PL=h.w.PL;
  h.server.on('POST '+base+'/zotero/sync',()=>({read_only:true,received:20,next_start:null}));
  await PL.research.open('papers');PL.confirm=async()=>false;
  await h.clickText('.research-body button','Read local Zotero');
  assert.equal(h.server.calledWith('POST',base+'/zotero/sync').length,0);
  PL.confirm=async()=>true;await h.clickText('.research-body button','Read local Zotero');
  assert.deepEqual(h.server.last('POST',base+'/zotero/sync').body,{allow_network:true,max_items:1000});
  assert.match(h.$('.dialog').textContent,/"received": 20/);
  assert.equal(h.server.calledWith('POST','/api/chat/sessions/'+fixtures.meta.session+'/turns').length,0);
  assert.deepEqual(h.errors,[]);h.close();
});
