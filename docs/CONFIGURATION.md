# Configuration

The installer creates live runtime files from the tracked `.example` files. Live files are intentionally excluded from Git.

## `.env`

`HOST_BIND_IP`
: IPv4 address on the host where TCP 8787 is published. The installer auto-detects a LAN address. Set it explicitly before installation when auto-detection is not appropriate.

`APP_TZ`
: IANA timezone used for rendered timestamps, for example `UTC` or another IANA timezone of your choice.

## `config/extras.config`

`price_refresh_minutes=10`
: Cache TTL for BTC main price, MXN conversion, 24-hour change, and configured coin-table prices.

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

`usd_mxn_fallback_rate=16.92`
: Fallback USD→MXN multiplier used only when a price provider returns USD but does not provide MXN directly. It is a fallback constant, not a live FX quote.

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
