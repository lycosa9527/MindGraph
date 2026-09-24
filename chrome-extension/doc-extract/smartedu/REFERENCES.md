# Lesson-platform extract — implementation notes

Token, metadata, and download helpers under `doc-extract/smartedu/` mirror the desktop file-reader lesson tab.

| Concern | Module |
|---------|--------|
| Auth token parse / sync | `token.js`, `token-read-page.js` |
| Activity URL → detail JSON | `url-parser.js` |
| Asset list from detail JSON | `metadata.js`, `models.js` |
| Binary download | `downloader.js` |
| MindMate markdown | `markdown-extract.js` |
