# Mind-map PDF export fonts

Runtime load order (no CDN):

1. `/api/mindmap_export_fonts/{file}` — server serves local cache / pulls from **Tencent COS**
2. `/fonts/{file}` — this folder (dev fallback)

Files must be **TrueType** (`.ttf`). jsPDF cannot embed Noto CJK OTF/CFF.

## 1) Vendor TrueType locally (once)

```bash
cd frontend
npm run vendor:mindmap-export-fonts
```

This converts `@fontsource/noto-sans-sc` Chinese-simplified WOFF2 → TTF under this folder.

## 2) Publish to COS (shared for all app hosts)

From repo root (conda + COS credentials in `.env`):

```bash
python scripts/db/publish_mindmap_export_fonts_to_cos.py
python scripts/db/publish_mindmap_export_fonts_to_cos.py --status
```

Objects land under:

`{COS_SYNC_KEY_PREFIX}/sync/fonts/mindmap-export/`

## PDF size

Full SC TrueType faces are ~2.5 MB each. The browser embeds them as-is: the
`subset-font` / `wawoff2` toolchain uses `new Function` and is blocked by the
app Content-Security-Policy (`script-src` without `unsafe-eval`).
