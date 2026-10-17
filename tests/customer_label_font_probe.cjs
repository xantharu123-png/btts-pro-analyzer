// Run with the app's emitted stylesheet on stdin; assert actual browser styles.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
let styles = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { styles += chunk; });
process.stdin.on('end', async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1440, 390, 320]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      await page.setContent(styles + `<article class="se-card"><div class="se-match-time">17:00</div>
        <div class="se-pick-label"><span>Endergebnis</span></div>
        <div class="se-number"><span>Modell</span><small class="se-meta">Buchmacher · 17:00</small></div>
        <a class="se-image-credit">Bildquelle</a></article>`);
      for (const selector of ['.se-match-time', '.se-pick-label span', '.se-number span', '.se-meta', '.se-image-credit']) {
        const size = await page.locator(selector).evaluate(el => parseFloat(getComputedStyle(el).fontSize));
        assert.ok(size >= 12, `${width}px ${selector}: ${size}px below 12px`);
      }
      await page.close();
    }
    process.stdout.write('Customer label font sizes >=12px at 1440/390/320px PASS\n');
  } finally {
    await browser.close();
  }
}).on('error', error => { throw error; });
