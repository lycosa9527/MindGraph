/**
 * Copy plain text to the clipboard with a DOM fallback when Clipboard API is unavailable.
 */

function fallbackCopyText(text: string): void {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.width = '1px'
  textarea.style.height = '1px'
  textarea.style.padding = '0'
  textarea.style.border = 'none'
  textarea.style.outline = 'none'
  textarea.style.boxShadow = 'none'
  textarea.style.background = 'transparent'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  textarea.setSelectionRange(0, textarea.value.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } finally {
    document.body.removeChild(textarea)
  }
  if (!ok) {
    throw new Error('Clipboard copy failed')
  }
}

export async function copyTextToClipboard(text: string): Promise<void> {
  const value = text.replace(/\s+$/u, '')
  if (!value) {
    throw new Error('Nothing to copy')
  }

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value)
      return
    } catch {
      // Secure-context / permission failures fall back to execCommand.
    }
  }

  fallbackCopyText(value)
}
