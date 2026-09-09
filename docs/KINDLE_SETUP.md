# Kindle Setup

The server renders an 800×600 grayscale PNG and a minimal HTML wrapper. Exact Kindle browser behavior varies by model and firmware, but the basic setup is intentionally simple.

1. Put the Kindle on the same trusted LAN as the server.
2. Complete the server installation and note the URL printed by `install.sh`.
3. Open that URL in the Kindle browser.
4. Leave the page open. The HTML wrapper reloads according to `page_refresh_minutes` (11 minutes by default).

For the cleanest display, use landscape/portrait orientation and browser zoom settings appropriate for the Kindle model. The rendered asset itself is always 800×600 in this release.

## Direct PNG

The raw image is available at:

```text
http://YOUR_LAN_IP:8787/kindle_btc_price.png
```

The root `/` page is usually preferable because it includes automatic page refresh.
