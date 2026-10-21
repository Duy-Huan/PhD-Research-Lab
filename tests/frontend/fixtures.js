'use strict';
// Responses recorded from the REAL backend by tools/frontend_fixtures.py (re-record after an API change).
// Keys: "METHOD /path", "METHOD /path?query" or "METHOD /path/:param"; meta = ids of the recorded session, runs, review.
const fs = require('node:fs');
const path = require('node:path');

const RAW = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures.json'), 'utf8'));
const clone = (v) => JSON.parse(JSON.stringify(v));

exports.meta = RAW.meta;
exports.get = (key) => clone(RAW[key].body);
exports.routes = () => {
  const out = {};
  for (const [k, v] of Object.entries(RAW)) {
    if (k === 'meta') continue;
    out[k] = () => ({__resp: true, body: clone(v.body), status: v.status});
  }
  return out;
};
