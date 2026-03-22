/**
 * discover.js — scrapes Google Maps search results for business listings.
 *
 * Strategy:
 * 1. Navigate to maps.google.com/search/<keyword+location> — opens results list
 * 2. Scroll to load all results
 * 3. Click each card, wait for panel URL to change, extract website/phone/email
 * 4. Deduplicate across keywords by name+address
 */

import { chromium } from "playwright";

const SCROLL_PAUSE_MIN = 500;
const SCROLL_PAUSE_MAX = 900;

// Domains we never want as "website" — they're Maps/review platforms not business sites
const BLOCKED_DOMAINS = [
  "google.com", "goo.gl", "tripadvisor.", "booking.com", "expedia.",
  "airbnb.", "agoda.", "jalan.net", "ikyu.com", "instagram.com",
  "facebook.com", "twitter.com", "x.com", "youtube.com", "airhost.",
  "weniseko.", "holidayniseko.", "powderhounds.", "snowjapan.",
];

function isBusinessWebsite(url) {
  if (!url) return false;
  if (!url.startsWith("http")) return false;
  return !BLOCKED_DOMAINS.some(d => url.includes(d));
}

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

export async function discoverBusinesses({ keywords, location, limit = 120, onProgress }) {
  const keywordList = keywords.split(",").map(k => k.trim()).filter(Boolean);
  const DEBUG = process.env.DISCOVER_DEBUG === "1";
  const emit  = onProgress || (() => {});

  console.log(`[discover] START keywords=${JSON.stringify(keywordList)} location="${location}" limit=${limit === 0 ? "all" : limit}`);
  emit({ type: "start", keywords: keywordList, location, limit });

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
      emit({ type: "keyword_start", keyword, query });

      const results = await _searchOneMaps({ searchUrl, limit, context, DEBUG, emit, keyword });
      let added = 0;
      for (const biz of results) {
        const key = `${biz.name}||${biz.address}`;
        if (!allBusinesses.has(key)) { allBusinesses.set(key, biz); added++; }
      }
      console.log(`[discover] "${keyword}": ${results.length} found, ${added} new (total: ${allBusinesses.size})`);
      emit({ type: "keyword_done", keyword, found: results.length, added, total: allBusinesses.size });
    }
  } finally {
    await browser.close();
  }

  const businesses = Array.from(allBusinesses.values());
  console.log(`[discover] DONE — ${businesses.length} unique, ${businesses.filter(b => b.website).length} with websites`);
  return { businesses };
}

