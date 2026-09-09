# Kindle Bitcoin Price Display

## The Oracle on Paper

A forgotten Kindle sits on a desk. Every few minutes, it wakes just enough to ask the markets a few simple questions:

**What is Bitcoin worth? How far are we from the all-time high? What has the last week looked like?**

No exchange app. No notifications. No doomscrolling. Just a quiet 800×600 e-ink dashboard built to stay useful for months at a time.

The functional core behind this public release was field-tested in daily use for more than a month before the repository was prepared for publication.

## What it shows

- BTC/USD plus a configurable secondary fiat price (MXN by default, 46 fiat codes supported in v1.7.0)
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
git clone https://github.com/lfgramajo/kindle-btc-display.git
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
secondary_fiat=MXN
coins=on
weather=off
```

CoinGecko `/coins/list` is skipped when every configured coin already has an explicit CoinGecko ID.

## Choose your fiat currency

The primary Bitcoin price is always shown in USD. The second Bitcoin price is configurable with `secondary_fiat` in `config/extras.config`; the release default is `MXN`. The selected code must be one of the fiat currencies supported by the application and CoinGecko.

```ini
secondary_fiat=MXN
```

### Supported fiat currencies in v1.7.0

The complete release-supported set is:

```text
AED ARS AUD BDT BHD BMD BRL CAD CHF CLP CNY CZK DKK EUR GBP GEL HKD HUF
IDR ILS INR JPY KRW KWD LKR MMK MXN MYR NGN NOK NZD PHP PKR PLN RUB SAR
SEK SGD THB TRY TWD UAH USD VEF VND ZAR
```

That is 46 fiat codes. The application validates `secondary_fiat` against this exact set, so unsupported codes fail clearly instead of being silently relabeled.

Former-G8 currency examples (today the G7 plus Russia): `CAD`, `GBP`, `EUR`, `JPY`, and `RUB`; the primary line already displays `USD`.

Currencies corresponding to the 2025 Chainalysis top-10 crypto-adoption markets: `INR`, `USD`, `PKR`, `VND`, `BRL`, `NGN`, `IDR`, `UAH`, `PHP`, and `RUB`. This is an adoption ranking, not a Bitcoin-only trading-volume ranking.

The release-supported list intentionally contains fiat codes only. CoinGecko's broader `supported_vs_currencies` endpoint also exposes non-fiat quote units, which are not enabled as `secondary_fiat` values in v1.7.0.

See [Configuration](docs/CONFIGURATION.md) for provider and cache behavior.

References: [CoinGecko supported currencies](https://docs.coingecko.com/reference/simple-supported-currencies) and [Chainalysis 2025 Global Crypto Adoption Index](https://www.chainalysis.com/blog/2025-global-crypto-adoption-index/).

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

- `config/extras.config`: refresh timing and optional modules
- `config/coins.config`: displayed altcoins and explicit CoinGecko IDs
- `config/weather.conf`: optional weather API credentials
- `.env`: LAN bind address and application timezone

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
