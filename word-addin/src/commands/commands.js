/* global Office, mgBaseUrl, mgHydratePrefs, mgLoadPrefs, mgWordAddinPageUrl */
/**
 * Ribbon executeFunction handlers.
 * MindMate / Settings open shell dialogs; Voice opens on Settings baseUrl
 * (same Origin as Fun-ASR WebSocket / CSWSH allowlist).
 */

/** @type {Record<string, Office.Dialog | null>} */
var mgDialogs = {
  mindmate: null,
  settings: null,
  voice: null,
}

function mgDialogPageUrl(relativeHtml) {
  try {
    return new URL(relativeHtml, window.location.href).href
  } catch (err) {
    return 'https://localhost:3000/src/taskpane/' + relativeHtml.replace(/^\.\.\/taskpane\//, '')
  }
}

function mgCompleteRibbonEvent(event) {
  if (event && typeof event.completed === 'function') {
    event.completed()
  }
}

/**
 * @param {string} key
 * @param {string} absoluteUrl
 * @param {{ height: number, width: number }} size percent of screen
 * @param {*} event
 */
function mgOpenDialogAtUrl(key, absoluteUrl, size, event) {
  try {
    if (typeof Office === 'undefined' || !Office.context || !Office.context.ui) {
      mgCompleteRibbonEvent(event)
      return
    }

    if (mgDialogs[key]) {
      mgCompleteRibbonEvent(event)
      return
    }

    Office.context.ui.displayDialogAsync(
      absoluteUrl,
      {
        height: size.height,
        width: size.width,
        displayInIframe: false,
      },
      function (asyncResult) {
        if (asyncResult.status === Office.AsyncResultStatus.Failed) {
          mgDialogs[key] = null
          mgCompleteRibbonEvent(event)
          return
        }
        mgDialogs[key] = asyncResult.value
        mgDialogs[key].addEventHandler(
          Office.EventType.DialogEventReceived,
          function (arg) {
            if (arg && (arg.error === 12006 || arg.error === 12002)) {
              mgDialogs[key] = null
            }
          }
        )
        mgCompleteRibbonEvent(event)
      }
    )
  } catch (err) {
    mgDialogs[key] = null
    mgCompleteRibbonEvent(event)
  }
}

/**
 * @param {string} key
 * @param {string} relativeHtml e.g. '../taskpane/settings.html'
 * @param {{ height: number, width: number }} size percent of screen
 * @param {*} event
 */
function mgOpenNamedDialog(key, relativeHtml, size, event) {
  mgOpenDialogAtUrl(key, mgDialogPageUrl(relativeHtml), size, event)
}

function openMindMateDialog(event) {
  mgOpenNamedDialog(
    'mindmate',
    '../taskpane/mindmate.html',
    { height: 72, width: 42 },
    event
  )
}

function openSettingsDialog(event) {
  // Compact login-only window (stays on shell so Server preset can change).
  mgOpenNamedDialog(
    'settings',
    '../taskpane/settings.html',
    { height: 48, width: 32 },
    event
  )
}

function openVoiceDialog(event) {
  // Same-origin with Settings API host → WS Origin matches CSWSH allowlist.
  var size = { height: 64, width: 36 }
  var hydrate =
    typeof mgHydratePrefs === 'function'
      ? mgHydratePrefs()
      : Promise.resolve(typeof mgLoadPrefs === 'function' ? mgLoadPrefs() : null)

  hydrate
    .then(function (prefs) {
      var url =
        typeof mgWordAddinPageUrl === 'function'
          ? mgWordAddinPageUrl('taskpane/voice.html', prefs)
          : mgBaseUrl(prefs) + '/word-addin/src/taskpane/voice.html'
      mgOpenDialogAtUrl('voice', url, size, event)
    })
    .catch(function () {
      var fallback =
        typeof mgWordAddinPageUrl === 'function'
          ? mgWordAddinPageUrl('taskpane/voice.html', null)
          : mgDialogPageUrl('../taskpane/voice.html')
      mgOpenDialogAtUrl('voice', fallback, size, event)
    })
}

Office.onReady(function () {
  if (Office.actions && typeof Office.actions.associate === 'function') {
    Office.actions.associate('openMindMateDialog', openMindMateDialog)
    Office.actions.associate('openSettingsDialog', openSettingsDialog)
    Office.actions.associate('openVoiceDialog', openVoiceDialog)
  }
})
