'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {boot,fixtures,R}=require('./harness');

test('first paint uses the stored language, font and explicit light theme before boot',async()=>{
  const h=await boot({noBoot:true,storage:{'pl.theme':'light','pl.font':'serif','pl.lang':'en'}});
  assert.equal(h.document.documentElement.dataset.theme,'light');assert.equal(h.document.documentElement.dataset.font,'serif');assert.equal(h.document.documentElement.lang,'en');
});

test('language, theme and font initialization tolerate unavailable browser storage',async()=>{
  const h=await boot({noBoot:true,before:w=>{w.Storage.prototype.getItem=()=>{throw new Error('blocked');};w.Storage.prototype.setItem=()=>{throw new Error('blocked');};}});
  const PL=h.w.PL;
  assert.equal(PL.lang,'vi');assert.equal(h.document.documentElement.dataset.theme,undefined);
  PL.setFont('serif');assert.equal(h.document.documentElement.dataset.font,'serif');
  PL.setFont('other');assert.equal(h.document.documentElement.dataset.font,'sans');
  PL.setLang('vi');PL.setLang('en');
  assert.equal(PL.t('{0}/{1}',null,7),'/7');
  // Standalone initialization is supported by these small shared scripts, independent of boot.
  delete h.w.PL;h.load('assets/i18n-en.js');assert.equal(typeof h.w.PL.EN,'object');
  h.w.PL.EN=null;h.load('assets/i18n-en.js');assert.equal(typeof h.w.PL.EN,'object');
});

test('legacy streaming fallback batches chunks without animation frames and handles non-Error failures',async()=>{
  const h=await boot({noBoot:true,routes:{'POST /events':()=>({__resp:true,sse:[{type:'delta',text:'first'},{type:'delta',text:' second'},{type:'done',ok:true}]})}});
  h.w.requestAnimationFrame=undefined;
  const seen=[];const result=await h.w.PL.sse('/events',null,text=>seen.push(text));
  assert.equal(result.ok,true);assert.equal(seen.at(-1),'first second');
  h.w.fetch=async()=>{throw 'Network vanished';};
  assert.equal(await h.w.PL.sse('/events',{}),null);assert.equal(h.toast(),'Network vanished');
});

const field=(h,name)=>h.$$('.sb label.field,.sb .field').find(el=>el.querySelector('span')?.textContent===h.w.PL.ui(name))?.querySelector('input,select');
const change=async(h,el,value)=>{assert.ok(el);if(el.type==='checkbox')el.checked=value;else el.value=value;el.dispatchEvent(new h.w.Event('change'));await h.idle(25);};
const posted=h=>JSON.parse(JSON.stringify(h.server.last('POST','/api/config').body));

test('slow provider probes do not block the settings form',async()=>{
  let release;const h=await boot({routes:{'GET /api/providers':()=>new Promise(resolve=>{release=resolve;})}});
  await h.w.PL.settings.open('providers');await h.until(()=>release);
  assert.ok(field(h,'Research engine mode'));assert.ok(h.$('.sb .list .spin'));
  release({providers:[]});await h.idle();assert.equal(h.$('.sb .list .spin'),null);
});

