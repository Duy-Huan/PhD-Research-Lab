// Run only against tools/demo_server.py: creates visibly labelled fixture Topic/papers.
// node tools/upgrade_ui_check.js http://127.0.0.1:8801 artifacts/upgrade-reconciliation/browser
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
    await evaluate(`(async()=>{await PL.post('/api/config',{ui:{language:'en'}});localStorage.setItem('pl.lang','en');location.reload();})()`);
    await sleep(700);await until('!!(window.PL?.state?.project && PL.chat && PL.lang==="en")');
    const topic=await evaluate(`PL.post('/api/research/topics',{title:'Upgrade QA fixture (not scientific literature)',sources:['arxiv']})`);
    const base='/api/research/topics/'+topic.id;
    await evaluate(`PL.post(${JSON.stringify(base+'/papers/import')},{records:Array.from({length:120},(_,i)=>({title:'Fixture paper '+i,doi:'10.9999/qa'+i,source:'browser_test_fixture',year:2025,citations:i,references:i?['10.9999/qa'+(i-1)]:[]}))})`);
    await evaluate(`PL.research.tid=${JSON.stringify(topic.id)};PL.research.open('papers')`);
    await check('Real API paginates 120 fixture papers without agent calls',`document.querySelectorAll('.research-card').length===25 && document.querySelector('.research-body').textContent.includes('120 Papers')`);
    await evaluate(`document.querySelector('.research-card input').click();PL.prompt=async()=> 'qa-tag'`);await click('Add tags');
    await until(`document.querySelector('.research-card').textContent.includes('qa-tag')`);
    await change('.research-filters input[aria-label="Tag"]','qa-tag');
    await until(`document.querySelectorAll('.research-card').length===1`);
    await check('Tag bulk action persists and filters through backend',`document.querySelector('.research-card').textContent.includes('qa-tag')`);
    await shot('upgrade-papers-en.png');
    await change('.research-filters input[aria-label="Tag"]','');await until(`document.querySelectorAll('.research-card').length===25`);
    await change('.research-filters > select:last-of-type','citations');
    await until(`document.querySelector('.research-card b').textContent==='Fixture paper 119'`);checks.push('Citation sort uses retained source counts');
    await change('.research-filters input[aria-label="To year"]','2024');await until(`document.querySelectorAll('.research-card').length===0`);checks.push('Upper-year filter returns actual empty result');
    await change('.research-filters input[aria-label="To year"]','');await until(`document.querySelectorAll('.research-card').length===25`);
    await click('Citation graph');await until(`!!document.querySelector('.dialog')`);
    await check('Citation graph retains exact versioned source edges',`(()=>{const g=JSON.parse(document.querySelector('.dialog pre').textContent);return g.nodes.length===120&&g.edges.length===119&&g.edges.every(e=>e.version_id&&e.cited_paper_id)})()`);
    await evaluate(`document.querySelector('.dialog-f button').click();PL.research.open('topics')`);await click('Archive Topic');
    await until(`Array.from(document.querySelectorAll('.research-card button')).some(b=>b.textContent==='Restore Topic')`);
    await check('Archived Topic retains its papers',`PL.get(${JSON.stringify(base+'/papers')}).then(r=>r.total===120)`);await click('Restore Topic');await until(`Array.from(document.querySelectorAll('.research-card button')).some(b=>b.textContent==='Archive Topic')`);
    await evaluate(`(async()=>{await PL.post('/api/config',{ui:{language:'vi'}});localStorage.setItem('pl.lang','vi');location.reload();})()`);await sleep(700);await until(`!!(window.PL?.state?.project&&PL.lang==='vi')`);
    await evaluate(`PL.research.tid=${JSON.stringify(topic.id)};PL.research.open('papers')`);
    await check('New Vietnamese controls are translated',`document.querySelector('.research-body').textContent.includes('Đồ thị trích dẫn')&&document.querySelector('.research-body').textContent.includes('Đọc Zotero cục bộ')&&document.querySelector('.research-body').textContent.includes('Bộ lọc bổ sung')`);
    await shot('upgrade-papers-vi.png');
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await shot('upgrade-papers-mobile.png');
    await check('Mobile research drawer remains accessible with central composer',`!!document.querySelector('#input')&&!document.querySelector('#panel').hidden&&document.documentElement.scrollWidth<=document.documentElement.clientWidth`);
    if(errors.length)throw Error('Browser exceptions: '+errors.join('; '));
    fs.writeFileSync(path.join(output,'upgrade-checks.json'),JSON.stringify({checks,errors,passed:true,topic_id:topic.id,scope:'Isolated demo data and real backend; no live scholarly calls or model inference'},null,2));
    console.log(checks.length+' upgrade browser checks passed');
  } catch(e) {
    fs.writeFileSync(path.join(output,'upgrade-checks.json'),JSON.stringify({checks,errors,failure:String(e)},null,2));console.error(String(e));process.exitCode=1;
  } finally {socket?.close();browser.kill();}
})();
