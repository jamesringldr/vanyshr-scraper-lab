FROM denoland/deno:2.1.4

WORKDIR /app

COPY deno.json deno.lock package.json ./
COPY packages ./packages
COPY apps ./apps

RUN deno cache --node-modules-dir=true --no-check apps/scraper-api/main.ts apps/scraper-worker/main.ts

ENV PORT=8080
