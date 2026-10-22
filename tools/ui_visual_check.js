// Real Edge visual/interaction regression against an isolated tools/demo_server.py.
// node tools/ui_visual_check.js http://127.0.0.1:8799 artifacts/ui-refinement
'use strict';
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const [url='http://127.0.0.1:8799',output='artifacts/ui-refinement']=process.argv.slice(2);
const port=9800+Math.floor(Math.random()*500);
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'phdlab-ui-'));
const browser=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless=new','--disable-gpu',`--remote-debugging-port=${port}`,'--window-size=1440,900','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
  let socket,sequence=0;const pending=new Map(),errors=[],checks=[];
  try{
    fs.mkdirSync(output,{recursive:true});
    let endpoint;
    for(let i=0;i<60&&!endpoint;i++){try{const pages=await(await fetch(`http://127.0.0.1:${port}/json`)).json();endpoint=pages.find(p=>p.type==='page')?.webSocketDebuggerUrl;}catch{}if(!endpoint)await sleep(150);}
    if(!endpoint)throw new Error('Edge debugging endpoint did not start');
    socket=new WebSocket(endpoint);await new Promise(resolve=>socket.onopen=resolve);
    socket.onmessage=message=>{const event=JSON.parse(message.data);if(pending.has(event.id)){const {resolve,reject}=pending.get(event.id);pending.delete(event.id);event.error?reject(new Error(event.error.message)):resolve(event.result);}
      if(event.method==='Runtime.exceptionThrown')errors.push(event.params.exceptionDetails.exception?.description||event.params.exceptionDetails.text);
      if(event.method==='Runtime.consoleAPICalled'&&event.params.type==='error')errors.push(event.params.args.map(a=>a.value||a.description).join(' '));};
    const call=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++sequence,{resolve,reject});socket.send(JSON.stringify({id:sequence,method,params}));});
    const evaluate=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value;};
    await call('Runtime.enable');
    const ready=async()=>{for(let i=0;i<80;i++){if(await evaluate('!!(window.PL?.chat && document.querySelector("#input") && PL.state.project)'))return;await sleep(100);}throw new Error('Application did not become ready');};
    const shot=async name=>{await sleep(350);const screen=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(output,name+'.png'),Buffer.from(screen.data,'base64'));};
    const check=async(name,expression)=>{const value=await evaluate(expression);checks.push({name,passed:!!value});if(!value)throw new Error('Visual check failed: '+name);};
    await call('Page.navigate',{url});await ready();
    await evaluate('(async()=>{await PL.post("/api/config",{ui:{language:"vi"}});localStorage.setItem("pl.lang","vi");location.reload();})()');await sleep(500);await ready();await shot('after');
    await check('Vietnamese shell is consistent','document.documentElement.lang === "vi" && document.querySelector("#projects-btn").textContent === "Dự án & hội thoại"');
    await evaluate('(async()=>{const {sessions}=await PL.get("/api/chat/sessions");await PL.chat.open(sessions[0].id);})()');
    await evaluate(`document.querySelector('.msg.user button[title="Ghim tin nhắn"]').click()`);await sleep(400);
    await evaluate('PL.chat.pinsPanel()');await shot('after-chat-pins');
    await check('pin is persisted and visible','PL.chat.s.messages.some(m=>m.pinned) && document.querySelectorAll(".pinned-messages article").length === 1');
    await evaluate(`document.querySelector('.pinned-messages button[title="Bỏ ghim tin nhắn"]').click()`);await sleep(400);
    await check('unpin refreshes drawer immediately','document.querySelectorAll(".pinned-messages article").length === 0');
    await evaluate('PL.projectsPanel()');await evaluate('document.querySelector(".project-group").open=true');await sleep(400);await shot('after-projects');
    await check('project drawer contains grouped conversations','document.querySelectorAll(".project-chat").length > 0');
    await evaluate('PL.settings.open("look")');await sleep(400);await shot('after-themes-light');
    await evaluate('PL.themes.select("lab-midnight")');await shot('after-themes-dark');
    await check('theme controls semantic colors','document.documentElement.dataset.themePackage === "lab-midnight" && document.querySelector("#theme-select").value === "lab-midnight" && getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() === "#a6b9ff"');
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',windowsVirtualKeyCode:9});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',windowsVirtualKeyCode:9});
    await evaluate('document.querySelector("#install-theme").focus()');
    await check('keyboard focus is visible','getComputedStyle(document.activeElement).outlineStyle !== "none" || getComputedStyle(document.activeElement).boxShadow !== "none"');
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});await shot('after-mobile-settings');
    await check('settings fit narrow viewport','document.querySelector(".dialog").getBoundingClientRect().width <= innerWidth && document.documentElement.scrollWidth <= innerWidth');
    await check('settings tabs retain a readable single row','[...document.querySelectorAll(".settings nav .nav")].every(el=>el.getBoundingClientRect().height < 60)');
    await evaluate('document.querySelector(".dialog").dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}))');
    await evaluate('PL.panels.close()');await shot('after-mobile-chat');
    await check('chat has no horizontal page overflow','document.documentElement.scrollWidth <= innerWidth && document.querySelector("#input").getBoundingClientRect().right <= innerWidth');
    await check('mobile header actions do not overlap','(()=>{const buttons=[...document.querySelectorAll("#top > button,#top-tools button")].filter(el=>getComputedStyle(el).display!=="none").sort((a,b)=>a.getBoundingClientRect().left-b.getBoundingClientRect().left);return buttons.every((el,i)=>i===0||el.getBoundingClientRect().left>=buttons[i-1].getBoundingClientRect().right-1);})()');
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
    await evaluate('(async()=>{await PL.post("/api/config",{ui:{language:"en"}});localStorage.setItem("pl.lang","en");PL.themes.select("light");location.reload();})()');await sleep(500);await ready();
    await evaluate('PL.settings.open("providers")');await sleep(400);await shot('after-english-settings');
    await check('English settings have translated runtime labels','document.documentElement.lang === "en" && document.querySelector(".settings").textContent.includes("Research engine mode") && !document.querySelector(".settings").textContent.includes("Chỉ đánh dấu")');
    await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
    await check('reduced motion is respected','parseFloat(getComputedStyle(document.querySelector(".btn")).transitionDuration) <= 0.001');
    fs.writeFileSync(path.join(output,'browser-checks.json'),JSON.stringify({checks,errors},null,2));
    if(errors.length)throw new Error(errors.join('\n'));
    console.log(`${checks.length} real-browser checks passed; screenshots saved in ${output}`);
  }catch(error){fs.writeFileSync(path.join(output,'browser-checks.json'),JSON.stringify({checks,errors,failure:String(error)},null,2));process.exitCode=1;console.error(error.message);}
  finally{socket?.close();browser.kill();}
})();
