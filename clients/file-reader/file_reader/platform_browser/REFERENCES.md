# Platform browser OSS reference map

| Site | OSS reference | Implementation |
|------|---------------|----------------|
| SmartEdu | tchMaterial-parser, FlyEduDownloader, smartedu-dl-go | `smartedu/` + `SmartEduExtractor` |
| Bilibili | yt-dlp, bilix (ref) | `YtdlpExtractor` |
| Douyin | yt-dlp | `YtdlpExtractor` |
| TikTok | yt-dlp | `YtdlpExtractor` |
| YouTube | yt-dlp + Playwright/WebView2 network PO token capture | `YtdlpExtractor` + `youtube_po.py` |
| WeChat Channels | Evil0ctal/WeChat-Channels-Video-File-Decryption (ref) | `channels_extractor` + `wechat_channels/` |
| Tencent Meeting | tencent-meeting-video-downloader | `MediaUrlExtractor` + `tencent_meeting/` |
| Baidu / 360doc | — | Login status only |

yt-dlp is GPL-3.0 — retain license notices in distributions bundling the library.

Default browser backend: Playwright Python driver + **bundled Chromium** (`PLAYWRIGHT_BROWSERS_PATH=0` in PyInstaller builds). Legacy embedded WebView2: `MINDGRAPH_BROWSER=webview2`.
