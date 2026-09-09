# Changelog

## v1.7.0

- Promoted v1.7.0-rc3 to the final release after clean-host installation, MXN-default, EUR-secondary-fiat, visual, cache-recovery, and uninstall/restore QA passed.
- No functional changes from the validated RC3 runtime; release metadata and version labels only.

## v1.7.0-rc3

- Restored configurable secondary BTC fiat with `secondary_fiat=MXN` as the default.
- CoinGecko requests and the rendered currency label now follow the selected fiat code.
- Added cache currency identity handling so a previous MXN cache cannot be mislabeled after switching fiat.
- Invalid or unsupported configured fiat codes fail validation instead of silently displaying the wrong currency.
- Documented G8-era major currencies and currencies used by the 2025 top-10 crypto-adoption markets as examples.
- Retained the legacy static MXN fallback only for `secondary_fiat=MXN`; it is never reused for another fiat.

## v1.7.0-rc2

- Fixed fresh-install success path incorrectly returning exit code 1.
- Sanitized public defaults and documentation to remove environment-specific identity/location markers.
- Changed the secondary BTC fiat display to MXN.
- Default coin table now contains the five highest-cap non-stablecoin altcoins at release: ETH, BNB, XRP, SOL, and TRX.
- Expanded generic OPSEC tests for private IPv4 ranges, home-directory paths, and `.home.arpa` names.

## v1.7.0-rc1

Public-release staging candidate based on the field-tested v1.6.3-r3 functional core.

- Added safe fresh-clone installer and cron deployment path.
- Public default uses host cron every 10 minutes with `internal_scheduler=off`.
- Added patient 180-second health readiness loop.
- Added root `SECURITY.md`, complete configuration/technical docs, Kindle setup, release process, and contribution guide.
- Removed systemd-timer instructions from the public deployment path.
- Added Git/Container ignore rules and CI/OPSEC checks.
- Weather failure logs no longer include exception URLs, reducing risk of API-key query strings appearing in logs.
- Application functional data-fetch/cache/render architecture otherwise remains based on v1.6.3-r3.

## v1.6.3-r3

- Proven deployment profile moved refresh ownership to host cron every 10 minutes.
- Internal application scheduler disabled in the validated production configuration.

## v1.6.3-r2

- Packaging fixed to extract into a top-level directory and exclude generated runtime artifacts.

## v1.6.3-r1

- Installer syntax-check bytecode moved out of the root-owned application directory.

## v1.6.3

- Added config-driven price, candle, ATH, and page-refresh intervals.
- Replaced hardcoded ATH TTL with `ath_refresh_hours`.
- Added split caches, `/status.json`, last-known-good rendering, BTC provider fallback, CoinGecko list skip/cache logic, refresh locking, and atomic PNG writes.

## v1.6.2

- Restored 800×600 PNG renderer and hardened Docker deployment.
