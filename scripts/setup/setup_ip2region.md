# IP2Region and dashboard assets setup

## Overview

MindGraph uses **local** IP geolocation (`services/auth/ip_geolocation.py`) with:

- **xdb databases**: `data/ip2region_v4.xdb` (required), `data/ip2region_v6.xdb` (optional)
- **Patch overrides**: `data/ip2region_issue/*.fix` → `data/ip2region_patches_cache.json`
- **Public dashboard static assets** (if you use `static/` ECharts + map): `static/js/echarts.min.js`, `static/data/china-geo.json`, optional embed into `static/js/public-dashboard.js`

## One-command install (recommended)

From the repository root:

```bash
python scripts/setup/dashboard_install.py
```

The script **asks yes/no questions** (pip, static assets, embed, xdb, IPv6, patches, re-download). Press Enter to accept the default shown in `[Y/n]` or `[y/N]`.

**Automation (no prompts):** set `MINDGRAPH_NON_INTERACTIVE=1`. Defaults: install pip package, dashboard assets, IPv4 xdb, patches; skip IPv6 xdb (large).

**Optional path override:** `MINDGRAPH_PROJECT_ROOT=/path/to/MindGraph`

The Vue frontend also bundles **echarts** via npm (`frontend/`); the script targets **legacy/static** dashboard files under `static/` when present.

## Manual database placement

If you do not run the script:

1. Open [ip2region data](https://github.com/lionsoul2014/ip2region/tree/master/data)
2. Copy `ip2region_v4.xdb` (and optionally `ip2region_v6.xdb`) into the project `data/` directory

## Database updates

Refresh periodically (monthly recommended): run the script again and choose to re-download when asked, or replace the xdb files under `data/` manually.

## Verification

After setup, restart the app and check logs for `[IPGeo]` lines, or hit APIs that use geolocation.
