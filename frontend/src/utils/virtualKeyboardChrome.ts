/**
 * On-screen keyboard chrome that must not commit inline node edit.
 * InlineEditableText listens for document pointerdown (capture) and blur-save;
 * taps on the keyboard / its language menu / the status-bar toggle are outside
 * the editor root and would otherwise close the <input> before keys can type.
 */
export const VIRTUAL_KEYBOARD_CHROME_SELECTOR = [
  '.virtual-keyboard-dock',
  '.virtual-keyboard-panel',
  '.simple-keyboard-host',
  '.simple-keyboard',
  '[data-virtual-keyboard-chrome]',
].join(',')

export function isVirtualKeyboardChromeElement(el: EventTarget | Node | null): boolean {
  if (!(el instanceof Element)) return false
  return Boolean(el.closest(VIRTUAL_KEYBOARD_CHROME_SELECTOR))
}

export function isVirtualKeyboardChromeEvent(event: Event): boolean {
  return isVirtualKeyboardChromeElement(event.target)
}

/** Dock stays mounted with v-show; closed state sets aria-hidden="true". */
export function isVirtualKeyboardPanelOpen(): boolean {
  const dock = document.querySelector('.virtual-keyboard-dock')
  if (!(dock instanceof HTMLElement)) return false
  return dock.getAttribute('aria-hidden') !== 'true'
}

export function isEditableTextField(
  el: EventTarget | null
): el is HTMLInputElement | HTMLTextAreaElement {
  return (
    (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) &&
    !el.readOnly &&
    !el.disabled
  )
}
