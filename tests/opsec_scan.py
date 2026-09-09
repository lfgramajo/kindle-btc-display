from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(
    r"(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})"
    r"|/home/[A-Za-z0-9._-]+"
    r"|[A-Za-z0-9._-]+\.home\.arpa",
    re.I,
)
SKIP = {Path(__file__).resolve()}

hits = []
for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts or path.resolve() in SKIP:
        continue
    if path.suffix in {".pyc", ".gz", ".png"}:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for lineno, line in enumerate(text.splitlines(), 1):
        if PATTERN.search(line):
            hits.append(f"{path.relative_to(ROOT)}:{lineno}:{line}")

if hits:
    print("OPSEC sentinel found private infrastructure markers:")
    print("\n".join(hits))
    sys.exit(1)
print("OPSEC sentinel: PASS")
