# Configuration

The installer creates live runtime files from the tracked `.example` files. Live files are intentionally excluded from Git.

## `.env`

`HOST_BIND_IP`
: IPv4 address on the host where TCP 8787 is published. The installer auto-detects a LAN address. Set it explicitly before installation when auto-detection is not appropriate.

`APP_TZ`
: IANA timezone used for rendered timestamps, for example `UTC` or another IANA timezone of your choice.

## `config/extras.config`

`price_refresh_minutes=10`
: Cache TTL for BTC main USD price, the configured secondary fiat price, 24-hour change, and configured coin-table prices.

`candles_refresh_minutes=10`
: Cache TTL for the 7-day BTC market data used to draw candlesticks.

`ath_refresh_hours=12`
: Cache TTL for BTC and configured-coin all-time-high data.

`page_refresh_minutes=11`
: HTML meta-refresh interval for the Kindle/browser page. Eleven minutes intentionally trails the default 10-minute backend cron trigger.

`internal_scheduler=off`
: Enables/disables the app's in-process scheduler. Public installs default to `off` because host cron owns the refresh trigger. Do not enable both scheduling paths unless you deliberately want both; cache freshness still limits network calls.

`scheduler_check_seconds=60`
: Wake interval for the in-process scheduler when `internal_scheduler=on`. It has no scheduling effect while the internal scheduler is off.

`secondary_fiat=MXN`
: Three-letter fiat code for the second Bitcoin price. `MXN` is the release default. A change in this value invalidates the currency identity of the cached secondary price, so an older MXN cache cannot be displayed under a different label. Unsupported codes fail validation rather than silently falling back to another currency.

Release-supported fiat codes:

```text
AED ARS AUD BDT BHD BMD BRL CAD CHF CLP CNY CZK DKK EUR GBP GEL HKD HUF
IDR ILS INR JPY KRW KWD LKR MMK MXN MYR NGN NOK NZD PHP PKR PLN RUB SAR
SEK SGD THB TRY TWD UAH USD VEF VND ZAR
```

Former-G8 examples (today the G7 plus Russia): `CAD`, `GBP`, `EUR`, `JPY`, `RUB`; the primary line already displays `USD`.

Currencies corresponding to the 2025 Chainalysis top-10 crypto-adoption markets: `INR`, `USD`, `PKR`, `VND`, `BRL`, `NGN`, `IDR`, `UAH`, `PHP`, `RUB`. This is an adoption ranking, not a Bitcoin-only volume ranking.

`usd_mxn_fallback_rate=16.92`
: Legacy USD→MXN fallback used only when `secondary_fiat=MXN` and a fallback provider gives USD but no MXN price. It is a user-editable constant, not a live FX quote, and is never applied to EUR, GBP, JPY, or any other selected fiat.

`coins=on`
: Shows/hides the configured coin table.

`weather=off`
: Enables/disables weather. When `off`, no weather provider is queried.

## `config/coins.config`

One coin per line:

```text
SYMBOL,coingecko_id,QUOTE
```

Example:

```text
ETH,ethereum,USD
BNB,binancecoin,USD
XRP,ripple,USD
SOL,solana,USD
TRX,tron,USD
```

Keep `coingecko_id` explicit. If every configured coin has an ID, the application skips CoinGecko `/coins/list`.

Lines may contain `#` comments.

## `config/weather.conf`

`city`
: Location string sent to the enabled weather provider.

`openweather_key`
: Optional OpenWeatherMap API key. Leave empty if unused.

`weatherapi_key`
: Optional WeatherAPI key. Leave empty if unused.

Weather is disabled by default, and these keys are not required for the Bitcoin display.

## Host cron

The installer writes:

```text
/etc/cron.d/kindle-btc-display-refresh
```

The default trigger fires at minute `0,10,20,30,40,50` of every hour and calls `/refresh`. The cache TTL values above decide whether each trigger performs live provider calls.

If you configure a price or candle TTL below 10 minutes, either adjust the host cron cadence accordingly or deliberately enable the internal scheduler.
