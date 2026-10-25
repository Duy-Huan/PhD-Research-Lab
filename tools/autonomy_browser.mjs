import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const puppeteer = require('puppeteer-core');
const [base, output] = process.argv.slice(2);
const report = { passed: false, pageErrors: [], failedRequests: [], screenshots: [], checks: [] };
const executablePath = process.env.PHDLAB_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const browser = await puppeteer.launch({ executablePath, headless: true, args: ['--disable-background-networking', '--no-first-run'] });
const page = await browser.newPage();
page.on('pageerror', error => report.pageErrors.push(String(error)));
page.on('requestfailed', request => report.failedRequests.push({ url: request.url(), error: request.failure()?.errorText }));
page.on('response', response => { if (response.status() >= 400) report.failedRequests.push({ url: response.url(), status: response.status() }); });
await page.setRequestInterception(true);
page.on('request', request => {
  if (/^(data:|blob:)/.test(request.url()) || new URL(request.url()).origin === new URL(base).origin) request.continue();
  else { report.failedRequests.push({ url: request.url(), error: 'External browser request denied' }); request.abort(); }
});
async function textClick(text) {
  await page.waitForFunction(text => [...document.querySelectorAll('button')].some(e => e.textContent?.trim() === text && !e.disabled), {}, text);
  await page.evaluate(text => [...document.querySelectorAll('button')].find(e => e.textContent?.trim() === text && !e.disabled).click(), text);
}
async function screenshot(name) {
  await page.screenshot({ path: path.join(output, name), fullPage: true });
  report.screenshots.push(name);
}
try {
  await page.setViewport({ width: 1440, height: 1000 });
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[title="Select Research Topic & SKB"]');
  await page.click('[title="Select Research Topic & SKB"]');
  const topics = await (await fetch(base + '/api/research/topics')).json();
  const title = topics.topics[0].title;
  await page.waitForFunction(title => [...document.querySelectorAll('.panel-b div')].some(e => e.textContent === title), {}, title);
  await page.evaluate(title => [...document.querySelectorAll('.panel-b div')].find(e => e.textContent === title).click(), title);
  await page.click('#drawer-close-btn');
  await textClick('Autonomous Missions');
  await textClick('Workflows L1–L4');
  await page.waitForSelector('section[aria-label="Workflows L1–L4"]');
  await page.select('section form select', 'L1');
  await page.type('section form textarea', 'Browser fixture: summarize these supplied sources in one concise sentence with uncertainty.');
  await page.waitForFunction(() => document.querySelectorAll('section form input[type="checkbox"]').length >= 2);
  const checkboxes = await page.$$('section form input[type="checkbox"]');
  if (checkboxes.length < 2) throw new Error('Missing source choices');
  await checkboxes[0].click(); await checkboxes[1].click();
  await textClick('Create draft');
  await page.waitForFunction(() => [...document.querySelectorAll('article')].some(e => e.textContent?.includes('Browser fixture:')));
  await screenshot('autonomy-desktop-draft.png');
  const article = await page.evaluateHandle(() => [...document.querySelectorAll('article')].find(e => e.textContent?.includes('Browser fixture:')));
  const note = await article.$('input');
  await note.type('Simulated browser user reviewed the displayed plan and source evidence.');
  await textClick('Approve plan and run');
  await textClick('Accept step');
  // The next acceptance must wait for a new result, rather than racing the disabled in-flight control.
  await page.waitForFunction(() => {
    const e = [...document.querySelectorAll('article')].find(e => e.textContent?.includes('Browser fixture:'));
    return e && [...e.querySelectorAll('pre')].some(p => p.textContent?.includes('"provider": "local"')) && e.textContent.includes('awaiting_step_review');
  }, { timeout: 60000 });
  await textClick('Accept step');
  await page.waitForFunction(() => [...document.querySelectorAll('article')].some(e => e.textContent?.includes('Browser fixture:') && e.textContent.includes('completed ·')));
  report.checks.push('Actual UI draft → exact plan approval → two result reviews → completed; real local inference');
  const details = await article.$('details');
  await details.evaluate(e => { e.open = true; });
  await screenshot('autonomy-desktop-completed.png');
  await page.setViewport({ width: 375, height: 812 });
  await details.evaluate(e => { e.open = false; });
  await page.$eval('.panel-b', e => { e.scrollTop = 0; });
  await page.keyboard.press('Tab');
  const geometry = await page.evaluate(() => {
    const bounds = document.getElementById('panel').getBoundingClientRect();
    return { viewport: innerWidth, document: document.documentElement.scrollWidth, focus: document.activeElement?.tagName, panelLeft: bounds.left, panelWidth: bounds.width };
  });
  report.mobile = geometry;
  if (geometry.document > geometry.viewport + 2) throw new Error('Mobile document has horizontal overflow: ' + JSON.stringify(geometry));
  if (geometry.panelLeft < -1 || geometry.panelLeft > 1 || geometry.panelWidth < geometry.viewport - 2) throw new Error('Mobile inspector is clipped/obscured: ' + JSON.stringify(geometry));
  await screenshot('autonomy-mobile.png');
  if (report.pageErrors.length) throw new Error('Browser runtime errors: ' + report.pageErrors.join('; '));
  if (report.failedRequests.length) throw new Error('Browser request failures: ' + JSON.stringify(report.failedRequests));
  report.passed = true;
} catch (error) {
  report.error = String(error.stack || error);
  await screenshot('autonomy-browser-failure.png');
} finally {
  await browser.close();
  fs.writeFileSync(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
}
console.log(JSON.stringify(report));
process.exitCode = report.passed ? 0 : 1;
