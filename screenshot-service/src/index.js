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

    // Don't log the actual screenshot/html — just confirm sizes
    res.json(result);

  } catch (err) {
    console.error(`[screenshot] Failed: ${err.message}`);
    res.status(502).json({ error: `Screenshot failed: ${err.message}` });
  }
});

app.listen(PORT, () => {
  console.log(`Shinrai screenshot service running on http://localhost:${PORT}`);
  console.log(`Health: http://localhost:${PORT}/health`);
});
