#!/usr/bin/env python3
"""Kindle Bitcoin Price Display — v1.7.0 public release.

Public-release reliability goals:
- Config-driven refresh intervals with comments in extras.config.
- Price/candle/ATH caches with last-known-good rendering.
- CoinGecko coin-list cache only when configured coin IDs are missing.
- BTC main price uses provider fallback instead of CoinGecko-only failure.
- Explicit /status.json diagnostics endpoint.
- Refresh lock to prevent overlapping refreshes.
- Atomic PNG writes so the Kindle never reads a half-written image.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import mimetypes
import os
import random
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytz
import requests
from PIL import Image, ImageDraw, ImageFont

VERSION = "1.7.0"
APP_NAME = "kindle-btc-display"
USER_AGENT = f"{APP_NAME}/{VERSION}"

# === Paths and Constants ===
BASE_DIR = Path(os.environ.get("APP_BASE_DIR", "/app"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", str(BASE_DIR / "config")))
LOGS_DIR = Path(os.environ.get("LOGS_DIR", str(BASE_DIR / "logs")))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(BASE_DIR / "output")))
CACHE_DIR = CONFIG_DIR / "cache"

OUTPUT_FILE = OUTPUT_DIR / "kindle_btc_price.png"
PRICE_CACHE_FILE = CACHE_DIR / "prices.json"
CANDLES_CACHE_FILE = CACHE_DIR / "candles.json"
ATH_CACHE_FILE = CACHE_DIR / "ath.json"
COINGECKO_LIST_CACHE_FILE = CACHE_DIR / "coingecko_coin_list.json"
STATUS_FILE = CACHE_DIR / "status.json"
PRICE_API_IDX_FILE = CACHE_DIR / "price_api_index.json"
REFRESH_LOCK_FILE = CACHE_DIR / "refresh.lock"

COINS_CONFIG_PATH = CONFIG_DIR / "coins.config"
WEATHER_CONF_PATH = CONFIG_DIR / "weather.conf"
EXTRAS_CONF_PATH = CONFIG_DIR / "extras.config"
ROUNDROBIN_FILE = CACHE_DIR / "weather_roundrobin.txt"

WIDTH, HEIGHT = 800, 600
FONT_PATH = os.environ.get("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_SIZE_MAIN = 64
FONT_SIZE_MED = 36
FONT_SIZE_SMALL = 28
FONT_SIZE_TINY = 18
TZ = pytz.timezone(os.environ.get("APP_TZ", "UTC"))

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINPAPRIKA_BASE = "https://api.coinpaprika.com/v1"
CRYPTOCOMPARE_BASE = "https://min-api.cryptocompare.com/data"
BINANCE_BASE = "https://api.binance.com"
KRAKEN_BASE = "https://api.kraken.com/0/public"
BANGUAT_EXCHANGE_RATE_URL = "https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx"

DEFAULT_EXTRAS = """# Kindle Bitcoin Price Display runtime config
#
# Timing values are configurable so API cadence and Kindle refresh behavior can
# be tuned without editing app.py.

# Fetch live BTC main price, configurable secondary fiat, 24h change, and coin table prices.
# Recommended: 10 minutes. Lower values increase API pressure.
price_refresh_minutes=10

# Fetch 7-day BTC market chart and rebuild the candlestick chart.
# Recommended: 10 minutes so the chart stays aligned with the displayed price.
candles_refresh_minutes=10

# Fetch all-time high data for every configured coin.
# Recommended: 12 hours. ATH changes rarely and this avoids heavy API usage.
ath_refresh_hours=12

# Refresh the browser/Kindle HTML page.
# Recommended: 11 minutes so the backend usually refreshes first.
page_refresh_minutes=11

# Internal scheduler checks caches and refreshes stale data.
# Public Docker installs use a host cron trigger every 10 minutes, so keep this off
# to avoid duplicate schedulers. Advanced standalone users may turn it on.
internal_scheduler=off
scheduler_check_seconds=60

# Secondary BTC fiat shown below USD. Must be a supported three-letter fiat code.
secondary_fiat=MXN

# Legacy MXN-only fallback conversion used only when secondary_fiat=MXN and a
# fallback provider gives USD but not MXN. It is never applied to other fiat.
usd_mxn_fallback_rate=16.92