async function _searchOneMaps({ searchUrl, limit, context, DEBUG, emit, keyword }) {
  emit = emit || (() => {});
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
    } catch {
      const visible = await page.evaluate(() => document.body.innerText.slice(0, 300)).catch(() => "");
      console.log(`[discover] results panel NOT found. Page: ${visible}`);
      await page.close();
      return [];
    }

    await randSleep(800, 1500);
    console.log("[discover] results panel found, scrolling...");

    // Scroll to load all result cards
    const resultsPanel = await page.$('div[role="feed"], div.m6QErb[style*="overflow"]');
    let prevCount = 0, stableRounds = 0;

    while (true) {
      const cards = await page.$$('a[href*="/maps/place/"]');
      const n = cards.length;
      if (limit > 0 && n >= limit) { console.log(`[discover] limit ${limit} reached`); break; }
      if (n === prevCount) {
        if (++stableRounds >= 4) { console.log(`[discover] stable at ${n} results`); break; }
      } else { stableRounds = 0; console.log(`[discover] ${n} results loaded...`); emit({ type: "scroll", count: n, keyword }); }
      prevCount = n;
      if (resultsPanel) {
        await resultsPanel.evaluate(el => el.scrollBy(0, Math.floor(300 + Math.random() * 300)));
      } else {
        await page.evaluate(() => window.scrollBy(0, Math.floor(300 + Math.random() * 300)));
      }
      await randSleep(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX);
    }

    // Step 1: extract all card metadata in one JS pass (no element handles held)
    const allCardData = await page.evaluate((lim) => {
      const cards = Array.from(document.querySelectorAll('a[href*="/maps/place/"]'));
      const toUse = lim > 0 ? cards.slice(0, lim) : cards;
      const seen = new Set();
      return toUse.map(card => {
        const href = card.getAttribute("href") || "";
        if (seen.has(href)) return null;
        seen.add(href);
        const container = card.parentElement || card;
        const name = container.querySelector('.qBF1Pd, .fontHeadlineSmall, [class*="fontHeadline"]')?.textContent?.trim() || "";
        if (!name) return null;
        const rating      = container.querySelector('span.MW4etd')?.textContent?.trim() || "";
        const reviewCount = container.querySelector('span.UY7F9')?.textContent?.replace(/[()]/g, "").trim() || "";
        const category    = container.querySelector('.W4Efsd > span:first-child, .DkEaL')?.textContent?.trim() || "";
        const address     = container.querySelector('.W4Efsd > span:last-child')?.textContent?.trim() || "";
        const placeMatch  = href.match(/\/maps\/place\/([^/@]+)/);
        const mapsUrl     = placeMatch ? `https://www.google.com/maps${placeMatch[0]}` : "";
        return { href, name, category, rating, reviewCount, address, mapsUrl };
      }).filter(Boolean);
    }, limit);

    console.log(`[discover] ${allCardData.length} cards collected, clicking for details...`);

    const businesses = [];

    // Step 2: click each card using a fresh query (not a stale handle)
    for (let i = 0; i < allCardData.length; i++) {
      const data = allCardData[i];
      let website = null, phone = null, email = null;
      try {
        // Always re-query — element handles go stale after other cards are clicked
        const escapedHref = data.href.replace(/"/g, '\"');
        const card = await page.$(`a[href="${escapedHref}"]`);
        if (card) {
          await card.scrollIntoViewIfNeeded().catch(() => {});
          await randSleep(150, 250);

          const panelBefore = await page.$eval(
            '[role="main"] h1, .DUwDvf, .fontHeadlineLarge',
            el => el.textContent.trim()
          ).catch(() => "");

          await card.click();

          // Poll until the detail panel updates to show this business
          for (let attempt = 0; attempt < 20; attempt++) {
            await sleep(200);
            const panelTitle = await page.$eval(
              '[role="main"] h1, .DUwDvf, .fontHeadlineLarge',
              el => el.textContent.trim()
            ).catch(() => "");
            if (panelTitle && panelTitle !== panelBefore) break;
          }

          website = await page.evaluate(() => {
            const specific = [
              'a[data-item-id="authority"]',
              'a[aria-label*="ウェブサイト"]',
              'a[aria-label*="website"]',
              'a[aria-label*="Website"]',
            ];
            for (const sel of specific) {
              const el = document.querySelector(sel);
              if (el?.getAttribute("href")?.startsWith("http")) return el.getAttribute("href");
            }
            const panel = document.querySelector('[role="main"]');
            if (!panel) return null;
            for (const a of panel.querySelectorAll('a[href^="http"]')) {
              const h = a.getAttribute("href") || "";
              if (h.startsWith("http") &&
                  !h.includes("google.com") && !h.includes("goo.gl") &&
                  !h.includes("tripadvisor") && !h.includes("booking.com") &&
                  !h.includes("instagram.com") && !h.includes("facebook.com") &&
                  !h.includes("airbnb") && !h.includes("agoda") && !h.includes("jalan.net")) {
                return h;
              }
            }
            return null;
          });

          if (!isBusinessWebsite(website)) website = null;

          phone = await page.$eval(
            '[data-item-id*="phone"], [aria-label*="電話番号"]',
            el => el.textContent.trim()
          ).catch(() => null);

          const bodyText = await page.$eval('[role="main"]', el => el.innerText).catch(() => "");
          const emailMatch = bodyText.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/);
          if (emailMatch) email = emailMatch[0].toLowerCase();

          await page.keyboard.press("Escape");
          await randSleep(200, 400);
        }
      } catch (e) {
        console.warn(`[discover] detail failed "${data.name}": ${e.message.split("\n")[0]}`);
      }

      businesses.push({
        name: data.name, category: data.category,
        rating: data.rating || null, review_count: data.reviewCount || null,
        address: data.address, maps_url: data.mapsUrl,
        website, phone, email, status: "new",
      });

      if (i % 10 === 0 || DEBUG) {
        console.log(`[discover] ${i + 1}/${allCardData.length}: ${data.name} → ${website || "—"}`);
      }
      emit({ type: "detail", index: i + 1, total: allCardData.length, name: data.name, website: website || null, keyword });
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
