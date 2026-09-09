#!/usr/bin/env bash
# Kindle Bitcoin Price Display — public installer
# Supported deployment target: Debian/Ubuntu-style Linux with Docker Compose and cron.

set -u

APP_ROOT="${APP_ROOT:-/opt/kindle-btc-display}"
CONTAINER="kindle-btc-display"
PORT="8787"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE_ROOT="/opt/kindle-btc-display-archive"

die() { echo "STOP: $*" >&2; exit 1; }

if [ "${1:-}" = "--help" ]; then
  echo "Usage: ./install.sh"
  echo "Optional environment: HOST_BIND_IP=x.x.x.x APP_TZ=Area/City APP_ROOT=/opt/kindle-btc-display"
  exit 0
fi

echo "== KINDLE BITCOIN PRICE DISPLAY 1.7.0-rc3 INSTALL =="
echo "SOURCE_DIR=$SOURCE_DIR"
echo "APP_ROOT=$APP_ROOT"

command -v sudo >/dev/null 2>&1 || die "sudo is required"
command -v docker >/dev/null 2>&1 || die "Docker is required"
command -v curl >/dev/null 2>&1 || die "curl is required"
command -v systemctl >/dev/null 2>&1 || die "systemd/systemctl is required for cron service management"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required"

if [ "$(realpath "$SOURCE_DIR")" = "$(realpath -m "$APP_ROOT")" ]; then
  die "run the installer from a clone/release directory, not from $APP_ROOT"
fi

HOST_BIND_IP="${HOST_BIND_IP:-}"
if [ -z "$HOST_BIND_IP" ]; then
  if command -v ip >/dev/null 2>&1; then
    HOST_BIND_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
  fi
fi
if [ -z "$HOST_BIND_IP" ]; then
  HOST_BIND_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
printf '%s' "$HOST_BIND_IP" | grep -Eq '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' || die "could not detect a LAN IPv4 address; rerun with HOST_BIND_IP=x.x.x.x"
APP_TZ="${APP_TZ:-UTC}"

echo "HOST_BIND_IP=$HOST_BIND_IP"
echo "APP_TZ=$APP_TZ"

echo
echo "== prebuild candidate image =="
( cd "$SOURCE_DIR" && sudo docker compose build ) || die "Docker image build failed; current installation was not touched"

echo
echo "== stop only the existing Kindle container =="
sudo docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

# Remove project-specific legacy systemd refresh units if upgrading from older releases.
sudo systemctl disable --now kindle-btc-display-refresh.timer >/dev/null 2>&1 || true
sudo rm -f /etc/systemd/system/kindle-btc-display-refresh.timer /etc/systemd/system/kindle-btc-display-refresh.service
sudo systemctl daemon-reload >/dev/null 2>&1 || true

ARCHIVE=""
if [ -d "$APP_ROOT" ]; then
  sudo mkdir -p "$ARCHIVE_ROOT"
  ARCHIVE="${ARCHIVE_ROOT}/kindle-btc-display.${STAMP}"
  sudo mv "$APP_ROOT" "$ARCHIVE" || die "could not archive existing application"
  echo "ARCHIVED=$ARCHIVE"
fi

echo
echo "== install source =="
sudo mkdir -p "$APP_ROOT"
sudo cp -a "$SOURCE_DIR/." "$APP_ROOT/" || die "copy failed"
sudo rm -rf "$APP_ROOT/.git"

# Restore live configuration/cache/output from the archived installation when present.
if [ -n "$ARCHIVE" ]; then
  [ -f "$ARCHIVE/.env" ] && sudo cp -a "$ARCHIVE/.env" "$APP_ROOT/.env"
  for f in coins.config extras.config weather.conf; do
    [ -f "$ARCHIVE/config/$f" ] && sudo cp -a "$ARCHIVE/config/$f" "$APP_ROOT/config/$f"
  done
  [ -d "$ARCHIVE/config/cache" ] && sudo cp -a "$ARCHIVE/config/cache" "$APP_ROOT/config/cache"
  [ -f "$ARCHIVE/output/kindle_btc_price.png" ] && sudo mkdir -p "$APP_ROOT/output" && sudo cp -a "$ARCHIVE/output/kindle_btc_price.png" "$APP_ROOT/output/"
fi

[ -f "$APP_ROOT/config/coins.config" ] || sudo cp "$APP_ROOT/config/coins.config.example" "$APP_ROOT/config/coins.config"
[ -f "$APP_ROOT/config/extras.config" ] || sudo cp "$APP_ROOT/config/extras.config.example" "$APP_ROOT/config/extras.config"
[ -f "$APP_ROOT/config/weather.conf" ] || sudo cp "$APP_ROOT/config/weather.conf.example" "$APP_ROOT/config/weather.conf"

