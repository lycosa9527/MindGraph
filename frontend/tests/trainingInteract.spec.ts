import { describe, expect, it } from 'vitest'

import { builderDiagramNodes } from '@/composables/training/builderDiagramBridge'
import { addOverlay } from '@/composables/training/trainingBuilderSteps'
import {
  interactReadCursor,
  nodeHasLink,
  orderedReadNodes,
  overlaysForReadNode,
  playOrderIds,
  readFocusNodeId,
  readInteract,
  reorderReadIds,
  saveDragBlanks,
  saveQuiz,
  saveReadSequence,
  savedReadOrder,
  setDragBlankOrder,
  setInteractBlankHint,
  setInteractMode,
  setNodeVideo,
  setReadOrder,
  shuffledBlanks,
  toggleInteractBlank,
} from '@/composables/training/trainingInteract'
import { alignInteractWithDiagram } from '@/composables/training/trainingInteractAlign'
import { advancePlayCursor, canAdvancePlayCursor } from '@/composables/training/trainingMarkSteps'
import type { TrainingCourseStep } from '@/types/training'

function step(): TrainingCourseStep {
  return { position: 0, type: 'canvas', page_key: 'canvas' }
}

describe('trainingInteract', () => {
  it('clears the interaction when the mode is turned off', () => {
    const row = step()
    setInteractMode(row, 'read')
    expect(row.interact?.mode).toBe('read')
    setInteractMode(row, null)
    expect(row.interact).toBeNull()
  })

  it('stores the node text as the blank answer and removes it on the second click', () => {
    const row = step()
    toggleInteractBlank(row, { id: 'n1', text: '根' })
    toggleInteractBlank(row, { id: 'n2', text: '叶' })
    toggleInteractBlank(row, { id: 'n1', text: '根' })
    expect(row.interact?.mode).toBe('drag')
    expect(row.interact?.blanks).toEqual([{ node_id: 'n2', answer: '叶' }])
  })

  it('stores a hint on a knocked-out node', () => {
    const row = step()
    toggleInteractBlank(row, { id: 'n1', text: '根' })
    setInteractBlankHint(row, 'n1', '  想想根的位置  ')
    expect(row.interact?.blanks).toEqual([{ node_id: 'n1', answer: '根', hint: '想想根的位置' }])
    setInteractBlankHint(row, 'n1', '   ')
    expect(row.interact?.blanks).toEqual([{ node_id: 'n1', answer: '根' }])
  })

  it('keeps one quiz per node', () => {
    const row = step()
    saveQuiz(row, {
      node_id: 'n1',
      prompt: '这是什么',
      choices: [
        { id: 'a', label: '根', correct: true },
        { id: 'b', label: '叶', correct: false },
        { id: 'c', label: '花', correct: false },
      ],
    })
    saveQuiz(row, {
      node_id: 'n1',
      prompt: '改题',
      choices: [
        { id: 'a', label: '根', correct: false },
        { id: 'b', label: '叶', correct: true },
        { id: 'c', label: '花', correct: false },
      ],
    })
    expect(row.interact?.quizzes).toHaveLength(1)
    expect(row.interact?.quizzes[0]?.prompt).toBe('改题')
    expect(row.interact?.mode).toBe('quiz')
  })

  it('walks the saved order, then the rest of the diagram', () => {
    const nodes = [
      { id: 'a', text: 'A' },
      { id: 'b', text: 'B' },
      { id: 'c', text: 'C' },
    ]
    expect(orderedReadNodes(nodes, ['c', 'missing']).map((node) => node.id)).toEqual([
      'c',
      'a',
      'b',
    ])
  })

  it('ignores an unknown mode', () => {
    const row = step()
    row.interact = {
      mode: 'nope' as 'read',
      read_order: [],
      blanks: [],
      quizzes: [],
      sequence_saved: false,
      node_extras: [],
    }
    expect(readInteract(row)).toBeNull()
  })

  it('saves a dragged reading order and keeps unknown nodes at the end', () => {
    const row = step()
    setReadOrder(row, reorderReadIds(['a', 'b', 'c', 'd'], 0, 2))
    expect(row.interact?.read_order).toEqual(['b', 'c', 'a', 'd'])
    expect(row.interact?.mode).toBe('read')
    const nodes = [
      { id: 'a', text: 'A' },
      { id: 'b', text: 'B' },
      { id: 'c', text: 'C' },
      { id: 'e', text: 'E' },
    ]
    expect(orderedReadNodes(nodes, row.interact?.read_order ?? []).map((node) => node.id)).toEqual([
      'b',
      'c',
      'a',
      'e',
    ])
  })

  it('commits guided reading and drops that commitment for another mode', () => {
    const row = step()
    saveReadSequence(row, ['c', 'a'])
    expect(row.interact?.sequence_saved).toBe(true)
    expect(row.interact?.mode).toBe('read')
    expect(row.interact?.read_order).toEqual(['c', 'a'])
    const previousNodes = builderDiagramNodes.value
    builderDiagramNodes.value = []
    expect(playOrderIds(row)).toEqual(['c', 'a'])
    builderDiagramNodes.value = previousNodes
    setInteractMode(row, 'drag')
    expect(row.interact?.sequence_saved).toBe(false)
    expect(row.interact?.mode).toBe('drag')
  })

  it('commits knocked-out nodes for preview and shuffles that list', () => {
    const row = step()
    toggleInteractBlank(row, { id: 'n1', text: '根' })
    toggleInteractBlank(row, { id: 'n2', text: '叶' })
    toggleInteractBlank(row, { id: 'n3', text: '花' })
    expect(row.interact?.sequence_saved).toBe(false)
    saveDragBlanks(row)
    expect(row.interact?.sequence_saved).toBe(true)
    expect(row.interact?.mode).toBe('drag')
    toggleInteractBlank(row, { id: 'n4', text: '果' })
    expect(row.interact?.sequence_saved).toBe(false)
    saveDragBlanks(row)
    expect(row.interact?.sequence_saved).toBe(true)
    const ids = (row.interact?.blanks ?? []).map((blank) => blank.node_id)
    const shuffled = shuffledBlanks(row.interact?.blanks ?? []).map((blank) => blank.node_id)
    expect(shuffled).toHaveLength(4)
    expect(new Set(shuffled)).toEqual(new Set(ids))
    setInteractMode(row, 'read')
    expect(row.interact?.sequence_saved).toBe(false)
  })

  it('links a walk node to a text bubble, a picture, and a library video', () => {
    const row = step()
    addOverlay(row, 'text', { node_id: 'n1', text: '' })
    addOverlay(row, 'role', { node_id: 'n1', asset_id: 'pic', link: 'image', src: 'u' })
    addOverlay(row, 'arrow', {})
    expect(nodeHasLink(row, 'n1', 'note')).toBe(true)
    expect(nodeHasLink(row, 'n1', 'image')).toBe(true)
    expect(nodeHasLink(row, 'n1', 'mascot')).toBe(false)
    expect(overlaysForReadNode(row.overlays || [], 'n1').map((overlay) => overlay.kind)).toEqual([
      'text',
      'role',
      'arrow',
    ])
    expect(overlaysForReadNode(row.overlays || [], null).map((overlay) => overlay.kind)).toEqual([
      'arrow',
    ])
    setNodeVideo(row, 'n1', 'vid-1')
    expect(nodeHasLink(row, 'n1', 'video')).toBe(true)
    expect(row.interact?.node_extras).toEqual([
      { node_id: 'n1', kinds: ['video'], vod_media_id: 'vid-1' },
    ])
    setNodeVideo(row, 'n1', null)
    expect(row.interact?.node_extras).toEqual([])
  })

  it('plays a saved order from the first node and keeps that node in focus', () => {
    const row = step()
    saveReadSequence(row, ['c', 'a', 'b'])
    expect(savedReadOrder(row)).toEqual(['c', 'a', 'b'])
    expect(readFocusNodeId(row)).toBe('c')
    interactReadCursor.value = 1
    expect(readFocusNodeId(row)).toBe('a')
    interactReadCursor.value = 0
    const deck = [row, step()]
    expect(advancePlayCursor(deck, 0, 1)).toBe(0)
    expect(interactReadCursor.value).toBe(1)
    expect(readFocusNodeId(row)).toBe('a')
    expect(advancePlayCursor(deck, 0, 1)).toBe(0)
    expect(readFocusNodeId(row)).toBe('b')
    expect(advancePlayCursor(deck, 0, 1)).toBe(1)
    expect(interactReadCursor.value).toBe(0)
  })

  it('walks the visible order list before it is saved', () => {
    const row = step()
    setInteractMode(row, 'read')
    builderDiagramNodes.value = [
      { id: 'a', text: 'A' },
      { id: 'b', text: 'B' },
      { id: 'c', text: 'C' },
    ]
    interactReadCursor.value = 0
    const deck = [row]
    expect(savedReadOrder(row)).toEqual([])
    expect(canAdvancePlayCursor(deck, 0, 1)).toBe(true)
    expect(advancePlayCursor(deck, 0, 1)).toBe(0)
    expect(interactReadCursor.value).toBe(1)
    expect(readFocusNodeId(row)).toBe('b')
    builderDiagramNodes.value = []
    interactReadCursor.value = 0
  })

  it('finishes marks and the node list before the next filmstrip slide', () => {
    const first = step()
    first.mark_steps = 2
    first.mark_step = 1
    saveReadSequence(first, ['a', 'b'])
    const deck = [first, step(), step()]
    interactReadCursor.value = 0
    expect(canAdvancePlayCursor(deck, 0, 1)).toBe(true)
    expect(advancePlayCursor(deck, 0, 1)).toBe(0)
    expect(first.mark_step).toBe(2)
    expect(interactReadCursor.value).toBe(0)
    expect(advancePlayCursor(deck, 0, 1)).toBe(0)
    expect(interactReadCursor.value).toBe(1)
    expect(advancePlayCursor(deck, 0, 1)).toBe(1)
    expect(advancePlayCursor(deck, 1, 1)).toBe(2)
    expect(canAdvancePlayCursor(deck, 2, 1)).toBe(false)
    interactReadCursor.value = 0
  })

  it('orders chips by node id so the tray is stable', () => {
    const first = shuffledBlanks([
      { node_id: 'bbbb', answer: 'B' },
      { node_id: 'aaaa', answer: 'A' },
    ])
    const second = shuffledBlanks([
      { node_id: 'aaaa', answer: 'A' },
      { node_id: 'bbbb', answer: 'B' },
    ])
    expect(first.map((row) => row.node_id)).toEqual(second.map((row) => row.node_id))
  })

  it('keeps drag-blank order and hints when the teacher reorders the list', () => {
    const row = step()
    toggleInteractBlank(row, { id: 'n1', text: '根' })
    toggleInteractBlank(row, { id: 'n2', text: '叶' })
    toggleInteractBlank(row, { id: 'n3', text: '花' })
    setInteractBlankHint(row, 'n2', '想想叶子')
    saveDragBlanks(row)
    setDragBlankOrder(row, ['n3', 'n1', 'n2'])
    expect(row.interact?.blanks).toEqual([
      { node_id: 'n3', answer: '花' },
      { node_id: 'n1', answer: '根' },
      { node_id: 'n2', answer: '叶', hint: '想想叶子' },
    ])
    expect(row.interact?.sequence_saved).toBe(true)
  })

  it('rewrites the guided-reading list when the diagram nodes change', () => {
    const row = step()
    saveReadSequence(row, ['gone', 'keep'])
    addOverlay(row, 'text', { node_id: 'gone', text: '旧' })
    addOverlay(row, 'arrow', {})
    expect(
      alignInteractWithDiagram(row, [
        { id: 'keep', text: '留下' },
        { id: 'added', text: '新节点' },
      ])
    ).toBe(true)
    expect(row.interact?.read_order).toEqual(['keep', 'added'])
    expect(row.interact?.sequence_saved).toBe(true)
    expect(row.overlays?.some((overlay) => overlay.node_id === 'gone')).toBe(false)
    expect(row.overlays?.some((overlay) => overlay.kind === 'arrow')).toBe(true)
  })

  it('updates drag answers from live node text and drops deleted blanks', () => {
    const row = step()
    toggleInteractBlank(row, { id: 'keep', text: '旧词' })
    toggleInteractBlank(row, { id: 'gone', text: '删除' })
    setInteractBlankHint(row, 'keep', '提示')
    saveDragBlanks(row)
    expect(
      alignInteractWithDiagram(row, [
        { id: 'keep', text: '新词' },
        { id: 'other', text: '其他' },
      ])
    ).toBe(true)
    expect(row.interact?.blanks).toEqual([{ node_id: 'keep', answer: '新词', hint: '提示' }])
    expect(row.interact?.sequence_saved).toBe(true)
    expect(row.interact?.read_order).toEqual([])
  })

  it('drops the play-ready flag when generate replaces every saved node', () => {
    const row = step()
    saveReadSequence(row, ['old-a', 'old-b'])
    expect(
      alignInteractWithDiagram(row, [
        { id: 'new-a', text: 'A' },
        { id: 'new-b', text: 'B' },
      ])
    ).toBe(true)
    expect(row.interact?.read_order).toEqual(['new-a', 'new-b'])
    expect(row.interact?.sequence_saved).toBe(false)
  })
})
