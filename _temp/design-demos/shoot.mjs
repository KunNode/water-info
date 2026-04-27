import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const file = pathToFileURL(resolve('./demo-apple-hig.html')).href;
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 960 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();

for (const mode of ['dark', 'light']) {
  await page.goto(file);
  await page.evaluate(m => localStorage.setItem('demo-fm-theme', m), mode);
  await page.goto(file);
  await page.waitForTimeout(350); // let 200ms transition settle
  await page.screenshot({ path: `./demo-apple-hig-${mode}.png`, fullPage: true });
  console.log(`shot ${mode}`);
}
await browser.close();
