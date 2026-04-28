import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const file = pathToFileURL(resolve('./demo-bigscreen-fluid.html')).href;
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
await page.goto(file);
await page.waitForTimeout(800); // let animations / particles settle
await page.screenshot({ path: './demo-bigscreen-fluid.png', fullPage: false });
console.log('shot bigscreen');
await browser.close();
