export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Only allow GET
    if (request.method !== "GET") {
      return new Response("method not allowed", { status: 405 });
    }

    // Auth check
    const token = request.headers.get("x-relay-token");
    if (!token || token !== env.RELAY_TOKEN) {
      return new Response("unauthorized", { status: 401 });
    }

    const url = new URL(request.url);
    const target = url.searchParams.get("url");
    if (!target) {
      return new Response("missing ?url param", { status: 400 });
    }

    // Only allow known scrape targets
    const allowed = [
      "https://www.zabasearch.com/",
      "https://www.fastpeoplesearch.com/",
    ];
    if (!allowed.some((prefix) => target.startsWith(prefix))) {
      return new Response("target not allowed", { status: 403 });
    }

    try {
      const response = await fetch(target, {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
          "Accept-Language": "en-US,en;q=0.9",
          "Cache-Control": "max-age=0",
          "Upgrade-Insecure-Requests": "1",
          "Sec-Fetch-Dest": "document",
          "Sec-Fetch-Mode": "navigate",
          "Sec-Fetch-Site": "none",
          "Sec-Fetch-User": "?1",
          "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
          "Sec-CH-UA-Mobile": "?0",
          "Sec-CH-UA-Platform": '"Windows"',
        },
        redirect: "follow",
      });

      const html = await response.text();

      return new Response(html, {
        status: response.status,
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "X-Relay-Status": response.status.toString(),
          "X-Html-Length": html.length.toString(),
        },
      });
    } catch (err) {
      return new Response(`fetch error: ${(err as Error).message}`, { status: 502 });
    }
  },
} satisfies ExportedHandler<Env>;

interface Env {
  RELAY_TOKEN: string;
}
