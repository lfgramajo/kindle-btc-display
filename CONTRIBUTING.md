# Contributing

Small, reviewable changes are preferred.

Before opening a pull request:

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py
bash -n install.sh
bash -n uninstall.sh
```

Do not include runtime config, cache, logs, generated PNGs, credentials, private hostnames, or LAN addresses in a pull request.

Changes to provider behavior should preserve last-known-good rendering and avoid unnecessary API pressure.
