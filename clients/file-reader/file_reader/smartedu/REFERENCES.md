# SmartEdu OSS reference map (file-reader)

Ports logic from community tools; keep behavior aligned with `chrome-extension/doc-extract/smartedu/REFERENCES.md`.

| Repo | License | Used for |
|------|---------|----------|
| [happycola233/tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) | MIT | `ND_UC_AUTH` token snippet, `X-ND-AUTH` header, `cs_path` CDN host swap |
| [cjhdevact/FlyEduDownloader](https://github.com/cjhdevact/FlyEduDownloader) | GPL (read-only) | `classActivity` → `national_lesson/resources/details/{activityId}.json` |
| [52beijixing/smartedu-download](https://github.com/52beijixing/smartedu-download) | — | Aug 2024 API notes; ffmpeg + m3u8 merge pattern |
| [hantang/smartedu-dl-go](https://github.com/hantang/smartedu-dl-go) | — | Optional `?accessToken=` suffix on download URLs (not used in v1) |

When updating URL templates or `ti_items` selection rules, update both this package and the Chrome extension SmartEdu module in the same change.

Multi-site browser registry: see [`../platform_browser/REFERENCES.md`](../platform_browser/REFERENCES.md).
