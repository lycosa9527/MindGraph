/* global Office */
/**
 * Ribbon executeFunction handlers.
 * MindMate / Voice / Settings open dedicated dialogs (not task panes).
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
 * @param {string} relativeHtml e.g. '../taskpane/settings.html'
 * @param {{ height: number, width: number }} size percent of screen
 * @param {*} event
 */
function mgOpenNamedDialog(key, relativeHtml, size, event) {
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
      mgDialogPageUrl(relativeHtml),
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

function openMindMateDialog(event) {
  mgOpenNamedDialog(
    'mindmate',
    '../taskpane/mindmate.html',
    { height: 72, width: 42 },
    event
  )
}

function openSettingsDialog(event) {
  // Compact login-only window
  mgOpenNamedDialog(
    'settings',
    '../taskpane/settings.html',
    { height: 48, width: 32 },
    event
  )
}

function openVoiceDialog(event) {
  // Dedicated recorder window (mic → Fun-ASR); not the SPA task pane.
  mgOpenNamedDialog(
    'voice',
    '../taskpane/voice.html',
    { height: 64, width: 36 },
    event
  )
}

Office.onReady(function () {
  if (Office.actions && typeof Office.actions.associate === 'function') {
    Office.actions.associate('openMindMateDialog', openMindMateDialog)
    Office.actions.associate('openSettingsDialog', openSettingsDialog)
    Office.actions.associate('openVoiceDialog', openVoiceDialog)
  }
})
