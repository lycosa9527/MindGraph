/* global Office */
/**
 * Ribbon executeFunction handlers.
 * MindMate opens a medium dedicated dialog so it can run beside the MindGraph task pane.
 */

var MIND_MATE_DIALOG_URL = 'https://localhost:3000/src/taskpane/mindmate.html'

/** @type {Office.Dialog | null} */
var mindMateDialog = null

function openMindMateDialog(event) {
  function done() {
    if (event && typeof event.completed === 'function') {
      event.completed()
    }
  }

  try {
    if (typeof Office === 'undefined' || !Office.context || !Office.context.ui) {
      done()
      return
    }

    // One dialog at a time — if already open, just finish (user can focus that window).
    if (mindMateDialog) {
      done()
      return
    }

    Office.context.ui.displayDialogAsync(
      MIND_MATE_DIALOG_URL,
      {
        // Percent of screen — medium dedicated chat window
        height: 72,
        width: 42,
        displayInIframe: false,
      },
      function (asyncResult) {
        if (asyncResult.status === Office.AsyncResultStatus.Failed) {
          mindMateDialog = null
          done()
          return
        }
        mindMateDialog = asyncResult.value
        mindMateDialog.addEventHandler(
          Office.EventType.DialogEventReceived,
          function (arg) {
            // Closed or navigation error — allow opening again
            if (arg && (arg.error === 12006 || arg.error === 12002)) {
              mindMateDialog = null
            }
          }
        )
        done()
      }
    )
  } catch (err) {
    mindMateDialog = null
    done()
  }
}

Office.onReady(function () {
  if (Office.actions && typeof Office.actions.associate === 'function') {
    Office.actions.associate('openMindMateDialog', openMindMateDialog)
  }
})
