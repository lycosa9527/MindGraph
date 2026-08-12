/**
 * Shared preferences for MindGraph for Word.
 * Prefer OfficeRuntime.storage; fall back to localStorage.
 */

var MG_PREFS_KEY = 'mindgraph_word_prefs_v1'
var MG_CLIENT_ID = 'word-addin'

var MG_DEFAULT_PREFS = {
  language: 'en',
  languageExplicit: false,
  baseUrl: 'https://test.mindspringedu.com',
  phone: '',
  apiToken: '',
  agentName: '',
  agentAvatarUrl: '',
}

var MG_BASE_URL_PRESETS = [
  { id: 'test', url: 'https://test.mindspringedu.com', labelZh: '测试', labelEn: 'Test' },
  { id: 'production', url: 'https://mg.mindspringedu.com', labelZh: '生产', labelEn: 'Production' },
  { id: 'local', url: 'http://localhost:9527', labelZh: '本地', labelEn: 'Local' },
]

function mgCloneDefaults() {
  return {
    language: MG_DEFAULT_PREFS.language,
    languageExplicit: MG_DEFAULT_PREFS.languageExplicit,
    baseUrl: MG_DEFAULT_PREFS.baseUrl,
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
        prefs.baseUrl = parsed.baseUrl.trim().replace(/\/+$/, '')
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
      prefs.baseUrl = partial.baseUrl.trim().replace(/\/+$/, '')
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
  return String(p.baseUrl || MG_DEFAULT_PREFS.baseUrl).replace(/\/+$/, '')
}
