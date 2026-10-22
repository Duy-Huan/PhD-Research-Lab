'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {boot,fixtures,R}=require('./harness');
const change=async(h,el,value)=>{if(el.type==='checkbox')el.checked=value;else el.value=value;el.dispatchEvent(new h.w.Event('change'));await h.idle(30);};
const options=el=>Array.from(el.options,o=>o.value);
const field=(h,label)=>h.byText('.sb label.field',label).querySelector('input,textarea,select');

test('agent models follow API, local and MCP sources; failed source changes roll back',async()=>{
  let cfg=fixtures.get('GET /api/config');
  cfg.agent_modes={research:'openai',reviewer:'cloud',utility:'local'};
  cfg.agent_models={research:'my-openai-model'};
  cfg.providers.anthropic.has_key=true;
  cfg.mcp_agent={enabled:false,url:'',tool:'',models:['mcp-one'],has_token:true};
  const h=await boot({storage:{'pl.lang':'en'},routes:{
    'GET /api/config':()=>cfg,
    'POST /api/config':req=>{for(const[k,v]of Object.entries(req.body))cfg[k]=typeof v==='object'?{...cfg[k],...v}:v;return cfg;},
    'GET /api/models/local':()=>({lmstudio:{models:[{id:'local-one'}]},ollama:{models:['ollama-one']}}),
    'POST /api/models/list':()=>({models:['account-only']})
  }});
  await h.w.PL.settings.open('models');await h.idle();
  assert.equal(h.$('[data-go=library]').textContent.trim(),'Library');
  const fallback=h.byText('.sb .field','Use configured cloud if a local model fails').querySelector('input');
  await change(h,fallback,false);assert.equal(h.server.last('POST','/api/config').body.fallback_to_cloud,false);
  const source=a=>h.$(`select[aria-label="${a} · Model source"]`);
  const model=a=>h.$(`select[aria-label="${a} · Model"]`);
  assert.ok(options(model('research')).includes('gpt-5'));
  assert.ok(options(model('research')).includes('my-openai-model'));
  assert.ok(!options(model('research')).some(m=>m.startsWith('claude')));
  await change(h,source('research'),'anthropic');
  assert.ok(options(model('research')).some(m=>m.startsWith('claude')));
  assert.ok(!options(model('research')).includes('my-openai-model'));
  await change(h,source('research'),'local');assert.ok(options(model('research')).includes('local-one'));
  await change(h,model('research'),'local-one');
  assert.equal(h.server.last('POST','/api/config').body.agent_models.research,'local-one');
  await change(h,source('research'),'ollama');assert.ok(options(model('research')).includes('ollama-one'));
  await change(h,source('research'),'mcp');assert.ok(options(model('research')).includes('mcp-one'));
  assert.ok(!options(model('research')).includes('local-one'));
  await change(h,source('utility'),'auto');assert.equal(model('utility').disabled,true);
  h.server.on('POST /api/config',()=>R({detail:'cannot save'},500));
  await change(h,source('research'),'openai');assert.equal(source('research').value,'mcp');assert.equal(source('research').disabled,false);
  h.server.on('POST /api/config',req=>{for(const[k,v]of Object.entries(req.body))cfg[k]=typeof v==='object'?{...cfg[k],...v}:v;return cfg;});
  await change(h,field(h,'Default cloud'),'openai');assert.ok(options(model('reviewer')).includes('gpt-5'));
  await change(h,source('reviewer'),'claude');
  assert.ok(options(model('reviewer')).some(m=>m.startsWith('claude')));
  const section=h.$('.mcp-agent-config');section.open=true;
  await change(h,section.querySelector('input[type=checkbox]'),true);
  for(const [label,value,key]of [['MCP endpoint','http://127.0.0.1:9000/mcp','url'],['Inference tool name','infer','tool'],['MCP model catalog','mcp-two\nmcp-three,mcp-two','models'],['MCP access token','private-token','token']]){
    const el=field(h,label);await change(h,el,value);
    assert.deepEqual(h.server.last('POST','/api/config').body.mcp_agent[key],key==='models'?['mcp-two','mcp-three']:value);
    if(key==='token')assert.equal(el.value,'');
  }
  assert.ok(options(model('research')).includes('mcp-three'));
  const apiRows=h.$$('.sb table')[1].querySelectorAll('tr');
  const openai=Array.from(apiRows).find(row=>row.cells[0].textContent.includes('OpenAI'));
  const select=openai.querySelector('select');await change(h,select,'gpt-5-mini');
  await change(h,openai.querySelector('details input'),'http://127.0.0.1:9001/v1');
  assert.equal(h.server.last('POST','/api/config').body.providers.openai.base_url,'http://127.0.0.1:9001/v1');
  Array.from(openai.querySelectorAll('button')).find(b=>b.textContent.includes('Models')).click();await h.idle();
  assert.equal(select.value,'gpt-5-mini');assert.ok(options(select).includes('__custom__'));
  assert.ok(options(model('reviewer')).some(m=>m.startsWith('claude')));
  await change(h,source('reviewer'),'openai');assert.ok(options(model('reviewer')).includes('account-only'));
  const key=openai.querySelector('input[type=password]');key.value='retry-secret';
  h.server.on('POST /api/config',()=>R({detail:'save rejected'},500));
  openai.querySelector('button').click();await h.idle();assert.equal(key.value,'retry-secret');assert.equal(openai.querySelector('button').disabled,false);
  const token=field(h,'MCP access token');await change(h,token,'retry-token');assert.equal(token.value,'retry-token');
  assert.deepEqual(h.errors,[]);
});

