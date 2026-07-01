/**
 * FPS smoke test — Google referral chain technique
 *
 * Flow: google.com → search "fast people search" → scroll past/back → click →
 *       attempt Turnstile checkbox (bezier path) → fill FPS search form
 *
 * Usage:  node smoke.mjs <firstName> <lastName> [city] [state]
 * Example: node smoke.mjs James Oehring Cameron MO
 *
 * Outputs: /tmp/fps-results.html, /tmp/fps-screenshot.png, /tmp/fps-video/, /tmp/fps-smoke.log
 */

import { chromium } from "playwright";
import { writeFileSync, mkdirSync } from "fs";

const [, , firstName, lastName, city, state] = process.argv;
if (!firstName || !lastName) {
  console.error("Usage: node smoke.mjs <firstName> <lastName> [city] [state]");
  process.exit(1);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const jitter = (min, max) => sleep(min + Math.random() * (max - min));

const LOG = [];
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  LOG.push(line);
}

// Bezier curve mouse movement
async function moveMouse(page, toX, toY) {
  const from = await page.evaluate(() => ({ x: window.__mx || 640, y: window.__my || 400 }));
  const cpX = from.x + (toX - from.x) * 0.4 + (Math.random() - 0.5) * 200;
  const cpY = from.y + (toY - from.y) * 0.4 + (Math.random() - 0.5) * 120;
  const steps = 18 + Math.floor(Math.random() * 12);
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = (1-t)*(1-t)*from.x + 2*(1-t)*t*cpX + t*t*toX;
    const y = (1-t)*(1-t)*from.y + 2*(1-t)*t*cpY + t*t*toY;
    await page.mouse.move(x, y);
    await sleep(8 + Math.random() * 18);
  }
  await page.evaluate(({ x, y }) => { window.__mx = x; window.__my = y; }, { x: toX, y: toY });
}

// Human typing with occasional mistype + backspace
const NEARBY = {
  a:'sq',b:'vgn',c:'xdv',d:'sec',e:'wr',f:'dgr',g:'fht',h:'gj',i:'ou',j:'hk',
  k:'jl',l:'k',m:'n',n:'mb',o:'ip',p:'o',q:'wa',r:'et',s:'ad',t:'ry',
  u:'yi',v:'cb',w:'qe',x:'cz',y:'tu',z:'x',' ':' ',
};
async function humanType(page, text) {
  for (let i = 0; i < text.length; i++) {
    const ch = text[i].toLowerCase();
    if (ch !== ' ' && Math.random() < 0.07 && NEARBY[ch]) {
      const wrong = NEARBY[ch][Math.floor(Math.random() * NEARBY[ch].length)];
      await page.keyboard.type(wrong, { delay: 55 + Math.random() * 90 });
      await jitter(80, 220);
      await page.keyboard.press("Backspace");
      await jitter(60, 180);
    }
    await page.keyboard.type(text[i], { delay: 55 + Math.random() * 110 });
    if (Math.random() < 0.08) await jitter(180, 550);
  }
}

// Ad domain blocklist
const AD_PATTERNS = [
  "doubleclick.net","googlesyndication.com","googleadservices.com",
  "googletagmanager.com","google-analytics.com","facebook.net","fbcdn.net",
  "amazon-adsystem.com","taboola.com","outbrain.com","criteo.com",
  "pubmatic.com","rubiconproject.com","openx.net","adsrvr.org",
  "moatads.com","adnxs.com","connatix.com","vidazoo.com","jwplayer.com",
];
const isAd = (url) => AD_PATTERNS.some((p) => url.includes(p));

function classifyHtml(html) {
  const lc = html.toLowerCase();
  if (lc.includes("just a moment") || lc.includes("checking your browser") ||
      lc.includes("access denied") || (lc.includes("cloudflare") && html.length < 5000))
    return "blocked";
  if (lc.includes("turnstile") || lc.includes("verify you are human") ||
      lc.includes("challenge-platform"))
    return "turnstile";
  if (lc.includes("no results found") || lc.includes("did not return any matches"))
    return "no_results";
  if (html.length > 5000 && (lc.includes('class="card"') || lc.includes("fastpeoplesearch")))
    return "success";
  return "unknown";
}
const countCards = (html) => (html.match(/class="card["\s]/g) || []).length;

