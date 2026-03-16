import { chromium } from "playwright";

export async function capture(url) {
  const browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--disable-gpu-compositing",
      "--disable-software-rasterizer",
    ],
  });

  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 },
      deviceScaleFactor: 1,
      userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      extraHTTPHeaders: { "Accept-Language": "ja,en;q=0.9" },
    });

    const page = await context.newPage();

    await page.route(
      /googletag|googleanalytics|gtag|doubleclick|facebook\.net|hotjar|clarity\.ms|amazon-adsystem/,
      route => route.abort()
    );

    await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: 30_000,
    });

    // Let JS frameworks render
    await page.waitForTimeout(3000);

    // Scroll to bottom and back to trigger lazy-loaded above-fold content, then return to top
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);

    // Cap at 1280x3000 — avoids Anthropic's 8000px image limit on tall pages.
    // Above-the-fold + first few sections is enough for a meaningful audit.
    const screenshotBuffer = await page.screenshot({
      clip: { x: 0, y: 0, width: 1280, height: 3000 },
      type: "jpeg",
      quality: 55,
      animations: "disabled",
    });

    const screenshot = screenshotBuffer.toString("base64");
    const html = await page.content();
    const title = await page.title();
    const finalUrl = page.url();

    console.log(`[capture] full-page screenshot: ${Math.round(screenshotBuffer.length / 1024)}KB base64=${Math.round(screenshot.length / 1024)}KB`);

    await context.close();
    return { screenshot, html, title, finalUrl };

  } finally {
    await browser.close();
  }
}
