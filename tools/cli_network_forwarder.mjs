// Agent container has --network=none. Only this sidecar socket reaches approved APIs.
import net from 'node:net';
import { spawn } from 'node:child_process';

const server = net.createServer((client) => {
  const remote = net.connect('/ipc/egress.sock');
  client.pipe(remote); remote.pipe(client);
  remote.on('error', () => client.destroy());
  client.on('error', () => remote.destroy());
  client.on('close', () => remote.destroy());
});
server.listen(3128, '127.0.0.1', () => {
  const args = process.argv.slice(2);
  if (!args.length) throw new Error('Native CLI command is required');
  const child = spawn(args[0], args.slice(1), { stdio: 'inherit', shell: false,
    env: { ...process.env, HTTPS_PROXY: 'http://127.0.0.1:3128', HTTP_PROXY: 'http://127.0.0.1:3128',
      ALL_PROXY: 'http://127.0.0.1:3128', NO_PROXY: '127.0.0.1,localhost', NODE_USE_ENV_PROXY: '1' } });
  child.on('error', () => { server.close(); process.exit(127); });
  child.on('exit', (code) => { server.close(); process.exit(code ?? 1); });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
});