// ─── Main ────────────────────────────────────────────────────────────────────

async function run() {
  const label = [firstName, lastName, city, state].filter(Boolean).join(" ");
  log(`FPS smoke test — "${label}"`);
  mkdirSync("/tmp/fps-video", { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  const context = await browser.newContext({
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    viewport: { width: 1280, height: 800 },
    locale: "en-US",
    timezoneId: "America/Chicago",
    extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" },
    recordVideo: { dir: "/tmp/fps-video/", size: { width: 1280, height: 800 } },
  });

  // Block ads + video on FPS pages only
  await context.route("**/*", (route) => {
    const url = route.request().url();
    const type = route.request().resourceType();
    if (isAd(url)) { route.abort(); return; }
    if (url.includes("fastpeoplesearch") && type === "media") { route.abort(); return; }
    route.continue();
  });

  const page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error") log(`  [browser:err] ${m.text().slice(0, 120)}`); });
  page.on("response", (r) => {
    const u = r.url();
    if (u.includes("fastpeoplesearch") || u.includes("cloudflare") || u.includes("turnstile"))
      log(`  [http] ${r.status()} ${u.slice(0, 110)}`);
  });

  try {
    // ── 1. Google ─────────────────────────────────────────────────────────────
    log("[1/5] Google...");
    await page.goto("https://www.google.com", { waitUntil: "domcontentloaded", timeout: 30000 });
    log(`  title: "${await page.title()}"`);
    await jitter(700, 1400);

    for (const sel of ['button:has-text("Accept all")', 'button:has-text("I agree")']) {
      const btn = page.locator(sel).first();
      if (await btn.count() > 0) { await btn.click(); await jitter(400, 800); break; }
    }

    // ── 2. Type search ────────────────────────────────────────────────────────
    log("[2/5] Typing search...");
    const searchBox = page.locator('textarea[name="q"], input[name="q"]').first();
    await searchBox.waitFor({ timeout: 10000 });
    const sbBox = await searchBox.boundingBox();
    if (sbBox) await moveMouse(page, sbBox.x + sbBox.width / 2, sbBox.y + sbBox.height / 2);
    await searchBox.click();
    await jitter(200, 500);
    await humanType(page, "fast people search");
    await jitter(400, 900);
    await page.keyboard.press("Enter");
    await page.waitForLoadState("domcontentloaded", { timeout: 15000 });
    await jitter(1200, 2000);

    const fpsCount = await page.locator('a[href*="fastpeoplesearch.com"]:visible').count();
    log(`  FPS links in results: ${fpsCount}`);

    if (fpsCount === 0) {
      log("  ERROR: no FPS links — Google may have blocked us");
      writeFileSync("/tmp/google-results.html", await page.content());
      await page.screenshot({ path: "/tmp/fps-screenshot.png" });
      await context.close(); await browser.close();
      writeFileSync("/tmp/fps-smoke.log", LOG.join("\n"));
      process.exit(1);
    }

    // ── 3. Scroll past result, back, then click ───────────────────────────────
    log("[3/5] Scroll past → back → click...");
    await page.mouse.wheel(0, 380);
    await jitter(600, 1200);
    await page.mouse.wheel(0, 280);
    await jitter(700, 1400);
    await page.mouse.wheel(0, -480);
    await jitter(500, 1000);

    const fpsLink = page.locator('a[href*="fastpeoplesearch.com"]:visible').first();
    const linkBox = await fpsLink.boundingBox();
    log(`  clicking: ${await fpsLink.getAttribute("href")}`);
    if (linkBox) {
      await moveMouse(page, linkBox.x + linkBox.width / 2, linkBox.y + linkBox.height / 2);
      await jitter(120, 300);
    }
    await fpsLink.click();
    await page.waitForLoadState("domcontentloaded", { timeout: 20000 });
    await jitter(1500, 3000);
    log(`  landed: ${page.url()} | title: "${await page.title()}"`);

    // ── 4. Turnstile — try to click checkbox regardless ───────────────────────
    const landingHtml = await page.content();
    const landingClass = classifyHtml(landingHtml);
    log(`  landing classification: ${landingClass}`);

    if (landingClass === "turnstile" || landingClass === "blocked") {
      log("[4/5] Turnstile present — waiting for iframe then clicking checkbox...");
      await jitter(2000, 3500); // give CF time to fully render the widget

      const selectors = [
        'input[type="checkbox"]',
        ".ctp-checkbox-label",
        '[class*="checkbox"]',
        "label",
        "body", // last resort — click center of iframe
      ];

      const turnstileFrame = page.frameLocator(
        'iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]'
      );

      let clicked = false;
      for (const sel of selectors) {
        try {
          const el = turnstileFrame.locator(sel).first();
          await el.waitFor({ timeout: 4000 });
          const elBox = await el.boundingBox();
          if (elBox) {
            const tx = elBox.x + elBox.width / 2 + (Math.random() - 0.5) * 6;
            const ty = elBox.y + elBox.height / 2 + (Math.random() - 0.5) * 4;
            log(`  found element via "${sel}" — moving (bezier) then clicking...`);
            await moveMouse(page, tx, ty);
            await jitter(200, 500);
            await el.click();
            clicked = true;
            log("  clicked — waiting up to 8s for Turnstile response...");
            await jitter(6000, 8000);
            break;
          }
        } catch (_) { /* try next */ }
      }

      if (!clicked) log("  could not locate Turnstile element in iframe");

      const afterHtml = await page.content();
      const afterClass = classifyHtml(afterHtml);
      log(`  classification after Turnstile attempt: ${afterClass}`);
    } else {
      log("[4/5] No Turnstile on landing — continuing...");
    }

    // ── 5. Fill FPS search form ────────────────────────────────────────────────
    log("[5/5] Looking for FPS search form...");
    const nameInput = page.locator(
      'input[name="name"], input[id="id_name"], input[placeholder*="Name" i]'
    ).first();

    if (await nameInput.count() > 0) {
      const ninBox = await nameInput.boundingBox();
      if (ninBox) await moveMouse(page, ninBox.x + ninBox.width / 2, ninBox.y + ninBox.height / 2);
      await nameInput.click();
      await jitter(200, 500);
      await humanType(page, `${firstName} ${lastName}`);
      await jitter(300, 700);

      if (city || state) {
        const locInput = page.locator(
          'input[name="state"], input[name="location"], input[placeholder*="City" i], input[placeholder*="State" i]'
        ).first();
        if (await locInput.count() > 0) {
          const locBox = await locInput.boundingBox();
          if (locBox) await moveMouse(page, locBox.x + locBox.width / 2, locBox.y + locBox.height / 2);
          await locInput.click();
          await jitter(150, 400);
          await humanType(page, [city, state].filter(Boolean).join(", "));
          await jitter(300, 600);
        }
      }

      await jitter(400, 800);
      await page.keyboard.press("Enter");
      await page.waitForLoadState("domcontentloaded", { timeout: 20000 });
      await jitter(2000, 4000);
      log(`  final url: ${page.url()}`);
    } else {
      log("  no search form found — classifying current page");
    }

    // ── Result ────────────────────────────────────────────────────────────────
    const html = await page.content();
    const classification = classifyHtml(html);
    const cards = countCards(html);

    await page.screenshot({ path: "/tmp/fps-screenshot.png" });
    writeFileSync("/tmp/fps-results.html", html);

    log("");
    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    log(`Classification: ${classification.toUpperCase()}`);
    if (classification === "success")         log(`✅ ~${cards} result cards`);
    else if (classification === "turnstile")  log("⚠  Turnstile not bypassed");
    else if (classification === "blocked")    log("✗  Hard blocked");
    else if (classification === "no_results") log("~  No results for query");
    else log(`?  Unknown — html length: ${html.length}`);
    log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

  } catch (err) {
    log(`ERROR: ${err.message}`);
    try {
      await page.screenshot({ path: "/tmp/fps-screenshot.png" });
      writeFileSync("/tmp/fps-error.html", await page.content());
    } catch (_) {}
  }

  await context.close();
  await browser.close();
  writeFileSync("/tmp/fps-smoke.log", LOG.join("\n"));
}

run();
