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

    // Scroll through the whole page to trigger lazy-loaded sections, then return to top
    await page.evaluate(async () => {
      await new Promise(resolve => {
        const distance = 400;
        const delay = 80;
        const timer = setInterval(() => {
          window.scrollBy(0, distance);
          if (window.scrollY + window.innerHeight >= document.body.scrollHeight) {
            clearInterval(timer);
            window.scrollTo(0, 0);
            resolve();
          }
        }, delay);
      });
    });
    await page.waitForTimeout(800);

    // Cap at 1280x7999 — just under Anthropic's 8000px image limit.
    // Full scroll above ensures lazy-loaded content is rendered before capture.
    const screenshotBuffer = await page.screenshot({
      clip: { x: 0, y: 0, width: 1280, height: 7999 },
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
