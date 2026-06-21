/** Mind-map v2 shortcut guide rows (display-only reference panel). */

export type MindMapShortcutGuideRow =
  | {
      id: string
      labelKey: string
      kind: 'keys'
      keys: string[]
    }
  | {
      id: string
      labelKey: string
      kind: 'edit'
    }
  | {
      id: string
      labelKey: string
      kind: 'arrows'
    }
  | {
      id: string
      labelKey: string
      kind: 'hint'
      hintKey: string
      icon: 'mouse' | 'hand'
    }

export const MIND_MAP_SHORTCUT_GUIDE_ROWS: MindMapShortcutGuideRow[] = [
  { id: 'tab', labelKey: 'canvas.shortcutGuide.addChild', kind: 'keys', keys: ['Tab'] },
  { id: 'enter', labelKey: 'canvas.shortcutGuide.addSibling', kind: 'keys', keys: ['Enter'] },
  { id: 'edit', labelKey: 'canvas.shortcutGuide.editText', kind: 'edit' },
  {
    id: 'delete',
    labelKey: 'canvas.shortcutGuide.deleteNode',
    kind: 'keys',
    keys: ['Delete', 'Backspace'],
  },
  { id: 'arrows', labelKey: 'canvas.shortcutGuide.selectNav', kind: 'arrows' },
  { id: 'undo', labelKey: 'canvas.shortcutGuide.undo', kind: 'keys', keys: ['Ctrl+Z'] },
  {
    id: 'redo',
    labelKey: 'canvas.shortcutGuide.redo',
    kind: 'keys',
    keys: ['Ctrl+Shift+Z', 'Ctrl+Y'],
  },
  { id: 'save', labelKey: 'canvas.shortcutGuide.save', kind: 'keys', keys: ['Ctrl+S'] },
  { id: 'clearText', labelKey: 'canvas.shortcutGuide.clearText', kind: 'keys', keys: ['-'] },
  { id: 'cancel', labelKey: 'canvas.shortcutGuide.cancel', kind: 'keys', keys: ['Esc'] },
  {
    id: 'multiSelect',
    labelKey: 'canvas.shortcutGuide.multiSelect',
    kind: 'hint',
    hintKey: 'canvas.shortcutGuide.multiSelectHint',
    icon: 'mouse',
  },
  {
    id: 'canvasPan',
    labelKey: 'canvas.shortcutGuide.canvasPan',
    kind: 'hint',
    hintKey: 'canvas.shortcutGuide.canvasPanHint',
    icon: 'hand',
  },
]

/** Row ids that must have matching keyboard handlers in useCanvasPageEditorShortcuts. */
export const MIND_MAP_SHORTCUT_GUIDE_WIRED_ROW_IDS = [
  'tab',
  'enter',
  'edit',
  'delete',
  'arrows',
  'undo',
  'redo',
  'save',
  'clearText',
  'cancel',
] as const
