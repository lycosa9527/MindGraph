"""Static HTML privacy policy for crawlers (Chrome Web Store, etc.)."""

from __future__ import annotations

from html import escape
from pathlib import Path

_COMPANY_EN = "Beijing Siyuan Zhijiao Technology Co., Ltd."
_COMPANY_ZH = "北京思源智教科技有限公司"

_EXTENSION_SECTION_ID = "browser-extension"

_PLATFORM_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "5. Information we collect",
        (
            "To provide, maintain, and improve services and meet legal obligations, we may collect:",
            (
                "(1) Account and identity information: phone number, name, school or "
                "organization, role, avatar, invitation code, and account status;"
            ),
            (
                "(2) Teaching and creative content: diagrams, notes, uploaded files and "
                "images, knowledge-base documents, and collaboration content;"
            ),
            (
                "(3) Interaction and generated content: inputs, outputs, and session "
                "identifiers in MindMate and similar modules;"
            ),
            (
                "(4) Usage and log data: sign-in times, feature usage, operation logs, "
                "device type, browser information, IP address, and error logs;"
            ),
            (
                "(5) Third-party binding data: if you bind DingTalk or similar accounts, "
                "we may store binding identifiers and necessary data returned by those platforms;"
            ),
            "(6) Security and compliance data: captcha verification, abnormal sign-in detection, and audit logs.",
        ),
    ),
    (
        "6. How we use information",
        (
            (
                "We process information to provide core services (registration, diagrams, "
                "collaboration, AI conversations, export, school management), maintain security "
                "and stability, improve the product using aggregated or de-identified data where "
                "possible, comply with law, and for other purposes with your explicit consent."
            ),
            "We do not sell personally identifiable information to unrelated third parties.",
        ),
    ),
    (
        "9. Sharing, transfer, and disclosure",
        (
            (
                "We share personal information only with your consent, as required by law, as "
                "necessary to provide services through entrusted processors (AI providers, cloud "
                "infrastructure, SMS verification, etc.), or with authorized school administrators "
                "in organization deployments."
            ),
        ),
    ),
    (
        "10. Storage and retention",
        (
            (
                "Your information is generally stored within the People's Republic of China. "
                "We retain information only as long as necessary for the purposes described in "
                "this policy, unless a longer period is required by law."
            ),
        ),
    ),
    (
        "11. Your rights",
        (
            (
                "You may request access, correction, deletion, consent withdrawal, or account "
                "cancellation through in-platform feedback or your school administrator, subject "
                "to applicable law and identity verification."
            ),
        ),
    ),
    (
        "13. Information security",
        (
            (
                "We use reasonable safeguards such as access control, encryption in transit, "
                "log auditing, and role-based permissions."
            ),
            (
                "No internet environment is absolutely secure. Please protect your credentials "
                "and report suspicious security events promptly."
            ),
        ),
    ),
    (
        "18. Contact",
        (
            (
                "Questions about this policy or personal information processing may be sent "
                "through in-platform feedback or your school's platform administrator."
            ),
            (
                "Requests for self-hosting, modification, or use beyond sign-in on this Platform "
                f"require written permission from {_COMPANY_EN} ({_COMPANY_ZH})."
            ),
        ),
    ),
)

_EXTENSION_SECTION: tuple[str, tuple[str, ...]] = (
    "Appendix: MindGraph browser extension (Chrome / Edge)",
    (
        "This appendix applies to the MindGraph browser extension and supplements the Privacy Policy above.",
        (
            "The extension stores locally on your device (chrome.storage.local): MindGraph server URL, "
            "API token (mgat_…), account phone number, UI language, SmartEdu login token (synced only "
            "when you visit SmartEdu sites while signed in), and optional MindMate session cache."
        ),
        (
            "The extension reads or processes web content only when you take action: generate a mind-map "
            "PNG, extract/download documents, use MindMate “include current page content”, or save to "
            "Document Summary (File Center). We do not crawl or monitor browsing in the background."
        ),
        (
            "Extracted page text, document content, or downloaded files are sent over HTTPS to the "
            "MindGraph server you configure and verify in extension Settings, solely to perform the "
            "feature you requested. Extension API calls use Bearer token auth and do not attach web "
            "login cookies."
        ),
        (
            "The extension may fetch document assets from third-party education or CDN hosts "
            "(e.g. SmartEdu, CNKI, Baidu Wenku) when you start an extract action. We do not sell or "
            "share personally identifiable information with unrelated third parties."
        ),
        (
            "You may revoke API tokens in the MindGraph web app (Account). Uninstalling the extension "
            "or clearing its data removes locally stored credentials. SmartEdu tokens are cleared "
            "automatically when they expire (e.g. HTTP 401)."
        ),
        (
            "Use https://mg.mindspringedu.com in production and https://test.mindspringedu.com "
            "for testing. The localhost dev preset uses HTTP and is intended for trusted "
            "development machines only."
        ),
    ),
)

