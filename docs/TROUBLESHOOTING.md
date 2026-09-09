# Troubleshooting

## Container status

```bash
cd /opt/kindle-btc-display
sudo docker compose ps
sudo docker logs --tail=160 kindle-btc-display
```

## Endpoints

```bash
curl -fsS http://YOUR_LAN_IP:8787/healthz
curl -fsS http://YOUR_LAN_IP:8787/status.json
curl -fsS http://YOUR_LAN_IP:8787/kindle_btc_price.png -o /tmp/kindle.png
file /tmp/kindle.png
```

## Host cron

```bash
sudo cat /etc/cron.d/kindle-btc-display-refresh
systemctl status cron --no-pager
tail -n 80 /opt/kindle-btc-display/logs/cron-refresh.log
```

On distributions that use `crond.service`, check that service instead of `cron.service`.

## Force a provider refresh

```bash
curl -fsS 'http://YOUR_LAN_IP:8787/refresh?force=1'
```

Use forced refreshes sparingly because they deliberately bypass normal cache age checks.

## `N/A` values

A main BTC `N/A` means no usable live main-price result was available and no usable last-good main-price cache existed. Check `/status.json` and recent container logs to see which providers were attempted.

## CoinGecko rate limits

The default configuration reduces API pressure by caching price/candle/ATH data and skipping `/coins/list` when CoinGecko IDs are explicit. If a provider throttles requests, allow the cache to carry the display rather than repeatedly using `force=1`.

## Port 8787

If installation cannot bind port 8787, check what already owns the port before changing the compose file:

```bash
sudo ss -ltnp | grep ':8787'
```
