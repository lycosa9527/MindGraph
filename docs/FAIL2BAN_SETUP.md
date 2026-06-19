# Fail2ban + AbuseIPDB (MindGraph)

MindGraph ships **Fail2ban templates** under [`resources/fail2ban/`](../resources/fail2ban/) and a Python **`fail2ban_integration`** module for deploy and **ban → AbuseIPDB** reporting. The Fail2ban **daemon** runs on the **Linux host** (systemd), not inside the FastAPI process.

## Official AbuseIPDB + Fail2Ban tutorial

AbuseIPDB documents the **stock** integration: Fail2ban **v0.10.0+** ships `action.d/abuseipdb.conf` (curl to `POST /api/v2/report`), `action_abuseipdb` in `jail.local`, and per-jail options like `abuseipdb_apikey` and `abuseipdb_category` (e.g. **18** brute-force, **22** SSH). See **[Integrating AbuseIPDB with Fail2Ban](https://www.abuseipdb.com/fail2ban.html)** for prerequisites, activation, category table, and troubleshooting (API limits, **~15 minute** duplicate-report throttle — they suggest `bantime = 900` or higher to align with that window).

This repo’s **MindGraph + NPM** flow uses a **custom** `action.d/mindgraph-abuseipdb.conf` that calls the bundled Python reporter (reads `/etc/fail2ban/abuseipdb.conf`) so ban reports match app-side categories and you do not embed the API key in `jail.local`. If you already use AbuseIPDB’s **built-in** action for other jails (e.g. `sshd`), you can keep that; our templates target **Nginx Proxy Manager** access logs and MindGraph deploy paths.

### AbuseIPDB APIv2 reference (Python docs)

Authoritative parameter tables and examples: **[AbuseIPDB APIv2](https://docs.abuseipdb.com/?python#introduction)**.

| Area | Link |
|------|------|
| Fail2Ban `actionban` → `POST /report` (`categories`, `Key` header, URL-encoded `ip`) | [Configuring Fail2Ban](https://docs.abuseipdb.com/?python#configuring-fail2ban) |
| `GET /check` — `ipAddress`, `maxAgeInDays`, `abuseConfidenceScore`, optional `verbose` | [CHECK endpoint](https://docs.abuseipdb.com/?python#check-endpoint) |
| `GET /reports` — paginated report history for an IP | [REPORTS endpoint](https://docs.abuseipdb.com/?python#reports-endpoint) · [Reports parameters](https://docs.abuseipdb.com/?python#reports-parameters) |
| `POST /report` — submit a report (same operation as Fail2Ban; used by MindGraph lockout / ban actions) | [REPORT endpoint](https://docs.abuseipdb.com/?python#report-endpoint) · [Report parameters](https://docs.abuseipdb.com/?python#report-parameters) |

**Note:** **REPORTS** (plural) lists existing reports; **REPORT** (singular) creates one. Do not confuse them.

## Prerequisites

- `sudo apt install fail2ban` (or your distro equivalent)
- `sudo systemctl enable --now fail2ban`
- **Nginx Proxy Manager** (or another reverse proxy) access logs on disk the host can read

`scripts/setup/setup.py` **Step 9** (system verification) runs **`fail2ban-client status`** on Linux and prints **SUCCESS** or **WARNING** like Redis/Qdrant, pointing at this doc.

### Bundled CLI (check / deploy / reload)

From the MindGraph repo root on Linux (set `PYTHONPATH` or use an editable install):

```bash
python3 -m services.infrastructure.security.fail2ban_integration check
sudo PYTHONPATH="$PWD" python3 -m services.infrastructure.security.fail2ban_integration setup --npm-home /root/npm --proxy-host 1
```

Subcommands: **`check`** (status + jail + logpath), **`deploy`** (copy templates and patch MindGraph path; optional `--npm-home` / `--proxy-host`), **`reload`**, **`validate`** (`fail2ban-regex` on the configured log), **`setup`** (deploy + reload + check). Use **`--help`** on the module or each subcommand.

On **Linux**, the application runs the same checks on startup (main worker only) and **exits with copy-paste instructions** if Fail2ban is missing, the daemon is down, templates are not under `/etc/fail2ban`, or the `npm-mindgraph` jail is not loaded. Disable with **`FAIL2BAN_STARTUP_CHECK=false`** in `.env` (e.g. Docker or dev hosts without Fail2ban). Optional **`FAIL2BAN_ETC`** overrides the config root (default `/etc/fail2ban`).

For **all** launch dependencies (Redis port free, HTTP port, Qdrant, Celery, PostgreSQL hints, Tesseract): run **`python -m services.infrastructure.utils.launch_commands`** and use the printed cheatsheet.

## Nginx Proxy Manager — standard layout (same on all servers)

NPM is usually deployed from a directory we call **`NPM_HOME`** (e.g. `~/npm` or `/root/npm`). Typical **`docker-compose.yml`**:

```yaml
services:
  app:
    image: 'jc21/nginx-proxy-manager:latest'
    restart: unless-stopped
    environment:
      TZ: "Australia/Brisbane"
    ports:
      - '80:80'
      - '81:81'
      - '443:443'
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
```

On the **host**, logs live under **`NPM_HOME/data/logs/`** (because `./data` is bind-mounted to `/data` in the container). Per–proxy-host access logs use:

| File | Use for Fail2ban `logpath` |
|------|----------------------------|
| `proxy-host-<N>_access.log` | **Yes** — one file per proxy host (replace `<N>` with the ID in NPM; first proxy is often `1`). |
| `proxy-host-<N>_error.log` | Optional — separate filter if you jail on errors. |
| `fallback_http_access.log` | Fallback / default host traffic (not the same as a specific proxy). |
| `fallback_*_error.log` | Error-only; use only if you write a matching filter. |

**Canonical path** for the first proxy host on a root install:

```text
/root/npm/data/logs/proxy-host-1_access.log
```

Use your real **`NPM_HOME`** if not `/root/npm` (e.g. `/home/deploy/npm/data/logs/proxy-host-1_access.log`).

Put that exact path in **`jail.d/mindgraph-npm.local.conf`** as `logpath = ...`. Validate with:

```bash
sudo fail2ban-regex /root/npm/data/logs/proxy-host-1_access.log /etc/fail2ban/filter.d/npm-mindgraph.conf
```

## Baseline blacklist file (`data/abuseipdb/`)

The repo includes [`data/abuseipdb/blacklist_baseline.txt`](../data/abuseipdb/blacklist_baseline.txt) (comments only until you populate it). At startup, MindGraph **merges** these IPs into Redis (same set used for middleware blacklist lookup) so they persist across remote syncs. Refresh from the API:

```bash
python scripts/setup/download_abuseipdb_baseline.py
```

See [`data/abuseipdb/README.md`](../data/abuseipdb/README.md) for format and redistribution notes.

### Redis shared blacklist key (AbuseIPDB + CrowdSec + baselines)

MindGraph stores the **combined** blocklist in a single Redis **SET** key:

| Key | Contents |
|-----|----------|
| `abuseipdb:blacklist:ips` | IPs from AbuseIPDB `GET /blacklist` (replace sync), merged **`SADD`** from `data/abuseipdb/blacklist_baseline.txt`, CrowdSec Raw IP List API, and `data/crowdsec/blocklist_baseline.txt`. The prefix is historical; the set is **not** AbuseIPDB-only. |

Optional metadata: `abuseipdb:blacklist:meta` (AbuseIPDB sync), `crowdsec:blocklist:meta` (last CrowdSec pull time).

### Verifying the request hot path (one `SISMEMBER` per request)

With **`ABUSEIPDB_BLACKLIST_LOOKUP_ENABLED`** and/or CrowdSec lookup enabled, middleware calls **`SISMEMBER`** on **`abuseipdb:blacklist:ips`** once per request for the client IP (no extra Redis round trips for the blacklist check itself).

**Staging check** — in another terminal, watch commands while you hit the app:

```bash
redis-cli -u "$REDIS_URL" MONITOR
```

Trigger a request that is not skipped by middleware (not `/health`, etc.). You should see a single **`SISMEMBER`** for the blacklist key per such request. `GET`/`SET` on other keys may appear from sessions, rate limits, etc.

Optional: set **`IP_REPUTATION_SISMEMBER_CACHE_TTL_SECONDS`** (see [`env.example`](../env.example)) to a small value (e.g. `2`). The TTL is read **once at startup** (with the SISMEMBER in-process cache); within that window the **same canonical client IP** can skip a Redis round trip. Entries can be briefly stale until TTL expires or the cache is cleared after a successful blocklist sync. Restart the process to change this variable.

After Redis connects, the app **snapshots** AbuseIPDB/CrowdSec lookup-related env flags once (`ip_reputation_env_snapshot`) so the middleware hot path does not re-parse `os.getenv` on every request. Restart the process to pick up `.env` changes.

## 1. AbuseIPDB in MindGraph (application)

Configure [`env.example`](../env.example) → `.env`:

- `ABUSEIPDB_ENABLED=true`
- `ABUSEIPDB_API_KEY=...`
- **`ABUSEIPDB_CHECK_ENABLED=false`** (default) — no live **`GET /check`** calls; blocks use the **daily blacklist** (plus baseline file) in Redis only. Set **`true`** only if you want per-IP reputation checks (counts against AbuseIPDB **check** quota, with Redis cache).
- Optional: `ABUSEIPDB_BLACKLIST_SYNC_ENABLED`, thresholds, TTLs

Daily **blacklist sync** runs in the app (Redis lock) when enabled; **middleware** blocks IPs in the synced Redis set. **Lockout** and **Fail2ban** can still **`POST /report`** when those features fire (separate quota from checks).

**When sync runs:** The blocklist scheduler uses the same clock as automated DB backups — **`BACKUP_HOUR`** (default **3** = 03:00 local time), so logs line up with backup/COS activity. It does not use `ABUSEIPDB_BLACKLIST_SYNC_INTERVAL_SECONDS` for timing; that variable still **clamps** to at least **86400** seconds (24h) for AbuseIPDB API semantics unless **`ABUSEIPDB_BLACKLIST_SYNC_RELAX_MIN_INTERVAL=true`**. AbuseIPDB **Standard** tier allows **5** `GET /blacklist` calls per day ([rate limits](https://docs.abuseipdb.com/?python#api-daily-rate-limits)). On **HTTP 429**, the scheduler waits **`Retry-After`** (or 3600s) before retrying and logs rate-limit headers.

## 2. Deploy Fail2ban templates

From the MindGraph repo root (Linux):

```bash
export MINDGRAPH_ROOT=/path/to/MindGraph
chmod +x scripts/deploy/fail2ban_sync.sh
sudo env MINDGRAPH_ROOT="$MINDGRAPH_ROOT" ./scripts/deploy/fail2ban_sync.sh
```

Or copy manually:

```bash
sudo cp -r resources/fail2ban/filter.d/* /etc/fail2ban/filter.d/
sudo cp -r resources/fail2ban/jail.d/* /etc/fail2ban/jail.d/
sudo cp -r resources/fail2ban/action.d/* /etc/fail2ban/action.d/
```

`deploy_fail2ban_templates` and the script above **overwrite** same-named files under `/etc/fail2ban/` — back up local edits before redeploying.

### Edit before `fail2ban-client reload`

1. **`jail.d/mindgraph-npm.local.conf`**
   - Set `logpath` to **`NPM_HOME/data/logs/proxy-host-<N>_access.log`** (see [Nginx Proxy Manager — standard layout](#nginx-proxy-manager--standard-layout-same-on-all-servers) above). The repo ships **`enabled = true`**; set **`enabled = false`** if you need the jail off until paths are correct.
   - **Firewall + AbuseIPDB (default):** the jail chains **`%(action_)s`** (your distro’s default ban action, e.g. iptables/nftables) with **`mindgraph-abuseipdb`**. Without the first line, Fail2ban would only run the Python reporter and **not** add kernel firewall rules. If `fail2ban-client reload` errors on `action_`, run `sudo fail2ban-client -d` and align with your `/etc/fail2ban/jail.local` / `[DEFAULT]` (some installs use `nftables` vs `iptables`).
   - **Report-only:** if blocking is done elsewhere (CDN, upstream), replace the `action` block with a single line `action = mindgraph-abuseipdb`.

2. **`action.d/mindgraph-abuseipdb.conf`**
   - Replace **`/CHANGE/ME/MindGraph`** with the **absolute path** to your MindGraph clone (same string used in `cd` for `python3 -m ...`).
   - **Miniconda:** Fail2ban runs with a minimal environment; point `actionban` at your conda env Python (e.g. `~/miniconda3/envs/mindgraph/bin/python`) as in the comment block in the action file, or symlink that interpreter as `python3` on the server.

3. **API key for ban reports** (Fail2ban does not read `.env`):

   ```bash
   sudo install -m 600 /dev/null /etc/fail2ban/abuseipdb.conf
   sudo sh -c 'echo "KEY=YOUR_ABUSEIPDB_API_KEY" >> /etc/fail2ban/abuseipdb.conf'
   ```

   See [`resources/fail2ban/abuseipdb.conf.example`](../resources/fail2ban/abuseipdb.conf.example).

### Validate filter

```bash
sudo fail2ban-regex /full/path/to/proxy-host-1_access.log /etc/fail2ban/filter.d/npm-mindgraph.conf
```

### Reload

```bash
sudo fail2ban-client reload
sudo fail2ban-client status npm-mindgraph
```

## 3. Test AbuseIPDB CLI (ban report)

```bash
cd /path/to/MindGraph
export PYTHONPATH="$PWD"
python3 -m services.infrastructure.security.fail2ban_integration.report_ban 198.51.100.1
```

Or use [`scripts/fail2ban_report_ban.sh`](../scripts/fail2ban_report_ban.sh) with `MINDGRAPH_ROOT` set.

## 4. Optional: `allowipv6` warning

If logs show `'allowipv6' not defined`, add to `/etc/fail2ban/jail.local`:

```ini
[DEFAULT]
allowipv6 = auto
```

## 5. Notes

- **Blacklist API** may require an AbuseIPDB subscription; if sync returns HTTP 403/401, the app logs and continues; **check** + **report** still work per your plan. **HTTP 429** on `/blacklist`, `/check`, or `/report` is logged with **`Retry-After`** and **`X-RateLimit-*`** when present.
- Tighten `failregex` after inspecting real NPM log lines to avoid blocking legitimate users (e.g. many 401s).
