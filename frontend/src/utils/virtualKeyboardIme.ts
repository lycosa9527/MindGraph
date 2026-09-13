/**
 * System IME / OS keyboard helpers for the canvas virtual keyboard.
 *
 * Browsers do not feed synthetic KeyboardEvents to the OS IME (events are not
 * trusted). The supported path is: focus an editable field, then show the
 * platform virtual keyboard when {@link Navigator.virtualKeyboard} exists.
 */
export type NavigatorVirtualKeyboard = {
  overlaysContent: boolean
  show(): void
  hide(): void
}

export function getNavigatorVirtualKeyboard(): NavigatorVirtualKeyboard | null {
  const candidate = (navigator as Navigator & { virtualKeyboard?: NavigatorVirtualKeyboard })
    .virtualKeyboard
  if (!candidate || typeof candidate.show !== 'function') {
    return null
  }
  return candidate
}

export function prepareFieldForSystemIme(
  el: HTMLInputElement | HTMLTextAreaElement,
  locale: string
): void {
  el.lang = locale
  el.setAttribute('inputmode', 'text')
  el.focus({ preventScroll: true })
}

export function showSystemVirtualKeyboard(
  el: HTMLInputElement | HTMLTextAreaElement,
  locale: string
): boolean {
  prepareFieldForSystemIme(el, locale)
  const api = getNavigatorVirtualKeyboard()
  if (!api) {
    return false
  }
  api.overlaysContent = true
  api.show()
  return true
}

export function hideSystemVirtualKeyboard(): void {
  const api = getNavigatorVirtualKeyboard()
  api?.hide()
}
