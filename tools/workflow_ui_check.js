// Real Edge workflow checks against tools/demo_server.py; no inference or native windows launched.
// node tools/workflow_ui_check.js http://127.0.0.1:8802 artifacts/workflow-ux/workflows
'use strict';
const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const [url,output]=process.argv.slice(2),port=10300+Math.floor(Math.random()*300);
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'phdlab-upgrade-'));
const browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu',`--remote-debugging-port=${port}`,'--window-size=1440,900','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  let socket,id=0;const pending=new Map(),errors=[],checks=[];
  try {
    fs.mkdirSync(output,{recursive:true});let endpoint;
    for(let i=0;i<60&&!endpoint;i++){try{const tabs=await(await fetch(`http://127.0.0.1:${port}/json`)).json();endpoint=tabs.find(t=>t.type==='page')?.webSocketDebuggerUrl;}catch{}if(!endpoint)await sleep(100);}
    if(!endpoint)throw Error('Edge did not start');
    socket=new WebSocket(endpoint);await new Promise(r=>socket.onopen=r);
    socket.onmessage=m=>{const e=JSON.parse(m.data);if(pending.has(e.id)){const p=pending.get(e.id);pending.delete(e.id);e.error?p.reject(Error(e.error.message)):p.resolve(e.result);}
      if(e.method==='Runtime.exceptionThrown')errors.push(e.params.exceptionDetails.exception?.description||e.params.exceptionDetails.text);};
    const call=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
    const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
    const until=async expression=>{for(let i=0;i<100;i++){if(await evaluate(expression))return;await sleep(80);}throw Error('Timed out: '+expression);};
    const check=async(name,expression)=>{if(!await evaluate(expression))throw Error(name);checks.push(name);};
    const click=text=>evaluate(`Array.from(document.querySelectorAll('.research-body button')).find(b=>b.textContent===${JSON.stringify(text)}).click()`);
    const change=(selector,value)=>evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change'));})()`);
    const shot=async name=>{await sleep(250);const r=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,name),Buffer.from(r.data,'base64'));};
    await call('Runtime.enable');await call('Page.navigate',{url});await until('!!(window.PL?.state?.project && PL.chat)');
    // Server language can trigger a first-boot reload; wait for that navigation before mutating settings.
    await sleep(800);await until('!!(window.PL?.state?.project && PL.chat)');
    await evaluate(`(async()=>{await PL.post('/api/config',{ui:{language:'en'}});localStorage.setItem('pl.lang','en');location.reload();})()`);
    await sleep(700);await until('!!(window.PL?.state?.project && PL.chat && PL.lang==="en")');
    await evaluate(`PL.post('/api/config',{agent_modes:{research:'openai'},agent_models:{research:'qa-openai-custom'},mcp_agent:{models:['qa-mcp-model']}})`);
    await evaluate(`PL.settings.open('models')`);await until(`!!document.querySelector('.agent-model-grid')`);
    await check('OpenAI agent shows only OpenAI catalog plus its own override',`(()=>{const values=[...document.querySelector('select[aria-label="research · Model"]').options].map(o=>o.value);return values.includes('gpt-5')&&values.includes('qa-openai-custom')&&!values.some(v=>v.startsWith('claude')||v.startsWith('gemini'));})()`);
    await check('English agent descriptions are translated',`!document.querySelector('.agent-model-grid').textContent.includes('điều phối')&&!document.querySelector('.sb').textContent.includes('thay thế đã kiểm chứng')`);
    await shot('models-desktop.png');
    await change('select[aria-label="research · Model source"]','gemini');
    await until(`document.querySelector('select[aria-label="research · Model"]').querySelector('option[value="gemini-2.5-pro"]')`);
    await check('Changing source resets old model in UI and persisted config',`(async()=>{const cfg=await PL.get('/api/config');return cfg.agent_modes.research==='gemini'&&!cfg.agent_models.research&&![...document.querySelector('select[aria-label="research · Model"]').options].some(o=>o.value==='qa-openai-custom');})()`);
    await change('select[aria-label="research · Model source"]','mcp');await until(`document.querySelector('select[aria-label="research · Model"]').querySelector('option[value="qa-mcp-model"]')`);
    await check('MCP has a separate catalog and explicit inference contract',`document.querySelector('.mcp-agent-config').textContent.includes('must accept system')&&![...document.querySelector('select[aria-label="research · Model"]').options].some(o=>o.value==='gpt-5')`);
    await change('select[aria-label="research · Model source"]','auto');await until(`document.querySelector('select[aria-label="research · Model"]').disabled`);
    await check('Auto routing cannot attach an override to every vendor',`document.querySelector('select[aria-label="research · Model"]').disabled`);
    await evaluate(`document.querySelector('.dialog-h button').focus()`);
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',windowsVirtualKeyCode:9,modifiers:8});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',windowsVirtualKeyCode:9});
    await check('Shift Tab wraps focus inside modal',`document.querySelector('.dialog').contains(document.activeElement)&&document.activeElement!==document.querySelector('.dialog-h button')`);
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    await evaluate(`document.querySelector('.settings .sb').scrollTop=0`);await shot('models-mobile.png');
    await check('Mobile agent cards expose complete controls without sideways scrolling',`(()=>{const table=document.querySelector('.agent-model-grid');return table.scrollWidth<=table.clientWidth&&[...table.querySelectorAll('select')].every(el=>el.getBoundingClientRect().left>=0&&el.getBoundingClientRect().right<=innerWidth)&&document.documentElement.scrollWidth<=innerWidth;})()`);
    await evaluate(`PL._closeModal()`);
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
    const topic=await evaluate(`PL.post('/api/research/topics',{title:'Workflow UX fixture (not research)',sources:['arxiv']})`);
    for(const engine of ['openscience','feynman'])await evaluate(`PL.post('/api/research/topics/${topic.id}/workspaces',{engine:${JSON.stringify(engine)}})`);
    await evaluate(`PL.research.tid=${JSON.stringify(topic.id)};document.querySelector('[data-go="engines"]').click()`);await until(`document.querySelectorAll('.research-body .research-card').length===2`);
    await check('Independent engines have discoverable open, editor and sync actions',`[...document.querySelectorAll('.research-body .research-card')].every(card=>card.textContent.includes('Open in VS Code')&&card.textContent.includes('Sync Now')&&card.querySelector('button').textContent.includes('↗'))`);
    await shot('engine-workspaces.png');
    // Review each major deterministic surface without sending a prompt or running experiments.
    await evaluate(`PL.panels.library()`);await until(`!document.querySelector('#panel').hidden&&document.querySelector('#panel-body input')`);
    await check('Library remains reachable beside the chat',`!!document.querySelector('#input')&&document.querySelector('#panel-body').textContent.length>40`);
    await shot('library.png');
    await evaluate(`PL.panels.code()`);await until(`document.querySelector('#panel-body').textContent.includes('VS Code')`);
    await check('Code workspace retains native editor workflow',`document.querySelector('#panel-body').textContent.includes('VS Code')`);
    await evaluate(`PL.panels.paper()`);await until(`document.querySelector('#panel-body').textContent.includes('/write')`);
    await check('Writing workspace opens without losing the composer',`!!document.querySelector('#input')&&!document.querySelector('#panel').hidden`);
    await evaluate(`PL.projectsPanel()`);await until(`!!document.querySelector('.project-browser')`);
    await check('Projects and conversations remain grouped',`document.querySelectorAll('.project-group').length>0`);
    await evaluate(`PL.panels.close();PL.settings.open('models')`);await until(`!!document.querySelector('.agent-model-grid')`);
    await evaluate(`(async()=>{await PL.post('/api/config',{ui:{language:'vi'}});localStorage.setItem('pl.lang','vi');location.reload();})()`);await sleep(700);await until('!!(window.PL?.state?.project && PL.lang==="vi")');
    await evaluate(`PL.settings.open('models')`);await until(`!!document.querySelector('.agent-model-grid')`);
    await check('Vietnamese MCP controls and agent model labels are consistent',`document.querySelector('.mcp-agent-config').textContent.includes('Cấu hình agent suy luận MCP')&&document.querySelector('select[aria-label="research · Nguồn model"]')`);
    await shot('models-vietnamese.png');
    if(errors.length)throw Error('Browser exceptions: '+errors.join('; '));
    fs.writeFileSync(path.join(output,'workflow-checks.json'),JSON.stringify({checks,errors,passed:true,scope:'Isolated demo with real backend. No model inference, paid calls or native windows launched.'},null,2));
    console.log(checks.length+' workflow browser checks passed');
  }catch(e){fs.writeFileSync(path.join(output,'workflow-checks.json'),JSON.stringify({checks,errors,failure:String(e)},null,2));console.error(String(e));process.exitCode=1;}
  finally{socket?.close();browser.kill();}
})();
