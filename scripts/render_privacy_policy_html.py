"""Write crawlable privacy-policy.html for Chrome Web Store and /privacy."""

from __future__ import annotations

from utils.privacy_policy_static import write_privacy_policy_files


def main() -> None:
    """Generate static privacy policy HTML files."""
    paths = write_privacy_policy_files()
    for path in paths:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
