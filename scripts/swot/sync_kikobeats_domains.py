"""
Download Kikobeats free-email-domains list into the repo (maintainer workflow).

Source: https://github.com/kikobeats/free-email-domains (MIT)
Raw JSON: https://raw.githubusercontent.com/kikobeats/free-email-domains/master/domains.json

Commit message hint: Update Kikobeats free-email domains (MIT, github.com/kikobeats/free-email-domains)
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/kikobeats/free-email-domains/master/domains.json"
OUT_REL = Path("data") / "kikobeats_free_email_domains.json"


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    out_path = root / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=120) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        print(f"Failed to download {SOURCE_URL}: {exc}", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, list):
        print("Expected a JSON array of domain strings.", file=sys.stderr)
        return 1

    out_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(data)} domains)")
    print("Attribution: MIT — github.com/kikobeats/free-email-domains (domains.json on master)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
