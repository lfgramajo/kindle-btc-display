from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, got {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app.py",
    "import time\nfrom datetime import datetime",
    "import time\nimport xml.etree.ElementTree as ET\nfrom datetime import datetime",
)
replace_once(
    "app.py",
    'KRAKEN_BASE = "https://api.kraken.com/0/public"',
    'KRAKEN_BASE = "https://api.kraken.com/0/public"\nBANGUAT_EXCHANGE_RATE_URL = "https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx"',
)

marker = '''def _secondary_from_mxn_fallback(price_usd: float | int | None, config: dict[str, Any]) -> float | int | None:\n'''
insert = '''def fetch_usd_gtq_banguat() -> float | None:\n    """Return Banco de Guatemala's current reference GTQ-per-USD rate."""\n    envelope = (\n        '<?xml version="1.0" encoding="utf-8"?>'\n        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '\n        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '\n        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'\n        '<soap:Body><TipoCambioDia xmlns="http://www.banguat.gob.gt/variables/ws/" />'\n        '</soap:Body></soap:Envelope>'\n    )\n    try:\n        response = requests.post(\n            BANGUAT_EXCHANGE_RATE_URL,\n            data=envelope.encode("utf-8"),\n            headers={\n                "Content-Type": "text/xml; charset=utf-8",\n                "SOAPAction": "http://www.banguat.gob.gt/variables/ws/TipoCambioDia",\n                "User-Agent": USER_AGENT,\n            },\n            timeout=10,\n        )\n        response.raise_for_status()\n        root = ET.fromstring(response.content)\n        references: list[float] = []\n        for element in root.iter():\n            if element.tag.endswith("referencia") and element.text:\n                try:\n                    value = float(element.text)\n                    if value > 0:\n                        references.append(value)\n                except ValueError:\n                    continue\n        if references:\n            return references[-1]\n        log_event("Banco de Guatemala response did not contain a USD/GTQ reference rate")\n    except Exception as e:\n        log_event(f"Banco de Guatemala USD/GTQ reference-rate error: {e}")\n    return None\n\n\n'''
replace_once("app.py", marker, insert + marker)

old_live = '''def fetch_btc_main_live(config: dict[str, Any]) -> dict[str, Any] | None:\n    providers = [\n        ("coingecko", lambda: fetch_btc_main_coingecko(config)),\n        ("cryptocompare", lambda: fetch_btc_main_cryptocompare(config)),\n        ("coinpaprika", lambda: fetch_btc_main_coinpaprika(config)),\n        ("binance", lambda: fetch_btc_main_binance(config)),\n        ("kraken", lambda: fetch_btc_main_kraken(config)),\n    ]\n    usd_only_fallback = None\n    for _name, fn in providers:\n        item = fn()\n        if item and item.get("price_usd") not in [None, "N/A"]:\n            if item.get("price_secondary") not in [None, "N/A"]:\n                return item\n            if usd_only_fallback is None:\n                usd_only_fallback = item\n    return usd_only_fallback\n'''
new_live = '''def fetch_btc_main_live(config: dict[str, Any]) -> dict[str, Any] | None:\n    providers = [\n        ("coingecko", lambda: fetch_btc_main_coingecko(config)),\n        ("cryptocompare", lambda: fetch_btc_main_cryptocompare(config)),\n        ("coinpaprika", lambda: fetch_btc_main_coinpaprika(config)),\n        ("binance", lambda: fetch_btc_main_binance(config)),\n        ("kraken", lambda: fetch_btc_main_kraken(config)),\n    ]\n    usd_only_fallback = None\n    gtq_rate: float | None = None\n    gtq_rate_attempted = False\n    for _name, fn in providers:\n        item = fn()\n        if item and item.get("price_usd") not in [None, "N/A"]:\n            if item.get("price_secondary") not in [None, "N/A"]:\n                return item\n            if config["secondary_fiat"] == "GTQ":\n                if not gtq_rate_attempted:\n                    gtq_rate = fetch_usd_gtq_banguat()\n                    gtq_rate_attempted = True\n                if gtq_rate is not None:\n                    item["price_secondary"] = numeric_price(float(item["price_usd"]) * gtq_rate)\n                    item["secondary_updated_at"] = now_ts()\n                    item["provider"] = f"{item.get('provider', _name)}+banguat"\n                    return item\n            if usd_only_fallback is None:\n                usd_only_fallback = item\n    return usd_only_fallback\n'''
replace_once("app.py", old_live, new_live)

