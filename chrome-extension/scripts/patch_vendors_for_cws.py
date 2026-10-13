"""Remove Chrome Web Store remotely-hosted-code patterns from vendored JS.

Manifest V3 review rejects ``eval(`` and ``new Function`` even when the
library is packaged. pdf.js 3.11.174 uses both (Node ``require`` and glyph /
PostScript compilers). JSZip's ``setImmediate`` polyfill uses ``new Function``
for string callbacks. The patched files keep the interpreter fallbacks and
only run a pdf.js worker that was loaded as a packaged script.
"""

from __future__ import annotations

from pathlib import Path

_EXTENSION_DIR = Path(__file__).resolve().parents[1]
_PDF_MAIN = _EXTENSION_DIR / "vendor" / "pdfjs" / "pdf.min.js"
_PDF_WORKER = _EXTENSION_DIR / "vendor" / "pdfjs" / "pdf.worker.min.js"
_JSZIP = _EXTENSION_DIR / "vendor" / "jszip.min.js"

_EVAL_SUPPORTED_OLD = (
    "static get isEvalSupported(){return shadow(this,"
    '"isEvalSupported",function isEvalSupported(){try{new Function("");'
    "return!0}catch{return!1}}())}"
)
_EVAL_SUPPORTED_NEW = 'static get isEvalSupported(){return shadow(this,"isEvalSupported",!1)}'

_FAKE_WORKER_OLD = (
    "const mainWorkerMessageHandler=this._mainThreadWorkerMessageHandler;"
    "if(mainWorkerMessageHandler)return mainWorkerMessageHandler;"
    'if(_util.isNodeJS&&"function"==typeof require){const worker=eval("require")'
    "(this.workerSrc);return worker.WorkerMessageHandler}"
    "await(0,_display_utils.loadScript)(this.workerSrc);"
    "return window.pdfjsWorker.WorkerMessageHandler"
)
_FAKE_WORKER_NEW = (
    "const mainWorkerMessageHandler=this._mainThreadWorkerMessageHandler;"
    "if(mainWorkerMessageHandler)return mainWorkerMessageHandler;"
    'throw new Error("PDF worker is not loaded")'
)

_GLYPH_COMPILER_OLD = (
    "if(this.isEvalSupported&&s.FeatureTest.isEvalSupported){const t=[];"
    'for(const e of i){const i=void 0!==e.args?e.args.join(","):"";'
    't.push("c.",e.cmd,"(",i,");\\n")}'
    'return this.compiledGlyphs[e]=new Function("c","size",t.join(""))}'
)

_POSTSCRIPT_COMPILER_OLD = (
    "if(t&&n.FeatureTest.isEvalSupported){const e=(new PostScriptCompiler)"
    ".compile(l,s,o);if(e)return new Function("
    '"src","srcOffset","dest","destOffset",e)}'
    '(0,n.info)("Unable to compile PS function");'
)

_CDN_WRAPPER_OLD = (
    "PDFWorkerUtil.createCDNWrapper=function(t){const e=`importScripts"
    '("${t}");`;return URL.createObjectURL(new Blob([e]))};'
)
_CDN_WRAPPER_NEW = 'PDFWorkerUtil.createCDNWrapper=function(){throw new Error("Remote workers are disabled")};'

_LOAD_SCRIPT_OLD = (
    "e.loadScript=function loadScript(t,e=!1){return new Promise(((i,s)=>{"
    'const n=document.createElement("script");n.src=t;n.onload=function(t)'
    "{e&&n.remove();i(t)};n.onerror=function(){s(new Error(`Cannot load "
    "script at: ${n.src}`))};(document.head||document.documentElement).append(n)}))};"
)
_LOAD_SCRIPT_NEW = (
    'e.loadScript=function loadScript(){return Promise.reject(new Error("Remote script loading is disabled"))};'
)

_JSZIP_OLD = '"function"!=typeof e&&(e=new Function(""+e));'
_JSZIP_NEW = 'if("function"!=typeof e)throw new TypeError("Expected function");'

