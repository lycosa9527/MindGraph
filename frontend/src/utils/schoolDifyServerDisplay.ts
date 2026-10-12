/**
 * What the school Dify form shows when a slot has no override.
 * A blank school URL or key displays the matching global default.
 * Saving still stores an override only after the admin edits the slot.
 */

export interface SchoolDifyUrlDraft {
  urlDirty: boolean
  draftUrl: string
}

export function applySchoolDifyUrlInput(
  value: string,
  schoolUrl: string,
  globalUrl: string
): SchoolDifyUrlDraft {
  const global = globalUrl.trim()
  const school = schoolUrl.trim()
  const trimmed = value.trim()
  if (!trimmed || trimmed === global) {
    if (school && trimmed !== school) {
      return { urlDirty: true, draftUrl: '' }
    }
    return { urlDirty: false, draftUrl: school }
  }
  return { urlDirty: true, draftUrl: value }
}

export function schoolDifyShownUrl(
  urlDirty: boolean,
  draftUrl: string,
  schoolUrl: string,
  globalUrl: string
): string {
  const global = globalUrl.trim()
  const school = schoolUrl.trim()
  if (urlDirty && draftUrl.trim()) {
    return draftUrl
  }
  if (urlDirty) {
    return global
  }
  return school || global
}

export function schoolDifyUsingGlobalUrl(
  urlDirty: boolean,
  draftUrl: string,
  schoolUrl: string,
  globalUrl: string
): boolean {
  const global = globalUrl.trim()
  if (!global) {
    return false
  }
  if (urlDirty) {
    return !draftUrl.trim()
  }
  return !schoolUrl.trim()
}

export function schoolDifyDisplayedKey(
  schoolMasked: string | null | undefined,
  globalMasked: string | null | undefined
): string {
  const school = (schoolMasked ?? '').trim()
  if (school) {
    return school
  }
  return (globalMasked ?? '').trim()
}

export function schoolDifyCredentialDraftUrl(
  draftUrl: string,
  typedKey: string,
  shownUrl: string
): string {
  const edited = draftUrl.trim()
  if (edited) {
    return edited
  }
  if (typedKey.trim()) {
    return shownUrl.trim()
  }
  return ''
}

export interface SchoolDifyPairWrite {
  clear: boolean
  url: string | null
  key: string | null
}

export function schoolDifyPairWrite(input: {
  draftUrl: string
  typedKey: string
  shownUrl: string
  urlDirty: boolean
  schoolUrl: string
  hasSchoolKey: boolean
}): SchoolDifyPairWrite | null {
  const typedKey = input.typedKey.trim()
  const schoolUrl = input.schoolUrl.trim()
  const revertedToGlobal = input.urlDirty && !input.draftUrl.trim() && Boolean(schoolUrl)
  const url = schoolDifyCredentialDraftUrl(input.draftUrl, typedKey, input.shownUrl)
  if (revertedToGlobal && !typedKey) {
    return { clear: true, url: null, key: null }
  }
  if (!url && !typedKey && !input.hasSchoolKey) {
    return { clear: true, url: null, key: null }
  }
  if (!url && !typedKey) {
    return null
  }
  return { clear: false, url: url || null, key: typedKey || null }
}
