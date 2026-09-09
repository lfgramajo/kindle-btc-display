import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("app", ROOT / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class AppTests(unittest.TestCase):
    def test_format_value_commas(self):
        self.assertEqual(app.format_value(123456), "123,456")
        self.assertEqual(app.format_value(0.1234567), "0.123457")

    def test_format_ath_decimals(self):
        self.assertEqual(app.format_ath(123456.789), "123,456.79")
        self.assertEqual(app.format_ath("N/A"), "N/A")
        self.assertEqual(app.format_ath(1.42), "1.42")

    def test_parse_config_ignores_inline_comments(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.conf"
            p.write_text("weather=off # no weather\n# comment\ncoins=on\n", encoding="utf-8")
            self.assertEqual(app.parse_config_lines(p), ["weather=off", "coins=on"])

    def test_read_extras_conf_timing_values(self):
        with tempfile.TemporaryDirectory() as td:
            old = app.EXTRAS_CONF_PATH
            app.EXTRAS_CONF_PATH = Path(td) / "extras.config"
            app.EXTRAS_CONF_PATH.write_text(
                "price_refresh_minutes=10\n"
                "candles_refresh_minutes=10\n"
                "ath_refresh_hours=12\n"
                "page_refresh_minutes=11\n"
                "weather=off\n"
                "coins=on\n",
                encoding="utf-8",
            )
            try:
                cfg = app.read_extras_conf()
                self.assertEqual(cfg["price_refresh_minutes"], 10)
                self.assertEqual(cfg["candles_refresh_minutes"], 10)
                self.assertEqual(cfg["ath_refresh_hours"], 12)
                self.assertEqual(cfg["page_refresh_minutes"], 11)
                self.assertFalse(cfg["weather_on"])
                self.assertTrue(cfg["coins_on"])
            finally:
                app.EXTRAS_CONF_PATH = old

    def test_needs_coingecko_list_false_when_ids_present(self):
        coins = [
            {"symbol": "BTC", "id": "bitcoin", "quote": "USD"},
            {"symbol": "SOL", "id": "solana", "quote": "USD"},
        ]
        self.assertFalse(app.needs_coingecko_list(coins))

    def test_needs_coingecko_list_true_when_id_missing(self):
        coins = [{"symbol": "BTC", "id": None, "quote": "USD"}]
        self.assertTrue(app.needs_coingecko_list(coins))

    def test_cache_is_fresh(self):
        self.assertTrue(app.cache_is_fresh({"updated_at": app.now_ts()}, 60))
        self.assertFalse(app.cache_is_fresh({"updated_at": app.now_ts() - 1000}, 60))

    def test_render_image_creates_png(self):
        with tempfile.TemporaryDirectory() as td:
            old_output = app.OUTPUT_FILE
            old_output_dir = app.OUTPUT_DIR
            app.OUTPUT_DIR = Path(td)
            app.OUTPUT_FILE = Path(td) / "kindle_btc_price.png"
            try:
                ohlc = [
                    {"open": 100, "high": 120, "low": 90, "close": 110},
                    {"open": 110, "high": 130, "low": 100, "close": 105},
                ]
                ts = [1700000000000, 1700086400000]
                app.render_image(100000, 1800000, 1200, 1, ohlc, ts, 123000, "2025-01-01 00:00:00", [["BTC/USD", 100000, 123000, "18.7%"]], None, True, False)
                self.assertTrue(app.OUTPUT_FILE.exists())
                self.assertGreater(app.OUTPUT_FILE.stat().st_size, 1000)
            finally:
                app.OUTPUT_FILE = old_output
                app.OUTPUT_DIR = old_output_dir

    def test_get_coingecko_list_skipped_when_ids_present(self):
        with tempfile.TemporaryDirectory() as td:
            old_cache_dir = app.CACHE_DIR
            old_file = app.COINGECKO_LIST_CACHE_FILE
            app.CACHE_DIR = Path(td)
            app.COINGECKO_LIST_CACHE_FILE = Path(td) / "coingecko_coin_list.json"
            status = {}
            try:
                with mock.patch.object(app, "request_json") as mocked:
                    result = app.get_coingecko_list_if_needed([{"symbol": "BTC", "id": "bitcoin", "quote": "USD"}], status)
                    self.assertEqual(result, [])
                    mocked.assert_not_called()
                    self.assertEqual(status["coingecko_coin_list"]["state"], "skipped")
            finally:
                app.CACHE_DIR = old_cache_dir
                app.COINGECKO_LIST_CACHE_FILE = old_file

    def test_default_altcoins_are_top_five_release_set_without_stablecoins(self):
        expected = [
            ("ETH", "ethereum"),
            ("BNB", "binancecoin"),
            ("XRP", "ripple"),
            ("SOL", "solana"),
            ("TRX", "tron"),
        ]
        lines = [line for line in app.DEFAULTS["coins.config"].splitlines() if line and not line.startswith("#")]
        actual = [(line.split(",")[0], line.split(",")[1]) for line in lines]
        self.assertEqual(actual, expected)

    def test_mxn_is_main_local_currency(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"vs_currencies": "usd,mxn"', source)
        self.assertIn("usd_mxn_fallback_rate", app.DEFAULT_EXTRAS)


if __name__ == "__main__":
    unittest.main()
