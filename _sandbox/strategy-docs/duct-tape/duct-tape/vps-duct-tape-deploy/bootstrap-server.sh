#!/usr/bin/env bash
# Idempotent VPS bootstrap for vanyshr-scraper-lab (Ubuntu 24.04).
# Run on the server as root: bash bootstrap-server.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq ca-certificates curl gnupg ufw fail2ban unattended-upgrades git

if ! id deploy &>/dev/null; then
  adduser --disabled-password --gecos "Vanyshr deploy" deploy
  usermod -aG sudo deploy
  mkdir -p /home/deploy/.ssh
  cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
  chown -R deploy:deploy /home/deploy/.ssh
  chmod 700 /home/deploy/.ssh
  chmod 600 /home/deploy/.ssh/authorized_keys
fi
echo 'deploy ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

if ! command -v docker &>/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker deploy
systemctl enable --now docker fail2ban

mkdir -p /opt/vanyshr/{caddy,scraper-lab}
chown -R deploy:deploy /opt/vanyshr

cat > /opt/vanyshr/caddy/docker-compose.yml <<'YAML'
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
YAML

cat > /opt/vanyshr/caddy/Caddyfile <<'CADDY'
scraper-lab.vanyshr.com {
    respond "vanyshr scraper-lab VPS OK" 200
}
CADDY

chown -R deploy:deploy /opt/vanyshr/caddy
cd /opt/vanyshr/caddy
docker compose up -d

echo "Bootstrap complete. Add DNS A record scraper-lab -> $(curl -sS ifconfig.me 2>/dev/null || echo THIS_SERVER_IP)"
