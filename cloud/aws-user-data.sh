#!/bin/bash
# Canarito host: Ubuntu 24.04, no inbound ports, managed through SSM only.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q unzip curl git python3 openjdk-17-jre-headless libpulse0 libnss3 libxcomposite1 libxcursor1 libxi6 libxtst6 \
  libxdamage1 libxrandr2 libxkbfile1 libx11-xcb1 libgbm1 libdrm2 libgl1 libasound2t64 unattended-upgrades
useradd --system --create-home --home-dir /var/lib/canarito --groups kvm canarito
SDK=/opt/android-sdk
mkdir -p $SDK/cmdline-tools && cd /tmp
curl -fsSL -o tools.zip https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip
unzip -q tools.zip && mv cmdline-tools $SDK/cmdline-tools/latest && rm tools.zip
(yes || true) | $SDK/cmdline-tools/latest/bin/sdkmanager --sdk_root=$SDK --licenses >/dev/null
chown -R canarito:canarito $SDK
git clone -q https://github.com/sebospc/canarito.git /opt/canarito && chown -R canarito:canarito /opt/canarito
cat > /etc/systemd/system/canarito@.service <<'UNIT'
[Unit]
Description=Canarito receptor %i
After=network-online.target
Wants=network-online.target
[Service]
User=canarito
Environment=ANDROID_HOME=/opt/android-sdk
ExecStart=/usr/bin/python3 /opt/canarito/canarito.py run --name %i
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
touch /var/lib/canarito/.bootstrap-done