# Optional modules.
coins=on
weather=off
"""

DEFAULTS: dict[str, Any] = {
    "weather.conf": "city=\nopenweather_key=\nweatherapi_key=\n",
    "extras.config": DEFAULT_EXTRAS,
    "coins.config": "# Format: SYMBOL,coingecko_id,QUOTE\n# Default release set: top five non-stablecoin altcoins by market cap at release.\n# Edit this file to choose a different set. Explicit CoinGecko IDs avoid /coins/list.\nETH,ethereum,USD\nBNB,binancecoin,USD\nXRP,ripple,USD\nSOL,solana,USD\nTRX,tron,USD\n",
}

SUPPORTED_SECONDARY_FIATS = {
    "AED", "ARS", "AUD", "BDT", "BHD", "BMD", "BRL", "CAD", "CHF", "CLP",
    "CNY", "CZK", "DKK", "EUR", "GBP", "GEL", "GTQ", "HKD", "HUF", "IDR", "ILS",
    "INR", "JPY", "KRW", "KWD", "LKR", "MMK", "MXN", "MYR", "NGN", "NOK",
    "NZD", "PHP", "PKR", "PLN", "RUB", "SAR", "SEK", "SGD", "THB", "TRY",
    "TWD", "UAH", "USD", "VEF", "VND", "ZAR",
}

PRICE_APIS = ["coinpaprika", "cryptocompare", "binance", "kraken", "coingecko"]
THREAD_LOCK = threading.Lock()

COINPAPRIKA_IDS = {
    "BTC": "btc-bitcoin",
    "ETH": "eth-ethereum",
    "BNB": "bnb-binance-coin",
    "SOL": "sol-solana",
    "XRP": "xrp-xrp",
    "TRX": "trx-tron",
    "AERO": "aero-aerodrome-finance",
}
BINANCE_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
    "TRX": "TRXUSDT",
}
KRAKEN_SYMBOLS = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "BNB": "BNBUSD",
    "SOL": "SOLUSD",
    "XRP": "XRPUSD",
}


def now_ts() -> float:
    return time.time()


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def ensure_dirs_and_files() -> None:
    for d in [CONFIG_DIR, LOGS_DIR, OUTPUT_DIR, CACHE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    for fname, content in DEFAULTS.items():
        fpath = CONFIG_DIR / fname
        if not fpath.exists():
            fpath.write_text(str(content), encoding="utf-8")


def log_event(msg: str) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        logfile = LOGS_DIR / f"btc_dashboard_{datetime.now(TZ).strftime('%Y-%m-%d')}.log"
        with logfile.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} | {msg}\n")
    except Exception:
        print(f"LOG_FALLBACK | {msg}", flush=True)


def parse_config_lines(path: Path) -> list[str]:
    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0]
                l = line.strip()
                if l:
                    lines.append(l)
    except FileNotFoundError:
        return []
    except Exception as e:
        log_event(f"Error parsing config {path}: {e}")
    return lines


def parse_key_value_config(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in parse_config_lines(path):
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def boolish(value: str, default: bool) -> bool:
    if value == "":
        return default
    return value.strip().lower() not in {"off", "0", "false", "no", "disabled"}


def read_int(raw: str | None, default: int, min_value: int) -> int:
    try:
        return max(min_value, int(str(raw).strip()))
    except Exception:
        return default


def read_float(raw: str | None, default: float, min_value: float) -> float:
    try:
        return max(min_value, float(str(raw).strip()))
    except Exception:
        return default


def normalize_secondary_fiat(raw: str | None) -> str:
    code = (raw or "MXN").strip().upper()
    if code not in SUPPORTED_SECONDARY_FIATS:
        raise ValueError(f"unsupported secondary_fiat={code!r}; choose a supported fiat code")
    return code


def read_extras_conf() -> dict[str, Any]:
    raw = parse_key_value_config(EXTRAS_CONF_PATH)
    # Backward compatibility with v1.6.2 refresh_seconds.
    legacy_refresh_minutes = None
    if "refresh_seconds" in raw:
        legacy_refresh_minutes = max(1, int(read_int(raw.get("refresh_seconds"), 600, 60) / 60))
    return {
        "weather_on": boolish(raw.get("weather", "off"), False),
        "coins_on": boolish(raw.get("coins", "on"), True),
        "price_refresh_minutes": read_int(raw.get("price_refresh_minutes"), legacy_refresh_minutes or 10, 1),
        "candles_refresh_minutes": read_int(raw.get("candles_refresh_minutes"), legacy_refresh_minutes or 10, 1),
        "ath_refresh_hours": read_int(raw.get("ath_refresh_hours"), 12, 1),
        "page_refresh_minutes": read_int(raw.get("page_refresh_minutes"), 11, 1),
        "internal_scheduler": boolish(raw.get("internal_scheduler", "off"), False),
        "scheduler_check_seconds": read_int(raw.get("scheduler_check_seconds"), 60, 30),
        "secondary_fiat": normalize_secondary_fiat(raw.get("secondary_fiat")),
        "usd_mxn_fallback_rate": read_float(raw.get("usd_mxn_fallback_rate"), 16.92, 0.01),
    }


def read_coins_conf() -> list[dict[str, str | None]]:
    coins: list[dict[str, str | None]] = []
    for raw in parse_config_lines(COINS_CONFIG_PATH):
        parts = [x.strip() for x in raw.split(",")]
        if len(parts) == 1:
            coins.append({"symbol": parts[0].upper(), "id": None, "quote": "USD"})
        elif len(parts) == 2:
            coins.append({"symbol": parts[0].upper(), "id": parts[1] or None, "quote": "USD"})
        elif len(parts) >= 3:
            coins.append({"symbol": parts[0].upper(), "id": parts[1] or None, "quote": parts[2].upper()})
    return coins


def read_weather_conf() -> tuple[str, str, str]:
    raw = parse_key_value_config(WEATHER_CONF_PATH)
    return raw.get("city", ""), raw.get("openweather_key", ""), raw.get("weatherapi_key", "")


def load_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception as e:
        log_event(f"Error loading json from {path}: {e}")
    return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True, indent=2)
        tmp.replace(path)
    except Exception as e:
        log_event(f"Error saving json to {path}: {e}")


def cache_age_seconds(cache: dict[str, Any]) -> float | None:
    ts = cache.get("updated_at") or cache.get("ts")
    try:
        return max(0.0, now_ts() - float(ts))
    except Exception:
        return None


def cache_is_fresh(cache: dict[str, Any], ttl_seconds: int) -> bool:
    age = cache_age_seconds(cache)
    return age is not None and age < ttl_seconds


def request_json(url: str, params: dict[str, Any] | None = None, timeout: int = 10) -> Any:
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.json()


@contextlib.contextmanager
def refresh_file_lock():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with REFRESH_LOCK_FILE.open("w", encoding="utf-8") as lockf:
        try:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("refresh already running") from exc
        lockf.write(f"pid={os.getpid()} ts={now_iso()}\n")
        lockf.flush()
        try:
            yield
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)


def load_price_api_index() -> dict[str, int]:
    raw = load_json(PRICE_API_IDX_FILE)
    return {str(k): int(v) for k, v in raw.items() if str(v).isdigit() or isinstance(v, int)}


def save_price_api_index(idx: dict[str, int]) -> None:
    save_json(PRICE_API_IDX_FILE, idx)


def coin_needs_cg_id(coin: dict[str, str | None]) -> bool:
    return not bool(coin.get("id"))


def needs_coingecko_list(coins: list[dict[str, str | None]]) -> bool:
    return any(coin_needs_cg_id(c) for c in coins)


def get_coingecko_list_if_needed(coins: list[dict[str, str | None]], status: dict[str, Any], force: bool = False) -> list[dict[str, Any]]:
    if not needs_coingecko_list(coins):
        status["coingecko_coin_list"] = {"state": "skipped", "reason": "all configured coins include CoinGecko IDs"}
        return []
    cache = load_json(COINGECKO_LIST_CACHE_FILE)
    if not force and cache_is_fresh(cache, 24 * 3600) and isinstance(cache.get("coins"), list):
        status["coingecko_coin_list"] = {"state": "cache", "age_seconds": int(cache_age_seconds(cache) or 0)}
        return cache.get("coins", [])
    try:
        coins_list = request_json(f"{COINGECKO_BASE}/coins/list", timeout=15)
        if isinstance(coins_list, list):
            save_json(COINGECKO_LIST_CACHE_FILE, {"updated_at": now_ts(), "updated_at_iso": now_iso(), "coins": coins_list})
            status["coingecko_coin_list"] = {"state": "live", "count": len(coins_list)}
            return coins_list
    except Exception as e:
        log_event(f"Error downloading CoinGecko coin list: {e}")
        status["coingecko_coin_list"] = {"state": "error", "error": str(e)}
    if isinstance(cache.get("coins"), list):
        status["coingecko_coin_list"] = {"state": "stale-cache", "age_seconds": int(cache_age_seconds(cache) or 0)}
        return cache.get("coins", [])
    return []


def resolve_coingecko_id(symbol: str, coins_list: list[dict[str, Any]]) -> str | None:
    s = symbol.lower()
    for c in coins_list:
        if c.get("symbol", "").lower() == s:
            return c.get("id")
    for c in coins_list:
        if c.get("id", "").lower() == s:
            return c.get("id")
    return None


def numeric_price(price: Any) -> float | int | None:
    try:
        value = float(price)
        if value <= 0:
            return None
        return int(round(value)) if value > 1 else round(value, 6)
    except Exception:
        return None


def fetch_price_coinpaprika(coin: dict[str, str | None]) -> float | int | None:
    symbol = str(coin["symbol"])
    id_ = COINPAPRIKA_IDS.get(symbol)
    if not id_:
        return None
    try:
        data = request_json(f"{COINPAPRIKA_BASE}/tickers/{id_}", timeout=10)
        quote = str(coin.get("quote") or "USD")
        price = data.get("quotes", {}).get(quote, {}).get("price")
        if price is None and quote == "USD":
            price = data.get("quotes", {}).get("USD", {}).get("price")
        return numeric_price(price)
    except Exception as e:
        log_event(f"CoinPaprika error for {symbol}: {e}")
    return None


def fetch_price_cryptocompare(coin: dict[str, str | None]) -> float | int | None:
    symbol, quote = str(coin["symbol"]), str(coin.get("quote") or "USD")
    try:
        data = request_json(f"{CRYPTOCOMPARE_BASE}/price", params={"fsym": symbol, "tsyms": quote}, timeout=10)
        return numeric_price(data.get(quote))
    except Exception as e:
        log_event(f"CryptoCompare error for {symbol}: {e}")
    return None


def fetch_price_binance(coin: dict[str, str | None]) -> float | int | None:
    symbol = BINANCE_SYMBOLS.get(str(coin["symbol"]))
    if not symbol or str(coin.get("quote") or "USD") != "USD":
        return None
    try:
        data = request_json(f"{BINANCE_BASE}/api/v3/ticker/price", params={"symbol": symbol}, timeout=10)
        return numeric_price(data.get("price"))
    except Exception as e:
        log_event(f"Binance error for {symbol}: {e}")
    return None


def fetch_price_kraken(coin: dict[str, str | None]) -> float | int | None:
    symbol = KRAKEN_SYMBOLS.get(str(coin["symbol"]))
    if not symbol or str(coin.get("quote") or "USD") != "USD":
        return None
    try:
        data = request_json(f"{KRAKEN_BASE}/Ticker", params={"pair": symbol}, timeout=10)
        result = data.get("result")
        if result:
            k = list(result.keys())[0]
            return numeric_price(result[k]["c"][0])
    except Exception as e:
        log_event(f"Kraken error for {symbol}: {e}")
    return None


def fetch_price_coingecko(coin: dict[str, str | None], coins_list: list[dict[str, Any]]) -> float | int | None:
    symbol = str(coin["symbol"])
    cg_id = coin.get("id") or resolve_coingecko_id(symbol, coins_list)
    if not cg_id:
        log_event(f"CoinGecko ID not found for {symbol}")
        return None
    try:
        quote = str(coin.get("quote") or "USD").lower()
        data = request_json(f"{COINGECKO_BASE}/simple/price", params={"ids": cg_id, "vs_currencies": quote}, timeout=10)
        return numeric_price(data.get(cg_id, {}).get(quote))
    except Exception as e:
        log_event(f"CoinGecko error for {symbol}: {e}")
    return None


def fetch_price_unified(coin: dict[str, str | None], coins_list: list[dict[str, Any]], api_idx_map: dict[str, int], provider_status: dict[str, Any]) -> tuple[float | int | str, str]:
    symbol = str(coin["symbol"])
    apis = [
        ("coinpaprika", fetch_price_coinpaprika),
        ("cryptocompare", fetch_price_cryptocompare),
        ("binance", fetch_price_binance),
        ("kraken", fetch_price_kraken),
        ("coingecko", lambda c: fetch_price_coingecko(c, coins_list)),
    ]
    idx = int(api_idx_map.get(symbol, random.randint(0, len(apis) - 1))) % len(apis)
    tried: list[str] = []
    for offset in range(len(apis)):
        name, api_fn = apis[(idx + offset) % len(apis)]
        tried.append(name)
        price = api_fn(coin)
        if price is not None and isinstance(price, (float, int)) and price > 0:
            api_idx_map[symbol] = (idx + offset + 1) % len(apis)
            provider_status[symbol] = {"state": "live", "provider": name, "tried": tried}
            return price, name
    api_idx_map[symbol] = (idx + 1) % len(apis)
    provider_status[symbol] = {"state": "error", "provider": "none", "tried": tried}
    return "N/A", "none"


def fetch_usd_gtq_banguat() -> float | None:
    """Return Banco de Guatemala's current reference GTQ-per-USD rate."""
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><TipoCambioDia xmlns="http://www.banguat.gob.gt/variables/ws/" />'
        '</soap:Body></soap:Envelope>'
    )
    try:
        response = requests.post(
            BANGUAT_EXCHANGE_RATE_URL,
            data=envelope.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "http://www.banguat.gob.gt/variables/ws/TipoCambioDia",
                "User-Agent": USER_AGENT,
            },
            timeout=10,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        references: list[float] = []
        for element in root.iter():
            if element.tag.endswith("referencia") and element.text:
                try:
                    value = float(element.text)
                    if value > 0:
                        references.append(value)
                except ValueError:
                    continue
        if references:
            return references[-1]
        log_event("Banco de Guatemala response did not contain a USD/GTQ reference rate")
    except Exception as e:
        log_event(f"Banco de Guatemala USD/GTQ reference-rate error: {e}")
    return None


