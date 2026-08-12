/* global mgLoadPrefs, mgT, Office */
/**
 * Shared helpers for task-pane pages.
 */

function mgApplyI18n(root) {
  var scope = root || document
  var nodes = scope.querySelectorAll('[data-i18n]')
  var i
  for (i = 0; i < nodes.length; i += 1) {
    var el = nodes[i]
    var key = el.getAttribute('data-i18n')
    if (key) {
      el.textContent = mgT(key)
    }
  }
  var placeholders = scope.querySelectorAll('[data-i18n-placeholder]')
  for (i = 0; i < placeholders.length; i += 1) {
    var input = placeholders[i]
    var pKey = input.getAttribute('data-i18n-placeholder')
    if (pKey) {
      input.setAttribute('placeholder', mgT(pKey))
    }
  }
}

function mgShowToast(message) {
  var toast = document.getElementById('mg-toast')
  if (!toast) {
    toast = document.createElement('div')
    toast.id = 'mg-toast'
    toast.className = 'mg-toast'
    document.body.appendChild(toast)
  }
  toast.textContent = message
  toast.classList.add('show')
  window.setTimeout(function () {
    toast.classList.remove('show')
  }, 1600)
}

function mgBootPage(onReady) {
  function run() {
    var hydrate =
      typeof mgHydratePrefs === 'function'
        ? mgHydratePrefs()
        : Promise.resolve(mgLoadPrefs())
    hydrate.then(function (prefs) {
      try {
        document.documentElement.lang = prefs.language === 'zh' ? 'zh-CN' : 'en'
      } catch (err) {
        // ignore
      }
      mgApplyI18n(document)
      if (typeof onReady === 'function') {
        onReady(prefs)
      }
    })
  }
  if (typeof Office !== 'undefined' && Office.onReady) {
    Office.onReady(function () {
      run()
    })
    return
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run)
  } else {
    run()
  }
}
