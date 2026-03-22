/**
 * discover.js — scrapes Google Maps search results for business listings.
 *
 * Strategy:
 * 1. Navigate to maps.google.com/search/<keyword+location> — opens results list
 * 2. Scroll to load all results
 * 3. Click each card to open the side panel and extract website/phone/email
 *    (much faster than separate navigations — panel loads in same page)
 * 4. Deduplicate across multiple keywords by name+address
 */

import { chromium } from "playwright";

const SCROLL_PAUSE_MIN = 500;
const SCROLL_PAUSE_MAX = 1000;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function rand(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function randSleep(min, max) { return sleep(rand(min, max)); }

async function applyStealthPatches(page) {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    Object.defineProperty(navigator, "plugins", {
      get: () => [
        { name: "Chrome PDF Plugin",  filename: "internal-pdf-viewer" },
        { name: "Chrome PDF Viewer",  filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai" },
        { name: "Native Client",      filename: "internal-nacl-plugin" },
      ],
    });
    Object.defineProperty(navigator, "languages", { get: () => ["ja", "en-US", "en"] });
    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
  });
}

export async function discoverBusinesses({ keywords, location, limit = 120 }) {
  const keywordList = keywords.split(",").map(k => k.trim()).filter(Boolean);
  const DEBUG = process.env.DISCOVER_DEBUG === "1";
  console.log(`[discover] START keywords=${JSON.stringify(keywordList)} location="${location}" limit=${limit === 0 ? "all" : limit}`);

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
      "--disable-blink-features=AutomationControlled",
      "--disable-features=IsolateOrigins,site-per-process",
      "--window-size=1280,900",
    ],
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    locale: "ja-JP",
    timezoneId: "Asia/Tokyo",
    extraHTTPHeaders: { "Accept-Language": "ja,en-US;q=0.9,en;q=0.8" },
  });

  const allBusinesses = new Map();

  try {
    for (const keyword of keywordList) {
      const query     = [keyword, location].filter(Boolean).join(" ");
      const searchUrl = `https://www.google.com/maps/search/${encodeURIComponent(query)}`;
      console.log(`[discover] searching: "${query}"`);

      const results = await _searchOneMaps({ searchUrl, limit, context, DEBUG });
      let added = 0;
      for (const biz of results) {
        const key = `${biz.name}||${biz.address}`;
        if (!allBusinesses.has(key)) { allBusinesses.set(key, biz); added++; }
      }
      console.log(`[discover] "${keyword}": ${results.length} found, ${added} new (total: ${allBusinesses.size})`);
    }
  } finally {
    await browser.close();
  }

  const businesses = Array.from(allBusinesses.values());
  console.log(`[discover] DONE — ${businesses.length} unique, ${businesses.filter(b => b.website).length} with websites`);
  return { businesses };
}