def _secondary_from_mxn_fallback(price_usd: float | int | None, config: dict[str, Any]) -> float | int | None:
    if config["secondary_fiat"] != "MXN" or price_usd is None:
        return None
    return numeric_price(float(price_usd) * float(config["usd_mxn_fallback_rate"]))


def _main_result(price_usd, price_secondary, secondary_fiat, change_pct, change_abs, provider):
    result = {
        "price_usd": price_usd,
        "price_secondary": price_secondary if price_secondary is not None else "N/A",
        "secondary_fiat": secondary_fiat,
        "change_pct": change_pct,
        "change_abs": change_abs,
        "provider": provider,
    }
    if result["price_secondary"] not in [None, "N/A"]:
        result["secondary_updated_at"] = now_ts()
    return result


def cached_secondary_fiat(main: dict[str, Any]) -> str | None:
    fiat = main.get("secondary_fiat")
    if fiat:
        return str(fiat).upper()
    if main.get("price_mxn") not in [None, "N/A"]:
        return "MXN"
    return None


def fetch_btc_main_coingecko(config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        secondary = str(config["secondary_fiat"]).lower()
        currencies = "usd" if secondary == "usd" else f"usd,{secondary}"
        data = request_json(
            f"{COINGECKO_BASE}/simple/price",
            params={"ids": "bitcoin", "vs_currencies": currencies, "include_24hr_change": "true"},
            timeout=10,
        )
        btc = data.get("bitcoin", {})
        price_usd = numeric_price(btc.get("usd"))
        price_secondary = numeric_price(btc.get(secondary))
        change_pct_raw = btc.get("usd_24h_change")
        if price_usd is None:
            return None
        if secondary == "usd" and price_secondary is None:
            price_secondary = price_usd
        change_pct = round(float(change_pct_raw), 2) if change_pct_raw is not None else "N/A"
        change_abs = int(round(float(price_usd) * (float(change_pct) / 100))) if isinstance(change_pct, (float, int)) else "N/A"
        return _main_result(price_usd, price_secondary, config["secondary_fiat"], change_pct, change_abs, "coingecko")
    except Exception as e:
        log_event(f"BTC main CoinGecko error: {e}")
    return None


def fetch_btc_main_cryptocompare(config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        secondary = str(config["secondary_fiat"])
        # CryptoCompare's existing MXN path is preserved. Other fiat support is not
        # assumed here without vendor documentation; CoinGecko is authoritative for
        # configurable secondary fiat in this release.
        tsyms = "USD,MXN" if secondary == "MXN" else "USD"
        data = request_json(f"{CRYPTOCOMPARE_BASE}/pricemultifull", params={"fsyms": "BTC", "tsyms": tsyms}, timeout=10)
        raw = data.get("RAW", {}).get("BTC", {})
        usd = raw.get("USD", {})
        price_usd = numeric_price(usd.get("PRICE"))
        price_secondary = None
        if secondary == "USD":
            price_secondary = price_usd
        elif secondary == "MXN":
            mxn = raw.get("MXN", {})
            price_secondary = numeric_price(mxn.get("PRICE")) or _secondary_from_mxn_fallback(price_usd, config)
        change_pct = round(float(usd.get("CHANGEPCT24HOUR")), 2) if usd.get("CHANGEPCT24HOUR") is not None else "N/A"
        change_abs = int(round(float(usd.get("CHANGE24HOUR")))) if usd.get("CHANGE24HOUR") is not None else "N/A"
        if price_usd is None:
            return None
        return _main_result(price_usd, price_secondary, secondary, change_pct, change_abs, "cryptocompare")
    except Exception as e:
        log_event(f"BTC main CryptoCompare error: {e}")
    return None


def fetch_btc_main_coinpaprika(config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        data = request_json(f"{COINPAPRIKA_BASE}/tickers/btc-bitcoin", timeout=10)
        usd = data.get("quotes", {}).get("USD", {})
        price_usd = numeric_price(usd.get("price"))
        change_pct = round(float(usd.get("percent_change_24h")), 2) if usd.get("percent_change_24h") is not None else "N/A"
        price_secondary = price_usd if config["secondary_fiat"] == "USD" else _secondary_from_mxn_fallback(price_usd, config)
        change_abs = int(round(float(price_usd) * (float(change_pct) / 100))) if price_usd and isinstance(change_pct, (float, int)) else "N/A"
        if price_usd is None:
            return None
        return _main_result(price_usd, price_secondary, config["secondary_fiat"], change_pct, change_abs, "coinpaprika")
    except Exception as e:
        log_event(f"BTC main CoinPaprika error: {e}")
    return None


def fetch_btc_main_binance(config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        data = request_json(f"{BINANCE_BASE}/api/v3/ticker/24hr", params={"symbol": "BTCUSDT"}, timeout=10)
        price_usd = numeric_price(data.get("lastPrice"))
        price_secondary = price_usd if config["secondary_fiat"] == "USD" else _secondary_from_mxn_fallback(price_usd, config)
        change_pct = round(float(data.get("priceChangePercent")), 2) if data.get("priceChangePercent") is not None else "N/A"
        change_abs = int(round(float(data.get("priceChange")))) if data.get("priceChange") is not None else "N/A"
        if price_usd is None:
            return None
        return _main_result(price_usd, price_secondary, config["secondary_fiat"], change_pct, change_abs, "binance")
    except Exception as e:
        log_event(f"BTC main Binance error: {e}")
    return None


def fetch_btc_main_kraken(config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        data = request_json(f"{KRAKEN_BASE}/Ticker", params={"pair": "XBTUSD"}, timeout=10)
        result = data.get("result", {})
        if not result:
            return None
        k = list(result.keys())[0]
        item = result[k]
        price = float(item["c"][0])
        open_price = float(item.get("o") or 0)
        price_usd = numeric_price(price)
        price_secondary = price_usd if config["secondary_fiat"] == "USD" else _secondary_from_mxn_fallback(price_usd, config)
        if open_price > 0:
            change_abs_val = price - open_price
            change_pct_val = (change_abs_val / open_price) * 100
            change_abs: float | int | str = int(round(change_abs_val))
            change_pct: float | str = round(change_pct_val, 2)
        else:
            change_abs = "N/A"
            change_pct = "N/A"
        if price_usd is None:
            return None
        return _main_result(price_usd, price_secondary, config["secondary_fiat"], change_pct, change_abs, "kraken")
    except Exception as e:
        log_event(f"BTC main Kraken error: {e}")
    return None


def fetch_btc_main_live(config: dict[str, Any]) -> dict[str, Any] | None:
    providers = [
        ("coingecko", lambda: fetch_btc_main_coingecko(config)),
        ("cryptocompare", lambda: fetch_btc_main_cryptocompare(config)),
        ("coinpaprika", lambda: fetch_btc_main_coinpaprika(config)),
        ("binance", lambda: fetch_btc_main_binance(config)),
        ("kraken", lambda: fetch_btc_main_kraken(config)),
    ]
    usd_only_fallback = None
    gtq_rate: float | None = None
    gtq_rate_attempted = False
    for _name, fn in providers:
        item = fn()
        if item and item.get("price_usd") not in [None, "N/A"]:
            if item.get("price_secondary") not in [None, "N/A"]:
                return item
            if config["secondary_fiat"] == "GTQ":
                if not gtq_rate_attempted:
                    gtq_rate = fetch_usd_gtq_banguat()
                    gtq_rate_attempted = True
                if gtq_rate is not None:
                    item["price_secondary"] = numeric_price(float(item["price_usd"]) * gtq_rate)
                    item["secondary_updated_at"] = now_ts()
                    item["provider"] = f"{item.get('provider', _name)}+banguat"
                    return item
            if usd_only_fallback is None:
                usd_only_fallback = item
    return usd_only_fallback

def fetch_btc_candles_live() -> dict[str, Any] | None:
    try:
        data = request_json(f"{COINGECKO_BASE}/coins/bitcoin/market_chart", params={"vs_currency": "usd", "days": "7"}, timeout=10)
        chart = data.get("prices", [])
        ohlc: list[dict[str, int]] = []
        ohlc_timestamps: list[int] = []
        if not chart:
            return None
        chunk = max(1, len(chart) // 7)
        for i in range(7):
            group = chart[i * chunk: (i + 1) * chunk]
            if group:
                prices = [p[1] for p in group]
                ohlc.append({"open": int(round(prices[0])), "high": int(round(max(prices))), "low": int(round(min(prices))), "close": int(round(prices[-1]))})
                ohlc_timestamps.append(int(group[-1][0]))
        if not ohlc:
            return None
        return {"ohlc": ohlc, "ohlc_timestamps": ohlc_timestamps, "provider": "coingecko"}
    except Exception as e:
        log_event(f"Error fetching BTC candles: {e}")
    return None


def get_ath_value(coin: dict[str, str | None], coins_list: list[dict[str, Any]], ath_cache: dict[str, Any], config: dict[str, Any], status: dict[str, Any], force: bool = False) -> tuple[Any, Any, str]:
    key = f"{coin['symbol']}_{coin.get('quote') or 'USD'}"
    ttl = int(config["ath_refresh_hours"]) * 3600
    cached = ath_cache.get(key, {}) if isinstance(ath_cache.get(key), dict) else {}
    if cached and not force and cache_is_fresh(cached, ttl):
        status.setdefault("ath", {})[key] = {"state": "cache", "age_seconds": int(cache_age_seconds(cached) or 0)}
        return cached.get("ath", "N/A"), cached.get("ath_time", "N/A"), "cache"
    cg_id = coin.get("id") or resolve_coingecko_id(str(coin["symbol"]), coins_list)
    if not cg_id:
        status.setdefault("ath", {})[key] = {"state": "no-coingecko-id"}
        if cached:
            return cached.get("ath", "N/A"), cached.get("ath_time", "N/A"), "stale-cache"
        return "N/A", "N/A", "none"
    try:
        data = request_json(
            f"{COINGECKO_BASE}/coins/{cg_id}",
            params={"localization": "false", "tickers": "false", "market_data": "true", "community_data": "false", "developer_data": "false", "sparkline": "false"},
            timeout=15,
        )
        quote = str(coin.get("quote") or "USD").lower()
        ath_val = data.get("market_data", {}).get("ath", {}).get(quote, "N/A")
        ath_time = data.get("market_data", {}).get("ath_date", {}).get(quote, None)
        if ath_time:
            ath_time = ath_time.replace("T", " ").split(".")[0]
        ath_cache[key] = {"ath": ath_val, "ath_time": ath_time, "updated_at": now_ts(), "updated_at_iso": now_iso(), "provider": "coingecko"}
        status.setdefault("ath", {})[key] = {"state": "live", "provider": "coingecko"}
        return ath_val, ath_time, "live"
    except Exception as e:
        log_event(f"Error fetching ATH for {key}: {e}")
        status.setdefault("ath", {})[key] = {"state": "error", "error": str(e)}
        if cached:
            return cached.get("ath", "N/A"), cached.get("ath_time", "N/A"), "stale-cache"
    return "N/A", "N/A", "none"


def get_weather_roundrobin() -> int:
    idx = 0
    try:
        if ROUNDROBIN_FILE.exists():
            idx = int(ROUNDROBIN_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    idx = (idx + 1) % 2
    ROUNDROBIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROUNDROBIN_FILE.write_text(str(idx), encoding="utf-8")
    return idx


def fetch_weather(city: str, openweather_key: str, weatherapi_key: str):
    idx = get_weather_roundrobin()
    apis = [
        {"name": "OpenWeatherMap", "key": openweather_key, "url": "https://api.openweathermap.org/data/2.5/weather", "city_param": "q", "appid_param": "appid"},
        {"name": "WeatherAPI", "key": weatherapi_key, "url": "https://api.weatherapi.com/v1/current.json", "city_param": "q", "appid_param": "key"},
    ]
    for try_idx in [idx, 1 - idx]:
        api = apis[try_idx]
        if not api["key"]:
            log_event(f"Weather provider {api['name']} missing API key in weather.conf")
            continue
        try:
            params = {api["city_param"]: city, api["appid_param"]: api["key"], "units": "metric"}
            data = request_json(api["url"], params=params, timeout=10)
            if api["name"] == "OpenWeatherMap":
                desc = data["weather"][0]["description"].capitalize()
                temp = round(data["main"]["temp"])
                rain = int(round(data.get("pop", data.get("rain", {}).get("1h", 0)) * 100)) if "pop" in data or "rain" in data else 0
                return desc, temp, rain, "N/A"
            desc = data["current"]["condition"]["text"]
            temp = round(data["current"]["temp_c"])
            rain = int(round(data["current"].get("precip_mm", 0)))
            aqi = data["current"].get("air_quality", {}).get("us-epa-index", "N/A")
            return desc, temp, rain, aqi
        except Exception as e:
            log_event(f"Weather provider {api['name']} failed: {type(e).__name__}")
            continue
    return "N/A", "N/A", "N/A", "N/A"


def draw_candlesticks(draw, ohlc, ohlc_timestamps, x, y, w, h, font, tz):
    n = len(ohlc or [])
    pad_x = 16
    candle_space = (w - 2 * pad_x) // max(n, 1)
    if n == 0:
        return
    all_high = max(d["high"] for d in ohlc)
    all_low = min(d["low"] for d in ohlc)

    def ymap(val):
        return y + h - int((val - all_low) / (all_high - all_low + 1e-9) * h)

    for i, (d, ts) in enumerate(zip(ohlc, ohlc_timestamps)):
        cx = x + pad_x + i * candle_space + candle_space // 2
        draw.line((cx, ymap(d["high"]), cx, ymap(d["low"])), fill=0, width=2)
        o = ymap(d["open"])
        c = ymap(d["close"])
        top, bottom = min(o, c), max(o, c)
        color = 0 if d["close"] >= d["open"] else 180
        draw.rectangle((cx - candle_space // 6, top, cx + candle_space // 6, bottom), fill=color, outline=0)
        dt = datetime.fromtimestamp(ts / 1000, tz)
        day_label = dt.strftime("%a")
        bbox = draw.textbbox((0, 0), day_label, font=font)
        label_w = bbox[2] - bbox[0]
        draw.text((cx - label_w // 2, y + h + 6), day_label, font=font, fill=0)


def format_value(val, decimals=2):
    if val in [None, "N/A"]:
        return "N/A"
    try:
        v = float(val)
        if abs(v) >= 1:
            return f"{v:,.0f}"
        return f"{v:,.6f}".rstrip("0").rstrip(".") if "." in f"{v:,.6f}" else f"{v:,.6f}"
    except Exception:
        return str(val)


def format_ath(val):
    if val in [None, "N/A"]:
        return "N/A"
    try:
        fval = float(val)
        if abs(fval) >= 1:
            return f"{fval:,.2f}"
        return f"{fval:,.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(val)


def format_secondary_price(price: Any, fiat: str) -> str:
    return f"{format_value(price)} {fiat}"


def format_age(seconds: float | int | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 90:
        return f"{minutes}m"
    hours = minutes // 60
    return f"{hours}h"


def render_image(
    price_usd, price_secondary, secondary_fiat, change_abs, change_pct, ohlc, ohlc_timestamps,
    btc_ath, btc_ath_time, coins_table, weather_data, coins_on=True, weather_on=True,
    data_note: str | None = None,
):
    img = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)
    y_cursor = 28

    font_main = ImageFont.truetype(FONT_PATH, FONT_SIZE_MAIN)
    btc_str = f"BTC: ${format_value(price_usd)}"
    bbox = draw.textbbox((0, 0), btc_str, font=font_main)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((WIDTH - w) // 2, y_cursor), btc_str, font=font_main, fill=0)
    y_cursor += h + 6

    font_med = ImageFont.truetype(FONT_PATH, FONT_SIZE_MED)
    secondary_str = format_secondary_price(price_secondary, secondary_fiat)
    bbox2 = draw.textbbox((0, 0), secondary_str, font=font_med)
    w2, h2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
    draw.text(((WIDTH - w2) // 2, y_cursor), secondary_str, font=font_med, fill=0)
    y_cursor += h2 + 4

    font_small = ImageFont.truetype(FONT_PATH, FONT_SIZE_SMALL)
    sign = "+" if change_abs != "N/A" and isinstance(change_abs, (int, float)) and change_abs >= 0 else ""
    pct_text = change_pct if change_pct != "N/A" else "N/A"
    change_str = f"24h: {sign}{format_value(change_abs)} USD  ({sign}{pct_text}%)"
    bbox3 = draw.textbbox((0, 0), change_str, font=font_small)
    w3, h3 = bbox3[2] - bbox3[0], bbox3[3] - bbox3[1]
    draw.text(((WIDTH - w3) // 2, y_cursor), change_str, font=font_small, fill=0)
    y_cursor += h3 + 6

    chart_h = 120
    font_tiny = ImageFont.truetype(FONT_PATH, FONT_SIZE_TINY)
    draw_candlesticks(draw, ohlc, ohlc_timestamps, 60, y_cursor, WIDTH - 120, chart_h, font_tiny, TZ)
    y_cursor += chart_h + FONT_SIZE_TINY + 10

    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    bbox4 = draw.textbbox((0, 0), now, font=font_small)
    w4, h4 = bbox4[2] - bbox4[0], bbox4[3] - bbox4[1]
    draw.text(((WIDTH - w4) // 2, y_cursor), now, font=font_small, fill=0)
    y_cursor += h4 + 18

    if btc_ath and btc_ath != "N/A":
        ath_disp = format_ath(btc_ath)
        ath_str = f"All-Time High: ${ath_disp} on {btc_ath_time if btc_ath_time else 'N/A'}"
        bbox5 = draw.textbbox((0, 0), ath_str, font=font_tiny)
        w5, h5 = bbox5[2] - bbox5[0], bbox5[3] - bbox5[1]
        draw.text(((WIDTH - w5) // 2, y_cursor), ath_str, font=font_tiny, fill=0)
        y_cursor += h5 + 12

    if coins_on and coins_table:
        font_tbl = ImageFont.truetype(FONT_PATH, FONT_SIZE_TINY)
        table_pad = 10
        col_widths = [100, 110, 110, 100]
        headers = ["Pair", "Price", "ATH", "% to ATH"]
        x0 = (WIDTH - sum(col_widths) - table_pad * 3) // 2
        for i, htxt in enumerate(headers):
            draw.text((x0 + sum(col_widths[:i]) + i * table_pad, y_cursor), htxt, font=font_tbl, fill=0)
        y_cursor += FONT_SIZE_TINY + 6
        for row in coins_table:
            pair_label, price, ath, pct_to_ath = row
            draw.text((x0, y_cursor), pair_label, font=font_tbl, fill=0)
            draw.text((x0 + col_widths[0] + table_pad, y_cursor), format_ath(price), font=font_tbl, fill=0)
            draw.text((x0 + sum(col_widths[:2]) + table_pad * 2, y_cursor), format_ath(ath), font=font_tbl, fill=0)
            draw.text((x0 + sum(col_widths[:3]) + table_pad * 3, y_cursor), str(pct_to_ath), font=font_tbl, fill=0)
            y_cursor += FONT_SIZE_TINY + 3
        y_cursor += 8

    if weather_on and weather_data:
        desc, temp, rain, aqi = weather_data
        font_weather = ImageFont.truetype(FONT_PATH, FONT_SIZE_TINY)
        weather_lines = [f"Weather: {desc}, {temp}°C", f"Rain: {rain}%", f"Air Quality: {aqi}"]
        for s in weather_lines:
            bboxw = draw.textbbox((0, 0), s, font=font_weather)
            ww = bboxw[2] - bboxw[0]
            draw.text(((WIDTH - ww) // 2, y_cursor), s, font=font_weather, fill=0)
            y_cursor += FONT_SIZE_TINY + 3

    if data_note:
        font_note = ImageFont.truetype(FONT_PATH, 14)
        bboxn = draw.textbbox((0, 0), data_note, font=font_note)
        wn = bboxn[2] - bboxn[0]
        draw.text(((WIDTH - wn) // 2, HEIGHT - 20), data_note, font=font_note, fill=0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_FILE.with_name(OUTPUT_FILE.name + ".tmp.png")
    img.save(tmp)
    tmp.replace(OUTPUT_FILE)
    print(f"[OK] Updated BTC image saved to {OUTPUT_FILE}", flush=True)


def build_coin_table(coins: list[dict[str, str | None]], price_cache: dict[str, Any], ath_results: dict[str, tuple[Any, Any, str]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    prices = price_cache.get("coins", {}) if isinstance(price_cache.get("coins"), dict) else {}
    for coin in coins:
        pair = f"{coin['symbol']}/{coin.get('quote') or 'USD'}"
        cached_price = prices.get(pair, {}).get("price") if isinstance(prices.get(pair), dict) else "N/A"
        ath, _ath_time, _source = ath_results.get(f"{coin['symbol']}_{coin.get('quote') or 'USD'}", ("N/A", "N/A", "none"))
        try:
            pct_to_ath = f"{100 * (1 - float(cached_price) / float(ath)):.1f}%" if isinstance(cached_price, (int, float)) and isinstance(ath, (int, float)) and float(ath) > 0 else "N/A"
        except Exception:
            pct_to_ath = "N/A"
        rows.append([pair, cached_price, ath, pct_to_ath])
    return rows


def update_once(force_network: bool = False) -> dict[str, Any]:
    with THREAD_LOCK:
        with refresh_file_lock():
            ensure_dirs_and_files()
            config = read_extras_conf()
            coins = read_coins_conf() if config["coins_on"] else []
            btc_coin = {"symbol": "BTC", "id": "bitcoin", "quote": "USD"}
            status: dict[str, Any] = {
                "version": VERSION,
                "started_at": now_iso(),
                "force_network": force_network,
                "config": {k: v for k, v in config.items() if k != "usd_mxn_fallback_rate"},
                "providers": {},
            }

            coins_list = get_coingecko_list_if_needed(coins, status, force=force_network)

            price_cache = load_json(PRICE_CACHE_FILE)
            price_ttl = int(config["price_refresh_minutes"]) * 60
            cached_main = price_cache.get("main", {}) if isinstance(price_cache.get("main"), dict) else {}
            cached_fiat = cached_secondary_fiat(cached_main)
            currency_changed = bool(cached_fiat) and cached_fiat != config["secondary_fiat"]
            prices_stale = force_network or currency_changed or not cache_is_fresh(price_cache, price_ttl)
            api_idx_map = load_price_api_index()
            if prices_stale:
                provider_status: dict[str, Any] = {}
                old_prices = price_cache.get("coins", {}) if isinstance(price_cache.get("coins"), dict) else {}
                btc_live = fetch_btc_main_live(config)
                if btc_live:
                    main = btc_live
                    price_status = {"state": "live", "provider": btc_live.get("provider")}
                    if main.get("price_secondary") in [None, "N/A"] and cached_secondary_fiat(cached_main) == config["secondary_fiat"]:
                        old_secondary = cached_main.get("price_secondary")
                        if old_secondary in [None, "N/A"] and config["secondary_fiat"] == "MXN":
                            old_secondary = cached_main.get("price_mxn")
                        if old_secondary not in [None, "N/A"]:
                            main["price_secondary"] = old_secondary
                            main["secondary_updated_at"] = cached_main.get("secondary_updated_at", price_cache.get("updated_at"))
                            main["secondary_source"] = "stale-cache"
                            try:
                                sec_age = int(max(0, now_ts() - float(main["secondary_updated_at"])))
                            except Exception:
                                sec_age = int(cache_age_seconds(price_cache) or 0)
                            price_status["secondary_state"] = "stale-cache"
                            price_status["secondary_age_seconds"] = sec_age
                    if "secondary_state" not in price_status:
                        price_status["secondary_state"] = "live" if main.get("price_secondary") not in [None, "N/A"] else "unavailable"
                    status["prices"] = price_status
                elif isinstance(price_cache.get("main"), dict) and price_cache["main"].get("price_usd") not in [None, "N/A"]:
                    cached = dict(price_cache["main"])
                    cached_fiat = cached_secondary_fiat(cached)
                    if cached_fiat == "MXN" and cached.get("price_secondary") in [None, "N/A"]:
                        cached["price_secondary"] = cached.get("price_mxn", "N/A")
                    if cached_fiat == config["secondary_fiat"]:
                        main = cached
                    else:
                        main = _main_result(cached.get("price_usd"), "N/A", config["secondary_fiat"], cached.get("change_pct", "N/A"), cached.get("change_abs", "N/A"), "stale-cache")
                    status["prices"] = {"state": "stale-cache", "age_seconds": int(cache_age_seconds(price_cache) or 0)}
                else:
                    main = _main_result("N/A", "N/A", config["secondary_fiat"], "N/A", "N/A", "none")
                    status["prices"] = {"state": "error", "provider": "none"}

                coin_prices: dict[str, Any] = {}
                for coin in coins:
                    pair = f"{coin['symbol']}/{coin.get('quote') or 'USD'}"
                    price, provider = fetch_price_unified(coin, coins_list, api_idx_map, provider_status)
                    if price == "N/A" and isinstance(old_prices.get(pair), dict) and old_prices[pair].get("price") not in [None, "N/A"]:
                        coin_prices[pair] = {**old_prices[pair], "source": "stale-cache", "cache_age_seconds": int(cache_age_seconds(price_cache) or 0)}
                    else:
                        coin_prices[pair] = {"price": price, "provider": provider, "source": "live", "updated_at": now_ts(), "updated_at_iso": now_iso()}
                price_cache = {"updated_at": now_ts(), "updated_at_iso": now_iso(), "main": main, "coins": coin_prices}
                save_json(PRICE_CACHE_FILE, price_cache)
                save_price_api_index(api_idx_map)
                status["providers"]["coin_prices"] = provider_status
            else:
                status["prices"] = {"state": "cache", "age_seconds": int(cache_age_seconds(price_cache) or 0)}

            candles_cache = load_json(CANDLES_CACHE_FILE)
            candles_ttl = int(config["candles_refresh_minutes"]) * 60
            candles_stale = force_network or not cache_is_fresh(candles_cache, candles_ttl)
            if candles_stale:
                candles_live = fetch_btc_candles_live()
                if candles_live:
                    candles_cache = {"updated_at": now_ts(), "updated_at_iso": now_iso(), **candles_live}
                    save_json(CANDLES_CACHE_FILE, candles_cache)
                    status["candles"] = {"state": "live", "provider": candles_live.get("provider")}
                elif candles_cache.get("ohlc"):
                    status["candles"] = {"state": "stale-cache", "age_seconds": int(cache_age_seconds(candles_cache) or 0)}
                else:
                    status["candles"] = {"state": "error", "provider": "none"}
            else:
                status["candles"] = {"state": "cache", "age_seconds": int(cache_age_seconds(candles_cache) or 0)}

            ath_cache = load_json(ATH_CACHE_FILE)
            ath_results: dict[str, tuple[Any, Any, str]] = {}
            for coin in [btc_coin] + coins:
                key = f"{coin['symbol']}_{coin.get('quote') or 'USD'}"
                ath_results[key] = get_ath_value(coin, coins_list, ath_cache, config, status, force=force_network)
            save_json(ATH_CACHE_FILE, ath_cache)

            weather_data = None
            if config["weather_on"]:
                city, openweather_key, weatherapi_key = read_weather_conf()
                weather_data = fetch_weather(city, openweather_key, weatherapi_key)
                status["weather"] = {"state": "queried"}
            else:
                status["weather"] = {"state": "off"}

            main = price_cache.get("main", {}) if isinstance(price_cache.get("main"), dict) else {}
            btc_ath, btc_ath_time, _btc_ath_source = ath_results.get("BTC_USD", ("N/A", "N/A", "none"))
            coins_table = build_coin_table(coins, price_cache, ath_results) if config["coins_on"] else []
            data_age = cache_age_seconds(price_cache)
            data_note = None
            if status.get("prices", {}).get("state") in {"stale-cache", "error"}:
                data_note = f"Data cache age: {format_age(data_age)}"
            render_image(
                main.get("price_usd", "N/A"),
                main.get("price_secondary", main.get("price_mxn", "N/A") if config["secondary_fiat"] == "MXN" else "N/A"),
                config["secondary_fiat"], main.get("change_abs", "N/A"), main.get("change_pct", "N/A"),
                candles_cache.get("ohlc", []), candles_cache.get("ohlc_timestamps", []), btc_ath, btc_ath_time,
                coins_table, weather_data, coins_on=config["coins_on"], weather_on=config["weather_on"], data_note=data_note,
            )
            status.update({
                "finished_at": now_iso(),
                "output_file": str(OUTPUT_FILE),
                "output_exists": OUTPUT_FILE.exists(),
                "price_cache_age_seconds": int(cache_age_seconds(price_cache) or 0),
                "candles_cache_age_seconds": int(cache_age_seconds(candles_cache) or 0),
            })
            save_json(STATUS_FILE, status)
            return status


def scheduler_loop() -> None:
    while True:
        try:
            config = read_extras_conf()
            if config.get("internal_scheduler", True):
                update_once(force_network=False)
            sleep_seconds = int(config.get("scheduler_check_seconds", 60))
        except RuntimeError as e:
            log_event(f"Scheduler skipped: {e}")
            sleep_seconds = 60
        except Exception as e:
            log_event(f"Scheduler update failed: {e}")
            sleep_seconds = 60
        time.sleep(max(30, sleep_seconds))


class Handler(BaseHTTPRequestHandler):
    server_version = f"KindleBTC/{VERSION}"

    def _send_bytes(self, data: bytes, content_type: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/healthz":
            self._send_bytes(b"ok\n", "text/plain; charset=utf-8")
            return
        if path == "/status.json":
            ensure_dirs_and_files()
            status = load_json(STATUS_FILE)
            if not status:
                status = {"version": VERSION, "state": "no-status-yet", "time": now_iso()}
            self._send_bytes(json.dumps(status, indent=2, sort_keys=True).encode("utf-8") + b"\n", "application/json; charset=utf-8")
            return
        if path == "/refresh":
            qs = parse_qs(parsed.query)
            force = qs.get("force", ["0"])[0].lower() in {"1", "true", "yes"}
            try:
                status = update_once(force_network=force)
                self._send_bytes(("refreshed\n" + json.dumps({"prices": status.get("prices"), "candles": status.get("candles")}) + "\n").encode("utf-8"), "text/plain; charset=utf-8")
            except RuntimeError as e:
                self._send_bytes(f"refresh skipped: {e}\n".encode("utf-8"), "text/plain; charset=utf-8", 409)
            except Exception as e:
                msg = f"refresh failed: {e}\n".encode("utf-8")
                self._send_bytes(msg, "text/plain; charset=utf-8", 500)
            return
        if path in {"/", "/index.html"}:
            ensure_dirs_and_files()
            config = read_extras_conf()
            page_refresh_seconds = int(config["page_refresh_minutes"]) * 60
            html = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<meta http-equiv='refresh' content='{page_refresh_seconds}'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                "<title>Kindle BTC</title></head>"
                "<body style='margin:0;background:#fff;text-align:center'>"
                "<img src='/kindle_btc_price.png' width='800' height='600' alt='Kindle Bitcoin Price Display'>"
                "</body></html>"
            ).encode("utf-8")
            self._send_bytes(html, "text/html; charset=utf-8")
            return
        if path == "/kindle_btc_price.png":
            if not OUTPUT_FILE.exists():
                try:
                    update_once(force_network=False)
                except RuntimeError:
                    pass
                except Exception as e:
                    msg = f"image unavailable: {e}\n".encode("utf-8")
                    self._send_bytes(msg, "text/plain; charset=utf-8", 503)
                    return
            if OUTPUT_FILE.exists():
                self._send_bytes(OUTPUT_FILE.read_bytes(), mimetypes.types_map.get(".png", "image/png"))
            else:
                self._send_bytes(b"image unavailable\n", "text/plain; charset=utf-8", 503)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def log_message(self, fmt: str, *args) -> None:
        safe = fmt.replace("\n", "\\n").replace("\r", "\\r")
        print(f"{self.address_string()} - {safe % args}", flush=True)


def main() -> None:
    ensure_dirs_and_files()
    mode = os.environ.get("APP_MODE", "server")
    if mode == "once":
        update_once(force_network=os.environ.get("FORCE_NETWORK", "0") in {"1", "true", "yes"})
        return
    try:
        update_once(force_network=False)
    except Exception as e:
        log_event(f"Initial update failed: {e}")
    config = read_extras_conf()
    if config.get("internal_scheduler", True):
        thread = threading.Thread(target=scheduler_loop, daemon=True)
        thread.start()
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "8787"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"{APP_NAME} {VERSION} listening on {host}:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
