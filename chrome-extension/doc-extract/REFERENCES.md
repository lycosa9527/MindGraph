# Document extract — host → engine map

Internal map of `hosts.js` entries to extract engines. Implementation details live in the linked modules.

| Host id | Engine | Modules |
|---------|--------|---------|
| smartedu | api-binary | `smartedu/` |
| cnki | api-binary (+ canvas fallback) | `cnki/`, `engines/cnki.js` |
| wenku | canvas-pdf (+ api-binary tier) | `hosts/wenku.js`, `engines/canvas-pdf.js`, `engines/api-binary.js` |
| doc88 / docin / taodocs / book118 | canvas-pdf | `hosts/docin.js`, `engines/canvas-pdf.js` |
| 360doc / collab_docs / article / generic | dom-article | `engines/dom-article.js` |
| other preview hosts | html2canvas-pdf | `engines/html2canvas-pdf.js` |

## Prep scripts

| Script | Purpose |
|--------|---------|
| `prep/unblock-copy.js` | Remove copy/select guards before extract |
| `prep/hide-chrome.js` | Hide toolbars / chrome before capture |
| `prep/expand-all.js` | Click read-all controls when present |
| `prep/autoscroll.js` | Scroll to load lazy preview pages |