async function _searchOneMaps({ searchUrl, limit, context, DEBUG }) {
  const ts = Date.now();

  async function dbgShot(page, label) {
    if (!DEBUG) return;
    const path = `/tmp/discover_${ts}_${label}.jpg`;
    await page.screenshot({ path, type: "jpeg", quality: 60 }).catch(() => {});
    console.log(`[discover:debug] ${label} | url=${page.url()} | title=${await page.title().catch(() => "?")} | shot=${path}`);
  }

  const page = await context.newPage();
  await applyStealthPatches(page);

  try {
    console.log(`[discover] goto: ${searchUrl}`);
    await page.goto(searchUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
    await randSleep(1500, 2500);
    await dbgShot(page, "01_after_goto");

    // Handle Google consent page
    if (page.url().includes("consent.google.com")) {
      console.log("[discover] consent page — clicking reject");
      try {
        const btn = page.locator('button:has-text("すべてを拒否"), button:has-text("Reject all")').first();
        await btn.waitFor({ timeout: 8000 });
        await btn.click();
        await page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 20_000 });
        await randSleep(2000, 3000);
        await dbgShot(page, "02_after_consent");
        console.log(`[discover] after consent: ${page.url()}`);
      } catch (e) {
        console.log(`[discover] consent failed: ${e.message}`);
        await page.close();
        return [];
      }
    }

    // Wait for results panel
    try {
      await page.waitForSelector('div[role="feed"], div.m6QErb', { timeout: 15_000 });
      console.log("[discover] results panel found");
    } catch {
      const visible = await page.evaluate(() => document.body.innerText.slice(0, 300)).catch(() => "");
      console.log(`[discover] results panel NOT found. Page: ${visible}`);
      await dbgShot(page, "03_no_panel");
      await page.close();
      return [];
    }

    await randSleep(800, 1500);

    // Scroll to load all result cards
    const resultsPanel = await page.$('div[role="feed"], div.m6QErb[style*="overflow"]');
    let prevCount = 0, stableRounds = 0;

    while (true) {
      const cards = await page.$$('a[href*="/maps/place/"]');
      const n = cards.length;
      if (limit > 0 && n >= limit) { console.log(`[discover] limit ${limit} reached`); break; }
      if (n === prevCount) {
        if (++stableRounds >= 4) { console.log(`[discover] stable at ${n} results`); break; }
      } else { stableRounds = 0; console.log(`[discover] ${n} results loaded...`); }
      prevCount = n;
      if (resultsPanel) {
        await resultsPanel.evaluate(el => el.scrollBy(0, Math.floor(300 + Math.random() * 300)));
      } else {
        await page.evaluate(() => window.scrollBy(0, Math.floor(300 + Math.random() * 300)));
      }
      await randSleep(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX);
    }

    // Collect all card hrefs and basic info first (no clicking yet)
    const cardData = await page.evaluate((lim) => {
      const cards = Array.from(document.querySelectorAll('a[href*="/maps/place/"]'));
      const toProcess = lim > 0 ? cards.slice(0, lim) : cards;
      const seen = new Set();
      return toProcess.map(card => {
        const href = card.getAttribute("href") || "";
        if (seen.has(href)) return null;
        seen.add(href);
        const container = card.parentElement || card;
        const name = container.querySelector('.qBF1Pd, .fontHeadlineSmall, [class*="fontHeadline"]')?.textContent?.trim() || "";
        if (!name) return null;
        const rating      = container.querySelector('span.MW4etd')?.textContent?.trim() || "";
        const reviewCount = container.querySelector('span.UY7F9')?.textContent?.replace(/[()]/g, "").trim() || "";
        const spans       = container.querySelectorAll('.W4Efsd span');
        const category    = spans[0]?.textContent?.trim() || "";
        const address     = Array.from(spans).find(s => s.textContent?.includes("丁目") || s.textContent?.match(/\d+/))?.textContent?.trim() || "";
        const placeMatch  = href.match(/\/maps\/place\/([^/]+)\//);
        const mapsUrl     = placeMatch ? `https://www.google.com/maps/place/${placeMatch[1]}` : "";
        return { name, category, rating: rating || null, review_count: reviewCount || null, address, maps_url: mapsUrl, href };
      }).filter(Boolean);
    }, limit);

    console.log(`[discover] ${cardData.length} cards to process, clicking each for details...`);

    // Now click each card to open the side panel and extract website/phone/email
    const businesses = [];
    for (let i = 0; i < cardData.length; i++) {
      const data = cardData[i];
      try {
        // Click the card link directly by href
        const card = await page.$(`a[href="${data.href}"]`);
        if (card) {
          // Scroll card into view first
          await card.scrollIntoViewIfNeeded();
          await randSleep(200, 400);
          await card.click();

          // Wait for side panel to load — it shows a detail panel on the right
          await page.waitForTimeout(1500);

          // Extract website from the now-open detail panel
          // Google Maps website button has various selectors depending on Maps version
          const website = await page.evaluate(() => {
            // Try multiple known selectors for the website link
            const selectors = [
              'a[data-item-id="authority"]',
              'a[aria-label*="ウェブサイト"]',
              'a[aria-label*="website"]',
              'a[aria-label*="Website"]',
              // The website link href starts with http and is NOT a maps URL
              'a[href^="http"]:not([href*="google"]):not([href*="maps"])',
            ];
            for (const sel of selectors) {
              const el = document.querySelector(sel);
              if (el) {
                const href = el.getAttribute("href");
                if (href && href.startsWith("http") && !href.includes("google.com/maps")) {
                  return href;
                }
              }
            }
            // Fallback: find any external link in the detail panel
            const panel = document.querySelector('[role="main"], .m6QErb');
            if (panel) {
              const links = Array.from(panel.querySelectorAll('a[href^="http"]'));
              const external = links.find(l => {
                const h = l.getAttribute("href") || "";
                return !h.includes("google.com") && !h.includes("goo.gl") && !h.includes("maps");
              });
              if (external) return external.getAttribute("href");
            }
            return null;
          });

          const phone = await page.evaluate(() => {
            const el = document.querySelector('[data-item-id*="phone"], [aria-label*="電話番号"], button[aria-label*="+"]');
            return el ? el.textContent.trim() : null;
          });

          const email = await page.evaluate(() => {
            const text = document.body.innerText;
            const m = text.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/);
            return m ? m[0].toLowerCase() : null;
          });

          businesses.push({
            name: data.name, category: data.category,
            rating: data.rating, review_count: data.review_count,
            address: data.address, maps_url: data.maps_url,
            website: website || null, phone: phone || null, email: email || null,
            status: "new",
          });

          if (DEBUG || i % 10 === 0) {
            console.log(`[discover] ${i + 1}/${cardData.length}: ${data.name} → ${website || "—"}`);
          }

          // Press Escape to close the panel before next card
          await page.keyboard.press("Escape");
          await randSleep(300, 600);
        } else {
          businesses.push({ name: data.name, category: data.category, rating: data.rating, review_count: data.review_count, address: data.address, maps_url: data.maps_url, website: null, phone: null, email: null, status: "new" });
        }
      } catch (e) {
        console.warn(`[discover] click failed "${data.name}": ${e.message}`);
        businesses.push({ name: data.name, category: data.category, rating: data.rating, review_count: data.review_count, address: data.address, maps_url: data.maps_url, website: null, phone: null, email: null, status: "new" });
      }
    }

    const withWebsite = businesses.filter(b => b.website).length;
    console.log(`[discover] complete: ${businesses.length} businesses, ${withWebsite} with websites`);

    await page.close();
    return businesses;

  } catch (e) {
    console.error(`[discover] error: ${e.message}`);
    await page.close().catch(() => {});
    return [];
  }
}
