// Real built UI + backend + Codex. Requests are observed, never stubbed.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const puppeteer = require('puppeteer-core');
const [base, output] = process.argv.slice(2);
fs.mkdirSync(output, {recursive: true});
const report = {passed: false, mockedRequests: 0, pageErrors: [], checks: [], sessions: []};
const browser = await puppeteer.launch({executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  headless: true, args: ['--no-first-run', '--disable-background-networking']});
const page = await browser.newPage();
page.on('pageerror', e => report.pageErrors.push(String(e)));
page.on('response', async res => {
  if (res.request().method() === 'POST' && res.url() === base + '/api/chat/sessions') {
    try { report.sessions.push((await res.json()).id); } catch {}
  }
});
async function send(text) {
  await page.waitForSelector('textarea');
  await page.type('textarea', text);
  await page.waitForSelector('button[title="Gửi"],button[title="Send (Enter)"]');
  await page.click('button[title="Gửi"],button[title="Send (Enter)"]');
}
async function newChat() {
  await page.evaluate(() => [...document.querySelectorAll('button')].find(e => ['New chat', 'Cuộc trò chuyện mới'].includes(e.textContent.trim()))?.click());
  await page.waitForSelector('button[title="Gửi"],button[title="Send (Enter)"]');
}
try {
  await page.setViewport({width: 1440, height: 1000});
  await page.goto(base, {waitUntil: 'networkidle2', timeout: 30000});
  await page.waitForFunction(() => [...document.querySelectorAll('textarea')].length > 0);
  await newChat();
  await page.waitForResponse(res => res.url().endsWith('/api/models') && res.status() === 200, {timeout: 5000}).catch(() => {});
  await send('Reply with the single word OK. Do not use tools or read files.');
  await page.waitForFunction(() => [...document.querySelectorAll('.msg-card.assistant')].some(e => /\bOK\b/.test(e.textContent)), {timeout: 120000});
  report.checks.push('Actual Composer send -> HTTP chat -> Codex subscription CLI -> rendered OK');
  await page.screenshot({path: path.join(output, 'codex-chat.png'), fullPage: true});
  await newChat();
  await send('/openscience Design a controlled experimental protocol & ablation study.');
  await page.waitForSelector('aside[aria-label^="Run RR-"]', {timeout: 15000});
  await page.waitForFunction(() => [...document.querySelectorAll('aside[aria-label^="Run RR-"]')].some(e => e.textContent.includes('APPROVAL_PENDING')), {timeout: 10000});
  const body = await page.$eval('.message-list', e => e.textContent);
  if (body.includes('Unknown command')) throw new Error('OpenScience command is still unknown');
  if (!body.includes('APPROVAL_PENDING')) throw new Error('Missing exact run approval state');
  report.checks.push('Exact reported /openscience prompt -> real backend plan -> visible approval card; no runtime execution claimed');
  await page.screenshot({path: path.join(output, 'openscience-plan.png'), fullPage: true});
  const cancel = await page.$('aside[aria-label^="Run RR-"] button:last-of-type');
  await cancel.click();
  await page.waitForFunction(() => [...document.querySelectorAll('aside')].some(e => e.textContent.includes('CANCELLED')), {timeout: 10000});
  report.checks.push('Cancel planned external run from the actual conversation');
  await page.setViewport({width: 375, height: 812});
  await page.screenshot({path: path.join(output, 'chat-mobile.png'), fullPage: true});
  report.passed = report.pageErrors.length === 0;
} catch (e) {
  report.error = String(e);
  await page.screenshot({path: path.join(output, 'failure.png'), fullPage: true}).catch(() => {});
} finally {
  fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify(report));
process.exitCode = report.passed ? 0 : 1;
