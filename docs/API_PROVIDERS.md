# API Providers

The application uses public provider endpoints and conservative cache intervals. Provider availability, policies, and rate limits can change over time; the software treats individual provider failures as recoverable whenever another provider or last-known-good cache data is available.

## BTC main block

Live attempts can use CoinGecko, CryptoCompare, CoinPaprika, Binance, and Kraken.

## Coin table

Per-symbol price attempts rotate across CoinPaprika, CryptoCompare, Binance, Kraken, and CoinGecko where that asset/quote is supported.

## Candles

The 7-day BTC candle chart currently uses CoinGecko market-chart data, backed by a last-known-good cache.

## ATH

ATH data currently uses CoinGecko market data and the `ath_refresh_hours` TTL.

## CoinGecko `/coins/list`

This endpoint is metadata only. It is skipped when every configured coin includes an explicit CoinGecko ID.
