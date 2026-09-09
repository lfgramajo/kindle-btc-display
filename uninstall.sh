#!/usr/bin/env bash
set -u
APP_ROOT="${APP_ROOT:-/opt/kindle-btc-display}"

echo "== KINDLE BITCOIN PRICE DISPLAY UNINSTALL =="

sudo rm -f /etc/cron.d/kindle-btc-display-refresh

# Also remove project-specific legacy systemd units from pre-cron releases.
sudo systemctl disable --now kindle-btc-display-refresh.timer >/dev/null 2>&1 || true
sudo rm -f /etc/systemd/system/kindle-btc-display-refresh.timer /etc/systemd/system/kindle-btc-display-refresh.service
sudo systemctl daemon-reload >/dev/null 2>&1 || true

if [ -d "$APP_ROOT" ]; then
  ( cd "$APP_ROOT" && sudo docker compose down ) || true
fi

echo "Runtime stopped. Application files remain at $APP_ROOT for manual review/removal."
