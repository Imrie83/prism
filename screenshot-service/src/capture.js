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

    // Navigate — try networkidle for a fully rendered page, fall back to
    // domcontentloaded if the site keeps the network busy indefinitely
    try {
      await page.goto(url, { waitUntil: "networkidle", timeout: 20_000 });
    } catch {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30_000 });
    }

    // Wait for common loading indicators to disappear
    // (spinners, skeleton loaders, loading overlays common on Japanese sites)
    try {
      await page.waitForFunction(() => {
        const selectors = [
          "[class*='loading']", "[class*='spinner']", "[class*='skeleton']",
          "[class*='loader']",  "[id*='loading']",    "[id*='spinner']",
          "[class*='preload']", "[class*='progress']",
        ];
        return selectors.every(sel => {
          const els = document.querySelectorAll(sel);
          return [...els].every(el => {
            const style = window.getComputedStyle(el);
            return style.display === "none" || style.visibility === "hidden" || style.opacity === "0";
          });
        });
      }, { timeout: 5_000 });
    } catch {
      // Loading indicators still visible after 5s — proceed anyway
    }

    // Extra settle time for CSS animations, carousels, and lazy image loading
    await page.waitForTimeout(4000);

    // Dismiss fixed cookie/GDPR banners and modal overlays that block content
    try {
      await page.evaluate(() => {
        const overlaySelectors = [
          "[class*='cookie']", "[class*='gdpr']", "[class*='modal']",
          "[class*='overlay']", "[class*='popup']", "[id*='cookie']",
          "[id*='modal']", "[id*='overlay']",
        ];
        for (const sel of overlaySelectors) {
          document.querySelectorAll(sel).forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.position === "fixed" || style.position === "absolute") {
              el.style.display = "none";
            }
          });
        }
      });
    } catch {}

    // Scroll through the whole page to trigger lazy-loaded sections
    await page.evaluate(async () => {
      await new Promise(resolve => {
        const distance = 300;
        const delay = 100;
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

    // Let lazy-loaded images render after scroll
    await page.waitForTimeout(1500);

    // Cap at 1280x7999 — just under Anthropic's 8000px image limit.
    const pageHeight = await page.evaluate(() => document.body.scrollHeight);
    const screenshotBuffer = await page.screenshot({
      clip: { x: 0, y: 0, width: 1280, height: Math.min(pageHeight, 7999) },
      type: "jpeg",
      quality: 60,
      animations: "disabled",
    });

    const screenshot = screenshotBuffer.toString("base64");
    const html = await page.content();
    const title = await page.title();
    const finalUrl = page.url();

    console.log(`[capture] screenshot: ${Math.round(screenshotBuffer.length / 1024)}KB base64=${Math.round(screenshot.length / 1024)}KB pageHeight=${pageHeight}px`);

    await context.close();
    return { screenshot, html, title, finalUrl, pageHeight };

  } finally {
    await browser.close();
  }
}
