/**
 * Shared preferences for MindGraph for Word.
 * Prefer OfficeRuntime.storage; fall back to localStorage.
 */

var MG_PREFS_KEY = 'mindgraph_word_prefs_v1'
var MG_CLIENT_ID = 'word-addin'

var MG_DEFAULT_PREFS = {
  language: 'en',
  languageExplicit: false,
  // Fallback for Vite localhost:3000 shell only; hosted /word-addin/ uses location.origin.
  baseUrl: 'https://test.mindspringedu.com',
  phone: '',
  apiToken: '',
  agentName: '',
  agentAvatarUrl: '',
}

var MG_BASE_URL_PRESETS = [
  { id: 'test', url: 'https://test.mindspringedu.com', labelZh: '测试', labelEn: 'Test' },
  { id: 'mg', url: 'https://mg.mindspringedu.com', labelZh: 'MG', labelEn: 'MG' },
  // Vite shell is :3000; MindGraph API + SPA for handoff is :9527.
  { id: 'local', url: 'http://localhost:9527', labelZh: '本地 :9527', labelEn: 'Local :9527' },
]

/**
 * When the shell is served from MindGraph at ``/word-addin/...``, return that origin.
 * Empty string for Vite/dev shells (path is ``/src/taskpane/...``).
 */
function mgShellHostOrigin() {
  try {
    if (typeof window === 'undefined' || !window.location) {
      return ''
    }
    var path = String(window.location.pathname || '')
    if (path.indexOf('/word-addin/') === -1) {
      return ''
    }
    return String(window.location.origin || '').replace(/\/+$/, '')
  } catch (err) {
    return ''
  }
}

function mgNormalizeBaseUrl(url) {
  return String(url || '')
    .trim()
    .replace(/\/+$/, '')
}

/** True when Settings must use the same origin as the hosted shell (CSP connect-src). */
function mgIsHostedSameOriginShell() {
  return Boolean(mgShellHostOrigin())
}

function mgDefaultBaseUrl() {
  return MG_DEFAULT_PREFS.baseUrl
}

function mgCloneDefaults() {
  return {
    language: MG_DEFAULT_PREFS.language,
    languageExplicit: MG_DEFAULT_PREFS.languageExplicit,
    baseUrl: mgDefaultBaseUrl(),
    phone: MG_DEFAULT_PREFS.phone,
    apiToken: MG_DEFAULT_PREFS.apiToken,
    agentName: MG_DEFAULT_PREFS.agentName,
    agentAvatarUrl: MG_DEFAULT_PREFS.agentAvatarUrl,
  }
}

function mgDetectOfficeLanguage() {
  try {
    if (typeof Office !== 'undefined' && Office.context) {
      var officeLang = String(
        Office.context.displayLanguage || Office.context.contentLanguage || ''
      ).toLowerCase()
      if (officeLang.indexOf('zh') === 0) {
        return 'zh'
      }
      if (officeLang) {
        return 'en'
      }
    }
  } catch (err) {
    // ignore
  }
  try {
    var nav = String(navigator.language || navigator.userLanguage || '').toLowerCase()
    if (nav.indexOf('zh') === 0) {
      return 'zh'
    }
  } catch (err2) {
    // ignore
  }
  return 'en'
}

function mgReadLocalStorage() {
  try {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem(MG_PREFS_KEY) || ''
    }
  } catch (err) {
    // ignore
  }
  return ''
}

function mgWriteLocalStorage(raw) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(MG_PREFS_KEY, raw)
    }
  } catch (err) {
    // ignore
  }
}

