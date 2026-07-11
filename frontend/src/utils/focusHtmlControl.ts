/**
 * Safe focus/select for DOM controls (guards non-element refs and missing methods).
 */
export function resolveHtmlControl(refValue: unknown): HTMLElement | null {
  const candidate = Array.isArray(refValue) ? refValue[0] : refValue
  if (candidate == null || typeof candidate !== 'object') {
    return null
  }
  return candidate as HTMLElement
}

export function focusHtmlControl(refValue: unknown): boolean {
  const el = resolveHtmlControl(refValue)
  if (el == null || typeof el.focus !== 'function') {
    return false
  }
  el.focus()
  return true
}

export function selectHtmlControl(refValue: unknown): boolean {
  const el = resolveHtmlControl(refValue)
  if (el == null || typeof (el as HTMLInputElement).select !== 'function') {
    return false
  }
  ;(el as HTMLInputElement).select()
  return true
}
