# Shinrai Screenshot Service

Local Playwright server that renders pages in a real browser and returns
a full-page screenshot + rendered HTML to the Cloudflare Worker.

## Setup

```bash
cd worker/screenshot-service
npm install
npx playwright install chromium   # downloads ~170MB Chromium binary (one-time)
npm run dev                        # starts on http://localhost:3000
```

## Usage

```bash
# Health check
curl http://localhost:3000/health

# Test a screenshot
curl -X POST http://localhost:3000/screenshot \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.co.jp"}' \
  | jq '{title, finalUrl, screenshotSize: (.screenshot | length), htmlSize: (.html | length)}'
```

## Switching to production (Browserless.io)

1. Sign up at https://www.browserless.io (free tier available)
2. Get your API key
3. Set in wrangler.toml (or `wrangler secret put`):
   SCREENSHOT_SERVICE_URL = "https://chrome.browserless.io"
   BROWSERLESS_API_KEY    = "your-key"
4. Update worker/src/v2/analyze.js to use the Browserless REST API format
   (their /screenshot endpoint takes the same URL + returns base64 PNG)

## Notes

- Playwright downloads ~170MB of Chromium on first `npx playwright install chromium`
- Each capture takes 5–15 seconds depending on page complexity
- The service keeps no state — each request is a fresh browser instance
- For production consider adding rate limiting and authentication