_PRIVACY_HTML_PATHS = (
    Path(__file__).resolve().parent.parent / "frontend" / "public" / "privacy-policy.html",
    Path(__file__).resolve().parent.parent / "static" / "privacy-policy.html",
)


def _paragraphs_html(paragraphs: tuple[str, ...]) -> str:
    return "".join(f"<p>{escape(text)}</p>" for text in paragraphs)


def _section_html(title: str, paragraphs: tuple[str, ...], section_id: str | None = None) -> str:
    id_attr = f' id="{section_id}"' if section_id else ""
    return f"<section{id_attr}><h2>{escape(title)}</h2>{_paragraphs_html(paragraphs)}</section>"


def build_privacy_policy_html() -> str:
    """Return crawlable HTML for Terms + Privacy + browser extension appendix."""
    platform_body = "".join(_section_html(title, paragraphs) for title, paragraphs in _PLATFORM_SECTIONS)
    extension_body = _section_html(
        _EXTENSION_SECTION[0],
        _EXTENSION_SECTION[1],
        section_id=_EXTENSION_SECTION_ID,
    )
    preamble = (
        f"MindGraph is an educational product developed and operated by {_COMPANY_EN} "
        f"({_COMPANY_ZH}). This document combines our Terms of Use and Privacy Policy. "
        "By using MindGraph or the MindGraph browser extension, you acknowledge that you "
        "have read and agree to this policy."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MindGraph Terms of Use &amp; Privacy Policy</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
      line-height: 1.55;
      color: #1c1917;
      background: #fafaf9;
      margin: 0;
      padding: 24px 20px 48px;
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      background: #fff;
      border: 1px solid #e7e5e4;
      border-radius: 8px;
      padding: 28px 32px 36px;
    }}
    h1 {{ font-size: 1.6rem; margin: 0 0 8px; }}
    .updated {{ color: #57534e; font-size: 0.9rem; margin: 0 0 20px; }}
    .preamble {{ margin-bottom: 24px; }}
    h2 {{ font-size: 1.1rem; margin: 24px 0 8px; }}
    p {{ margin: 0 0 10px; }}
    footer {{
      max-width: 720px;
      margin: 16px auto 0;
      color: #78716c;
      font-size: 0.85rem;
      text-align: center;
    }}
  </style>
</head>
<body>
  <main>
    <h1>MindGraph Terms of Use &amp; Privacy Policy</h1>
    <p class="updated">Last updated: 19 June 2026</p>
    <p class="preamble">{escape(preamble)}</p>
    {platform_body}
    {extension_body}
  </main>
  <footer>京ICP备2025126228号 · {_COMPANY_EN}</footer>
</body>
</html>
"""


def privacy_policy_source_path() -> Path:
    """Preferred on-disk path for the static privacy policy HTML."""
    primary = _PRIVACY_HTML_PATHS[0]
    if primary.is_file():
        return primary
    fallback = _PRIVACY_HTML_PATHS[1]
    if fallback.is_file():
        return fallback
    return primary


def write_privacy_policy_files() -> list[Path]:
    """Write static privacy HTML to frontend/public and static/."""
    html = build_privacy_policy_html()
    written: list[Path] = []
    for path in _PRIVACY_HTML_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        written.append(path)
    return written