# Host cron owns scheduling in the public deployment, so disable the in-process scheduler.
if grep -Eq '^internal_scheduler=' "$APP_ROOT/config/extras.config"; then
  sudo sed -i 's/^internal_scheduler=.*/internal_scheduler=off/' "$APP_ROOT/config/extras.config"
else
  printf '\ninternal_scheduler=off\n' | sudo tee -a "$APP_ROOT/config/extras.config" >/dev/null
fi

if [ ! -f "$APP_ROOT/.env" ]; then
  printf 'HOST_BIND_IP=%s\nAPP_TZ=%s\n' "$HOST_BIND_IP" "$APP_TZ" | sudo tee "$APP_ROOT/.env" >/dev/null
fi

# When upgrading, the preserved .env is authoritative for the actual bind address/timezone.
ENV_HOST_BIND_IP="$(awk -F= '/^HOST_BIND_IP=/{print $2; exit}' "$APP_ROOT/.env" 2>/dev/null)"
ENV_APP_TZ="$(awk -F= '/^APP_TZ=/{print $2; exit}' "$APP_ROOT/.env" 2>/dev/null)"
[ -n "$ENV_HOST_BIND_IP" ] && HOST_BIND_IP="$ENV_HOST_BIND_IP"
[ -n "$ENV_APP_TZ" ] && APP_TZ="$ENV_APP_TZ"
printf '%s' "$HOST_BIND_IP" | grep -Eq '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' || die "invalid HOST_BIND_IP in $APP_ROOT/.env"

sudo mkdir -p "$APP_ROOT/config/cache" "$APP_ROOT/output" "$APP_ROOT/logs"
sudo chown -R 10001:10001 "$APP_ROOT/config" "$APP_ROOT/output" "$APP_ROOT/logs"
sudo chmod 755 "$APP_ROOT" "$APP_ROOT/config" "$APP_ROOT/output" "$APP_ROOT/logs"

echo
echo "== start =="
( cd "$APP_ROOT" && sudo docker compose up -d --no-build ) || die "container start failed; previous installation remains archived at ${ARCHIVE:-none}"

echo
echo "== wait for health =="
HEALTH_OK=0
i=0
while [ "$i" -lt 90 ]; do
  if curl -fsS "http://${HOST_BIND_IP}:${PORT}/healthz" >/dev/null 2>&1; then
    HEALTH_OK=1
    break
  fi
  sleep 2
  i=$((i + 1))
done
if [ "$HEALTH_OK" -ne 1 ]; then
  sudo docker logs --tail=120 "$CONTAINER" 2>/dev/null || true
  die "health check did not become ready within 180 seconds"
fi

echo
echo "== install host cron trigger =="
CRON_FILE="/etc/cron.d/kindle-btc-display-refresh"
printf '%s\n' \
  '# Kindle Bitcoin Price Display — cache-aware refresh trigger' \
  'SHELL=/bin/sh' \
  'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
  '' \
  "0,10,20,30,40,50 * * * * root /usr/bin/curl -fsS http://${HOST_BIND_IP}:${PORT}/refresh >> ${APP_ROOT}/logs/cron-refresh.log 2>&1" \
  | sudo tee "$CRON_FILE" >/dev/null
sudo chmod 644 "$CRON_FILE"

if systemctl list-unit-files cron.service >/dev/null 2>&1; then
  sudo systemctl enable --now cron >/dev/null 2>&1 || die "could not enable cron.service"
elif systemctl list-unit-files crond.service >/dev/null 2>&1; then
  sudo systemctl enable --now crond >/dev/null 2>&1 || die "could not enable crond.service"
else
  die "cron service not found"
fi

echo
echo "== smoke =="
curl -fsS "http://${HOST_BIND_IP}:${PORT}/healthz" || die "healthz failed"
echo
curl -fsS "http://${HOST_BIND_IP}:${PORT}/status.json" | sed -n '1,80p'
curl -fsS "http://${HOST_BIND_IP}:${PORT}/kindle_btc_price.png" -o /tmp/kindle-btc-display-install-proof.png || die "PNG fetch failed"
file /tmp/kindle-btc-display-install-proof.png 2>/dev/null || true

echo
echo "INSTALL=GREEN"
echo "URL=http://${HOST_BIND_IP}:${PORT}/"
echo "CRON_FILE=$CRON_FILE"
if [ -n "$ARCHIVE" ]; then
  echo "ROLLBACK_ARCHIVE=$ARCHIVE"
fi
