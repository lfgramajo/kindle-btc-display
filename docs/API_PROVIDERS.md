# API Providers

The application uses public provider endpoints and conservative cache intervals. Provider availability, policies, and rate limits can change over time; the software treats individual provider failures as recoverable whenever another provider or last-known-good cache data is available.

## BTC main block

The BTC main block has an explicit fallback chain for the primary USD price and 24-hour movement:

1. CoinGecko
2. CryptoCompare
3. CoinPaprika
4. Binance
5. Kraken

This path is failover, not round-robin. Each fresh BTC-main network attempt starts with CoinGecko. If that provider does not produce a usable result for the requested display, the application tries the next provider in order and continues until one succeeds. If no provider can produce a usable live value, the application falls back to matching last-known-good cache data when available.

The configurable `secondary_fiat` path normally uses CoinGecko. CoinGecko's `/simple/price` request asks for USD plus the configured supported fiat code. For `GTQ`, CoinGecko is attempted first; if it returns USD but no GTQ value, the application fetches Banco de Guatemala's official `TipoCambioDia` USD/GTQ reference rate and converts the live BTC/USD value. The existing CryptoCompare/MXN path and the user-editable static MXN fallback are retained only for `secondary_fiat=MXN`; v1.7.0 does not assume undocumented arbitrary-fiat support from the other providers. If a secondary-fiat request cannot be refreshed, a matching last-known-good secondary cache may be retained. A cache for one fiat is never relabeled as another.

## Coin table

Per-symbol coin prices use a persistent round-robin rotation in this order:

1. CoinPaprika
2. CryptoCompare
3. Binance
4. Kraken
5. CoinGecko

The first run for a symbol may begin at any point in that rotation. After a provider succeeds, the application saves the next provider as that symbol's starting point for the following refresh. If the starting provider fails, the application immediately tries the next provider, then the next, wrapping around the list until a live price is found or all five have been attempted.

Example: if a symbol starts with CryptoCompare and CryptoCompare fails, the sequence is Binance, Kraken, CoinGecko, then CoinPaprika. If Binance succeeds, that symbol starts with Kraken on its next network refresh. The saved per-symbol rotation state survives refreshes through the application's price-provider index cache.

If all five providers fail for a coin, the application uses that coin's last-known-good cached price when available rather than replacing a valid prior value with `N/A`.

## Candles

The 7-day BTC candle chart currently uses CoinGecko market-chart data, backed by a last-known-good cache.

## ATH

ATH data currently uses CoinGecko market data and the `ath_refresh_hours` TTL.

## CoinGecko `/coins/list`

This endpoint is metadata only. It is skipped when every configured coin includes an explicit CoinGecko ID.
