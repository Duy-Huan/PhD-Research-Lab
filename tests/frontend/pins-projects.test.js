'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {boot,fixtures,R}=require('./harness');
const SID=fixtures.meta.session;
test('concurrent message pins survive stale refreshes, search full text without accents and jump visibly',async()=>{
  let session=fixtures.get('GET /api/chat/sessions/:id');session.messages=session.messages.slice(0,2);
  session.messages[0].content='A'.repeat(500)+' Nghiên cứu trí tuệ';session.messages[1].content='Second pinned finding';
  const pending=[];
  const h=await boot({hash:'#/chat/'+SID,routes:{'GET /api/chat/sessions/:id':()=>session,
    'PUT /api/chat/sessions/:sid/messages/:mid/pin':req=>new Promise(resolve=>pending.push({req,resolve}))}});
  const C=h.w.PL.chat;
  h.$('.msg.user button[title="Ghim tin nhắn"]').click();h.$('.msg.ai button[title="Ghim tin nhắn"]').click();await h.until(()=>pending.length===2);
  await C.refresh(); // replaces message objects while both requests are outstanding
  assert.equal(C.s.messages.filter(m=>m.pinned).length,2);
  C.pinsPanel();h.$('.pinned-messages button[title="Bỏ ghim tin nhắn"]').click();await h.idle();assert.equal(pending.length,2);
  pending[1].resolve({});pending[0].resolve({});await h.idle(40);
  await C.refresh(); // stale backend snapshot must not erase successful pins
  assert.equal(C.s.messages.filter(m=>m.pinned).length,2);
  session.messages.forEach(m=>{m.pinned=true;});await C.refresh();await C.refresh();
  await h.click('#pinned-btn');assert.equal(h.$$('.pinned-messages article').length,2);
  await h.input('.pin-search','nghien cuu tri tue');assert.equal(h.$$('.pinned-messages article').length,1);assert.match(h.$('.pinned-messages article').textContent,/Nghiên cứu/);
  await h.input('.pin-search','no-match-xyz');assert.equal(h.$$('.pinned-messages article').length,0);assert.match(h.$('.pinned-messages').textContent,/Không có tin nhắn/);
  h.w.matchMedia=()=>({matches:true});await h.input('.pin-search','Second');await h.clickText('.pinned-messages button','Đến tin nhắn');
  await h.until(()=>h.document.activeElement.matches('.msg.pin-target'));assert.equal(h.$('#panel').hidden,true);assert.match(h.document.activeElement.textContent,/Second pinned/);
  assert.ok(h.document.activeElement.classList.contains('pin-target'));await h.idle(1850);assert.equal(h.document.activeElement.classList.contains('pin-target'),false);
  assert.deepEqual(h.errors,[]);
});
test('conversation pins and lightweight chat projects group chats without moving research data',async()=>{
  let groups=[{id:'cg-one',name:'Draft project'}];let sessions=fixtures.get('GET /api/chat/sessions').sessions.slice(0,1);sessions.push({...sessions[0],id:'as-1234567890',title:'Second conversation'});
  sessions[0].chat_project='cg-one';sessions[0].pinned=true;sessions[1].pinned=true;
  sessions.push({...sessions[0],id:'as-aabbccddee',pinned:false});
  const h=await boot({routes:{
    'GET /api/chat/projects':()=>({projects:groups}), 'GET /api/chat/sessions':()=>({sessions}),
    'POST /api/chat/projects':req=>{const group={id:'cg-new',name:req.body.name};groups.push(group);return group;},
    'PUT /api/chat/sessions/:id':req=>{Object.assign(sessions.find(s=>s.id===req.params[0]),req.body);return {};},
    'POST /api/chat/sessions':()=>({id:SID})
  }});
  assert.ok(h.$('.chat-project'));assert.match(h.$('.chat-project summary').textContent,/Draft project/);
  assert.match(h.$('#threads').textContent,/Hội thoại đã ghim/);
  const menu=async()=>{await h.click('[data-session=as-1234567890] .more');};
  await menu();await h.clickText('.menu .mi','Bỏ ghim hội thoại');assert.equal(sessions[1].pinned,false);
  await menu();await h.clickText('.menu .mi','Ghim hội thoại');assert.equal(sessions[1].pinned,true);
  await menu();await h.clickText('.menu .mi','Chuyển vào dự án');
  await h.change('.dialog select','cg-one');await h.clickText('.dialog-f button','Lưu');assert.equal(h.server.last('PUT','/api/chat/sessions/').body.chat_project,'cg-one');
  await h.click('.chat-project button');assert.equal(h.server.last('POST','/api/chat/sessions').path,'/api/chat/sessions');
  h.w.PL.prompt=async()=> 'New notes';await h.click('#new-chat-project');assert.equal(groups.at(-1).name,'New notes');
  await h.w.PL.chat.createChatProject(sessions[0].id);assert.equal(h.server.last('PUT','/api/chat/sessions/').body.chat_project,'cg-new');
  await menu();await h.clickText('.menu .mi','Chuyển vào dự án');
  h.server.on('PUT /api/chat/sessions/:id',()=>R({detail:'cannot move'},500));await h.clickText('.dialog-f button','Lưu');assert.match(h.toast(),/cannot move/);
  await h.clickText('.dialog-f button','Dự án hội thoại mới');await h.idle(30);
  h.w.PL.prompt=async()=>null;await h.w.PL.chat.createChatProject();h.w.PL.prompt=async()=> '   ';await h.w.PL.chat.createChatProject();
  h.w.PL.prompt=async()=> 'Failure';h.server.on('POST /api/chat/projects',()=>R({detail:'cannot create'},500));await h.w.PL.chat.createChatProject();assert.match(h.toast(),/cannot create/);
  h.server.on('GET /api/chat/projects',()=>R({detail:'offline'},500));await h.w.PL.chat.loadList();assert.equal(h.$('.chat-project'),null);
  h.server.on('GET /api/chat/projects',()=>({}));await h.w.PL.chat.loadList();await menu();await h.clickText('.menu .mi','Chuyển vào dự án');assert.equal(h.$('.dialog select').options.length,1);
});
test('review closes the obscuring drawer and extracted manuscript text can be retried',async()=>{
  const rid=fixtures.meta.review;let fail=true;
  const h=await boot({routes:{'GET /api/review/:id/text':()=>fail?R({detail:'parse unavailable'},500):'Visible manuscript text'}});
  await h.w.PL.panels.library();await h.go('#/review/'+rid,80);assert.equal(h.$('#panel').hidden,true);
  const details=h.$('.manuscript-preview');details.open=true;await h.idle(30);assert.match(h.$('.manuscript-text').textContent,/parse unavailable/);
  details.open=false;await h.idle();fail=false;details.open=true;await h.idle(30);assert.equal(h.$('.manuscript-text').textContent,'Visible manuscript text');
  details.open=false;await h.idle();details.open=true;await h.idle();
  h.server.on('GET /api/review/:id/text',()=> '');h.w.PL.go('#/review/'+rid);await h.idle(80);h.$('.manuscript-preview').open=true;await h.idle(30);assert.match(h.$('.manuscript-text').textContent,/Chưa có văn bản/);
});
