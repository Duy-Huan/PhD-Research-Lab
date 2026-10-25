const fs=require('node:fs'),path=require('node:path');const {createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve('frontend/package.json'))('playwright');
(async()=>{const out=process.env.PHDLAB_E2E_OUTPUT,browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:375,height:900}});await context.tracing.start({screenshots:true,snapshots:true});
 try{const page=await context.newPage();await page.goto(process.env.PHDLAB_E2E_URL+'/dist/react.html');
 await page.getByRole('button',{name:'Open sidebar',exact:true}).click();await page.getByRole('button',{name:'System Settings',exact:true}).click();
 await page.locator('.settings-studio-content').waitFor();
 const back=page.getByRole('button',{name:'Back to Workspace',exact:true});let failure=null;
 try{await back.click({trial:true,timeout:2000})}catch(e){failure=String(e)}
 const result={mode:'REAL_LOCAL',steps:['375x900 viewport','Open sidebar','System Settings','Try Back to Workspace without dismissing sidebar'],expected:'Selecting Settings closes mobile navigation overlay so settings controls are actionable',actual:{sidebarVisible:await page.getByRole('complementary',{name:'Sidebar',exact:true}).isVisible(),backActionable:!failure,failure},status:failure?'REPRODUCED':'NOT_REPRODUCED'};
 fs.writeFileSync(path.join(out,'reproduction.json'),JSON.stringify(result,null,2));await page.screenshot({path:path.join(out,'reproduction.png')});console.log(JSON.stringify({status:result.status,sidebarVisible:result.actual.sidebarVisible,backActionable:!failure}));
 }finally{await context.tracing.stop({path:path.join(out,'reproduction-trace.zip')});await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=2});
