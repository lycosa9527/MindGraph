# Host permissions audit

Manifest `host_permissions` are split into **explicit MindGraph servers** plus **document-extract fetch** patterns.

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
| `*://*.smartedu.cn/*` | Lesson-platform pages + content script |
| `*://*.cbern.com.cn/*` | Lesson CDN metadata/assets |
| `https://wkretype.bdimg.com/*` | Direct PDF reader tier |
| `https://*/*` | Document hosts listed in [`doc-extract/hosts.js`](doc-extract/hosts.js) |
| `http://*/*` | Rare HTTP document sites |
| `file:///*` | Local PDF tabs the user opens |

Page capture (`executeScript`) uses **`activeTab`** + **`scripting`** on the tab the user activates — not gated by MindGraph host permissions.

## Why wildcards remain

Doc-extract engines fetch binary assets from many third-party hosts when the user starts an extract. Listing every host explicitly would be fragile; MindGraph API origins are pinned separately to limit credential exfiltration scope.
