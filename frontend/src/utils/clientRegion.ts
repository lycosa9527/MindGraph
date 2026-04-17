/**
 * Client region hint for registration UI (mainland China vs international vs both).
 * Server sets mg_client_region cookie; we read it first to avoid repeat GeoIP calls.
 */

export const CLIENT_REGION_COOKIE = 'mg_client_region'

/** When GeoIP country is unknown, server may omit cookie; we remember hybrid mode for this tab. */
export const CLIENT_REGION_UNKNOWN_SESSION_KEY = 'mg_client_region_unknown_fallback'

export type ClientRegion = 'cn' | 'intl' | 'both'

export function readClientRegionCookie(): ClientRegion | null {
  if (typeof document === 'undefined') {
    return null
  }
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${CLIENT_REGION_COOKIE}=(cn|intl|both)(?:;|$)`)
  )
  if (!match) {
    return null
  }
  return match[1] as ClientRegion
}

export function readUnknownRegionSessionFallback(): boolean {
  if (typeof sessionStorage === 'undefined') {
    return false
  }
  return sessionStorage.getItem(CLIENT_REGION_UNKNOWN_SESSION_KEY) === '1'
}

export function setUnknownRegionSessionFallback() {
  try {
    sessionStorage.setItem(CLIENT_REGION_UNKNOWN_SESSION_KEY, '1')
  } catch {
    /* ignore quota / private mode */
  }
}

/**
 * True when the browser's preferred language list indicates Simplified Chinese
 * (e.g. zh-CN, zh-Hans), excluding Traditional (zh-TW, zh-HK, zh-Hant, …).
 */
export function isBrowserLanguageSimplifiedChinese(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const rawList =
    navigator.languages && navigator.languages.length > 0
      ? navigator.languages
      : [navigator.language]
  for (const raw of rawList) {
    if (!raw) {
      continue
    }
    const tag = raw.toLowerCase()
    if (!tag.startsWith('zh')) {
      continue
    }
    if (tag === 'zh-tw' || tag.startsWith('zh-tw-')) {
      return false
    }
    if (tag === 'zh-hk' || tag.startsWith('zh-hk-')) {
      return false
    }
    if (tag === 'zh-mo' || tag.startsWith('zh-mo-')) {
      return false
    }
    if (tag.startsWith('zh-hant')) {
      return false
    }
    if (tag.startsWith('zh-hans')) {
      return true
    }
    if (tag === 'zh-cn' || tag.startsWith('zh-cn-')) {
      return true
    }
    if (tag === 'zh-sg' || tag.startsWith('zh-sg-')) {
      return true
    }
    if (tag === 'zh-my' || tag.startsWith('zh-my-')) {
      return true
    }
  }
  return false
}
