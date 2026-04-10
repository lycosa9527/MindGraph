"""Report SMS/SES-related ERRORS keys in messages.py missing zh/en/az."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / "models" / "domain" / "messages.py").read_text(encoding="utf-8")
lines = TEXT.splitlines()

KEYWORDS = (
    "sms",
    "email",
    "phone_not_registered",
    "verification_",
    "too_many_sms",
    "too_many_email",
    "registration_email",
    "email_login",
    "login_email",
)


def is_sms_email_key(name: str) -> bool:
    return any(k in name for k in KEYWORDS)


def main() -> None:
    in_errors = False
    current_key: str | None = None
    block: list[str] = []
    missing: list[tuple[str, str]] = []
    sms_email_keys: list[str] = []

    for line in lines:
        if line.strip().startswith("ERRORS = {"):
            in_errors = True
            continue
        if in_errors and line.strip().startswith("SUCCESS = {"):
            break
        if not in_errors:
            continue
        m = re.match(r'\s+"([a-z0-9_]+)":\s*\{', line)
        if m:
            if current_key and block:
                body = "\n".join(block)
                if is_sms_email_key(current_key):
                    sms_email_keys.append(current_key)
                    for lang in ("zh", "en", "az"):
                        if f'"{lang}":' not in body:
                            missing.append((current_key, lang))
            current_key = m.group(1)
            block = [line]
            continue
        if current_key:
            block.append(line)

    if current_key and block:
        body = "\n".join(block)
        if is_sms_email_key(current_key):
            sms_email_keys.append(current_key)
            for lang in ("zh", "en", "az"):
                if f'"{lang}":' not in body:
                    missing.append((current_key, lang))

    print("SMS/email-related ERRORS keys:", len(set(sms_email_keys)))
    print("Entries missing zh, en, or az:", len(missing))
    for item in missing:
        print(" ", item[0], "-> missing", item[1])


if __name__ == "__main__":
    main()
