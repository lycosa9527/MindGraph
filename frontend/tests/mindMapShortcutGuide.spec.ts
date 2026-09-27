import { describe, expect, it } from 'vitest'

import {
  resolveEnterKeyEvent,
  resolveInsertKeyEvent,
  resolveTabKeyEvent,
} from '@/composables/canvasPage/canvasPageEditorShortcutRouting'
import { collabHistoryWouldBlock } from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import {
  MIND_MAP_SHORTCUT_GUIDE_ROWS,
  MIND_MAP_SHORTCUT_GUIDE_WIRED_ROW_IDS,
  resolveDiagramShortcutGuideRows,
  resolveMindMapShortcutGuideRows,
} from '@/config/mindMapShortcutGuide'

describe('canvasPageEditorShortcutRouting', () => {
  describe('resolveTabKeyEvent', () => {
    it('routes mind map Tab to add child', () => {
      expect(resolveTabKeyEvent('mindmap')).toBe('diagram:add_child_requested')
      expect(resolveTabKeyEvent('mind_map')).toBe('diagram:add_child_requested')
    })

    it('does not use Tab on thinking maps', () => {
      expect(resolveTabKeyEvent('brace_map')).toBeNull()
      expect(resolveTabKeyEvent('flow_map')).toBeNull()
      expect(resolveTabKeyEvent('bubble_map')).toBeNull()
      expect(resolveTabKeyEvent('circle_map')).toBeNull()
      expect(resolveTabKeyEvent('tree_map')).toBeNull()
      expect(resolveTabKeyEvent('multi_flow_map')).toBeNull()
    })

    it('returns null for concept map', () => {
      expect(resolveTabKeyEvent('concept_map')).toBeNull()
    })
  })

  describe('resolveInsertKeyEvent', () => {
    it('routes mind map Insert to add child (Tab alias)', () => {
      expect(resolveInsertKeyEvent('mindmap')).toBe('diagram:add_child_requested')
      expect(resolveInsertKeyEvent('mind_map')).toBe('diagram:add_child_requested')
    })

    it('does not use Insert on thinking maps', () => {
      expect(resolveInsertKeyEvent('brace_map')).toBeNull()
      expect(resolveInsertKeyEvent('flow_map')).toBeNull()
      expect(resolveInsertKeyEvent('bubble_map')).toBeNull()
      expect(resolveInsertKeyEvent('tree_map')).toBeNull()
      expect(resolveInsertKeyEvent('multi_flow_map')).toBeNull()
    })

    it('ignores Insert on concept maps', () => {
      expect(resolveInsertKeyEvent('concept_map')).toBeNull()
      expect(resolveInsertKeyEvent(null)).toBeNull()
    })
  })

  describe('resolveEnterKeyEvent', () => {
    it('routes mind map Enter to add sibling', () => {
      expect(resolveEnterKeyEvent('mindmap')).toBe('diagram:add_sibling_requested')
      expect(resolveEnterKeyEvent('mind_map')).toBe('diagram:add_sibling_requested')
    })

    it('routes thinking maps Enter to add node for the selection', () => {
      expect(resolveEnterKeyEvent('tree_map')).toBe('diagram:add_node_requested')
      expect(resolveEnterKeyEvent('multi_flow_map')).toBe('diagram:add_node_requested')
      expect(resolveEnterKeyEvent('brace_map')).toBe('diagram:add_node_requested')
      expect(resolveEnterKeyEvent('flow_map')).toBe('diagram:add_node_requested')
      expect(resolveEnterKeyEvent('double_bubble_map')).toBe('diagram:add_node_requested')
    })

    it('returns null for concept map only', () => {
      expect(resolveEnterKeyEvent('concept_map')).toBeNull()
    })

    it('routes bubble and circle maps Enter to add node', () => {
      expect(resolveEnterKeyEvent('bubble_map')).toBe('diagram:add_node_requested')
      expect(resolveEnterKeyEvent('circle_map')).toBe('diagram:add_node_requested')
      expect(resolveEnterKeyEvent('bridge_map')).toBe('diagram:add_node_requested')
    })
  })
})

describe('thinking map shortcut guide', () => {
  it('does not copy mind-map child, sibling, or arrow rows', () => {
    const rows = resolveDiagramShortcutGuideRows('circle_map', false)
    const labels = rows.map((row) => row.labelKey)
    const enter = rows.find((row) => row.id === 'enter')
    expect(labels).toContain('canvas.toolbar.addAssociation')
    expect(enter).toMatchObject({ kind: 'keys', keys: ['Enter'] })
    expect(rows.some((row) => row.kind === 'keys' && row.keys.includes('Tab'))).toBe(false)
    expect(rows.some((row) => row.kind === 'keys' && row.keys.includes('Insert'))).toBe(false)
    expect(labels).not.toContain('canvas.shortcutGuide.addChild')
    expect(labels).not.toContain('canvas.shortcutGuide.addSibling')
    expect(rows.some((row) => row.kind === 'arrows')).toBe(false)
  })

  it('lists Enter as the tree-map add shortcut', () => {
    const rows = resolveDiagramShortcutGuideRows('tree_map', false)
    const enter = rows.find((row) => row.id === 'enter')
    expect(rows.find((row) => row.id === 'tab')).toBeUndefined()
    expect(enter).toMatchObject({
      labelKey: 'canvas.toolbar.addNode',
      kind: 'keys',
      keys: ['Enter'],
    })
  })
})

