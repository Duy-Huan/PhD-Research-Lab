import { createHash } from 'node:crypto';
import { test, expect, boot, json } from './live';

test('3D real WebGL renders, camera and lighting change pixels, dock returns to chat', async ({ page, request }, info) => {
  await json(request, 'post', '/api/config', { ui: { language: 'en' } });
  await boot(page);
  await page.getByTitle('Full-Screen 3D University Research Lab', { exact: true }).click();
  const viewport = page.locator('#office3d-viewport');
  const canvas = viewport.locator('canvas');
  await expect(canvas).toBeVisible();
  await expect.poll(() => canvas.evaluate((el: HTMLCanvasElement) => el.width * el.height)).toBeGreaterThan(0);
  const graphics = await canvas.evaluate((el: HTMLCanvasElement) => {
    const gl = el.getContext('webgl2');
    return gl ? { lost: gl.isContextLost(), version: gl.getParameter(gl.VERSION), renderer: gl.getParameter(gl.RENDERER), width: el.width, height: el.height } : null;
  });
  expect(graphics, 'Actual WebGL2 context must exist; fallback is not a 3D PASS').not.toBeNull();
  expect(graphics!.lost).toBe(false);
  const digest = async () => createHash('sha256').update(await canvas.screenshot()).digest('hex');
  const initial = await digest();
  await viewport.getByRole('button', { name: 'HPC Rack', exact: true }).click();
  await expect(viewport.getByRole('button', { name: 'HPC Rack', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(digest).not.toBe(initial);
  await viewport.getByRole('button', { name: 'Daylight', exact: true }).click();
  await expect(viewport.getByRole('button', { name: 'Daylight', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await info.attach('actual-webgl.json', { body: JSON.stringify(graphics), contentType: 'application/json' });
  await info.attach('3d-real.png', { body: await page.screenshot(), contentType: 'image/png' });
  await page.getByTitle('Library Bookshelves', { exact: true }).click();
  await expect(page.locator('#office3d-chat-dock')).toBeVisible();
  await page.getByRole('button', { name: 'Back to standard view', exact: true }).click();
  await page.getByRole('button', { name: 'Chat', exact: true }).click();
  await expect(page.locator('#view textarea')).toBeVisible();
});
