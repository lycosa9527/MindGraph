# Document extract — host → engine → OSS reference map

Audit of GreasyFork / GitHub sources ported into `chrome-extension/doc-extract/`. Line refs are approximate (upstream DOM changes often).

| Host id | Site | Engine | Primary OSS | Ported into |
|---------|------|--------|-------------|-------------|
| smartedu | 国家智慧教育 | api-binary → `smartedu/` | tchMaterial-parser, FlyEduDownloader | `smartedu/url-parser.js`, `metadata.js`, `downloader.js` |
| wenku | 百度文库 | canvas-pdf (+ api-binary tier) | GreasyFork 437609 `bdwk()`, wks | `hosts/wenku.js`, `engines/canvas-pdf.js`, `engines/api-binary.js` |
| doc88 | 道客巴巴 | canvas-pdf | 437609, 435884 | `hosts/docin.js` hide lists, `canvas-pdf.js` |
| docin | 豆丁网 | canvas-pdf | 437609 `docin_ele` | `hosts/docin.js` |
| taodocs | 淘豆网 | canvas-pdf | 437609 | `hosts.js` row |
| book118 | 原创力文档 | canvas-pdf | 437609 `book118_ele` | `hosts.js` row |
| 360doc | 360个人图书馆 | dom-article | 435884 `#articlecontent` | `engines/dom-article.js` |
| deliwenku | 得力文库 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| mbalib | MBA智库 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| iask | 爱问 / 新浪文档 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| dugen | 读根网 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| gb688 | 国标网 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| safewk | 安全文库网 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| renrendoc | 人人文库 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| yunzhan365 | 云展网 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| wenku_so | 360文库 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| wenkub | 文库吧 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| jinchutou | 金锄头 | html2canvas-pdf | 435884, rty813 | `engines/html2canvas-pdf.js` |
| nrsis | 自然资源标准 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| ssap | 中国社会科学文库 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| jg_class | 技工教育网 | html2canvas-pdf | 435884 | `engines/html2canvas-pdf.js` |
| sdlib | 山东图书馆等 | html2canvas-pdf | 435884 extras | `engines/html2canvas-pdf.js` |
| collab_docs | 腾讯文档 / 语雀 / 飞书 | dom-article | Lift_Copy_Restrictions | `prep/unblock-copy.js`, `dom-article.js` |
| article | CSDN / 知乎 / 简书等 | dom-article | article-extractor patterns | `engines/dom-article.js` |
| generic | any http(s) page | dom-article | existing mind map selectors | `engines/dom-article.js` |

## Prep scripts (437609 / 435884 / Lift_Copy_Restrictions)

| Script | OSS source | Purpose |
|--------|------------|---------|
| `prep/unblock-copy.js` | Lift_Copy_Restrictions | Remove copy/select guards before extract |
| `prep/hide-chrome.js` | 437609 `bdwk_ele`, `docin_ele`, `book118_ele` | Hide toolbars / watermarks |
| `prep/expand-all.js` | 437609 `bdwk()` expand clicks | 展开全文 / read-all |
| `prep/autoscroll.js` | 437609 scroll loop (~500 ms) | Lazy-load all preview pages |

## Engine internals

| Engine | Key OSS functions | Our module |
|--------|-------------------|------------|
| canvas-pdf | 437609 `downloadPDF()` canvas loop | `engines/canvas-pdf.js` |
| html2canvas-pdf | 435884 `elems_to_canvases`, `imgs_to_pdf` | `engines/html2canvas-pdf.js` |
| api-binary | tchMaterial-parser CDN fetch, wks reader URLs | `engines/api-binary.js`, `smartedu/` |
| dom-article | 360doc `#articlecontent`, article-extractor | `engines/dom-article.js` |
