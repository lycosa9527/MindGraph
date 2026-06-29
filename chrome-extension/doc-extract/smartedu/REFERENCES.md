# SmartEdu extract — OSS reference map

Parallel to `clients/file-reader/file_reader/smartedu/REFERENCES.md` (file-reader plan).

| Repo | Use in extension |
|------|------------------|
| [happycola233/tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) | `ND_UC_AUTH-*` token, `X-ND-AUTH` header, URL kinds |
| [cjhdevact/FlyEduDownloader](https://github.com/cjhdevact/FlyEduDownloader) | `classActivity` → `national_lesson/.../details/{activityId}.json` |
| [52beijixing/smartedu-download](https://github.com/52beijixing/smartedu-download) | Post-2024 auth; original vs transcode PDF |
| [hantang/smartedu-dl-go](https://github.com/hantang/smartedu-dl-go) | `?accessToken=` download URL suffix |

Module pairs (keep inline sync comments in sync with file-reader):

| Extension | File reader |
|-----------|-------------|
| `url-parser.js` | `url_parser.py` |
| `models.js` | `models.py` |
| `metadata.js` | `metadata.py` |
| `downloader.js` | `downloader.py` |
| `token.js` | `token_store.py` |

Fixtures: `tests/fixtures/doc-extract/smartedu/`.