describe('mindMapShortcutGuide parity', () => {
  it('lists every wired keyboard row in the guide config', () => {
    const rowIds = MIND_MAP_SHORTCUT_GUIDE_ROWS.map((row) => row.id)
    for (const wiredId of MIND_MAP_SHORTCUT_GUIDE_WIRED_ROW_IDS) {
      expect(rowIds).toContain(wiredId)
    }
  })

  it('documents mind-map Tab/Insert and Enter shortcuts', () => {
    const tabRow = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'tab')
    const enterRow = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'enter')
    expect(tabRow?.kind).toBe('keys')
    expect(enterRow?.kind).toBe('keys')
    if (tabRow?.kind === 'keys') {
      expect(tabRow.keys).toEqual(['Tab', 'Insert'])
    }
    if (enterRow?.kind === 'keys') {
      expect(enterRow.keys).toEqual(['Enter'])
    }
  })

  it('documents redo, save, clear text, and escape shortcuts', () => {
    const redo = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'redo')
    const save = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'save')
    const recalcLayout = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'recalcLayout')
    const clearText = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'clearText')
    const cancel = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'cancel')

    expect(redo?.kind).toBe('keys')
    expect(save?.kind).toBe('keys')
    expect(recalcLayout?.kind).toBe('keys')
    expect(clearText?.kind).toBe('keys')
    expect(cancel?.kind).toBe('keys')

    if (redo?.kind === 'keys') {
      expect(redo.keys).toContain('Ctrl+Shift+Z')
    }
    if (save?.kind === 'keys') {
      expect(save.keys).toEqual(['Ctrl+S'])
    }
    if (recalcLayout?.kind === 'keys') {
      expect(recalcLayout.keys).toEqual(['Ctrl+Shift+L'])
    }
    if (clearText?.kind === 'keys') {
      expect(clearText.keys).toEqual(['-'])
    }
    const learningSheetAnswers = MIND_MAP_SHORTCUT_GUIDE_ROWS.find(
      (row) => row.id === 'learningSheetAnswers'
    )
    expect(learningSheetAnswers?.kind).toBe('keys')
    if (learningSheetAnswers?.kind === 'keys') {
      expect(learningSheetAnswers.keys).toEqual(['Ctrl+Shift+H'])
    }
    if (cancel?.kind === 'keys') {
      expect(cancel.keys).toEqual(['Esc'])
    }
  })

  it('pins learning sheet answers shortcut at top while learning sheet mode is active', () => {
    const pinned = resolveMindMapShortcutGuideRows(true)
    expect(pinned[0]?.id).toBe('learningSheetAnswers')

    const normal = resolveMindMapShortcutGuideRows(false)
    expect(normal.map((row) => row.id)).toEqual(MIND_MAP_SHORTCUT_GUIDE_ROWS.map((row) => row.id))
  })
})

describe('collabHistoryWouldBlock', () => {
  const baseData = {
    nodes: [
      { id: 'a', text: 'A' },
      { id: 'b', text: 'B' },
    ],
  }
  const prevData = {
    nodes: [
      { id: 'a', text: 'A-old' },
      { id: 'b', text: 'B' },
    ],
  }

  it('returns false when not in a workshop', () => {
    expect(
      collabHistoryWouldBlock('undo', {
        workshopCode: null,
        activeEditors: new Map([['a', { user_id: 99 }]]),
        currentUserId: 1,
        history: [{ data: prevData }],
        historyIndex: 1,
        data: baseData,
      })
    ).toBe(false)
  })

  it('blocks undo when another user is editing a changed node', () => {
    expect(
      collabHistoryWouldBlock('undo', {
        workshopCode: 'WS1',
        activeEditors: new Map([['a', { user_id: 99 }]]),
        currentUserId: 1,
        history: [{ data: prevData }],
        historyIndex: 1,
        data: baseData,
      })
    ).toBe(true)
  })

  it('allows undo when the current user holds the active editor lock', () => {
    expect(
      collabHistoryWouldBlock('undo', {
        workshopCode: 'WS1',
        activeEditors: new Map([['a', { user_id: 1 }]]),
        currentUserId: 1,
        history: [{ data: prevData }],
        historyIndex: 1,
        data: baseData,
      })
    ).toBe(false)
  })
})