replace_once(
    "README.md",
    "CoinGecko's API changelog explicitly added Guatemala (`GTQ`) to its supported currencies, and v1.7.0 includes it as a selectable secondary fiat. CoinGecko's supported-currencies reference also exposes `VEF`; v1.7.0 retains that legacy Venezuelan code for provider compatibility.",
    "CoinGecko's API changelog historically added Guatemala (`GTQ`), but its current `supported_vs_currencies` response does not return GTQ. v1.7.0 therefore uses CoinGecko directly if it supplies GTQ and otherwise combines the live BTC/USD price with Banco de Guatemala's official USD/GTQ reference rate. CoinGecko's supported-currencies reference also exposes `VEF`; v1.7.0 retains that legacy Venezuelan code for provider compatibility.",
)
replace_once(
    "README.md",
    "References: [CoinGecko supported currencies](https://docs.coingecko.com/reference/simple-supported-currencies) and [Chainalysis 2025 Global Crypto Adoption Index](https://www.chainalysis.com/blog/2025-global-crypto-adoption-index/).",
    "References: [CoinGecko supported currencies](https://docs.coingecko.com/reference/simple-supported-currencies), [CoinGecko changelog entry listing GTQ](https://docs.coingecko.com/changelog/10122018), [Banco de Guatemala TipoCambioDia Web Service](https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?op=TipoCambioDia), and [Chainalysis 2025 Global Crypto Adoption Index](https://www.chainalysis.com/blog/2025-global-crypto-adoption-index/).",
)

replace_once(
    "docs/CONFIGURATION.md",
    "Former-G8 examples (today the G7 plus Russia): `CAD`, `GBP`, `EUR`, `JPY`, `RUB`; the primary line already displays `USD`.",
    "GTQ provider note: CoinGecko's current supported-currency response omits GTQ, so when `secondary_fiat=GTQ` the application uses Banco de Guatemala's official daily USD/GTQ reference rate if CoinGecko does not provide a direct GTQ value.\n\nFormer-G8 examples (today the G7 plus Russia): `CAD`, `GBP`, `EUR`, `JPY`, `RUB`; the primary line already displays `USD`.",
)

replace_once(
    "docs/API_PROVIDERS.md",
    "The configurable `secondary_fiat` path is authoritative through CoinGecko in v1.7.0. CoinGecko's `/simple/price` request asks for USD plus the configured supported fiat code. The existing CryptoCompare/MXN path and the user-editable static MXN fallback are retained only for `secondary_fiat=MXN`; v1.7.0 does not assume undocumented arbitrary-fiat support from the other providers. If a non-MXN secondary-fiat request cannot be refreshed, a matching last-known-good secondary cache may be retained. A cache for one fiat is never relabeled as another.",
    "The configurable `secondary_fiat` path normally uses CoinGecko. CoinGecko's `/simple/price` request asks for USD plus the configured supported fiat code. For `GTQ`, CoinGecko is attempted first; if it returns USD but no GTQ value, the application fetches Banco de Guatemala's official `TipoCambioDia` USD/GTQ reference rate and converts the live BTC/USD value. The existing CryptoCompare/MXN path and the user-editable static MXN fallback are retained only for `secondary_fiat=MXN`; v1.7.0 does not assume undocumented arbitrary-fiat support from the other providers. If a secondary-fiat request cannot be refreshed, a matching last-known-good secondary cache may be retained. A cache for one fiat is never relabeled as another.",
)

replace_once(
    "docs/TECHNICAL.md",
    "The main BTC line remains USD. `secondary_fiat` controls the second BTC price and rendered label. `MXN` is the release default. CoinGecko is the authoritative arbitrary-fiat provider in v1.7.0 because its official `vs_currencies` interface publishes a supported-currency list. Existing fallback providers continue protecting the USD main price. The legacy static conversion is restricted to MXN only.",
    "The main BTC line remains USD. `secondary_fiat` controls the second BTC price and rendered label. `MXN` is the release default. CoinGecko is the normal arbitrary-fiat provider in v1.7.0. GTQ has a deliberate exception: if CoinGecko does not return GTQ, the application multiplies the selected live BTC/USD provider value by Banco de Guatemala's official `TipoCambioDia` USD/GTQ reference rate. Existing fallback providers continue protecting the USD main price. The legacy static conversion is restricted to MXN only.",
)

replace_once(
    "CHANGELOG.md",
    "- Added an explicit public table of all 47 release-supported fiat codes with currency names and country or issuing region, including GTQ (Guatemalan quetzal).",
    "- Added an explicit public table of all 47 release-supported fiat codes with currency names and country or issuing region, including GTQ (Guatemalan quetzal), with an official Banco de Guatemala USD/GTQ reference-rate fallback when CoinGecko omits GTQ.",
)

print("GTQ_BANGUAT_PATCH=APPLIED")
