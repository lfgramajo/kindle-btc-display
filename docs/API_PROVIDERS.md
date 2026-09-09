# API Providers

The application uses public provider endpoints and conservative cache intervals. Provider availability, policies, and rate limits can change over time; the software treats individual provider failures as recoverable whenever another provider or last-known-good cache data is available.

## BTC main block

Live attempts can use CoinGecko, CryptoCompare, CoinPaprika, Binance, and Kraken for the primary USD price and 24-hour movement.

The configurable `secondary_fiat` path is authoritative through CoinGecko in v1.7.0-rc3. CoinGecko's `/simple/price` request asks for USD plus the configured supported fiat code. The existing CryptoCompare/MXN path and the user-editable static MXN fallback are retained only for `secondary_fiat=MXN`; RC3 does not assume undocumented arbitrary-fiat support from the other providers. If a non-MXN secondary-fiat request cannot be refreshed, a matching last-known-good secondary cache may be retained. A cache for one fiat is never relabeled as another.

## Coin table

Per-symbol price attempts rotate across CoinPaprika, CryptoCompare, Binance, Kraken, and CoinGecko where that asset/quote is supported.

## Candles

The 7-day BTC candle chart currently uses CoinGecko market-chart data, backed by a last-known-good cache.

## ATH

ATH data currently uses CoinGecko market data and the `ath_refresh_hours` TTL.

## CoinGecko `/coins/list`

This endpoint is metadata only. It is skipped when every configured coin includes an explicit CoinGecko ID.
