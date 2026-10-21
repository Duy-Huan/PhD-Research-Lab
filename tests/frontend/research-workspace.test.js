'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {boot, fixtures, R} = require('./harness');
const SID = fixtures.meta.session;
const TID = 'b4b26242-7e59-424d-8467-565121eb36c3';
const PID = 'b54b9233-8733-4282-9ba3-0483dc03af3d';
const topic = {id: TID, title: 'MRI denoising', objectives: 'Grounded evidence', keywords: ['MRI'], sources: ['openalex'], cadence: 'manual', pdf_limit: 10, enabled: false};
const paper = {id: PID, title: 'Denoising evidence', year: 2024, venue: 'Known venue', sources: ['OpenAlex'], level: 0, state: 'candidate', oa_locations: [{url:'https://example.org/a.pdf'}], flags: ['preprint'], association: {matched_terms:['MRI']}, versions: []};
const actions = [['find', 'papers'], ['topic', 'topics'], ['workspace', 'workspaces'], ['sync', 'workspaces'], ['jobs', 'jobs']].map(([name, route_or_component_key]) => ({name, route_or_component_key, title:name, description:'0 LLM calls', aliases:[], category:'quick_action', mode:'ui', availability:'available'}));
async function page(extra = {}) {
  return boot({hash:'#/chat/' + SID, routes: {
    'GET /api/chat/sessions/:id': () => ({...fixtures.get('GET /api/chat/sessions/:id'), topic_id:TID}),
    'GET /api/skills': () => ({...fixtures.get('GET /api/skills'), actions}),
    'GET /api/research/topics': () => ({project_id:'p', topics:[topic]}),
    [`GET /api/research/topics/${TID}/papers`]: req => ({papers:[paper], total:101, offset:Number(req.query.offset)}),
    [`GET /api/research/topics/${TID}/workspaces`]: () => ({workspaces:[]}),
    [`GET /api/research/topics/${TID}/artifacts`]: () => ({artifacts:[]}),
    [`GET /api/research/topics/${TID}/provenance`]: () => ({events:[]}),
    [`GET /api/research/topics/${TID}/findings`]: () => ({findings:[]}),
    'GET /api/research/jobs': () => ({jobs:[]}),
    ...extra,
  }});
}
const noTurns = h => assert.equal(h.server.calledWith('POST', '/api/chat/sessions/' + SID + '/turns').length, 0);

test('/find and /sync are deterministic; drawer preserves the chat composer', async () => {
  const h = await page();
  const composer = h.$('#input');
  await h.w.PL.chat.submit('/find'); await h.idle(30);
  assert.equal(h.$('.research-body').dataset.mode, 'papers');
  assert.equal(h.$('#input'), composer);
  assert.match(h.$('.research-card').textContent, /Denoising evidence/);
  await h.w.PL.chat.submit('/sync'); await h.idle(30);
  assert.equal(h.$('.research-body').dataset.mode, 'workspaces');
  noTurns(h);
  assert.deepEqual(h.errors, []);
});

test('search/filter/page calls backend; selections feed explicit AI turn only', async () => {
  const h = await page();
  await h.w.PL.research.open('papers');
  await h.input('.research-filters input[type=search]', 'MRI'); await h.idle(35);
  assert.equal(h.server.last('GET', '/api/research/topics/' + TID + '/papers').query.q, 'MRI');
  await h.clickText('.research-body button', '→');
  assert.equal(h.server.last('GET', '/api/research/topics/' + TID + '/papers').query.offset, '25');
  await h.click('.research-card input[type=checkbox]');
  assert.equal(h.$$('#research-chips button').length, 1);
  noTurns(h);
  h.w.PL.research.ai('review'); noTurns(h);
  assert.match(h.$('#input').value, /^\/review/);
  await h.w.PL.chat.submit();
  const req = h.server.last('POST', '/api/chat/sessions/' + SID + '/turns');
  assert.deepEqual(req.body.overrides.sources, ['paper:' + PID]);
});

test('bulk download queues real backend job; job failures remain visible and retryable', async () => {
  const h = await page({
    'GET /api/research/jobs': () => ({jobs:[{id:'job1', kind:'download', status:'failed', updated:'2026-10-21T00:00:00Z', payload:{error:'No verified OA PDF'}}]}),
    [`POST /api/research/topics/${TID}/papers/bulk`]: () => ({id:'job1',status:'queued'}),
    'POST /api/research/jobs/job1/retry': () => ({id:'job2',status:'queued'}),
  });
  await h.w.PL.research.open('papers');
  await h.click('.research-card input[type=checkbox]');
  await h.clickText('.research-bulk button', 'OA PDF'); await h.idle(30);
  assert.equal(h.server.last('POST', '/api/research/topics/' + TID + '/papers/bulk').body.action, 'download');
  assert.match(h.$('.research-body').textContent, /No verified OA PDF/);
  await h.clickText('.research-body button', 'Retry');
  assert.equal(h.server.calledWith('POST', '/api/research/jobs/job1/retry').length, 1);
  noTurns(h);
});

test('topic switch clears selections and creates a separate bound conversation', async () => {
  const h = await page({'POST /api/chat/sessions': () => ({id:'as-newtopic'})});
  h.w.PL.research.toggle('paper:' + PID, 'Selected', true);
  await h.w.PL.research.switchTopic('another-topic');
  assert.equal(h.w.PL.research.selected.size, 0);
  assert.equal(h.server.last('POST','/api/chat/sessions').body.topic_id, 'another-topic');
  noTurns(h);
});

test('missing backend and unavailable plugin show errors without invoking AI', async () => {
  const h = await page({'GET /api/research/topics': () => R({detail:'Topic service offline'},503)});
  await h.w.PL.research.open('papers');
  assert.match(h.$('.research-body').textContent, /Topic service offline/);
  await h.w.PL.research.dispatch({availability:'disabled',route_or_component_key:'papers'});
  noTurns(h);
  await assert.rejects(h.w.PL.research.dispatch({availability:'available',route_or_component_key:'arbitrary-plugin-code'}), /Unregistered/);
});

test('quick palette opens a whitelisted panel; topic sources are removable', async () => {
  const h = await page();
  await h.input('#input','/find');
  await h.key('#input','Enter'); await h.idle(30);
  assert.equal(h.$('.research-body').dataset.mode,'papers');
  noTurns(h);
  h.w.PL.research.toggle('paper:' + PID, 'Paper', true);
  await h.click('#research-chips button');
  assert.equal(h.w.PL.research.selected.size,0);
});
