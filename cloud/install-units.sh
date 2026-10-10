#!/bin/bash
# Installs the app server units and cloudflared. Safe to run again. Touches no receptor and not adb.
# Run as root from the repo: sudo bash /opt/canarito/cloud/install-units.sh
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
case "$(uname -m)" in
  x86_64) arch=amd64 ;;
  aarch64) arch=arm64 ;;
  *) echo "unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac
if [ ! -x /usr/local/bin/cloudflared ]; then
  curl -fsSL -o /usr/local/bin/cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$arch"
  chmod 755 /usr/local/bin/cloudflared
fi
install -m 644 "$repo/cloud/canarito-serve.service" "$repo/cloud/canarito-serve-demo.service" /etc/systemd/system/
# The tunnel token is written on the host by its operator. Without the file the unit stays off
# instead of restarting forever.
cat > /etc/systemd/system/cloudflared.service <<'UNIT'
[Unit]
Description=Cloudflare tunnel to the Canarito app server
After=network-online.target
Wants=network-online.target
ConditionPathExists=/var/lib/canarito/.cloudflared-token
[Service]
User=canarito
ExecStart=/usr/local/bin/cloudflared --no-autoupdate tunnel run --token-file /var/lib/canarito/.cloudflared-token
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
# The demo server is for App Review only: install its unit, enable it by hand when needed.
systemctl enable canarito-serve cloudflared
