'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {boot, fixtures, R} = require('./harness');
const SID = fixtures.meta.session;

test('theme packages validate colors, import VS Code colors, persist, replace and remove', async () => {
  const h = await boot(); const T = h.w.PL.themes, root = h.document.documentElement;
  for (const raw of [null, [], 'x', {}, {id:'bad id',name:'Bad',colors:{bg:'#fff'}}, {id:'light',name:'Reserved',colors:{bg:'#fff'}}, {name:'x',base:'wrong',colors:{}}, {name:'x',colors:[]}, {name:'x',colors:{unknown:'#fff'}}, {name:'x',colors:{bg:'url(https://evil.test)'}}, {name:'x',colors:{bg:123}}]) assert.throws(() => T.validate(raw));
  assert.throws(() => T.install({id:'lab-forest',name:'Override',colors:{bg:'#fff'}}));
  const theme = T.install({name:'Ocean Theme', type:'light', colors:{'editor.background':'#eff', 'button.background':'#123456', 'button.foreground':'#fff', unsupported:'url(x)'}});
  assert.equal(theme.id,'ocean-theme'); assert.equal(theme.base,'light');
  assert.equal(root.style.getPropertyValue('--bg'),'#eff');
  assert.equal(root.style.getPropertyValue('--accent'),'#123456');
  assert.equal(root.style.getPropertyValue('--accent-ink'),'#fff');
  assert.equal(root.dataset.themePackage,'ocean-theme');
  assert.equal(JSON.parse(h.w.localStorage.getItem('pl.themePackages')).length,1);
  T.install({id:'ocean-theme', name:'Ocean 2', base:'dark',colors:{bg:'#1234',ink:'#ffffffee'}});
  assert.equal(T.list().length,3); assert.equal(root.dataset.theme,'dark');
  T.remove('ocean-theme'); assert.equal(root.dataset.themePackage,undefined); assert.equal(h.w.localStorage.getItem('pl.theme'),null);
  T.select('lab-forest'); T.remove('not-selected'); assert.equal(root.dataset.themePackage,'lab-forest');
  assert.equal(T.apply('missing-package'),'system');
  assert.equal(root.style.getPropertyValue('--bg'),'');
  T.apply('light'); assert.equal(root.dataset.theme,'light');
  h.w.localStorage.setItem('pl.themePackages','[null,{},[]]'); assert.equal(T.list().length,2);
  h.w.localStorage.setItem('pl.themePackages','{}'); assert.equal(T.list().length,2);
  h.w.localStorage.setItem('pl.themePackages',JSON.stringify(Array.from({length:30},(_,i)=>({id:'theme-'+i,name:'Theme '+i,colors:{bg:'#fff'}}))));
  assert.throws(() => T.install({id:'one-more',name:'One more',colors:{bg:'#fff'}}),/30/);
});

test('theme package controls handle upload, invalid JSON, size, empty selection and uninstall', async () => {
  const h = await boot(); const PL=h.w.PL;
  await PL.settings.open('look'); await h.idle();
  await h.click('#install-theme');assert.equal(h.$('#theme-file').hidden,true);
  await h.clickText('.theme-card button','Áp dụng');
  assert.equal(h.document.documentElement.dataset.themePackage,'lab-midnight');
  assert.equal(h.$('#theme-select').value,'lab-midnight');
  const upload = async file => {
    const el=h.$('#theme-file'); Object.defineProperty(el,'files',{value:file?[file]:[],configurable:true});
    el.dispatchEvent(new h.w.Event('change')); await h.idle(35);
  };
  await upload(null);
  await upload({size:70000,text:async()=>''}); assert.match(h.toast(),/64 KB/);
  await upload({size:1,text:async()=>'{'}); assert.match(h.toast(),/JSON/);
  await upload({size:100,text:async()=>JSON.stringify({name:'Imported',colors:{bg:'#123'}})});
  assert.equal(h.document.documentElement.dataset.themePackage,'imported');
  assert.match(h.$('.theme-grid').textContent,/Imported/);
  await h.clickText('.theme-card button','Gỡ cài đặt',35);
  assert.doesNotMatch(h.$('.theme-grid').textContent,/Imported/);
  const proto=h.w.Storage.prototype, orig=proto.setItem;
  proto.setItem=()=>{throw new Error('Storage unavailable');};
  PL.themes.select('dark'); assert.equal(h.document.documentElement.dataset.theme,'dark');
  assert.throws(()=>PL.themes.install({name:'Lost',colors:{bg:'#fff'}}),/Storage/);
  proto.setItem=orig;
  assert.deepEqual(h.errors,[]);
});

