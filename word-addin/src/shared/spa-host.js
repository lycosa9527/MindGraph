/* global MG_CLIENT_ID, mgAuthStatus, mgBaseUrl, mgExpandTaskPaneHalfSoon, mgLoadPrefs, mgT */
/**
 * Open a live MindGraph SPA path in the task pane (desktop embed).
 * With saved mgat_: handoff → cookies → redirect; else guest with ?embed=word-addin.
 */

function mgSpaGuestUrl(base, path) {
  var clean = String(path || '/mindgraph').split('?')[0]
  if (clean.charAt(0) !== '/') {
    clean = '/' + clean
  }
  return base + clean + '?embed=word-addin'
}

/**
 * @param {string} path SPA path e.g. /mindmate, /mindgraph, /showcase
 * @param {{ statusEl?: HTMLElement|null, guestRow?: HTMLElement|null, openGuestBtn?: HTMLElement|null }} ui
 */
function mgOpenSpaHost(path, ui) {
  var prefs = mgLoadPrefs()
  var base = mgBaseUrl(prefs)
  var statusEl = ui && ui.statusEl
  var guestRow = ui && ui.guestRow
  var openGuestBtn = ui && ui.openGuestBtn
  var expandPane = !ui || ui.expandPane !== false

  // Widen before navigating away (SPA origin may not have Office.js).
  if (expandPane && typeof mgExpandTaskPaneHalfSoon === 'function') {
    mgExpandTaskPaneHalfSoon()
  }

  function openGuest() {
    window.location.replace(mgSpaGuestUrl(base, path))
  }

  if (openGuestBtn) {
    openGuestBtn.addEventListener('click', openGuest)
  }

  if (mgAuthStatus(prefs) !== 'saved') {
    if (statusEl) {
      statusEl.textContent = mgT('spaNeedAuth')
    }
    if (guestRow) {
      guestRow.style.display = 'flex'
    }
    return
  }

  if (statusEl) {
    statusEl.textContent = mgT('spaOpening')
  }

  fetch(base + '/api/auth/embed/handoff', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + prefs.apiToken,
      'X-MG-Account': prefs.phone,
      'X-MG-Client': MG_CLIENT_ID,
      Accept: 'application/json',
    },
  })
    .then(function (res) {
      if (!res.ok) {
        throw new Error('handoff ' + res.status)
      }
      return res.json()
    })
    .then(function (body) {
      if (!body || !body.handoff) {
        throw new Error('missing handoff')
      }
      var nextPath = String(path || '/mindgraph').split('?')[0]
      if (nextPath.charAt(0) !== '/') {
        nextPath = '/' + nextPath
      }
      var complete =
        base +
        '/api/auth/embed/complete?handoff=' +
        encodeURIComponent(body.handoff) +
        '&next=' +
        encodeURIComponent(nextPath)
      window.location.replace(complete)
    })
    .catch(function () {
      if (statusEl) {
        statusEl.textContent = mgT('handoffFailed')
      }
      if (guestRow) {
        guestRow.style.display = 'flex'
      }
      window.setTimeout(openGuest, 1200)
    })
}
