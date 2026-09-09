# Changelog

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
