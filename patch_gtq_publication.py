from pathlib import Path
import ast


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one match in {path}: {old!r}; found {text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app.py",
    '    "CNY", "CZK", "DKK", "EUR", "GBP", "GEL", "HKD", "HUF", "IDR", "ILS",',
    '    "CNY", "CZK", "DKK", "EUR", "GBP", "GEL", "GTQ", "HKD", "HUF", "IDR", "ILS",',
)

replace_once(
    "README.md",
    "- 46 supported fiat codes in v1.7.0",
    "- 47 supported fiat codes in v1.7.0",
)
replace_once(
    "README.md",
    "| GEL | Georgian lari | Georgia |\n| HKD | Hong Kong dollar | Hong Kong |",
    "| GEL | Georgian lari | Georgia |\n| GTQ | Guatemalan quetzal | Guatemala |\n| HKD | Hong Kong dollar | Hong Kong |",
)
replace_once(
    "README.md",
    "CoinGecko's current supported-currencies endpoint still exposes `VEF`; v1.7.0 therefore retains it for provider compatibility even though it is a legacy Venezuelan currency code.",
    "CoinGecko's API changelog explicitly added Guatemala (`GTQ`) to its supported currencies, and v1.7.0 includes it as a selectable secondary fiat. CoinGecko's supported-currencies reference also exposes `VEF`; v1.7.0 retains that legacy Venezuelan code for provider compatibility.",
)

replace_once(
    "docs/CONFIGURATION.md",
    "AED ARS AUD BDT BHD BMD BRL CAD CHF CLP CNY CZK DKK EUR GBP GEL HKD HUF",
    "AED ARS AUD BDT BHD BMD BRL CAD CHF CLP CNY CZK DKK EUR GBP GEL GTQ HKD HUF",
)

replace_once(
    "CHANGELOG.md",
    "- Added an explicit public table of all 46 release-supported fiat codes with currency names and country or issuing region.",
    "- Added an explicit public table of all 47 release-supported fiat codes with currency names and country or issuing region, including GTQ (Guatemalan quetzal).",
)

# Static parity checks before the branch is allowed to merge.
source = Path("app.py").read_text(encoding="utf-8")
tree = ast.parse(source)
supported = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SUPPORTED_SECONDARY_FIATS" for t in node.targets):
        supported = set(ast.literal_eval(node.value))
        break
if supported is None:
    raise SystemExit("SUPPORTED_SECONDARY_FIATS not found")
if "GTQ" not in supported or len(supported) != 47:
    raise SystemExit(f"unexpected supported fiat set: GTQ={('GTQ' in supported)} count={len(supported)}")

readme = Path("README.md").read_text(encoding="utf-8")
if "| GTQ | Guatemalan quetzal | Guatemala |" not in readme:
    raise SystemExit("README GTQ row missing")
if "47 supported fiat codes" not in readme:
    raise SystemExit("README fiat count missing")

config_doc = Path("docs/CONFIGURATION.md").read_text(encoding="utf-8")
if " GTQ " not in config_doc:
    raise SystemExit("CONFIGURATION.md GTQ code missing")

print("GTQ_PATCH_STATIC_CHECK=PASS")
