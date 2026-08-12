/* global Office */
/**
 * Widen the Office task pane toward half the Word window.
 * Requires TaskPaneApi 1.1 (Word desktop M365 ~2507+ / recent Mac).
 * On Windows/Mac the platform max is 50% of the client window.
 */

function mgExpandTaskPaneHalf() {
  try {
    if (typeof Office === 'undefined' || !Office.context || !Office.context.requirements) {
      return false
    }
    if (!Office.context.requirements.isSetSupported('TaskPaneApi', '1.1')) {
      return false
    }
    if (
      !Office.extensionLifeCycle ||
      !Office.extensionLifeCycle.taskpane ||
      typeof Office.extensionLifeCycle.taskpane.setWidth !== 'function'
    ) {
      return false
    }

    var screenW =
      (typeof window !== 'undefined' &&
        window.screen &&
        (window.screen.availWidth || window.screen.width)) ||
      1600
    // Aim for half the display; Office clamps to ≤50% of the Word client.
    // Slightly under 50% of screen avoids a silent no-op when Word is not fully maximized.
    var target = Math.floor(screenW * 0.5)
    if (target < 51) {
      target = 51
    }
    Office.extensionLifeCycle.taskpane.setWidth(target)
    return true
  } catch (err) {
    return false
  }
}

/**
 * Expand now and once more shortly after (some hosts apply width more reliably on a tick).
 */
function mgExpandTaskPaneHalfSoon() {
  mgExpandTaskPaneHalf()
  if (typeof window !== 'undefined') {
    window.setTimeout(function () {
      mgExpandTaskPaneHalf()
    }, 250)
  }
}
