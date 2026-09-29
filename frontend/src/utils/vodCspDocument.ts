/**
 * The installed app used to replay a saved page, including its Content-Security-Policy.
 * TCPlayer then could not load tcsdk.com or reach the play hosts. A fresh document
 * carries data-mg-csp-vod when the policy allows those hosts.
 */

const RELOAD_KEY = 'mg-csp-vod-reload'

export function shouldReloadForVodCsp(
  featureVod: boolean,
  hasMarker: boolean,
  alreadyReloaded: boolean,
  isDev: boolean
): boolean {
  if (isDev || !featureVod || hasMarker) {
    return false
  }
  return !alreadyReloaded
}

function reloadFlagSet(): boolean {
  try {
    return sessionStorage.getItem(RELOAD_KEY) === '1'
  } catch {
    return true
  }
}

function rememberReload(): boolean {
  try {
    sessionStorage.setItem(RELOAD_KEY, '1')
    return true
  } catch {
    return false
  }
}

function clearReloadFlag(): void {
  try {
    sessionStorage.removeItem(RELOAD_KEY)
  } catch {
    return
  }
}

export function maybeReloadForVodCsp(featureVod: boolean): void {
  if (typeof window === 'undefined') {
    return
  }
  const hasMarker = document.documentElement.dataset.mgCspVod === '1'
  if (hasMarker) {
    clearReloadFlag()
    return
  }
  if (!shouldReloadForVodCsp(featureVod, hasMarker, reloadFlagSet(), import.meta.env.DEV)) {
    return
  }
  if (!rememberReload()) {
    return
  }
  window.location.reload()
}
