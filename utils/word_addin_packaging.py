"""Production Word add-in packaging: hosted shell URLs + deploy zip (manifest)."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORD_ADDIN_DIR = _PROJECT_ROOT / "word-addin"
MANIFEST_TEMPLATE = WORD_ADDIN_DIR / "manifest.xml"
DEFAULT_OUTPUT = WORD_ADDIN_DIR / "dist" / "mindgraph-word-addin.zip"

_DEV_ORIGIN = "https://localhost:3000"
_SHELL_PREFIX = "/word-addin"

# Stable production add-in Id (must differ from repo/dev Id so npm start cannot
# overwrite Install.cmd's WEF Developer registry value).
PRODUCTION_ADDIN_ID = "a8f3c2e1-4b5d-6e7f-8901-23456789abcd"
PRODUCTION_DISPLAY_NAME = "MindGraph"

_ALWAYS_APP_DOMAINS = (
    "https://test.mindspringedu.com",
    "https://mg.mindspringedu.com",
    "https://365.kdocs.cn",
)

_SCRIPTS_DIR = WORD_ADDIN_DIR / "scripts"
_WINDOWS_DIR = _SCRIPTS_DIR / "windows"
_MAC_DIR = _SCRIPTS_DIR / "mac"

# (source dir, arcname relative to zip root, unix_executable)
_DEPLOY_SCRIPTS: tuple[tuple[Path, str, bool], ...] = (
    (_WINDOWS_DIR / "Install.cmd", "windows/Install.cmd", False),
    (_WINDOWS_DIR / "Uninstall.cmd", "windows/Uninstall.cmd", False),
    (
        _WINDOWS_DIR / "Install-MindGraphWordAddin.ps1",
        "windows/Install-MindGraphWordAddin.ps1",
        False,
    ),
    (_MAC_DIR / "Install.command", "mac/Install.command", True),
    (_MAC_DIR / "Uninstall.command", "mac/Uninstall.command", True),
    (
        _MAC_DIR / "Install-MindGraphWordAddin.sh",
        "mac/Install-MindGraphWordAddin.sh",
        True,
    ),
)

_README_MD = """# MindGraph for Word — install

The add-in UI is hosted on your MindGraph server. **No Node.js.**

```
mindgraph-word-addin/
├── README.md          ← this file
├── manifest.xml       ← shared Office manifest (do not edit)
├── windows/           ← Windows 10 / Windows 11
│   ├── Install.cmd
│   ├── Uninstall.cmd
│   └── Install-MindGraphWordAddin.ps1
└── mac/               ← macOS
    ├── Install.command
    ├── Uninstall.command
    └── Install-MindGraphWordAddin.sh
```

## Windows 10 / Windows 11 (each PC, once)

Requires desktop **Microsoft Word** (Microsoft 365 or Office 2016+). No admin rights.

1. Unzip anywhere (Desktop is fine)
2. Open **`windows\\Install.cmd`** (double-click)
3. Installer copies the manifest to  
   `%LOCALAPPDATA%\\MindGraph\\WordAddin\\manifest.xml`  
   and registers that path — **you may delete the unzip folder**
4. Installer closes Word if it was open, then relaunches it
5. **Open or create a document** (custom tabs often hide on the blank start screen)
6. **MindGraph** ribbon → **Settings** → server + phone + `mgat_` → Save

Remove: run **`windows\\Uninstall.cmd`** from the zip (or keep a copy of `windows\\`), or delete  
`%LOCALAPPDATA%\\MindGraph\\WordAddin` after clearing the WEF Developer registry entry via Uninstall.cmd.

## macOS (each Mac, once)

Requires desktop **Microsoft Word for Mac** (Microsoft 365). No admin rights.

1. Unzip anywhere
2. Open **`mac/Install.command`** (double-click; allow Terminal if asked).  
   If blocked: right-click → Open, or in Terminal:
   `chmod +x mac/*.command mac/*.sh && open mac/Install.command`
3. Quit Word completely (**Word → Quit**), reopen, open a document
4. **MindGraph** ribbon (or **Home → Add-ins**)
5. **Settings** → server + phone + `mgat_` → Save

Mac install **copies** the manifest into Word’s `wef` folder — **you may delete the unzip folder**.  
Remove: double-click **`mac/Uninstall.command`**.

## School Microsoft 365 admin (optional)

Works for Windows and Mac teachers in the tenant:

1. Admin center → **Settings** → **Integrated apps** → **Upload custom apps**
2. Upload root **`manifest.xml`** → assign users/groups
3. Teachers only open Word (skip `windows/` / `mac/` scripts)

## Requirements

| Supported | Not this package |
|-----------|------------------|
| Windows 10 + desktop Word | Word Online alone |
| Windows 11 + desktop Word | Word for iPad (different deploy) |
| macOS + Word for Mac | |

