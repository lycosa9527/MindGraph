# Host permissions audit

Manifest `host_permissions` (v0.4.18+) are split into **explicit MindGraph servers** plus **document-extract fetch** wildcards.

## MindGraph API (Settings dropdown presets)

| Origin | Purpose |
|--------|---------|
| `https://mg.mindspringedu.com/*` | Production |
| `https://test.mindspringedu.com/*` | Test |
| `http://localhost:9527/*` | Local dev (HTTP — see Settings warning) |
| `http://127.0.0.1:9527/*` | Local dev alternate |

## Document extract (service worker `fetch`)

| Pattern | Purpose |
|---------|---------|
| `*://*.smartedu.cn/*` | SmartEdu pages + content script |
| `*://*.cbern.com.cn/*` | SmartEdu CDN metadata/assets |
| `https://wkretype.bdimg.com/*` | Baidu Wenku direct PDF tier |
| `https://*/*` | ~25 document hosts in [`doc-extract/hosts.js`](doc-extract/hosts.js) |
| `http://*/*` | Rare HTTP document sites |

Page capture (`executeScript`) uses **`activeTab`** + **`scripting`** on the tab the user activates — not gated by MindGraph host permissions.

## Why wildcards remain

Doc-extract engines fetch binary assets from many third-party hosts (see [`doc-extract/REFERENCES.md`](doc-extract/REFERENCES.md)). Listing every host explicitly would be fragile; MindGraph API origins are pinned separately to limit credential exfiltration scope.
