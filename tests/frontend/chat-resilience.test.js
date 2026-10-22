'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {boot,fixtures,R}=require('./harness');
const SID=fixtures.meta.session,RID=fixtures.meta.runs[0];
const session=()=>({...fixtures.get('GET /api/chat/sessions/:id'),title:'',messages:[{id:'u',role:'user',content:'Question',ts:1},{id:'a',role:'assistant',content:'Answer evidence',provider:'app:auto',ts:2}],approvals:[],artifacts:[],memory_items:[],turns:[]});
async function page(routes={},extra={}){return boot({...extra,hash:'#/chat/'+SID,routes:{'GET /api/chat/sessions/:id':()=>session(),...routes}});}

test('exporting another sidebar conversation opens it before offering an export',async()=>{
  const h=await page({'GET /api/chat/sessions':()=>({sessions:[{id:'as-another',title:'Other project conversation',updated:1}]})});
  await h.click('#threads .more');await h.clickText('.menu.pop button','Xuất cuộc');
  assert.equal(h.w.location.hash,'#/chat/as-another');assert.equal(h.server.last('POST','/api/export'),undefined);
});

test('failed session lists, stale opens and coalesced refreshes never replace the active chat',async()=>{
  let release;
  const h=await page();const PL=h.w.PL,C=PL.chat;
  h.server.on('GET /api/chat/sessions',()=>R({detail:'No list'},503));await C.loadList();assert.match(h.$('#threads').textContent,/Chưa có cuộc/);
  h.server.on('GET /api/chat/sessions/:id',()=>new Promise(resolve=>{release=resolve;}));
  const stale=C.open('as-stale');await h.until(()=>release);await C.open(null);release(session());await stale;assert.equal(C.sid,null);assert.ok(h.$('.hello'));
  h.server.on('GET /api/chat/sessions/:id',()=>session());await C.open(SID);
  release=null;h.server.on('GET /api/chat/sessions/:id',()=>{if(release)return session();return new Promise(resolve=>{release=resolve;});});
  const count=h.server.calledWith('GET','/api/chat/sessions/').length;
  const first=C.refresh();await h.until(()=>release);await C.refresh();await C.refresh();release(session());await first;await h.idle(20);
  assert.equal(h.server.calledWith('GET','/api/chat/sessions/').length-count,2);
  // Returning from an empty session reuses the existing thread shell and removes its welcome view.
  h.server.on('GET /api/chat/sessions/:id',()=>({...session(),messages:[]}));await C.open(SID);await h.idle();assert.ok(h.$('.hello'));
  h.server.on('GET /api/chat/sessions/:id',()=>session());await C.refresh();assert.equal(h.$('.hello'),null);assert.equal(h.$$('.msg').length,2);
});

test('chat popups, exports and model selectors handle default model, live pending data and outside clicks',async()=>{
  let release;
  const h=await page();const PL=h.w.PL,C=PL.chat;
  h.w.HTMLAnchorElement.prototype.click=()=>{};h.w.URL.createObjectURL=()=> 'blob:x';h.w.URL.revokeObjectURL=()=>{};
  h.server.on('POST /api/export',()=>R('export',200));
  await h.click('.msg.ai button[title^="Xuất"]');await h.clickText('.menu.pop button','Markdown');assert.equal(h.server.last('POST','/api/export').body.title,'answer');
  await h.click('#threads .more');await h.clickText('.menu.pop button','Xuất cuộc');assert.ok(h.$('.menu.pop'));await h.clickText('.menu.pop button','Markdown');
  h.$('.msg.ai').remove();await h.clickText('#top-tools button','Xuất');await h.clickText('.menu.pop button','HTML');assert.doesNotMatch(h.server.last('POST','/api/export').body.html,/Answer evidence/);
  await C.open(null);h.server.on('GET /api/chat/sessions/:id',()=>new Promise(resolve=>{release=resolve;}));const pending=C.open(SID);await h.until(()=>release);
  await h.click('#threads .more');await h.clickText('.menu.pop button','Xuất cuộc');assert.equal(h.$('.menu.pop'),null);release(session());await pending;
  C.s.settings={provider:'test:provider',model:'current'};
  C.models={providers:[{id:'test:provider',label:'Custom provider',transport:'api',available:true,models:['current','other'],reasoning:[]}]};
  PL.menu(h.$('#model'),[{label:'Existing popup'}]);await h.click('#model');assert.doesNotMatch(h.$('.picker').textContent,/Existing popup/);
  const select=h.$('.picker select');assert.equal(select.value,'current');await h.change(select,'other');assert.equal(h.server.last('PUT','/api/chat/sessions/'+SID).body.settings.model,'other');
  C.s.settings={provider:'test:provider'};C.models.providers[0].models=undefined;await h.click('#model');assert.equal(h.$('.picker select').options.length,1);
  h.$('.picker .reason').click();await h.idle();h.document.body.dispatchEvent(new h.w.MouseEvent('mousedown',{bubbles:true}));assert.equal(h.$('.menu.sub'),null);assert.equal(h.$('.picker'),null);
  const menu=PL.menu(h.$('#model'),[{label:'First'},{label:'Last'}]);await h.idle();menu.querySelectorAll('button')[1].focus();await h.key(menu,'ArrowDown');assert.equal(h.document.activeElement.textContent,'First');
});

