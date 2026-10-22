'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {boot,fixtures,R}=require('./harness');
const RID=fixtures.meta.runs[0],RVID=fixtures.meta.review;

test('advanced dashboard and paper drawers recover when optional APIs are unavailable',async()=>{
  let ais={installed:true,has_tex:true,has_pdf:false},complete={type:'done',ok:true};
  const h=await boot({hash:'#/dashboard',routes:{'GET /api/dashboard?advanced=1':()=>R({detail:'Monitor down'},503),
    'GET /api/paper/ais':()=>ais,'POST /api/paper/ais/writeup':()=>R('',200,{sse:[complete]}),
    'POST /api/library/rank':()=>({checked:0})
  }});const PL=h.w.PL;
  const det=h.$('details.adv');det.open=true;det.dispatchEvent(new h.w.Event('toggle'));await h.idle(35);assert.match(det.textContent,/Không đọc được GPU/);
  await h.go('#/chat/'+fixtures.meta.session);await PL.panels.paper();assert.equal(h.$('#panel-body select option').value,'icml');assert.match(h.$('#panel-body').textContent,/Commit \?/);assert.equal(h.$('#panel-body a[href$="/pdf"]'),null);
  await h.clickText('#panel-body button','Viết lại toàn bài',40);assert.match(h.toast(),/Đã viết xong bản thảo/);
  complete={type:'done',dropped_citations:[]};await h.clickText('#panel-body button','Viết lại toàn bài',40);assert.match(h.toast(),/Đã viết xong bản thảo/);
  await h.clickText('#panel-body button','Biên dịch PDF (/latex)',45);assert.equal(h.server.last('POST','/api/chat/sessions/').body.text,'/latex');
  h.server.on('GET /api/paper/ais',()=>R({detail:'Adapter unavailable'},503));await PL.panels.paper();assert.match(h.$('#panel-body').textContent,/chưa được cài/);
  await PL.panels.library();await h.clickText('#panel-body button','Kiểm tra ranking');assert.match(h.toast(),/0 tạp chí có hạng/);
});

test('run timelines use the selected language and reference cards support sparse conference metadata',async()=>{
  const h=await boot({storage:{'pl.lang':'en'},routes:{'GET /api/config':()=>({...fixtures.get('GET /api/config'),ui:{language:'en'}})}});
  await h.w.PL.panels.run(RID);assert.ok(h.$('ol.timeline li .s'));
  const card=h.w.PL.panels.paperCard({title:'Human title',doi:'10.1/source',url:'https://example.org/paper',journal_ranking:{core_rank:'A'}});
  assert.match(card.textContent,/CORE A/);
  assert.deepEqual(h.errors,[]);
});

test('review file chooser and venue lookup handle failed local data and sparse CORE results',async()=>{
  let lookup=R({detail:'Local index unavailable'},503);
  const h=await boot({hash:'#/review',routes:{'GET /api/review':()=>({reviews:[],active:''}),
    'POST /api/review/upload':()=>({meta:{id:RVID}}),'GET /api/review/:id':()=>fixtures.get('GET /api/review/:id'),
    'GET /api/ranking/lookup':()=>lookup
  }});
  await h.setFiles(h.$('.drop input[type=file]'),[]);assert.equal(h.server.last('POST','/api/review/upload'),undefined);
  await h.setFiles(h.$('.drop input[type=file]'),['manuscript.pdf']);await h.idle(35);assert.equal(h.w.location.hash,'#/review/'+RVID);
  await h.change('#rv-main input.input','Unknown venue');assert.match(h.$('#rv-main small[role=status]').textContent,/Không tìm thấy hạng/);
  lookup={conference:{title:'Conference with no acronym',rank:'B',source:'CORE'}};await h.change('#rv-main input.input','Sparse conference');assert.match(h.$('#rv-main small[role=status]').textContent,/Conference with no acronym/);
});
