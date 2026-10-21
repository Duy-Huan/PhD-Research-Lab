'use strict';
const test = require('node:test');
const assert = require('node:assert');
const {boot} = require('./harness');

test('boots on the home screen with the recorded project', async () => {
  const h = await boot();
  assert.match(h.$('#proj-name').textContent, /Default project/);
  assert.ok(h.$('.hello h1'));
  assert.deepStrictEqual(h.server.unmatched, []);
  assert.deepStrictEqual(h.errors, []);
});
