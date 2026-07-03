# DNS for scraper-lab VPS

This is a **new subdomain** for the Hetzner scraper host. It does **not** change your app’s primary URL (`app.vanyshr.com` on Vercel) or `www.vanyshr.com`.

Add this record in Cloudflare for zone **vanyshr.com** (DNS only / grey cloud for first Let's Encrypt issuance):

| Type | Name        | Content          | Proxy |
|------|-------------|------------------|-------|
| A    | scraper-lab | 178.156.171.112  | Off   |

After propagation, Caddy on the VPS will obtain a certificate automatically. Restart if needed:

```bash
ssh deploy@178.156.171.112
cd /opt/vanyshr/caddy && docker compose restart caddy && docker compose logs -f caddy
```

Verify:

```bash
curl -sS https://scraper-lab.vanyshr.com/
```

Expected body: `vanyshr scraper-lab VPS OK`
