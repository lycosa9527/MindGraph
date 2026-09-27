import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { isMindMapDiagramType } from '@/composables/mindMap/mindMapArrowNavigation'

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
  { id: 'tab', labelKey: 'canvas.shortcutGuide.addChild', kind: 'keys', keys: ['Tab', 'Insert'] },
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
  {
    id: 'recalcLayout',
    labelKey: 'canvas.shortcutGuide.recalcLayout',
    kind: 'keys',
    keys: ['Ctrl+Shift+L'],
  },
  {
    id: 'learningSheetAnswers',
    labelKey: 'canvas.shortcutGuide.learningSheetAnswers',
    kind: 'keys',
    keys: ['Ctrl+Shift+H'],
  },
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
  'recalcLayout',
  'clearText',
  'learningSheetAnswers',
  'cancel',
] as const

const LEARNING_SHEET_SHORTCUT_ROW_ID = 'learningSheetAnswers'

/** Pin learning-sheet shortcut at top while mode is active (visible without scrolling). */
export function resolveMindMapShortcutGuideRows(
  isLearningSheet: boolean
): MindMapShortcutGuideRow[] {
  return pinLearningSheetShortcutRow(MIND_MAP_SHORTCUT_GUIDE_ROWS, isLearningSheet)
}

const MIND_MAP_ONLY_SHORTCUT_ROW_IDS = new Set(['tab', 'enter', 'arrows'])

function pinLearningSheetShortcutRow(
  rows: MindMapShortcutGuideRow[],
  isLearningSheet: boolean
): MindMapShortcutGuideRow[] {
  const learningRow = rows.find((row) => row.id === LEARNING_SHEET_SHORTCUT_ROW_ID)
  const otherRows = rows.filter((row) => row.id !== LEARNING_SHEET_SHORTCUT_ROW_ID)
  if (!isLearningSheet || !learningRow) return rows
  return [learningRow, ...otherRows]
}

function keysRow(id: string, labelKey: string, keys: string[]): MindMapShortcutGuideRow {
  return { id, labelKey, kind: 'keys', keys }
}

/** Enter adds a node for the clicked selection. Tab and Insert are not shortcuts. */
function thinkingMapInsertRows(diagramType: string | null | undefined): MindMapShortcutGuideRow[] {
  switch (diagramType) {
    case 'circle_map':
      return [keysRow('enter', 'canvas.toolbar.addAssociation', ['Enter'])]
    case 'bubble_map':
      return [keysRow('enter', 'canvas.toolbar.addAttribute', ['Enter'])]
    case 'bridge_map':
      return [keysRow('enter', 'canvas.toolbar.addAnalogyPair', ['Enter'])]
    case 'double_bubble_map':
    case 'tree_map':
    case 'brace_map':
    case 'flow_map':
    case 'multi_flow_map':
      return [keysRow('enter', 'canvas.toolbar.addNode', ['Enter'])]
    default:
      return []
  }
}

/**
 * Shortcut card for the open diagram.
 * Mind maps keep child / sibling / arrow navigation.
 * Thinking maps list Enter to add a node, and keep Space / double-click to edit.
 */
export function resolveDiagramShortcutGuideRows(
  diagramType: string | null | undefined,
  isLearningSheet: boolean
): MindMapShortcutGuideRow[] {
  if (isMindMapDiagramType(diagramType)) {
    return resolveMindMapShortcutGuideRows(isLearningSheet)
  }
  const shared = MIND_MAP_SHORTCUT_GUIDE_ROWS.filter(
    (row) => !MIND_MAP_ONLY_SHORTCUT_ROW_IDS.has(row.id)
  )
  const inserts = isThinkingMapDiagramType(diagramType) ? thinkingMapInsertRows(diagramType) : []
  return pinLearningSheetShortcutRow([...inserts, ...shared], isLearningSheet)
}