MindGraph site must be **HTTPS**.
"""


def normalize_public_origin(origin: str) -> str:
    """Normalize a public site origin (no trailing slash)."""
    cleaned = (origin or "").strip().rstrip("/")
    if not cleaned:
        raise ValueError("public origin is required")
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"
    return cleaned


def build_production_manifest_xml(public_origin: str) -> str:
    """
    Rewrite the repo manifest so all add-in shell URLs use ``{origin}/word-addin/...``.

    The SPA (MindMate / MindGraph pages) still lives on the same MindGraph host;
    AppDomains include that origin plus known production hosts.
    """
    origin = normalize_public_origin(public_origin)
    if not MANIFEST_TEMPLATE.is_file():
        raise FileNotFoundError(str(MANIFEST_TEMPLATE))
    raw = MANIFEST_TEMPLATE.read_text(encoding="utf-8")
    shell = f"{origin}{_SHELL_PREFIX}"

    # Distinct production Id / labels (repo template is localhost "MindGraph Dev").
    rewritten = re.sub(
        r"<Id>[^<]+</Id>",
        f"<Id>{PRODUCTION_ADDIN_ID}</Id>",
        raw,
        count=1,
    )
    rewritten = re.sub(
        r'(<DisplayName\s+DefaultValue=")[^"]*(")',
        rf"\g<1>{PRODUCTION_DISPLAY_NAME}\2",
        rewritten,
        count=1,
    )
    for resid in (
        "GetStarted.Title",
        "Tab.Label",
        "Group.Label",
    ):
        rewritten = re.sub(
            rf'(<bt:String id="{re.escape(resid)}" DefaultValue=")[^"]*(")',
            rf"\g<1>{PRODUCTION_DISPLAY_NAME}\2",
            rewritten,
            count=1,
        )

    # AppDomain must be an origin (scheme + host [+ port]), never a path.
    # Rewrite loopback AppDomains to the public origin BEFORE replacing asset
    # URLs with ``{origin}/word-addin`` — a blind replace would turn
    # ``https://localhost:3000`` into ``https://host/word-addin``, which Office
    # rejects (add-in installs but CustomTab never appears on the ribbon).
    rewritten = re.sub(
        r"<AppDomain>https?://(?:localhost|127\.0\.0\.1)(?::\d+)?/?</AppDomain>",
        f"<AppDomain>{origin}</AppDomain>",
        rewritten,
    )
    rewritten = rewritten.replace(_DEV_ORIGIN, shell)

    # Rebuild AppDomains: unique origins only (no paths, no loopback).
    preferred = [origin, *_ALWAYS_APP_DOMAINS]
    unique_domains: list[str] = []
    for host in preferred:
        if host not in unique_domains:
            unique_domains.append(host)
    domains_xml = (
        "  <AppDomains>\n"
        + "".join(f"    <AppDomain>{host}</AppDomain>\n" for host in unique_domains)
        + "  </AppDomains>"
    )
    rewritten, domain_subs = re.subn(
        r"  <AppDomains>.*?</AppDomains>",
        domains_xml,
        rewritten,
        count=1,
        flags=re.DOTALL,
    )
    if domain_subs != 1:
        raise RuntimeError("production manifest rewrite failed (AppDomains block)")

    if f"{shell}/src/taskpane/mindgraph.html" not in rewritten:
        raise RuntimeError("production manifest rewrite failed (mindgraph URL missing)")
    if f"<AppDomain>{shell}</AppDomain>" in rewritten:
        raise RuntimeError("production manifest rewrite failed (path AppDomain)")
    if f"<AppDomain>{origin}</AppDomain>" not in rewritten:
        raise RuntimeError("production manifest rewrite failed (origin AppDomain missing)")
    if f"<Id>{PRODUCTION_ADDIN_ID}</Id>" not in rewritten:
        raise RuntimeError("production manifest rewrite failed (production Id missing)")
    if "MindGraph Dev" in rewritten:
        raise RuntimeError("production manifest rewrite failed (dev label left in)")
    if _DEV_ORIGIN in rewritten:
        raise RuntimeError("production manifest rewrite failed (localhost URL left in)")
    return rewritten


def _zip_write_file(
    archive: zipfile.ZipFile,
    source: Path,
    arcname: str,
    *,
    unix_executable: bool = False,
) -> None:
    """Add a file to the zip; optionally set Unix execute bits for Mac .command/.sh."""
    data = source.read_bytes()
    info = zipfile.ZipInfo(arcname)
    info.compress_type = zipfile.ZIP_DEFLATED
    if unix_executable:
        # Regular file 0o100755 → external_attr high 16 bits (Unix).
        info.external_attr = 0o100755 << 16
    archive.writestr(info, data)


def build_word_addin_deploy_zip_bytes(public_origin: str) -> bytes:
    """
    Zip for account-modal download: README + manifest + windows/ + mac/ installers.

    Static add-in files are served by the MindGraph server at ``/word-addin/``;
    users do not need the source tree or Node.js.
    """
    manifest_xml = build_production_manifest_xml(public_origin)
    for source, _arcname, _executable in _DEPLOY_SCRIPTS:
        if not source.is_file():
            raise FileNotFoundError(str(source))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", _README_MD.encode("utf-8"))
        archive.writestr("manifest.xml", manifest_xml.encode("utf-8"))
        for source, arcname, executable in _DEPLOY_SCRIPTS:
            _zip_write_file(
                archive,
                source,
                arcname,
                unix_executable=executable,
            )
    data = buffer.getvalue()
    if not data:
        raise RuntimeError("Word add-in deploy zip is empty")
    return data


def build_word_addin_zip_bytes(public_origin: str | None = None) -> bytes:
    """
    Deploy zip for downloads.

    ``public_origin`` is required for production URLs (e.g. https://mg.mindspringedu.com).
    """
    if not public_origin:
        raise ValueError("public_origin is required for the Word add-in deploy zip")
    return build_word_addin_deploy_zip_bytes(public_origin)
