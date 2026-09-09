# Kindle Bitcoin Price Display

## The Oracle on Paper

A forgotten Kindle sits on a desk. Every few minutes, it wakes just enough to ask the markets a few simple questions:

**What is Bitcoin worth? How far are we from the all-time high? What has the last week looked like?**

No exchange app. No notifications. No doomscrolling. Just a quiet 800×600 e-ink dashboard built to stay useful for months at a time.

The functional core behind this public release was field-tested in daily use for more than a month before the repository was prepared for publication.

## What it shows

- BTC/USD and BTC/MXN
- 24-hour BTC change
- 7-day BTC candlestick chart
- Bitcoin ATH
- Top-five non-stablecoin altcoin price/ATH table by default (configurable)
- Optional weather module
- Last-known-good data when a provider temporarily fails

## Why an old Kindle?

E-ink is calm, readable, low-power, and perfect for information that should be present without demanding attention. This project turns an otherwise retired Kindle into a small market instrument for the desk.

## Quick install

### Requirements

- Debian/Ubuntu-style Linux host
- Docker Engine with Docker Compose v2
- `curl`
- `cron`
- A Kindle or browser on the same LAN

```bash
git clone https://github.com/YOUR-ACCOUNT/kindle-btc-display.git
cd kindle-btc-display
./install.sh
```

The installer:

1. builds the image before touching an existing installation,
2. binds the service to a detected LAN IPv4 address,
3. creates runtime config from `.example` files,
4. starts a hardened non-root Docker container,
5. installs a host cron refresh trigger every 10 minutes, and
6. waits for `/healthz` before declaring the install GREEN.

It never performs a global Docker prune and only targets the `kindle-btc-display` application.

At completion it prints the URL, for example:

```text
http://YOUR_LAN_IP:8787/
```

## Refresh model

The host cron job calls `/refresh` every 10 minutes. The app then checks its cache TTLs before making network requests. Defaults:

```ini
price_refresh_minutes=10
candles_refresh_minutes=10
ath_refresh_hours=12
page_refresh_minutes=11
internal_scheduler=off
coins=on
weather=off
```

CoinGecko `/coins/list` is skipped when every configured coin already has an explicit CoinGecko ID.

## Provider resilience

BTC main pricing is not CoinGecko-only. The application can fall through multiple public providers and retains last-known-good cache data if live calls fail. The current 7-day candle source is CoinGecko with cache fallback.

## Endpoints

```text
/                         HTML wrapper
/kindle_btc_price.png      rendered 800×600 PNG
/refresh                   cache-aware refresh
/refresh?force=1           force live provider attempts
/healthz                   liveness check
/status.json               cache/provider diagnostics
```

## Configuration

- `config/extras.config` — refresh timing and optional modules
- `config/coins.config` — displayed altcoins and explicit CoinGecko IDs
- `config/weather.conf` — optional weather API credentials
- `.env` — LAN bind address and application timezone

See [Configuration](docs/CONFIGURATION.md) and the [Technical Manual](docs/TECHNICAL.md).

## Kindle setup

See [Kindle Setup](docs/KINDLE_SETUP.md).

## Security

**LAN only by design.** Do not expose port 8787 directly to the public internet. No API secrets are required for the default Bitcoin display. Weather credentials are optional and must remain in the untracked runtime `config/weather.conf`.

See [SECURITY.md](SECURITY.md).

## Troubleshooting

See [Troubleshooting](docs/TROUBLESHOOTING.md).

## License

MIT. See [LICENSE](LICENSE).
