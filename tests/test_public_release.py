import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicReleaseTests(unittest.TestCase):
    def test_runtime_artifacts_not_tracked(self):
        forbidden = [
            ROOT / ".env",
            ROOT / "config" / "coins.config",
            ROOT / "config" / "extras.config",
            ROOT / "config" / "weather.conf",
            ROOT / "config" / "cache",
            ROOT / "logs",
            ROOT / "output",
        ]
        self.assertEqual([str(p) for p in forbidden if p.exists()], [])

    def test_no_environment_specific_markers(self):
        pattern = re.compile(
            r"(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})"
            r"|/home/[A-Za-z0-9._-]+"
            r"|[A-Za-z0-9._-]+\.home\.arpa",
            re.I,
        )
        hits = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or path.suffix in {".pyc"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for n, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{n}:{line}")
        self.assertEqual(hits, [])

    def test_security_policy_states_lan_only_and_no_default_secrets(self):
        text = (ROOT / "SECURITY.md").read_text(encoding="utf-8").lower()
        self.assertIn("lan-only", text)
        self.assertIn("requires **no secrets**", text)


    def test_secondary_fiat_default_and_readme_examples(self):
        extras = (ROOT / "config" / "extras.config.example").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertRegex(extras, r"(?m)^secondary_fiat=MXN$")
        self.assertIn("configurable secondary fiat", readme.lower())
        for code in ["CAD", "GBP", "EUR", "JPY", "RUB", "INR", "PKR", "VND", "BRL", "NGN", "IDR", "UAH", "PHP"]:
            self.assertIn(code, readme)

    def test_internal_scheduler_public_default_is_off(self):
        text = (ROOT / "config" / "extras.config.example").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^internal_scheduler=off$")


if __name__ == "__main__":
    unittest.main()