test('model routing and runtime controls save explicit configuration changes',async()=>{
  const cfg=fixtures.get('GET /api/config');delete cfg.routing;delete cfg.gateway;delete cfg.mcp;
  cfg.local_model='local-current';cfg.ollama_model='ollama-current';
  const h=await boot({routes:{'GET /api/config':()=>cfg,'POST /api/config':()=>({...cfg,routing:{},gateway:{},mcp:{}}),'GET /api/models/local':()=>({lmstudio:{models:[{id:'local-current'},'bare-model']},ollama:{models:[{id:'ollama-current'}]}})}});
  const PL=h.w.PL;await PL.settings.open('models');await h.idle();
  await change(h,h.$$('.sb table.grid')[1].querySelector('select'),''); // choosing a cloud model is staged until Save.
  await change(h,h.byText('.sb .field',PL.ui('Capability-aware failover')).querySelector('input'),false);assert.deepEqual(posted(h),{routing:{capability_aware:false}});
  const chain=h.$$('.sb label.field').find(el=>el.firstChild.textContent==='reasoning');for(const select of chain.querySelectorAll('select'))await change(h,select,'@cloud');
  await h.click(chain.querySelector('button'));assert.deepEqual(posted(h).routing.chains.reasoning,['@cloud']);
  const verified=h.byText('.sb label.field','reasoning · model');verified.querySelector('option').selected=true;await change(h,verified.querySelector('select'),verified.querySelector('option').value);assert.ok(posted(h).routing.verified_fallbacks.reasoning.length);
  await change(h,field(h,'Model LM Studio'),'local-current');assert.equal(posted(h).local_model,'local-current');
  await change(h,field(h,'Model Ollama'),'ollama-current');assert.equal(posted(h).ollama_model,'ollama-current');
  await PL.settings.open('providers');await h.idle();
  const toggles=[['Codex app-server (prototype)',{gateway:{codex_app_server:true}}],['Enable OpenScience runtime adapter',{openscience:{enabled:true}}],['I reviewed the separate runtime, permissions and trace sharing',{openscience:{policy_confirmed:true}}],['Allow proposed code execution in the workspace',{openscience:{allow_execution:true}}]];
  for(const [label,patch] of toggles){const el=h.byText('.sb .field',PL.ui(label)).querySelector('input[type=checkbox]');await change(h,el,true);assert.deepEqual(posted(h),patch);}
  const catalog=h.byText('.sb label.field','codex · model catalog').querySelector('textarea');await change(h,catalog,'model-a\nmodel-b,model-a');assert.deepEqual(posted(h).gateway.cli_models.codex,['model-a','model-b']);
  for(const [label,value,key] of [['OpenScience loopback URL','http://127.0.0.1:4097','base_url'],['OpenScience timeout (seconds)','123','timeout_s'],['Artifact budget (MiB total)','12','max_artifact_mb'],['OpenScience model provider (optional; required for Auto qualification)','local','model_provider']]){
    await change(h,field(h,label),value);assert.equal(posted(h).openscience[key],/^(timeout_s|max_artifact_mb)$/.test(key)?Number(value):value);
  }
  const tasks=field(h,'Qualified tasks for this configured model');tasks.options[0].selected=true;tasks.dispatchEvent(new h.w.Event('change'));await h.idle(25);assert.deepEqual(posted(h),{openscience:{qualified_tasks:['literature']}});
  await change(h,h.byText('.sb .field','Tự kiểm tra ranking').querySelector('input'),false);assert.deepEqual(posted(h),{ranking:{auto:false}});
  await change(h,field(h,'Bộ xếp hạng CORE'),'CORE2023');assert.deepEqual(posted(h),{ranking:{core_source:'CORE2023'}});
  await change(h,field(h,'Làm mới CORE sau (ngày)'),'45');assert.deepEqual(posted(h),{ranking:{refresh_days:45}});
  for(const [tab,label,key] of [['mcp','MCP research tools','expose_research'],['mcp','MCP write proposals','allow_writes']]){
    await PL.settings.open(tab);await change(h,h.byText('.sb .field',PL.ui(label)).querySelector('input'),true);assert.deepEqual(posted(h),{mcp:{[key]:true}});
  }
  await PL.settings.open('hardware');await change(h,h.byText('.sb .field','ClearML Server (online)').querySelector('input'),true);assert.deepEqual(posted(h),{clearml:{server_enabled:true}});
  await change(h,field(h,'ClearML Web URL'),'https://clearml.example');assert.deepEqual(posted(h),{clearml:{web_url:'https://clearml.example'}});
  assert.deepEqual(h.errors,[]);
});

test('plugin and ranking defaults, language save failure and restored drawer navigation remain usable',async()=>{
  const cfg=fixtures.get('GET /api/config');let fail=false;
  const h=await boot({storage:{'pl.panel':JSON.stringify({kind:'unknown'})},routes:{'POST /api/config':()=>fail?R({detail:'Not saved'},500):cfg,
    'GET /api/plugins':()=>({root:'local',plugins:[{id:'empty',name:'Empty'},{id:'many',name:'Many',skills:Array.from({length:7},(_,i)=>({name:'s'+i,title:'Skill '+i,enabled:true}))}]}),
    'POST /api/plugins':()=>({id:'new-plugin'}),
    'GET /api/ranking':()=>({})
  }});const PL=h.w.PL;
  await PL.settings.open('plugins');await h.idle();
  const skill=h.$('.sb details input');skill.checked=false;skill.dispatchEvent(new h.w.Event('change'));await h.idle();assert.equal(h.server.last('PUT','/api/plugins/skills/s0').body.enabled,false);
  PL.confirm=async()=>false;await h.click('.sb button[title="Gỡ plugin"]');assert.equal(h.server.last('DELETE','/api/plugins/'),undefined);
  await h.input('.sb input.input','https://github.com/acme/theme');await h.clickText('.sb button','Cài plugin');assert.ok(h.server.last('POST','/api/plugins'));
  await PL.settings.open('providers');await h.idle();assert.match(h.$('.sb').textContent,/0/);
  await PL.settings.open('look');fail=true;await change(h,field(h,'Ngôn ngữ giao diện và câu trả lời của AI'),'en');assert.match(h.toast(),/Not saved/);
  fail=false;let selected;PL.setLang=value=>{selected=value;};await change(h,field(h,'Ngôn ngữ giao diện và câu trả lời của AI'),'vi');assert.equal(selected,'vi');
  await h.click('#topic-btn');assert.equal(h.$('#panel').hidden,false);
  await h.click('#panel-btn');await h.click('#panel-btn');await h.click('.nav[data-go=research]');assert.equal(h.$('#panel').hidden,false);
  assert.deepEqual(h.errors,[]);
  const restored=await boot({storage:{'pl.panel':JSON.stringify({kind:'library'})}});assert.equal(restored.$('#panel').hidden,false);
});