test('pin user and assistant messages independently of result pins, browse and unpin', async () => {
  let session=fixtures.get('GET /api/chat/sessions/:id');
  const h=await boot({hash:'#/chat/'+SID,routes:{
    'GET /api/chat/sessions/:id':()=>session,
    'PUT /api/chat/sessions/:sid/messages/:mid/pin':req=>{session.messages.find(m=>m.id===req.params[1]).pinned=req.body.pinned;return session;}
  }});
  await h.click('#pinned-btn'); assert.match(h.$('#panel-body').textContent,/Chưa có tin nhắn/);
  await h.click('.msg.user button[title="Ghim tin nhắn"]');
  assert.equal(h.server.last('PUT','/api/chat/sessions/').body.pinned,true);
  await h.click('.msg.ai button[title="Ghim tin nhắn"]');
  assert.equal(h.server.calledWith('POST','/api/pins').length,0);
  await h.click('#pinned-btn'); assert.equal(h.$$('.pinned-messages article').length,2);
  await h.clickText('.pinned-messages button','Đến tin nhắn'); assert.ok(h.document.activeElement.matches('.msg'));
  const target=h.document.activeElement;
  h.w.matchMedia=()=>({matches:true}); await h.clickText('.pinned-messages button','Đến tin nhắn');
  target.remove(); await h.clickText('.pinned-messages button','Đến tin nhắn');
  await h.click('.pinned-messages button[title="Bỏ ghim tin nhắn"]');
  await h.click('#pinned-btn'); assert.equal(h.$$('.pinned-messages article').length,1);
  await h.w.PL.chat.open(SID); await h.click('#pinned-btn'); assert.equal(h.$$('.pinned-messages article').length,1);
  assert.ok(h.$$('.chat-day time').length); assert.match(h.$('.message-time').dateTime,/T/);
  assert.deepEqual(h.errors,[]);
});

test('failed pin keeps prior state; calendar dates and English labels are localized', async () => {
  const date=new Date(); date.setHours(0,0,0,0); date.setDate(date.getDate()-1);
  const h=await boot({storage:{'pl.lang':'en'},hash:'#/chat/'+SID,routes:{
    'GET /api/config':()=>({...fixtures.get('GET /api/config'),ui:{language:'en'}}),
    'GET /api/chat/sessions':()=>({sessions:[{id:SID,title:'User Vietnamese: nghiên cứu',updated:date.getTime()/1000}]}),
    'PUT /api/chat/sessions/:sid/messages/:mid/pin':()=>R({detail:'pin rejected'},409)
  }});
  assert.equal(h.$('#threads .tgroup').textContent,'Yesterday');
  await h.click('.msg.user button[title="Pin message"]'); assert.match(h.toast(),/pin rejected/);
  assert.ok(h.$('.msg.user button[title="Pin message"]'));
  assert.match(h.$('.message-time').textContent,/[A-Za-z]+/);
  assert.match(h.$('#threads').textContent,/nghiên cứu/);
  assert.equal(h.w.PL.ui('Teams'),'Teams'); h.w.PL.lang='vi'; assert.equal(h.w.PL.ui('Teams'),'Nhóm nghiên cứu');
  assert.equal(h.w.PL.ui('User content stays intact'),'User content stays intact');
});

test('pin updates preserve another drawer, block duplicate clicks and ignore replies after navigation',async()=>{
  const h=await boot({hash:'#/chat/'+SID});const PL=h.w.PL;
  await PL.panels.outline();await h.click('.msg.user button[title="Ghim tin nhắn"]');
  assert.equal(PL.store.get('panel').kind,'outline');assert.ok(h.$('.msg.user button[title="Bỏ ghim tin nhắn"]'));
  PL.panels.close();await h.click('.msg.user button[title="Bỏ ghim tin nhắn"]');assert.ok(h.$('.msg.user button[title="Ghim tin nhắn"]'));
  let release;h.server.on('PUT /api/chat/sessions/:sid/messages/:mid/pin',()=>new Promise(resolve=>{release=resolve;}));
  const button=h.$('.msg.user button[title="Ghim tin nhắn"]');await h.click(button);assert.equal(button.disabled,true);
  await h.click(button);assert.equal(h.server.calledWith('PUT','/api/chat/sessions/').length,3);
  await PL.chat.open(null);release({});await h.idle();assert.equal(PL.chat.s,null);assert.equal(button.disabled,false);
});

test('project drawer groups chats, retries loading, switches only after activation and creates project', async () => {
  const cfg=fixtures.get('GET /api/config'); const p=cfg.project;
  const other={...p,name:'Second',data_dir:p.data_dir+'/second'};
  let fail=true, activate=false;
  const h=await boot({routes:{
    'GET /api/config':()=>cfg,
    'GET /api/projects':()=>({projects:[p,other]}),
    'GET /api/projects/conversations':req=>fail?R({detail:'Read failed'},500):{sessions:req.query.directory===p.data_dir?[{id:SID,title:'Own chat',updated:Date.now()/1000}]:[]},
    'POST /api/projects/activate':()=>activate?{ok:true}:R({detail:'Cannot switch'},409)
  }});
  await h.click('#projects-btn'); const group=h.$('.project-group');
  group.open=true; await h.idle(30); assert.match(h.toast(),/Read failed/);
  fail=false; group.open=false; await h.idle(); group.open=true; await h.idle(30);
  assert.match(group.textContent,/Own chat/);
  group.open=false; await h.idle(); group.open=true; await h.idle();
  assert.equal(h.server.calledWith('GET','/api/projects/conversations').length,2);
  await h.click('.project-chat'); assert.equal(h.w.location.hash,'#/chat/'+SID);
  await h.click('#projects-btn'); const second=h.$$('.project-group')[1]; second.open=true; await h.idle(30);
  assert.match(second.textContent,/Chưa có cuộc trò chuyện/);
  await h.click(second.querySelector('button')); assert.match(h.toast(),/Cannot switch/); assert.equal(h.$('#panel').hidden,false);
  activate=true; await h.click(second.querySelector('button')); assert.equal(h.$('#panel').hidden,true);
  await h.click('#create-project'); assert.match(h.$('.dialog').textContent,/Tên dự án/);
  assert.deepEqual(h.errors,[]);
});
