# Kindle Bitcoin Price Display

## The Oracle on Paper

A forgotten Kindle sits on a desk. Every few minutes, it wakes just enough to ask the markets a few simple questions:

**What is Bitcoin worth? How far are we from the all-time high? What has the last week looked like?**

No exchange app. No notifications. No doomscrolling. Just a quiet 800×600 e-ink dashboard built to stay useful for months at a time.

The functional core behind this public release was field-tested in daily use for more than a month before the repository was prepared for publication.

## What it shows

- BTC/USD plus a configurable secondary fiat price, MXN by default
- 47 supported fiat codes in v1.7.0
- 24-hour BTC change
- 7-day BTC candlestick chart
- Bitcoin ATH
- Top-five non-stablecoin altcoin price/ATH table by default, configurable
- Optional weather module
- Last-known-good data when a provider temporarily fails

## Why an old Kindle?

E-ink is calm, readable, low-power, and useful for information that should be present without demanding attention. This project turns an otherwise retired Kindle into a small market instrument for the desk.

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

1. builds the Docker image before touching an existing installation,
2. detects the host LAN IPv4 address unless `HOST_BIND_IP` is provided,
3. creates runtime configuration from the tracked `.example` files,
4. starts a hardened non-root Docker container,
5. installs a host cron refresh trigger every 10 minutes,
6. waits for `/healthz` before declaring the install GREEN.

It never performs a global Docker prune and only targets the `kindle-btc-display` application.

At completion it prints the URL, for example:

```text
http://YOUR_LAN_IP:8787/
```

## HTTP server

No separate Apache, Nginx, Flask, Gunicorn, or other web server needs to be installed.

The HTTP service is built into `app.py` using Python's standard-library `ThreadingHTTPServer`. The Dockerfile starts it automatically with:

```text
python /app/app.py
```

Inside the container it listens on `0.0.0.0:8787`. Docker publishes port 8787 only on the host address selected by the installer and stored in `.env`.

The installer handles the complete server startup through Docker Compose. A normal installation does not require manually starting Python or configuring a separate HTTP daemon.

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

The primary Bitcoin price is always shown in USD. The second Bitcoin price is configured with `secondary_fiat` in `config/extras.config`. The release default is `MXN`.

```ini
secondary_fiat=MXN
```

The application validates the selected code against the release-supported set. Unsupported codes fail validation instead of silently being relabeled.

### Supported fiat currencies in v1.7.0

| Code | Currency | Country / issuing region |
| --- | --- | --- |
| AED | United Arab Emirates dirham | United Arab Emirates |
| ARS | Argentine peso | Argentina |
| AUD | Australian dollar | Australia |
| BDT | Bangladeshi taka | Bangladesh |
| BHD | Bahraini dinar | Bahrain |
| BMD | Bermudian dollar | Bermuda |
| BRL | Brazilian real | Brazil |
| CAD | Canadian dollar | Canada |
| CHF | Swiss franc | Switzerland and Liechtenstein |
| CLP | Chilean peso | Chile |
| CNY | Chinese yuan, renminbi | China |
| CZK | Czech koruna | Czech Republic |
| DKK | Danish krone | Denmark |
| EUR | Euro | Euro area, European Union |
| GBP | Pound sterling | United Kingdom |
| GEL | Georgian lari | Georgia |
| GTQ | Guatemalan quetzal | Guatemala |
| HKD | Hong Kong dollar | Hong Kong |
| HUF | Hungarian forint | Hungary |
| IDR | Indonesian rupiah | Indonesia |
| ILS | Israeli new shekel | Israel |
| INR | Indian rupee | India |
| JPY | Japanese yen | Japan |
| KRW | South Korean won | South Korea |
| KWD | Kuwaiti dinar | Kuwait |
| LKR | Sri Lankan rupee | Sri Lanka |
| MMK | Myanmar kyat | Myanmar |
| MXN | Mexican peso | Mexico |
| MYR | Malaysian ringgit | Malaysia |
| NGN | Nigerian naira | Nigeria |
| NOK | Norwegian krone | Norway |
| NZD | New Zealand dollar | New Zealand |
| PHP | Philippine peso | Philippines |
| PKR | Pakistani rupee | Pakistan |
| PLN | Polish złoty | Poland |
| RUB | Russian ruble | Russia |
| SAR | Saudi riyal | Saudi Arabia |
| SEK | Swedish krona | Sweden |
| SGD | Singapore dollar | Singapore |
| THB | Thai baht | Thailand |
| TRY | Turkish lira | Türkiye |
| TWD | New Taiwan dollar | Taiwan |
| UAH | Ukrainian hryvnia | Ukraine |
| USD | United States dollar | United States |
| VEF | Venezuelan bolívar fuerte, legacy code | Venezuela |
| VND | Vietnamese đồng | Vietnam |
| ZAR | South African rand | South Africa |

CoinGecko's API changelog historically added Guatemala (`GTQ`), but its current `supported_vs_currencies` response does not return GTQ. v1.7.0 therefore uses CoinGecko directly if it supplies GTQ and otherwise combines the live BTC/USD price with Banco de Guatemala's official USD/GTQ reference rate. CoinGecko's supported-currencies reference also exposes `VEF`; v1.7.0 retains that legacy Venezuelan code for provider compatibility.

Former-G8 currency examples, today the G7 plus Russia: `CAD`, `GBP`, `EUR`, `JPY`, and `RUB`; the primary line already displays `USD`.

Currencies corresponding to the 2025 Chainalysis top-10 crypto-adoption markets: `INR`, `USD`, `PKR`, `VND`, `BRL`, `NGN`, `IDR`, `UAH`, `PHP`, and `RUB`. This is an adoption ranking, not a Bitcoin-only trading-volume ranking.

The release-supported list intentionally contains fiat codes only. CoinGecko's broader `supported_vs_currencies` endpoint also exposes non-fiat quote units, which are not enabled as `secondary_fiat` values in v1.7.0.

See [Configuration](docs/CONFIGURATION.md) for provider and cache behavior.

References: [CoinGecko supported currencies](https://docs.coingecko.com/reference/simple-supported-currencies), [CoinGecko changelog entry listing GTQ](https://docs.coingecko.com/changelog/10122018), [Banco de Guatemala TipoCambioDia Web Service](https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?op=TipoCambioDia), and [Chainalysis 2025 Global Crypto Adoption Index](https://www.chainalysis.com/blog/2025-global-crypto-adoption-index/).

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

## Repository scope

The public repository is intentionally limited to files needed to install, run, configure, understand, secure, and troubleshoot the application. Private QA evidence, release-engineering tests, CI scaffolding, release manifests, and internal release-process documents are not part of the public runtime repository.

## License

MIT. See [LICENSE](LICENSE).
