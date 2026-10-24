import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const src = path.join(__dirname, 'dist', 'react.html');
const dest = path.join(__dirname, 'dist', 'index.html');

if (fs.existsSync(src)) {
  fs.copyFileSync(src, dest);
  console.log('✓ Successfully created dist/index.html from dist/react.html');
} else {
  console.warn('Warning: dist/react.html not found to copy.');
}
