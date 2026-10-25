import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const rootDir = fileURLToPath(new URL('..', import.meta.url));
const artifacts = process.env.PHDLAB_E2E_OUTPUT
  ? resolve(process.env.PHDLAB_E2E_OUTPUT)
  : resolve(rootDir, 'output/playwright/regression');
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1, // Active project is application-wide; concurrent tests must use separate servers.
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  outputDir: resolve(artifacts, 'results'),
  reporter: [['line'], ['html', { outputFolder: resolve(artifacts, 'html'), open: 'never' }],
    ['json', { outputFile: resolve(artifacts, 'results.json') }]],
  use: {
    baseURL: process.env.PHDLAB_E2E_URL || 'http://127.0.0.1:5174',
    browserName: 'chromium',
    headless: process.env.HEADED ? false : true,
    viewport: { width: 1440, height: 900 },
    trace: 'on', screenshot: 'on', video: 'retain-on-failure',
    actionTimeout: 15_000,
  },
});
