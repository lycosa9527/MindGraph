/**
 * Keyboard Composable - Keyboard shortcuts
 *
 * Editor delete is owned by the canvas capture listener. This module only
 * registers the shortcuts it is given.
 */
import { onMounted, onUnmounted } from 'vue'

export interface KeyboardShortcut {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  meta?: boolean
  handler: (event: KeyboardEvent) => void
  preventDefault?: boolean
}

export function useKeyboard(shortcuts: KeyboardShortcut[]) {
  function isTypingInInput(): boolean {
    const active = document.activeElement as HTMLElement | null
    if (!active) return false
    const tag = active.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
    if (active.isContentEditable) return true
    return !!active.closest?.('.inline-edit-input, .inline-edit-wrapper')
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (!event.key) return
    const typing = isTypingInInput()
    for (const shortcut of shortcuts) {
      const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase()
      const ctrlMatch = !!shortcut.ctrl === (event.ctrlKey || event.metaKey)
      const shiftMatch = !!shortcut.shift === event.shiftKey
      const altMatch = !!shortcut.alt === event.altKey

      if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
        const hasChordModifier = !!(shortcut.ctrl || shortcut.alt || shortcut.meta)
        if (typing && !hasChordModifier) {
          return
        }
        if (shortcut.preventDefault !== false) {
          event.preventDefault()
        }
        shortcut.handler(event)
        return
      }
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })
}

/**
 * Common editor shortcuts
 */
export function useEditorShortcuts(handlers: {
  undo?: () => void
  redo?: () => void
  save?: () => void
  delete?: () => void
  selectAll?: () => void
  copy?: () => void
  cut?: () => void
  paste?: () => void
  escape?: () => void
  addNode?: () => void
  addBranch?: () => void
  addChild?: () => void
  clearNodeText?: () => void
}) {
  const shortcuts: KeyboardShortcut[] = []

  if (handlers.undo) {
    shortcuts.push({ key: 'z', ctrl: true, handler: handlers.undo })
  }

  if (handlers.redo) {
    shortcuts.push({ key: 'z', ctrl: true, shift: true, handler: handlers.redo })
    shortcuts.push({ key: 'y', ctrl: true, handler: handlers.redo })
  }

  if (handlers.save) {
    shortcuts.push({ key: 's', ctrl: true, handler: handlers.save })
  }

  if (handlers.delete) {
    shortcuts.push({ key: 'Delete', handler: handlers.delete, preventDefault: false })
    shortcuts.push({ key: 'Backspace', handler: handlers.delete, preventDefault: false })
  }

  if (handlers.selectAll) {
    shortcuts.push({ key: 'a', ctrl: true, handler: handlers.selectAll })
  }

  if (handlers.copy) {
    shortcuts.push({ key: 'c', ctrl: true, handler: handlers.copy, preventDefault: false })
  }

  if (handlers.cut) {
    shortcuts.push({ key: 'x', ctrl: true, handler: handlers.cut, preventDefault: false })
  }

  if (handlers.paste) {
    shortcuts.push({ key: 'v', ctrl: true, handler: handlers.paste, preventDefault: false })
  }

  if (handlers.escape) {
    shortcuts.push({ key: 'Escape', handler: handlers.escape })
  }

  if (handlers.addNode) {
    shortcuts.push({ key: '=', handler: handlers.addNode })
  }

  if (handlers.addBranch) {
    shortcuts.push({ key: 'Tab', handler: handlers.addBranch })
  }

  if (handlers.addChild) {
    shortcuts.push({ key: 'Enter', handler: handlers.addChild })
  }

  if (handlers.clearNodeText) {
    shortcuts.push({ key: '-', handler: handlers.clearNodeText })
  }

  useKeyboard(shortcuts)
}
