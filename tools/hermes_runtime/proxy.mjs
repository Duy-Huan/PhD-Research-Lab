// Trusted RPC ingress and the existing domain-filtered egress proxy share an IPC volume.
import http from 'node:http';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { registerScopedBridge, removeScopedBridge } from './cli_egress_proxy.mjs';

fs.mkdirSync('/ipc/hermes', { recursive: true, mode: 0o777 });
fs.chmodSync('/ipc/hermes', 0o777);
const secret = process.env.PHDLAB_RPC_TOKEN || '';
if (secret.length < 48) throw new Error('RPC authentication is required');
const authorized = request => {
  const actual = Buffer.from(request.headers.authorization || '');
  const expected = Buffer.from(`Bearer ${secret}`);
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
};
const server = http.createServer((request, response) => {
  if (!authorized(request)) { response.writeHead(401); response.end(); return; }
  if (!/^(\/v1\/(health|models|jobs)(\/[a-f0-9]{32}(\/cancel)?)?)$/.test(request.url || '')) {
    response.writeHead(404); response.end(); return;
  }
  let bytes = 0;
  const chunks = [];
  request.on('data', chunk => {
    bytes += chunk.length;
    if (bytes > 1048576) { request.destroy(); return; }
    chunks.push(chunk);
  });
  request.on('end', () => {
    let body = Buffer.concat(chunks);
    let job;
    try {
      if (request.method === 'POST' && request.url === '/v1/jobs') {
        const data = JSON.parse(body);
        if (!/^[a-f0-9]{32}$/.test(data.id || '')) throw new Error('Invalid job');
        job = data.id;
        if (data.mcp) {
          registerScopedBridge(job, data.mcp.port, data.mcp.token, data.deadline_s);
          // A PhD Lab bearer token never enters the Hermes agent or its persistent home.
          data.tools = Array.isArray(data.mcp.tools) ? data.mcp.tools : [];
          delete data.mcp;
          body = Buffer.from(JSON.stringify(data));
        }
      }
    } catch { response.writeHead(400); response.end('Invalid RPC body'); return; }
    const upstream = http.request({ socketPath: '/ipc/hermes/rpc.sock', path: request.url,
      method: request.method, headers: { 'Content-Type': 'application/json', 'Content-Length': body.length } }, result => {
      response.writeHead(result.statusCode, { 'Content-Type': 'application/json' }); result.pipe(response);
      if (job && result.statusCode >= 400) removeScopedBridge(job);
    });
    upstream.setTimeout(40000, () => upstream.destroy());
    upstream.on('error', () => { if (!response.headersSent) response.writeHead(503); response.end('{"state":"UNAVAILABLE"}'); });
    upstream.end(body);
  });
});
server.maxConnections = 16;
server.requestTimeout = 15000;
server.headersTimeout = 10000;
server.listen(8080, '0.0.0.0'); // Docker publishes this on host127.0.0.1 ONLY.
