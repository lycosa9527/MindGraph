window.__mgPwaInstallEarly = null
window.addEventListener('beforeinstallprompt', function (event) {
  event.preventDefault()
  window.__mgPwaInstallEarly = event
})

// pdfjs-dist evaluates `Iterator.prototype.join` at module load. Classic script
// so the identifier exists before any ES module (WeChat / older WebViews).
;(function (globalObject) {
  if (typeof globalObject.Iterator === 'function') {
    return
  }
  function IteratorCtor() {
    throw new TypeError('Abstract class Iterator not directly constructable')
  }
  globalObject.Iterator = IteratorCtor
})(typeof globalThis !== 'undefined' ? globalThis : window);
