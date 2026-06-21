import { describe, expect, it } from 'vitest'

import {
  resolveEnterKeyEvent,
  resolveTabKeyEvent,
} from '@/composables/canvasPage/canvasPageEditorShortcutRouting'
import { collabHistoryWouldBlock } from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import {
  MIND_MAP_SHORTCUT_GUIDE_ROWS,
  MIND_MAP_SHORTCUT_GUIDE_WIRED_ROW_IDS,
} from '@/config/mindMapShortcutGuide'

describe('canvasPageEditorShortcutRouting', () => {
  describe('resolveTabKeyEvent', () => {
    it('routes mind map Tab to add child', () => {
      expect(resolveTabKeyEvent('mindmap')).toBe('diagram:add_child_requested')
      expect(resolveTabKeyEvent('mind_map')).toBe('diagram:add_child_requested')
    })

    it('routes brace and flow maps Tab to add branch', () => {
      expect(resolveTabKeyEvent('brace_map')).toBe('diagram:add_branch_requested')
      expect(resolveTabKeyEvent('flow_map')).toBe('diagram:add_branch_requested')
    })

    it('routes other diagram types Tab to add node', () => {
      expect(resolveTabKeyEvent('bubble_map')).toBe('diagram:add_node_requested')
      expect(resolveTabKeyEvent('tree_map')).toBe('diagram:add_node_requested')
    })

    it('returns null for concept map', () => {
      expect(resolveTabKeyEvent('concept_map')).toBeNull()
    })
  })

  describe('resolveEnterKeyEvent', () => {
    it('routes mind map Enter to add sibling', () => {
      expect(resolveEnterKeyEvent('mindmap')).toBe('diagram:add_sibling_requested')
      expect(resolveEnterKeyEvent('mind_map')).toBe('diagram:add_sibling_requested')
    })

    it('routes tree and multi-flow maps Enter to add node', () => {
      expect(resolveEnterKeyEvent('tree_map')).toBe('diagram:add_node_requested')
      expect(resolveEnterKeyEvent('multi_flow_map')).toBe('diagram:add_node_requested')
    })

    it('routes brace and flow maps Enter to add child', () => {
      expect(resolveEnterKeyEvent('brace_map')).toBe('diagram:add_child_requested')
      expect(resolveEnterKeyEvent('flow_map')).toBe('diagram:add_child_requested')
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

describe('mindMapShortcutGuide parity', () => {
  it('lists every wired keyboard row in the guide config', () => {
    const rowIds = MIND_MAP_SHORTCUT_GUIDE_ROWS.map((row) => row.id)
    for (const wiredId of MIND_MAP_SHORTCUT_GUIDE_WIRED_ROW_IDS) {
      expect(rowIds).toContain(wiredId)
    }
  })

  it('documents mind-map Tab and Enter shortcuts', () => {
    const tabRow = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'tab')
    const enterRow = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'enter')
    expect(tabRow?.kind).toBe('keys')
    expect(enterRow?.kind).toBe('keys')
    if (tabRow?.kind === 'keys') {
      expect(tabRow.keys).toEqual(['Tab'])
    }
    if (enterRow?.kind === 'keys') {
      expect(enterRow.keys).toEqual(['Enter'])
    }
  })

  it('documents redo, save, clear text, and escape shortcuts', () => {
    const redo = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'redo')
    const save = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'save')
    const clearText = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'clearText')
    const cancel = MIND_MAP_SHORTCUT_GUIDE_ROWS.find((row) => row.id === 'cancel')

    expect(redo?.kind).toBe('keys')
    expect(save?.kind).toBe('keys')
    expect(clearText?.kind).toBe('keys')
    expect(cancel?.kind).toBe('keys')

    if (redo?.kind === 'keys') {
      expect(redo.keys).toContain('Ctrl+Shift+Z')
    }
    if (save?.kind === 'keys') {
      expect(save.keys).toEqual(['Ctrl+S'])
    }
    if (clearText?.kind === 'keys') {
      expect(clearText.keys).toEqual(['-'])
    }
    if (cancel?.kind === 'keys') {
      expect(cancel.keys).toEqual(['Esc'])
    }
  })
})

describe('collabHistoryWouldBlock', () => {
  const baseData = { nodes: [{ id: 'a', text: 'A' }, { id: 'b', text: 'B' }] }
  const prevData = { nodes: [{ id: 'a', text: 'A-old' }, { id: 'b', text: 'B' }] }

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
