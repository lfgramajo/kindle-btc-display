# Technical Manual

## Architecture

Kindle Bitcoin Price Display is a small Python HTTP service that renders a single 800×600 grayscale PNG and serves it through explicit routes. Docker provides dependency isolation and a constrained runtime. A host cron trigger wakes the app every 10 minutes; cache TTLs determine whether provider calls are needed.

```text
Host cron
   │
   └── GET /refresh every 10 min
            │
            ├── prices cache ── provider fallback
            ├── candles cache ─ CoinGecko + last-good fallback
            ├── ATH cache ───── CoinGecko + last-good fallback
            └── atomic PNG render
                        │
                        └── Kindle/browser GET /kindle_btc_price.png
```

## Runtime files

```text
config/coins.config
config/extras.config
config/weather.conf
config/cache/prices.json
config/cache/candles.json
config/cache/ath.json
config/cache/coingecko_coin_list.json
config/cache/status.json
config/cache/price_api_index.json
config/cache/refresh.lock
output/kindle_btc_price.png
logs/
```

None of these mutable runtime files belong in the public repository except the three `.example` configs.

## Scheduling

Public installs use host cron and set `internal_scheduler=off`. The cron trigger is intentionally simple: it calls `/refresh`; the application then decides whether each cache is stale.

Default timing:

- host cron trigger: every 10 minutes
- `price_refresh_minutes`: 10
- `candles_refresh_minutes`: 10
- `ath_refresh_hours`: 12
- `page_refresh_minutes`: 11

This keeps the scheduler independent from provider logic and prevents a failed provider call from destroying the last-good rendered state.

## Configuration reference

Every public configuration value is documented in [CONFIGURATION.md](CONFIGURATION.md), including `.env`, `extras.config`, `coins.config`, `weather.conf`, and the host cron relationship.

## BTC main-price fallback

The main BTC block is no longer CoinGecko-only. Live attempts can use:

```text
CoinGecko → CryptoCompare → CoinPaprika → Binance → Kraken
```

A successful provider supplies the main BTC value. If live calls fail and a prior main-price cache exists, the application renders the stale cache rather than immediately blanking the display.

## Coin-table fallback

Coin-table price providers are rotated per symbol and may include:

```text
CoinPaprika → CryptoCompare → Binance → Kraken → CoinGecko
```

Provider support varies by asset; unsupported combinations fall forward to the next provider.

## Candles

The 7-day BTC chart currently uses CoinGecko market-chart data. If the live candle request fails, the last-known-good candle cache is retained.

## ATH

ATH data uses CoinGecko per-coin market data and the configurable `ath_refresh_hours` TTL. Cached ATH values remain available if a refresh fails.

## CoinGecko coin-list optimization

`/coins/list` is metadata, not price data. The application downloads it only when at least one configured coin lacks an explicit CoinGecko ID. When every coin has an ID, the request is skipped entirely.

## Refresh locking

A process lock and `fcntl` file lock at `config/cache/refresh.lock` prevent overlapping refresh work. A concurrent request receives a conflict response rather than running a second provider cycle.

## Atomic PNG writes

Rendering writes to a temporary PNG and uses an atomic filesystem replacement for the final output. The web server therefore never intentionally serves a half-written image.

## HTTP endpoints

`/`
: Minimal HTML wrapper with configurable meta-refresh.

`/kindle_btc_price.png`
: Current rendered PNG.

`/refresh`
: Cache-aware refresh.

`/refresh?force=1`
: Forces live provider attempts regardless of cache age.

`/healthz`
: Lightweight liveness endpoint.

`/status.json`
: Last refresh/provider/cache diagnostics.

## Docker security

The default compose deployment runs as UID/GID 10001, uses a read-only root filesystem, drops all Linux capabilities, enables `no-new-privileges`, limits resources, and does not mount the Docker socket. Mutable config/cache, logs, and output are explicit host bind mounts.

## Networking

The container listens on `0.0.0.0:8787` internally. Docker publishes that port only on `HOST_BIND_IP`. The installer chooses a host IPv4 address and writes it to `.env`.

The application is intentionally unauthenticated and is therefore a LAN-only service.

## Upgrade behavior

The installer prebuilds the candidate image before stopping the current Kindle container. If an existing `/opt/kindle-btc-display` is present, it is moved to a timestamped archive under `/opt/kindle-btc-display-archive/`. Live config/cache and the last rendered PNG are restored into the new application root. No global Docker prune is used.

## Tests

The repository unit tests cover formatting, config parsing, cache freshness, CoinGecko list skip logic, and PNG rendering. CI also performs Python syntax checks, shell syntax checks, an OPSEC sentinel scan, and a Docker build.
