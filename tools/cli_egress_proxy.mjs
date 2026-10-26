// Trusted sidecar: HTTPS CONNECT to explicit provider domains, over a Unix socket.
import http from 'node:http';
import net from 'node:net';
import dns from 'node:dns/promises';
import fs from 'node:fs';

const domains = new Set((process.env.PHDLAB_ALLOWED_DOMAINS || '').split(',').filter(Boolean));
const socket = '/ipc/egress.sock';
// Hermes RPC ingress can install short-lived, exact-job tool grants. CLI behavior is unchanged.
const scopedBridges = new Map();
export function registerScopedBridge(job, port, token, seconds) {
  if (!/^[a-f0-9]{32}$/.test(job || '') || !Number.isInteger(port) || port < 1 || port > 65535 ||
      typeof token !== 'string' || !/^[A-Za-z0-9_.:-]{16,512}$/.test(token) ||
      !Number.isInteger(seconds) || seconds < 5 || seconds > 1800) throw new Error('Invalid scoped bridge');
  for (const [key, value] of scopedBridges) if (value.until < Date.now()) scopedBridges.delete(key);
  const existing = scopedBridges.get(job);
  if (existing) {
    if (existing.port !== port || existing.token !== token) throw new Error('Cannot replace an active job grant');
    return; // An idempotent request cannot extend its original authority deadline.
  }
  if (scopedBridges.size >= 64 && !scopedBridges.has(job)) throw new Error('Scoped bridge capacity reached');
  scopedBridges.set(job, { port, token, until: Date.now() + seconds * 1000 });
}
export function removeScopedBridge(job) { scopedBridges.delete(job); }
function publicAddress(address) {
  if (net.isIP(address) === 4) {
    const [a, b] = address.split('.').map(Number);
    return !(a === 0 || a === 10 || a === 127 || a >= 224 || (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) ||
      (a === 100 && b >= 64 && b <= 127) || (a === 198 && [18, 19].includes(b)));
  }
  return /^[23]/i.test(address) && !address.toLowerCase().startsWith('2001:db8:');
}
const server = http.createServer((request, response) => {
  // The only host service exposed is the project-scoped MCP endpoint, with a read/tool grant.
  const scoped = scopedBridges.get(request.headers['x-phdlab-job']);
  const grant = scoped && scoped.until > Date.now() ? scoped : null;
  const port = grant?.port || process.env.PHDLAB_MCP_PORT;
  const token = grant?.token || process.env.PHDLAB_MCP_TOKEN;
  if (request.method !== 'POST' || request.url !== '/mcp' || !port || !token) {
    response.writeHead(403); response.end('Endpoint denied'); return;
  }
  let bytes = 0;
  const upstream = http.request({ hostname: 'host.docker.internal', port: Number(port), path: '/mcp', method: 'POST',
    headers: { 'Content-Type': 'application/json', Host: `127.0.0.1:${port}`,
      Authorization: `Bearer ${token}`,
      ...(request.headers['mcp-session-id'] ? { 'Mcp-Session-Id': request.headers['mcp-session-id'] } : {}) } }, result => {
    response.writeHead(result.statusCode, { 'Content-Type': 'application/json',
      ...(result.headers['mcp-session-id'] ? { 'Mcp-Session-Id': result.headers['mcp-session-id'] } : {}) });
    result.pipe(response);
  });
  upstream.setTimeout(30_000, () => upstream.destroy());
  upstream.on('error', () => { if (!response.headersSent) response.writeHead(502); response.end('MCP bridge unavailable'); });
  request.on('data', chunk => { bytes += chunk.length; if (bytes > 1024 * 1024) { upstream.destroy(); request.destroy(); } });
  request.pipe(upstream);
});
server.on('connect', async (request, client, head) => {
  let upstream;
  try {
    const match = /^([a-z0-9.-]+):443$/i.exec(request.url || '');
    if (!match || !domains.has(match[1].toLowerCase())) throw new Error('domain denied');
    const resolved = await dns.lookup(match[1], { all: true });
    if (!resolved.length || resolved.some(({ address }) => !publicAddress(address))) throw new Error('address denied');
    // Connect to the validated IP, not a second DNS lookup.
    const target = resolved.find(item => item.family === 4) || resolved[0];
    upstream = net.connect({ host: target.address, family: target.family, port: 443 });
    upstream.setTimeout(120_000, () => upstream.destroy());
    upstream.once('connect', () => {
      client.write('HTTP/1.1 200 Connection Established\r\n\r\n');
      if (head.length) upstream.write(head);
      client.pipe(upstream); upstream.pipe(client);
    });
    upstream.on('error', (error) => { console.error(JSON.stringify({ domain: match[1], error: error.code })); client.destroy(); });
    client.on('error', () => upstream.destroy());
    client.on('close', () => upstream.destroy());
  } catch (error) {
    console.error(JSON.stringify({ event: 'denied', reason: String(error.message).slice(0, 80) }));
    client.end('HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n');
    upstream?.destroy();
  }
});
server.maxConnections = 32;
server.requestTimeout = 15_000;
server.headersTimeout = 10_000;
if (fs.existsSync(socket)) fs.unlinkSync(socket);
server.listen(socket, () => fs.chmodSync(socket, 0o666));
