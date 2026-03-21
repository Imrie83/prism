import express  from "express";
import { capture } from "./capture.js";

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Health check — useful to verify the service is up before the Worker calls it
app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "shinrai-screenshot" });
});

/**
 * POST /screenshot
 * Body: { "url": "https://example.co.jp" }
 *
 * Returns:
 * {
 *   screenshot : "<base64 PNG>",
 *   html       : "<rendered HTML string>",
 *   title      : "Page title",
 *   finalUrl   : "https://..." (after redirects)
 * }
 */
app.post("/screenshot", async (req, res) => {
  const { url } = req.body;

  if (!url || !/^https?:\/\//i.test(url)) {
    return res.status(400).json({ error: "A valid URL is required" });
  }

  console.log(`[screenshot] Capturing: ${url}`);
  const startTime = Date.now();

  try {
    const result = await capture(url);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[screenshot] Done in ${elapsed}s — screenshot ${Math.round(result.screenshot.length / 1024)}KB, HTML ${Math.round(result.html.length / 1024)}KB`);
    res.json(result);
  } catch (err) {
    console.error(`[screenshot] Failed: ${err.message}`);
    res.status(502).json({ error: `Screenshot failed: ${err.message}` });
  }
});

/**
 * POST /screenshot-offset
 * Body: { "url": "https://...", "offset_y": 7999 }
 * Takes a second screenshot starting from offset_y — used for vision-only mode on tall pages.
 */
app.post("/screenshot-offset", async (req, res) => {
  const { url, offset_y = 7999 } = req.body;

  if (!url || !/^https?:\/\//i.test(url)) {
    return res.status(400).json({ error: "A valid URL is required" });
  }

  console.log(`[screenshot-offset] Capturing ${url} from y=${offset_y}`);
  const startTime = Date.now();

  try {
    const { chromium } = await import("playwright");
    const browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
             "--disable-gpu", "--disable-gpu-compositing", "--disable-software-rasterizer"],
    });
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1,
      userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      extraHTTPHeaders: { "Accept-Language": "ja,en;q=0.9" },
    });
    const page = await context.newPage();
    await page.route(/googletag|googleanalytics|gtag|doubleclick|facebook\.net|hotjar|clarity\.ms|amazon-adsystem/, r => r.abort());
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await page.waitForTimeout(2000);

    const pageHeight = await page.evaluate(() => document.body.scrollHeight);
    const clipHeight = Math.min(7999, Math.max(0, pageHeight - offset_y));

    if (clipHeight <= 0) {
      await browser.close();
      return res.json({ screenshot: null, offset_y, pageHeight });
    }

    const buf = await page.screenshot({
      clip: { x: 0, y: offset_y, width: 1280, height: clipHeight },
      type: "jpeg", quality: 55, animations: "disabled",
    });
    await browser.close();

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[screenshot-offset] Done in ${elapsed}s — ${Math.round(buf.length / 1024)}KB clip y=${offset_y}..${offset_y + clipHeight}`);
    res.json({ screenshot: buf.toString("base64"), offset_y, pageHeight, clipHeight });
  } catch (err) {
    console.error(`[screenshot-offset] Failed: ${err.message}`);
    res.status(502).json({ error: `Screenshot offset failed: ${err.message}` });
  }
});

app.listen(PORT, () => {
  console.log(`Shinrai screenshot service running on http://localhost:${PORT}`);
  console.log(`Health: http://localhost:${PORT}/health`);
});