test('project-level new chat sends only selected settings and creates no phantom topic',async()=>{
  const h=await boot({routes:{'POST /api/chat/sessions':()=>({id:fixtures.meta.session})}});
  await h.w.PL.chat.open();h.w.PL.chat.pending={provider:'cli:codex'};
  h.w.PL.research.tid='';await h.w.PL.chat.submit('A scoped project question');
  const body=h.server.calls.find(c=>c.method==='POST'&&c.path==='/api/chat/sessions').body;
  assert.deepEqual(JSON.parse(JSON.stringify(body)),{settings:{provider:'cli:codex'}});
});

test('provider without a saved model and empty MCP credentials still has scoped choices',async()=>{
  const cfg=fixtures.get('GET /api/config');cfg.agent_modes.research='custom';delete cfg.provider_specs.custom.models;
  cfg.mcp_agent={models:[],url:'http://127.0.0.1/mcp',tool:'infer'};
  const h=await boot({routes:{'GET /api/config':()=>cfg}});await h.w.PL.settings.open('models');
  assert.equal(h.$('select[aria-label="research · Model"]').options.length,2);
  assert.equal(h.$('.mcp-agent-config input[type=password]').value,'');
  h.w.PL.research.onSession(null);h.w.PL.research.onSession({});
});

test('modal keyboard focus stays inside, returns to its opener and replaces listeners cleanly',async()=>{
  const h=await boot();const PL=h.w.PL;
  h.$('#new-chat').focus();
  const close=PL.modal({title:'Keyboard review',body:PL.h('input'),actions:[{label:'Done'}]});
  assert.equal(h.document.activeElement,h.$('.dialog input'));
  const last=h.$('.dialog-f button');last.focus();await h.key(last,'Tab');assert.equal(h.document.activeElement,h.$('.dialog-h button'));
  await h.key(h.document.activeElement,'Tab',{shiftKey:true});assert.equal(h.document.activeElement,last);
  h.$('#new-chat').focus();await h.key(h.document.activeElement,'Tab');assert.equal(h.document.activeElement,h.$('.dialog-h button'));
  const input=h.$('.dialog input');input.focus();await h.key(input,'Tab');assert.equal(h.document.activeElement,input); // browser normally advances internal focus
  close();close();assert.equal(h.document.activeElement,h.$('#new-chat'));
  const opener=PL.h('button');h.document.body.append(opener);opener.focus();
  PL.modal({title:'Removed opener',body:'Text'});opener.remove();
  PL.modal({title:'Replacement',body:'Text'});
  await h.key('.dialog','Escape');assert.equal(h.$('#modal').hidden,true);
  PL.modal({title:'First',body:'Text',actions:[{label:'Next',onClick:()=>{PL.modal({title:'Second',body:'Still open'});}}]});
  await h.clickText('.dialog-f button','Next');assert.equal(h.$('.dialog h2').textContent,'Second');
  assert.deepEqual(h.errors,[]);
});

test('engine shortcut opens scoped workspaces and offers the separate editor action',async()=>{
  const tid='ux-topic',w={id:'ux-workspace',engine:'feynman',path:'D:/Topic files',capabilities:{binary_available:true},artifact_count:0};
  const h=await boot({storage:{'pl.lang':'en'},routes:{
    'GET /api/research/topics':()=>({topics:[{id:tid,title:'UX Topic'}]}),
    [`GET /api/research/topics/${tid}/workspaces`]:()=>({workspaces:[w]})
  }});
  h.w.PL.research.tid=tid;
  await h.click('[data-go=engines]');await h.idle();
  await h.clickText('.research-body button','Open in VS Code');
  assert.equal(h.server.last('POST','/api/research/workspaces/ux-workspace/editor').path,'/api/research/workspaces/ux-workspace/editor');
  assert.equal(h.toast(),'Opened in a separate window');
});