test('note selection menus handle empty quotes, orphaned notes, navigation and disappearing session data',async()=>{
  let s=session();s.notes=[{id:'n1',message_id:'a',quote:'Answer',text:'',status:'open',created:1}];
  const h=await page({'GET /api/chat/sessions/:id':()=>s,'POST /api/chat/sessions/:id/notes':()=>({id:'n2'})});const PL=h.w.PL,C=PL.chat;
  const selected={messageId:'a',quote:'Answer',prefix:'',rect:{left:0,width:10,top:100}};PL.tools.selectionInAnswer=()=>selected;
  h.$('#thread').dispatchEvent(new h.w.MouseEvent('mouseup'));await h.idle();
  let button=h.$('.sel-pop button');const mouse=new h.w.MouseEvent('mousedown',{cancelable:true});button.dispatchEvent(mouse);assert.equal(mouse.defaultPrevented,true);
  h.$('#thread').dispatchEvent(new h.w.MouseEvent('mouseup'));await h.idle();assert.equal(h.$$('.sel-pop').length,1);
  const ask=h.$$('.sel-pop button')[1];const down=new h.w.MouseEvent('mousedown',{cancelable:true});ask.dispatchEvent(down);assert.equal(down.defaultPrevented,true);
  h.$('#thread').dispatchEvent(new h.w.Event('scroll'));assert.equal(h.$('.sel-pop'),null);h.$('#thread').dispatchEvent(new h.w.Event('scroll'));
  await h.click('#notes-btn');await h.click('.note-item button[title="Tuỳ chọn"]');assert.match(h.$('.menu.pop .mh').textContent,/chưa có nội dung/);
  await h.key('.menu.pop','Escape');s={...s,messages:[...s.messages.slice(0,1),{...s.messages[1],content:''}]};await C.open(SID);
  await h.click('.msg.ai button[title^="Ghi chú"]');assert.equal(h.$('.dialog .note-quote').textContent,'');
  PL.store.set('panel',null);await h.clickText('.dialog-f button','Lưu ghi chú');assert.equal(h.$('.dialog'),null);
  await C.open(null);C.notesPanel();assert.match(h.$('#panel-body').textContent,/Chưa có ghi chú/);
  // A notes drawer can outlive its chat while the user starts another conversation.
  await C.open(SID);C.notesPanel();await C.open(null);await h.click('.note-item button[title="Tuỳ chọn"]');assert.equal(h.$('.menu.pop'),null);
});

test('streaming fallback coalesces rapid chunks and ignores frames detached by navigation',async()=>{
  const s=session();s.turns=[{id:'turn-live',status:'running'}];
  const h=await page({'GET /api/chat/sessions/:id':()=>s},{before:w=>{w.requestAnimationFrame=undefined;}});const C=h.w.PL.chat;
  const es=h.ES.all.find(e=>e.url.includes('/api/chat/sessions/'+SID+'/stream'));
  const delta=text=>es.send({type:'message.delta',turn_id:'turn-live',data:{text}});
  delta('First');delta(' second');delta(' third');await h.idle(30);assert.match(h.$('.live .prose').textContent,/First second third/);
  delta(' detached');C.live['turn-live'].el=null;await h.idle(30);assert.ok(h.$('.live'));
  C.live['turn-live'].el=h.$('.live .prose');delta(' navigated');await C.open(null);await h.idle(30);assert.equal(h.$('.live'),null);
  await C.open(null);assert.ok(h.$('.hello'));
});

test('native run cards expose partial output and runtime recovery with unavailable backends',async()=>{
  const s=fixtures.get('GET /api/chat/sessions/:id');let run=fixtures.get('GET /api/runs/'+RID);
  run={...run,status:'RUNNING',current:run.steps[0].id,proposal:{job_id:'job-native'},steps:[{...run.steps[0],result:{engine_partial:'Observed partial output'}}]};
  let detail={job:{state:'waiting',native_run_id:''},receipt:{state:'admitted'}};
  const h=await page({'GET /api/chat/sessions/:id':()=>s,['GET /api/runs/'+RID]:()=>run,'GET /api/research-engines/jobs/job-native':()=>detail});const PL=h.w.PL,C=PL.chat;
  await h.until(()=>h.$('.card.run pre'));assert.match(h.$('.card.run').textContent,/Observed partial output/);
  await h.clickText('.card.run button','OpenScience');assert.match(h.$('.dialog').textContent,/admitted/);
  detail={job:{state:'waiting',native_run_id:''},pending:[{id:'q',kind:'question',questions:[{header:'Header prompt'},{}]},{id:'empty',kind:'question'}]};
  const questions=[];PL.prompt=async(title,q)=>{questions.push(q);return 'answer';};
  await PL.engineJob(run,'job-native');await h.clickText('.dialog button','Trả lời');assert.deepEqual(questions,['Header prompt','Trả lời']);
  await h.click(h.$$('.dialog button').filter(b=>b.textContent==='Trả lời')[1]);
  h.server.on('GET /api/research-engines/jobs/job-native',()=>R({detail:'Runtime offline'},503));await PL.engineJob(run,'job-native');assert.match(h.toast(),/Runtime offline/);
  run.status='COMPLETED';await C.refreshRun(RID);assert.doesNotMatch(h.$('.card.run').textContent,/Observed partial output/);
  h.server.on('GET /api/runs/'+RID,()=>R({detail:'Gone'},404));await C.open(null);await C.open(SID);await h.until(()=>h.$('.card.run')?.textContent.includes('không còn'));
});
