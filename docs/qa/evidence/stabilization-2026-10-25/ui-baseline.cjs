const {createRequire}=require('node:module');
const fs=require('node:fs');const path=require('node:path');
const load=createRequire(path.resolve('frontend/package.json'));
const {chromium}=load('playwright');
async function main(){
 const out=process.env.PHDLAB_E2E_OUTPUT; const origin=process.env.PHDLAB_E2E_URL;
 if(!out||!origin)throw Error('Owned application lease required');
 const browser=await chromium.launch({headless:true});const records=[];const errors=[];
 try{
  for(const width of [375,768,1280,1920]){
   const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
   await context.tracing.start({screenshots:true,snapshots:true,sources:false});
   const page=await context.newPage();const events=[];
   page.on('pageerror',e=>events.push({kind:'pageerror',message:e.message}));
   page.on('console',e=>{if(e.type()==='error')events.push({kind:'console',message:e.text()})});
   page.on('requestfailed',r=>events.push({kind:'requestfailed',url:r.url(),failure:r.failure()}));
   page.on('response',r=>{if(r.status()>=400)events.push({kind:'http-error',url:r.url(),status:r.status()})});
   try{
    await page.goto(origin+'/dist/react.html');
    await page.locator('#view textarea').waitFor();
    for(const surface of ['workspace','settings']){
     if(surface==='settings'){const settings=page.getByRole('button',{name:'System Settings',exact:true});if(!await settings.isVisible())await page.getByRole('button',{name:'Open sidebar',exact:true}).click();await settings.click();}
     if(surface==='settings')await page.locator('.settings-studio-content').waitFor();
     await page.evaluate(()=>document.fonts.ready);
     await page.addScriptTag({path:load.resolve('axe-core/axe.min.js')});
     const axe=await page.evaluate(async()=>await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}}));
     const metrics=await page.evaluate(()=>({documentWidth:document.documentElement.scrollWidth,viewport:innerWidth,
      unnamedButtons:[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length&&!e.textContent.trim()&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')&&!e.getAttribute('title')).map(e=>e.outerHTML.slice(0,350)),
      dialogs:[...document.querySelectorAll('[role=dialog]')].map(e=>({label:e.getAttribute('aria-label'),modal:e.getAttribute('aria-modal')}))}));
     const tabs=[];for(let i=0;i<12;i++){await page.keyboard.press('Tab');tabs.push(await page.evaluate(()=>({tag:document.activeElement.tagName,name:document.activeElement.getAttribute('aria-label')||document.activeElement.textContent?.trim().slice(0,80),id:document.activeElement.id})));}
     const screenshot=`${surface}-${width}.png`;await page.screenshot({path:path.join(out,screenshot),fullPage:true,animations:'disabled'});
     const raw=`${surface}-${width}-axe.json`;fs.writeFileSync(path.join(out,raw),JSON.stringify(axe,null,2));
     records.push({surface,width,metrics,tabs,screenshot,axe_file:raw,violations:axe.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,helpUrl:v.helpUrl,nodes:v.nodes.map(n=>({target:n.target,html:n.html,failureSummary:n.failureSummary}))})),incomplete_count:axe.incomplete.length});
    }
   }catch(e){await page.screenshot({path:path.join(out,`failure-${width}.png`)}).catch(()=>{});errors.push({width,error:String(e)})}
   finally{await context.tracing.stop({path:path.join(out,`trace-${width}.zip`)});await context.close();}
   fs.writeFileSync(path.join(out,`events-${width}.json`),JSON.stringify(events,null,2));
  }
 }finally{await browser.close();}
 const result={mode:'REAL_LOCAL',scope:'Workspace and Settings rendered baseline; not full system acceptance',browser:'Chromium',axe_version:load('axe-core/package.json').version,visual_baseline_review:'PENDING',records,errors};
 fs.writeFileSync(path.join(out,'ui-baseline.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify({scans:records.length,errors:errors.length,violations:records.map(r=>({surface:r.surface,width:r.width,rules:r.violations.map(v=>v.id)}))}));
 if(errors.length)process.exitCode=2;
}
main().catch(e=>{console.error(e);process.exitCode=2});
