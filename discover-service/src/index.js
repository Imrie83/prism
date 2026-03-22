import express from "express";
import { discoverBusinesses } from "./discover.js";

const app  = express();
const PORT = process.env.PORT || 3001;

app.use(express.json({ limit: "10mb" }));

app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "prism-discover" });
});

/**
 * POST /discover
 * Body: { "keywords": "ツアー, キャンプ", "location": "北海道", "limit": 120 }
 * limit=0 means "all results"
 * Streams NDJSON progress events, final line: { type: "done", businesses: [...] }
 */
app.post("/discover", async (req, res) => {
  const { keywords, location, limit = 120 } = req.body;
  if (!keywords) return res.status(400).json({ error: "keywords required" });

  console.log(`[discover] POST keywords="${keywords}" location="${location}" limit=${limit}`);

  res.setHeader("Content-Type", "application/x-ndjson");
  res.setHeader("Transfer-Encoding", "chunked");
  res.flushHeaders();

  const send = (obj) => res.write(JSON.stringify(obj) + "\n");
  const startTime = Date.now();

  try {
    const result = await discoverBusinesses({
      keywords, location, limit,
      onProgress: (event) => send(event),
    });
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[discover] done in ${elapsed}s — ${result.businesses?.length ?? 0} businesses`);
    send({ type: "done", businesses: result.businesses, elapsed });
    res.end();
  } catch (err) {
    console.error(`[discover] Failed: ${err.message}`);
    send({ type: "error", error: `Discover failed: ${err.message}` });
    res.end();
  }
});

app.listen(PORT, () => {
  console.log(`Prism discover service running on http://localhost:${PORT}`);
  console.log(`Health: http://localhost:${PORT}/health`);
});
