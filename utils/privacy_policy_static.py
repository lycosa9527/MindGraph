"""Static HTML privacy policy for crawlers (Chrome Web Store, etc.)."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import NamedTuple

from services.infrastructure.utils.search_indexing import SEARCH_DESCRIPTION

_COMPANY_EN = "Beijing Siyuan Zhijiao Technology Co., Ltd."
_COMPANY_ZH = "北京思源智教科技有限公司"

_USER_AGREEMENT_SECTION_ID = "user-agreement"
_PRIVACY_POLICY_SECTION_ID = "privacy-policy"
_EXTENSION_SECTION_ID = "browser-extension"


class _HtmlSection(NamedTuple):
    title: str
    paragraphs: tuple[str, ...]
    section_id: str = ""


# Full English text matches frontend/src/content/authSoftwareAgreement.ts.
# Numbering is continuous: 1–4 terms, 5–18 privacy and remaining terms.
_PLATFORM_SECTIONS: tuple[_HtmlSection, ...] = (
    _HtmlSection(
        "1. Acceptance and scope",
        (
            (
                f"This document is a legal agreement between you and {_COMPANY_EN} ({_COMPANY_ZH}) "
                "regarding your use of MindGraph and related services, and explains how we process "
                "your personal information and related data."
            ),
            (
                "If you do not agree, do not use the Platform. If you use the Platform on behalf of "
                "a school or organization, you represent that you are authorized to bind that "
                "organization to this document."
            ),
            (
                "If your school or organization has signed a separate written service agreement with "
                "us, that agreement prevails where it conflicts with this document; otherwise this "
                "document applies."
            ),
        ),
        _USER_AGREEMENT_SECTION_ID,
    ),
    _HtmlSection(
        "2. Services",
        (
            (
                "The Platform provides AI-assisted diagram generation, knowledge organization, "
                "MindMate conversations, collaboration, third-party integrations, and related "
                "educational tools. Available features may change over time."
            ),
            (
                'The Platform is provided "as is". We work to keep it stable and secure but do not '
                "guarantee uninterrupted, error-free service or that it will meet every specific "
                "teaching need."
            ),
            (
                "AI-generated content is for reference only and is not professional advice. You "
                "should independently verify accuracy and suitability in your teaching practice."
            ),
        ),
    ),
    _HtmlSection(
        "3. Your responsibilities and accounts",
        (
            (
                "Provide accurate registration information and keep your account credentials secure. "
                "You are responsible for activity under your account."
            ),
            (
                "Do not use the Platform to create or distribute unlawful, infringing, false, "
                "harassing, or otherwise harmful content, or to disrupt the Platform or others' rights."
            ),
            (
                "If you upload, input, or generate content involving student or other personal "
                "information, ensure you have required authorization from the school, guardians, or "
                "other rights holders, and upload only what is necessary for teaching purposes."
            ),
        ),
    ),
    _HtmlSection(
        "4. Intellectual property and proprietary license",
        (
            (
                f"MindGraph and its software, interface design, trademarks, documentation, algorithms, "
                f"and related technology are owned by {_COMPANY_EN} ({_COMPANY_ZH}) or respective "
                "rights holders."
            ),
            (
                "MindGraph is protected by a Proprietary License and is not open-source software. "
                "Without authorization, you may not run, modify, copy, distribute, commercially "
                "exploit, or create derivative works."
            ),
            (
                "Except for sign-in use expressly authorized through this Platform under this "
                "document, any use of the software or related materials (including self-hosting, "
                "modification, sublicensing, independent operation inside or outside schools, or use "
                "in competitions, training, or publications) requires prior written permission from "
                "the Company."
            ),
            (
                "Copyright and other lawful rights in teaching content you upload or generate remain "
                "yours or belong to respective rights holders. You grant us a non-exclusive license "
                "to use such content as reasonably necessary to provide services, perform this "
                "document, and conduct statistical analysis. Without our permission, you may not use "
                "Platform data to compete with the Platform, bulk-scrape, or harm Platform security "
                "or stability."
            ),
        ),
    ),
    _HtmlSection(
        "5. Information we collect",
        (
            "To provide, maintain, and improve services and meet legal obligations, we may collect:",
            (
                "(1) Account and identity information: phone number, name, school or organization, "
                "role, avatar, invitation code, and account status;"
            ),
            (
                "(2) Teaching and creative content: diagrams, notes, uploaded files and images, "
                "knowledge-base documents, and collaboration content;"
            ),
            (
                "(3) Interaction and generated content: inputs, outputs, and session identifiers in "
                "MindMate and similar modules (exact scope depends on product features);"
            ),
            (
                "(4) Usage and log data: sign-in times, feature usage, operation logs, device type, "
                "browser information, IP address, and error logs;"
            ),
            (
                "(5) Third-party binding data: if you bind DingTalk or similar accounts, we may store "
                "binding identifiers and necessary data returned by those platforms;"
            ),
            ("(6) Security and compliance data: captcha verification, abnormal sign-in detection, and audit logs."),
        ),
        _PRIVACY_POLICY_SECTION_ID,
    ),
    _HtmlSection(
        "6. How we use information",
        (
            "We process information for the following purposes:",
            (
                "(1) Core services: registration and sign-in, diagram generation and storage, "
                "collaboration, AI conversations, export, and school or organization management;"
            ),
            (
                "(2) Security and stability: authentication, troubleshooting, fraud and abuse "
                "prevention, and system maintenance;"
            ),
            (
                "(3) Product improvement: statistical analysis, feature optimization, and model "
                "evaluation (preferably using de-identified or aggregated data);"
            ),
            ("(4) Compliance with applicable laws and lawful requests from regulators or judicial authorities;"),
            "(5) Other purposes with your separate explicit consent.",
            (
                "We process information only as necessary for these purposes and take reasonable "
                "steps to reduce the risk of identifying specific individuals."
            ),
        ),
    ),
    _HtmlSection(
        "7. Educational research use",
        (
            (
                "To improve teaching quality, learning experience, educational research, and product "
                "development, we may analyze Platform data in compliance with applicable law, "
                "including to:"
            ),
            ("(1) aggregate usage and feature outcomes for teaching research and product improvement;"),
            (
                "(2) use de-identified or non-personally identifiable data for academic research, "
                "publications, or industry reports in education;"
            ),
            "(3) evaluate AI-assisted teaching effectiveness using anonymized or aggregated data.",
            (
                "If research requires personally identifiable information, we will obtain your "
                "separate explicit consent, or ensure that a school or other lawful controller has "
                "provided the required authorization."
            ),
        ),
    ),
    _HtmlSection(
        "8. Third-party services and processors",
        (
            (
                "To operate the Platform, we may use third-party services and share necessary "
                "information with them, such as:"
            ),
            "(1) large-model and AI inference providers (for generation, understanding, and analysis);",
            "(2) collaboration and messaging platforms (such as DingTalk);",
            "(3) cloud infrastructure, databases, caches, search, and object storage services;",
            "(4) SMS verification, security, and other technical service providers.",
            (
                "We require third parties to process information within the entrusted scope and apply "
                "reasonable security measures. Specific providers and scope may change as our business "
                "evolves; we will update this document or provide in-product notice for material "
                "changes where practical."
            ),
        ),
    ),
    _HtmlSection(
        "9. Sharing, transfer, and disclosure",
        (
            (
                "We do not sell personally identifiable information to unrelated third parties. Except "
                "as described below, we do not share your personal information with third parties:"
            ),
            "(1) with your explicit consent;",
            (
                "(2) as required by applicable law, litigation/arbitration, or lawful requests from "
                "government or judicial authorities;"
            ),
            (
                "(3) as necessary to perform this document or provide services, including to third "
                "parties listed in Section 8;"
            ),
            (
                "(4) in school or organization deployments, to authorized administrators of your "
                "organization for duties within their management scope."
            ),
            (
                "If a merger, acquisition, or asset transfer occurs, we will require the successor to "
                "remain bound by this document or obtain your consent again."
            ),
        ),
    ),
    _HtmlSection(
        "10. Storage and retention",
        (
            (
                "Your information is generally stored within the People's Republic of China. We retain "
                "information only as long as necessary for the purposes described in this document, "
                "unless a longer period is required by law or agreed with you."
            ),
            (
                "After account cancellation, school contract termination, or when processing purposes "
                "are fulfilled, we will delete or anonymize relevant information as required by law, "
                "except where retention is legally required. Data in backups may be deleted later, but "
                "we will stop processing it except for storage and security protection."
            ),
        ),
    ),
    _HtmlSection(
        "11. Your rights",
        (
            "Under applicable law, you may have the following rights regarding personal information:",
            (
                "(1) access and copy: learn what information we hold about you through account "
                "settings or your platform administrator;"
            ),
            "(2) correction and supplementation: request correction or supplementation if information is inaccurate;",
            "(3) deletion: request deletion where legal conditions are met;",
            (
                "(4) withdraw consent: withdraw consent for specific processing, without affecting "
                "prior processing based on consent;"
            ),
            (
                "(5) account cancellation: request account cancellation and we will handle related "
                "data as required by law."
            ),
            (
                "Contact us through in-platform feedback or your school administrator to exercise "
                "these rights. We will respond within a reasonable period and may verify your identity "
                "for security."
            ),
        ),
    ),
    _HtmlSection(
        "12. Minors and student personal information",
        (
            (
                "The Platform is primarily intended for teachers and school staff. If students use the "
                "Platform directly or indirectly, schools and teachers must ensure lawful authorization "
                "from guardians or the school, and avoid uploading student personal information beyond "
                "what is necessary for teaching."
            ),
            (
                "We do not knowingly collect personal information from children under 14 without "
                "guardian consent or valid school authorization. If you believe we have collected such "
                "information improperly, contact us for deletion."
            ),
        ),
    ),
    _HtmlSection(
        "13. Information security",
        (
            (
                "We use reasonable safeguards such as access control, encryption in transit, log "
                "auditing, and role-based permissions, and we continue to improve our security posture."
            ),
            (
                "Despite reasonable measures, no internet environment is absolutely secure. Please "
                "protect your credentials and report suspicious security events promptly."
            ),
            (
                "If a personal information security incident occurs, we will activate our response plan "
                "as required by law and inform you of the general situation, potential impact, and "
                "measures taken by reasonable means."
            ),
        ),
    ),
    _HtmlSection(
        "14. Changes, suspension, and termination",
        (
            (
                "We may suspend or discontinue some or all services for maintenance, upgrades, "
                "compliance, or force majeure, and will try to provide advance notice when practical."
            ),
            (
                "If you materially breach this document or applicable law, we may restrict, suspend, or "
                "terminate your access and retain records as required by law."
            ),
        ),
    ),
    _HtmlSection(
        "15. Disclaimer",
        (
            (
                "To the maximum extent permitted by law, we are not liable beyond legal requirements "
                "for losses caused by force majeure, third-party failures, network interruption, or "
                "your own actions."
            ),
            (
                "You are responsible for disputes, infringement claims, or teaching decisions arising "
                "from content you upload, publish, or rely on from AI-generated output, except where "
                "applicable law provides otherwise."
            ),
        ),
    ),
    _HtmlSection(
        "16. Revisions",
        (
            (
                "We may revise this document as our business or legal obligations change. Updated "
                "versions will be published on the Platform; continued use means acceptance. For "
                "material changes affecting your significant rights, we will notify you by dialog, "
                "in-product notice, or other reasonable means."
            ),
        ),
    ),
    _HtmlSection(
        "17. Governing law and dispute resolution",
        (
            (
                "This document is governed by the laws of the mainland of the People's Republic of "
                "China (excluding conflict-of-law rules)."
            ),
            (
                "Disputes arising from or relating to this document should first be resolved through "
                "friendly negotiation. If negotiation fails, either party may bring suit in a court "
                "with jurisdiction at the Company's domicile."
            ),
        ),
    ),
    _HtmlSection(
        "18. Contact",
        (
            (
                "Questions, complaints, or requests regarding this document, personal information "
                "processing, or software licensing may be sent through in-platform feedback or your "
                "school's platform administrator."
            ),
            (
                "Requests for self-hosting, modification, or any use beyond sign-in on this Platform "
                f"require written permission from {_COMPANY_EN} ({_COMPANY_ZH})."
            ),
        ),
    ),
)

_EXTENSION_SECTION: tuple[str, tuple[str, ...]] = (
    "Appendix: MindGraph browser extension",
    (
        "This appendix applies to the MindGraph browser extension and supplements the Privacy Policy above.",
        (
            "The extension stores locally on your device (chrome.storage.local): MindGraph server URL, "
            "API token (mgat_…), account phone number, UI language, education-platform session tokens "
            "(synced only when you visit matching sites while signed in), and optional MindMate session cache."
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
            "The extension may fetch document assets from third-party education or CDN hosts that you "
            "open and are authorized to access, only when you start an extract action. We do not sell "
            "or share personally identifiable information with unrelated third parties."
        ),
        (
            "You may revoke API tokens in the MindGraph web app (Account). Uninstalling the extension "
            "or clearing its data removes locally stored credentials. Education-platform session tokens "
            "are cleared automatically when they expire (e.g. HTTP 401)."
        ),
        (
            "Use https://mg.mindspringedu.com in production. The localhost dev preset uses HTTP and "
            "is intended for trusted development machines only."
        ),
        (
            "Use of information received through this extension adheres to the Chrome Web Store User "
            "Data Policy, including the Limited Use requirements, and to Microsoft Edge Add-ons "
            "personal-information rules: data is used only to provide or improve the single disclosed "
            "purpose above, not for personalized ads, and is not sold to data brokers."
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
    platform_body = "".join(
        _section_html(section.title, section.paragraphs, section.section_id or None) for section in _PLATFORM_SECTIONS
    )
    extension_body = _section_html(
        _EXTENSION_SECTION[0],
        _EXTENSION_SECTION[1],
        section_id=_EXTENSION_SECTION_ID,
    )
    preamble = (
        "MindGraph (Mind Platform, 迈特教研) is an educational product developed and operated by "
        f"{_COMPANY_EN} ({_COMPANY_ZH}). This document combines our Terms of Use and Privacy Policy. "
        "By using MindGraph or the MindGraph browser extension, you acknowledge that you "
        "have read and agree to this policy."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="{escape(SEARCH_DESCRIPTION)}" />
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
