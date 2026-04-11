# AbuseIPDB blacklist baseline (optional)

## Purpose

`blacklist_baseline.txt` is a **shipped or operator-maintained** list of IPs (one per line) merged into Redis set `abuseipdb:blacklist:ips` at **startup** and again after each **successful** remote `/blacklist` sync, so a static baseline is not wiped when the API refreshes the set.

## Format

- One **IPv4 or IPv6** per line
- Lines starting with `#` and blank lines are ignored

## Refresh from AbuseIPDB API

```bash
python scripts/setup/download_abuseipdb_baseline.py
```

Requires `ABUSEIPDB_API_KEY` and an API plan that includes the blacklist endpoint.

## Legal

Review AbuseIPDB terms before redistributing bulk blacklist data.
