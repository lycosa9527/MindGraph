# CrowdSec blocklist baseline

`blocklist_baseline.txt` is optional shipped data (one IP per line, `#` comments allowed). It is merged into the shared Redis blacklist at startup and after each successful AbuseIPDB blacklist sync, alongside the live CrowdSec API pull.

Refresh from your Console Raw IP List integration:

```bash
python scripts/setup/download_crowdsec_baseline.py
```

Requires `.env` with `CROWDSEC_BLOCKLIST_URL` (or `CROWDSEC_BLOCKLIST_INTEGRATION_ID`) and Basic Auth credentials. Community plans are often limited to about one download per 24 hours.