function mgMergePrefsRaw(raw, prefs) {
  if (!raw) {
    return prefs
  }
  try {
    var parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      if (parsed.language === 'en' || parsed.language === 'zh') {
        prefs.language = parsed.language
      }
      if (typeof parsed.languageExplicit === 'boolean') {
        prefs.languageExplicit = parsed.languageExplicit
      } else if (parsed.language === 'en' || parsed.language === 'zh') {
        // Legacy saves chose a language in Settings — treat as explicit.
        prefs.languageExplicit = true
      }
      if (typeof parsed.baseUrl === 'string' && parsed.baseUrl.trim()) {
        prefs.baseUrl = mgNormalizeBaseUrl(parsed.baseUrl)
      }
      if (typeof parsed.phone === 'string') {
        prefs.phone = parsed.phone.trim()
      }
      if (typeof parsed.apiToken === 'string') {
        prefs.apiToken = parsed.apiToken.trim()
      }
      if (typeof parsed.agentName === 'string') {
        prefs.agentName = parsed.agentName.trim()
      }
      if (typeof parsed.agentAvatarUrl === 'string') {
        prefs.agentAvatarUrl = parsed.agentAvatarUrl.trim()
      }
    }
  } catch (err) {
    // keep defaults
  }
  return prefs
}

function mgLoadPrefs() {
  return mgMergePrefsRaw(mgReadLocalStorage(), mgCloneDefaults())
}

/**
 * Prefer OfficeRuntime.storage when available (shared across task panes),
 * then mirror into localStorage for sync reads.
 * Applies Office UI language when the user has not set language explicitly.
 */
function mgHydratePrefs() {
  return new Promise(function (resolve) {
    var finish = function (raw) {
      if (raw) {
        mgWriteLocalStorage(raw)
      }
      var prefs = mgLoadPrefs()
      if (!prefs.languageExplicit) {
        var detected = mgDetectOfficeLanguage()
        if (detected !== prefs.language) {
          prefs = mgSavePrefs({ language: detected, languageExplicit: false })
        }
      }
      resolve(prefs)
    }
    if (
      typeof OfficeRuntime === 'undefined' ||
      !OfficeRuntime.storage ||
      typeof OfficeRuntime.storage.getItem !== 'function'
    ) {
      finish(mgReadLocalStorage())
      return
    }
    OfficeRuntime.storage
      .getItem(MG_PREFS_KEY)
      .then(function (raw) {
        finish(raw || mgReadLocalStorage())
      })
      .catch(function () {
        finish(mgReadLocalStorage())
      })
  })
}

function mgSavePrefs(partial) {
  var prefs = mgLoadPrefs()
  if (partial && typeof partial === 'object') {
    if (partial.language === 'en' || partial.language === 'zh') {
      prefs.language = partial.language
    }
    if (typeof partial.languageExplicit === 'boolean') {
      prefs.languageExplicit = partial.languageExplicit
    }
    if (typeof partial.baseUrl === 'string' && partial.baseUrl.trim()) {
      prefs.baseUrl = mgNormalizeBaseUrl(partial.baseUrl)
    }
    if (typeof partial.phone === 'string') {
      prefs.phone = partial.phone.trim()
    }
    if (typeof partial.apiToken === 'string') {
      prefs.apiToken = partial.apiToken.trim()
    }
    if (typeof partial.agentName === 'string') {
      prefs.agentName = partial.agentName.trim()
    }
    if (typeof partial.agentAvatarUrl === 'string') {
      prefs.agentAvatarUrl = partial.agentAvatarUrl.trim()
    }
  }
  var raw = JSON.stringify(prefs)
  mgWriteLocalStorage(raw)
  if (
    typeof OfficeRuntime !== 'undefined' &&
    OfficeRuntime.storage &&
    typeof OfficeRuntime.storage.setItem === 'function'
  ) {
    OfficeRuntime.storage.setItem(MG_PREFS_KEY, raw).catch(function () {
      // ignore
    })
  }
  return prefs
}

function mgClearAuthPrefs() {
  return mgSavePrefs({
    phone: '',
    apiToken: '',
    agentName: '',
    agentAvatarUrl: '',
  })
}

function mgAuthStatus(prefs) {
  var p = prefs || mgLoadPrefs()
  if (p.apiToken && p.phone) {
    return 'saved'
  }
  return 'empty'
}

function mgBaseUrl(prefs) {
  var p = prefs || mgLoadPrefs()
  return mgNormalizeBaseUrl(p.baseUrl || mgDefaultBaseUrl())
}
