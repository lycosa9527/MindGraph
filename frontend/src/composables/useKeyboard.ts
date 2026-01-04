/**
 * Keyboard Composable - Keyboard shortcuts
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
  function handleKeydown(event: KeyboardEvent): void {
    for (const shortcut of shortcuts) {
      const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase()
      const ctrlMatch = !!shortcut.ctrl === (event.ctrlKey || event.metaKey)
      const shiftMatch = !!shortcut.shift === event.shiftKey
      const altMatch = !!shortcut.alt === event.altKey

      if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
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
  paste?: () => void
  escape?: () => void
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

  if (handlers.paste) {
    shortcuts.push({ key: 'v', ctrl: true, handler: handlers.paste, preventDefault: false })
  }

  if (handlers.escape) {
    shortcuts.push({ key: 'Escape', handler: handlers.escape })
  }

  useKeyboard(shortcuts)
}
