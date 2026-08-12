/* global MG_CLIENT_ID, mgAuthStatus, mgBaseUrl, mgExpandTaskPaneHalfSoon, mgHydratePrefs, mgLoadPrefs, mgT */
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
 * Probe phone + mgat_ via validate-only endpoint (no Redis handoff code minted).
 * @param {{ baseUrl?: string, phone?: string, apiToken?: string }} prefs
 * @returns {Promise<{ ok: boolean, status: number, reason: string }>}
 */
function mgProbeEmbedAuth(prefs) {
  var p = prefs || mgLoadPrefs()
  var phone = String(p.phone || '').trim()
  var token = String(p.apiToken || '').trim()
  if (!phone || !token) {
    return Promise.resolve({ ok: false, status: 0, reason: 'empty' })
  }
  if (token.indexOf('mgat_') !== 0) {
    return Promise.resolve({ ok: false, status: 0, reason: 'token' })
  }
  var base = mgBaseUrl(p)
  return fetch(base + '/api/auth/embed/probe', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + token,
      'X-MG-Account': phone,
      'X-MG-Client': MG_CLIENT_ID,
      Accept: 'application/json',
    },
  })
    .then(function (res) {
      if (res.ok) {
        return res.json().then(function (body) {
          if (!body || body.ok !== true) {
            return { ok: false, status: res.status, reason: 'missing' }
          }
          return { ok: true, status: res.status, reason: 'ok' }
        })
      }
      // 401/403 = credentials; 404/405 = probe not deployed / wrong method; else server.
      if (res.status === 401 || res.status === 403) {
        return { ok: false, status: res.status, reason: 'auth' }
      }
      if (res.status === 404 || res.status === 405) {
        return { ok: false, status: res.status, reason: 'unsupported' }
      }
      return { ok: false, status: res.status, reason: 'server' }
    })
    .catch(function () {
      return { ok: false, status: 0, reason: 'network' }
    })
}

/**
 * @param {string} path SPA path e.g. /mindmate, /mindgraph, /showcase
 * @param {{ statusEl?: HTMLElement|null, guestRow?: HTMLElement|null, openGuestBtn?: HTMLElement|null, expandPane?: boolean }} ui
 */
function mgOpenSpaHost(path, ui) {
  var statusEl = ui && ui.statusEl
  var guestRow = ui && ui.guestRow
  var openGuestBtn = ui && ui.openGuestBtn
  var expandPane = !ui || ui.expandPane !== false

  // Widen before navigating away (SPA origin may not have Office.js).
  if (expandPane && typeof mgExpandTaskPaneHalfSoon === 'function') {
    mgExpandTaskPaneHalfSoon()
  }

  function showGuestOption(messageKey) {
    if (statusEl) {
      statusEl.textContent = mgT(messageKey)
    }
    if (guestRow) {
      guestRow.style.display = 'flex'
    }
  }

  if (statusEl) {
    statusEl.textContent = mgT('spaOpening')
  }

  var hydrate =
    typeof mgHydratePrefs === 'function'
      ? mgHydratePrefs()
      : Promise.resolve(mgLoadPrefs())

  hydrate.then(function (prefs) {
    var base = mgBaseUrl(prefs)

    function openGuest() {
      window.location.replace(mgSpaGuestUrl(base, path))
    }

    if (openGuestBtn) {
      openGuestBtn.addEventListener('click', openGuest)
    }

    if (mgAuthStatus(prefs) !== 'saved') {
      showGuestOption('spaNeedAuth')
      return
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
        // Top-level navigation: Set-Cookie on SPA origin → login-free session.
        window.location.replace(complete)
      })
      .catch(function () {
        // Stay on the shell — do not auto-open guest (guest hits /auth on protected routes).
        showGuestOption('handoffFailed')
      })
  })
}
