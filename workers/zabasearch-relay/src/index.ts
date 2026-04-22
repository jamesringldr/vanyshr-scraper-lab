/**
 * zabasearch-relay — Cloudflare Worker
 *
 * Endpoints:
 *   GET  /phone?number=XXXXXXXXXX   Phone lookup (no auth, CORS open)
 *   GET  /relay?url=...             URL proxy for Supabase Edge Functions
 *                                   (requires X-Relay-Token header or ?token=)
 */

interface Env {
  RELAY_TOKEN?: string;
}

// ── Shared constants ────────────────────────────────────────────────────────

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Relay-Token",
} as const;

const ZABA_HEADERS: HeadersInit = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
  Referer: "https://www.zabasearch.com/",
};

const ALLOWED_DOMAINS = ["zabasearch.com", "fastpeoplesearch.com"];

// ── Types ───────────────────────────────────────────────────────────────────

export type ZabaPhoneResult = {
  phone: string;
  source_url: string;
  name: string | null;
  age: string | null;
  birth_year: string | null;
  line_type: string | null;
  carrier: string | null;
  location: string | null;
  time_zone: string | null;
  aliases: string[];
  related_persons: Array<{ name: string; href: string }>;
  most_recent_address: string | null;
  previous_addresses: string[];
  email_domains: string[];
  previous_phones: string[];
  social_media: string[];
  jobs: string[];
  education: string[];
  professional_licenses: string[];
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function jsonResp(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

function normalizePhone(raw: string): string | null {
  const digits = raw.replace(/\D/g, "");
  const d = digits.length === 11 && digits[0] === "1" ? digits.slice(1) : digits;
  return d.length === 10 ? d : null;
}

// ── HTML parsing ─────────────────────────────────────────────────────────────

async function parsePhonePage(
  response: Response,
  phone: string,
  sourceUrl: string
): Promise<{ result: ZabaPhoneResult; found: boolean }> {
  const data: ZabaPhoneResult = {
    phone,
    source_url: sourceUrl,
    name: null,
    age: null,
    birth_year: null,
    line_type: null,
    carrier: null,
    location: null,
    time_zone: null,
    aliases: [],
    related_persons: [],
    most_recent_address: null,
    previous_addresses: [],
    email_domains: [],
    previous_phones: [],
    social_media: [],
    jobs: [],
    education: [],
    professional_licenses: [],
  };

  let resultTopFound = false;

  // ── Buffers (shared mutable state, safe because HTML is sequential) ────────
  let nameTextBuf = "";
  let thTextBuf = "";
  let tdTextBuf = "";
  const pendingThKeys: string[] = []; // FIFO queue: th keys waiting for matching td values

  let nameLiBuf = "";
  let relatedABuf = "";
  let relatedAHref = "";
  let locH5Buf = "";
  let locLiBuf = "";
  let locationCtx: "most-recent" | "previous" | null = null;
  let mostRecentDone = false;
  let emailLiBuf = "";
  let inBlurSpan = false;
  let prevPhoneBuf = "";
  let socialBuf = "";
  let jobsBuf = "";
  let eduBuf = "";
  let licBuf = "";

  // Maps a th key to its corresponding ZabaPhoneResult field
  function mapField(key: string, value: string | null): void {
    if (!value) return;
    switch (key) {
      case "age":        data.age = value; break;
      case "birth year": data.birth_year = value; break;
      case "line type":  data.line_type = value; break;
      case "carrier":    data.carrier = value; break;
      case "location":   data.location = value; break;
      case "time zone":  data.time_zone = value; break;
    }
  }

  const rewriter = new HTMLRewriter()

    // ── Detect whether a result page loaded at all ──────────────────────────
    .on("#result-top-content", {
      element() {
        resultTopFound = true;
      },
    })

    // ── Name: first <h3> inside #result-top-content ─────────────────────────
    .on("#result-top-content h3", {
      element(el) {
        nameTextBuf = "";
        el.onEndTag(() => {
          if (!data.name) data.name = nameTextBuf.trim() || null;
        });
      },
      text(chunk) {
        nameTextBuf += chunk.text;
      },
    })

    // ── Table th: push key to FIFO queue ────────────────────────────────────
    // Handles both same-row th+td (Line Type) and cross-row th/td (Age table)
    .on("#result-top-content table th", {
      element(el) {
        thTextBuf = "";
        el.onEndTag(() => {
          const k = thTextBuf.trim().toLowerCase();
          if (k) pendingThKeys.push(k);
        });
      },
      text(chunk) {
        thTextBuf += chunk.text;
      },
    })

    // ── Table td: shift matching key from FIFO queue ─────────────────────────
    .on("#result-top-content table td", {
      element(el) {
        tdTextBuf = "";
        el.onEndTag(() => {
          const key = pendingThKeys.shift();
          if (key) mapField(key, tdTextBuf.trim() || null);
        });
      },
      text(chunk) {
        tdTextBuf += chunk.text;
      },
    })

    // ── Aliases ─────────────────────────────────────────────────────────────
    .on("#phone-number-names ul li", {
      element(el) {
        nameLiBuf = "";
        el.onEndTag(() => {
          const t = nameLiBuf.trim();
          if (t && !data.aliases.includes(t)) data.aliases.push(t);
        });
      },
      text(chunk) {
        nameLiBuf += chunk.text;
      },
    })

    // ── Related persons ──────────────────────────────────────────────────────
    .on("#phone-number-related ul li a", {
      element(el) {
        relatedABuf = "";
        relatedAHref = el.getAttribute("href") ?? "";
        el.onEndTag(() => {
          const name = relatedABuf.trim();
          if (name) data.related_persons.push({ name, href: relatedAHref });
        });
      },
      text(chunk) {
        relatedABuf += chunk.text;
      },
    })

    // ── Location h5 sets context for following li items ──────────────────────
    .on("#phone-number-locations h5", {
      element(el) {
        locH5Buf = "";
        el.onEndTag(() => {
          const t = locH5Buf.toLowerCase();
          if (t.includes("most recent")) locationCtx = "most-recent";
          else if (t.includes("previous")) locationCtx = "previous";
          else locationCtx = null;
        });
      },
      text(chunk) {
        locH5Buf += chunk.text;
      },
    })
    .on("#phone-number-locations ul li", {
      element(el) {
        locLiBuf = "";
        const ctx = locationCtx; // Capture at element-open time (before h5 can change it)
        el.onEndTag(() => {
          const t = locLiBuf.trim();
          if (!t) return;
          if (ctx === "most-recent" && !mostRecentDone) {
            data.most_recent_address = t;
            mostRecentDone = true;
          } else if (ctx === "previous") {
            data.previous_addresses.push(t);
          }
        });
      },
      text(chunk) {
        locLiBuf += chunk.text;
      },
    })

    // ── Email domains — suppress blurred username prefix ────────────────────
    .on("#phone-number-emails ul li span.blur", {
      element(el) {
        inBlurSpan = true;
        el.onEndTag(() => {
          inBlurSpan = false;
        });
      },
    })
    .on("#phone-number-emails ul li", {
      element(el) {
        emailLiBuf = "";
        el.onEndTag(() => {
          // After removing the blurred part, the remaining text is "@domain.com"
          const raw = emailLiBuf.trim().replace(/^@\s*/, "");
          if (raw) data.email_domains.push(`@${raw}`);
        });
      },
      text(chunk) {
        if (!inBlurSpan) emailLiBuf += chunk.text;
      },
    })

    // ── Previous phones ──────────────────────────────────────────────────────
    .on("#phone-number-previous ul li", {
      element(el) {
        prevPhoneBuf = "";
        el.onEndTag(() => {
          const t = prevPhoneBuf.trim();
          if (t) data.previous_phones.push(t);
        });
      },
      text(chunk) {
        prevPhoneBuf += chunk.text;
      },
    })

    // ── Social media ─────────────────────────────────────────────────────────
    .on("#phone-number-socialmedia ul li", {
      element(el) {
        socialBuf = "";
        el.onEndTag(() => {
          const t = socialBuf.trim();
          if (t) data.social_media.push(t);
        });
      },
      text(chunk) {
        socialBuf += chunk.text;
      },
    })

    // ── Jobs ─────────────────────────────────────────────────────────────────
    .on("#phone-number-jobs ul li", {
      element(el) {
        jobsBuf = "";
        el.onEndTag(() => {
          const t = jobsBuf.trim();
          if (t) data.jobs.push(t);
        });
      },
      text(chunk) {
        jobsBuf += chunk.text;
      },
    })

    // ── Education ────────────────────────────────────────────────────────────
    .on("#phone-number-education ul li", {
      element(el) {
        eduBuf = "";
        el.onEndTag(() => {
          const t = eduBuf.trim();
          if (t) data.education.push(t);
        });
      },
      text(chunk) {
        eduBuf += chunk.text;
      },
    })

    // ── Professional licenses ─────────────────────────────────────────────────
    .on("#phone-number-licenses ul li", {
      element(el) {
        licBuf = "";
        el.onEndTag(() => {
          const t = licBuf.trim();
          if (t) data.professional_licenses.push(t);
        });
      },
      text(chunk) {
        licBuf += chunk.text;
      },
    });

  // Consuming the transformed response drives all HTMLRewriter callbacks
  await rewriter.transform(response).text();

  return { result: data, found: resultTopFound };
}

// ── Route handlers ──────────────────────────────────────────────────────────

async function handlePhone(rawNumber: string): Promise<Response> {
  const phone = normalizePhone(rawNumber);
  if (!phone) return jsonResp({ error: "invalid_phone" }, 400);

  const formatted = `${phone.slice(0, 3)}-${phone.slice(3, 6)}-${phone.slice(6)}`;
  const sourceUrl = `https://www.zabasearch.com/phone/${formatted}`;

  let zabaResp: Response;
  try {
    zabaResp = await fetch(sourceUrl, { headers: ZABA_HEADERS });
  } catch {
    return jsonResp({ error: "fetch_failed" }, 502);
  }

  if (!zabaResp.ok) return jsonResp({ error: "fetch_failed" }, 502);

  const { result, found } = await parsePhonePage(zabaResp, phone, sourceUrl);
  if (!found) return jsonResp({ error: "no_result" }, 404);

  return jsonResp(result);
}

async function handleRelay(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const token =
    request.headers.get("X-Relay-Token") ?? url.searchParams.get("token");

  if (!env.RELAY_TOKEN || token !== env.RELAY_TOKEN) {
    return jsonResp({ error: "unauthorized" }, 401);
  }

  const targetUrl = url.searchParams.get("url");
  if (!targetUrl) return jsonResp({ error: "missing_url" }, 400);

  try {
    const parsed = new URL(targetUrl);
    const allowed = ALLOWED_DOMAINS.some(
      (d) => parsed.hostname === d || parsed.hostname.endsWith(`.${d}`)
    );
    if (!allowed) return jsonResp({ error: "domain_not_allowed" }, 403);
  } catch {
    return jsonResp({ error: "invalid_url" }, 400);
  }

  let upstream: Response;
  try {
    upstream = await fetch(targetUrl, { headers: ZABA_HEADERS });
  } catch {
    return jsonResp({ error: "fetch_failed" }, 502);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      ...CORS,
      "Content-Type":
        upstream.headers.get("Content-Type") ?? "text/html; charset=utf-8",
    },
  });
}

// ── Worker entry point ───────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    const { pathname, searchParams } = new URL(request.url);

    if (pathname === "/phone") {
      return handlePhone(searchParams.get("number") ?? "");
    }

    if (pathname === "/relay" || pathname === "/") {
      return handleRelay(request, env);
    }

    return jsonResp({ error: "not_found" }, 404);
  },
};