# setImmediate polyfills inject a src-less <script> as an IE timer. Chrome uses
# MessageChannel instead, but the script constructor is still in the package.
_JSZIP_SCRIPT_TIMER_OLD = (
    'r="document"in t&&"onreadystatechange"in t.document.createElement("script")'
    "?function(){var e=t.document.createElement("
    '"script");e.onreadystatechange=function(){u(),e.onreadystatechange=null,'
    "e.parentNode.removeChild(e),e=null},t.document.documentElement.appendChild(e)}"
    ":function(){setTimeout(u,0)}"
)
_JSZIP_SCRIPT_TIMER_NEW = "r=function(){setTimeout(u,0)}"

_JSZIP_SCRIPT_TIMER_2_OLD = (
    ':l&&"onreadystatechange"in l.createElement("script")?(s=l.documentElement,'
    'function(e){var t=l.createElement("script");t.onreadystatechange=function()'
    "{c(e),t.onreadystatechange=null,s.removeChild(t),t=null},s.appendChild(t)})"
    ":function(e){setTimeout(c,0,e)}"
)
_JSZIP_SCRIPT_TIMER_2_NEW = ":function(e){setTimeout(c,0,e)}"

_INITIALIZE_MARKER = "_initialize(){if(!PDFWorkerUtil.isWorkerDisabled"
_INITIALIZE_PATCHED = "_initialize(){this._setupFakeWorker()}"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace one occurrence, or leave text that was already patched."""
    count = text.count(old)
    if count == 1:
        return text.replace(old, new, 1)
    if count == 0 and (not new or new in text):
        return text
    raise RuntimeError(f"{label}: expected 1 match, found {count}")


def _force_fake_worker(text: str) -> str:
    """Skip ``new Worker(url)`` so pdf.js cannot fetch a worker script."""
    if _INITIALIZE_PATCHED in text and _INITIALIZE_MARKER not in text:
        return text
    start = text.find(_INITIALIZE_MARKER)
    if start < 0:
        raise RuntimeError("PDFWorker._initialize remote-worker branch is missing")
    depth = 0
    end = start + len("_initialize()")
    for index in range(end, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    else:
        raise RuntimeError("PDFWorker._initialize brace match failed")
    return text[:start] + _INITIALIZE_PATCHED + text[end:]


def patch_pdf_main(text: str) -> str:
    """Return pdf.min.js with remote-code mechanisms removed."""
    text = _force_fake_worker(text)
    text = _replace_once(text, _FAKE_WORKER_OLD, _FAKE_WORKER_NEW, "fake worker loader")
    text = _replace_once(text, _EVAL_SUPPORTED_OLD, _EVAL_SUPPORTED_NEW, "pdf isEvalSupported")
    text = _replace_once(text, _GLYPH_COMPILER_OLD, "", "glyph compiler")
    text = _replace_once(text, _CDN_WRAPPER_OLD, _CDN_WRAPPER_NEW, "CDN worker wrapper")
    return _replace_once(text, _LOAD_SCRIPT_OLD, _LOAD_SCRIPT_NEW, "loadScript")


def patch_pdf_worker(text: str) -> str:
    """Return pdf.worker.min.js with ``new Function`` compilers removed."""
    text = _replace_once(text, _EVAL_SUPPORTED_OLD, _EVAL_SUPPORTED_NEW, "worker isEvalSupported")
    return _replace_once(text, _POSTSCRIPT_COMPILER_OLD, "", "PostScript compiler")


def patch_jszip(text: str) -> str:
    """Return JSZip without string eval or script-tag timers."""
    text = _replace_once(text, _JSZIP_OLD, _JSZIP_NEW, "jszip setImmediate")
    text = _replace_once(text, _JSZIP_SCRIPT_TIMER_OLD, _JSZIP_SCRIPT_TIMER_NEW, "jszip script timer")
    return _replace_once(
        text,
        _JSZIP_SCRIPT_TIMER_2_OLD,
        _JSZIP_SCRIPT_TIMER_2_NEW,
        "jszip script timer 2",
    )


def _write_if_changed(path: Path, text: str) -> None:
    current = path.read_text(encoding="utf-8")
    if current != text:
        path.write_text(text, encoding="utf-8")


def main() -> None:
    """Patch vendored pdf.js and JSZip in place."""
    _write_if_changed(_PDF_MAIN, patch_pdf_main(_PDF_MAIN.read_text(encoding="utf-8")))
    _write_if_changed(_PDF_WORKER, patch_pdf_worker(_PDF_WORKER.read_text(encoding="utf-8")))
    _write_if_changed(_JSZIP, patch_jszip(_JSZIP.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
