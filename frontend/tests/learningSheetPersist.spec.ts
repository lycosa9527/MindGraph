import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  handleLearningSheetPickNodeClick,
  learningSheetFloatBarOpen,
  learningSheetPickActive,
  restoreLearningSheetUiFromDiagram,
  toggleLearningSheetAnswersVisibility,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'
import { useDiagramStore } from '@/stores/diagram'

describe('learning sheet persistence', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))
    setActivePinia(createPinia())
    learningSheetPickActive.value = false
    learningSheetFloatBarOpen.value = false
  })

  function loadMindMapWithBranch(): { branchId: string; branchText: string } {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')

    const branch = diagramStore.data?.nodes.find(
      (node) => node.type === 'branch' && String(node.text ?? '').trim().length > 0
    )
    if (!branch) {
      throw new Error('expected a branch node in default mind map template')
    }

    return { branchId: branch.id, branchText: String(branch.text ?? '').trim() }
  }

  function topicChildBranchIds(): string[] {
    const diagramStore = useDiagramStore()
    const connections = diagramStore.data?.connections ?? []
    return connections.filter((connection) => connection.source === 'topic').map((c) => c.target)
  }

  it('round-trips learning sheet blanks and show-answers preference via spec save/load', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()

    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)
    diagramStore.setLearningSheetShowAnswers(false)

    const spec = diagramStore.getSpecForSave()
    expect(spec).toBeTruthy()
    expect(spec!.is_learning_sheet).toBe(true)
    expect(spec!.learning_sheet_show_answers).toBe(false)

    const blankedNode = (spec!.nodes as { id: string; text?: string; data?: Record<string, unknown> }[]).find(
      (node) => node.id === branchId
    )
    expect(blankedNode?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect(blankedNode?.data?.hiddenAnswer).toBe(branchText)

    diagramStore.loadFromSpec(spec!, diagramStore.type!)

    expect(diagramStore.isLearningSheet).toBe(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(false)
    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(true)

    const reloaded = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(reloaded?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect((reloaded?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(branchText)
  })

  it('restores float bar UI when diagram reloads in learning sheet mode', () => {
    const diagramStore = useDiagramStore()
    loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)

    learningSheetFloatBarOpen.value = false
    restoreLearningSheetUiFromDiagram()

    expect(learningSheetFloatBarOpen.value).toBe(true)
    expect(learningSheetPickActive.value).toBe(false)
  })

  it('toggles show-answers preference', () => {
    const diagramStore = useDiagramStore()
    loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(true)

    expect(toggleLearningSheetAnswersVisibility()).toBe(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(false)

    expect(toggleLearningSheetAnswersVisibility()).toBe(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(true)

    diagramStore.setLearningSheetMode(false)
    expect(toggleLearningSheetAnswersVisibility()).toBe(false)
  })

  it('restores blanked text after adding a child (tree rebuild)', () => {
    const diagramStore = useDiagramStore()
    loadMindMapWithBranch()
    const l1Ids = topicChildBranchIds()
    if (l1Ids.length < 2) {
      throw new Error('expected at least two top-level branches')
    }
    const [blankId, addUnderId] = l1Ids
    const branchText = String(
      diagramStore.data?.nodes.find((node) => node.id === blankId)?.text ?? ''
    ).trim()

    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(blankId)
    expect(diagramStore.isNodeBlankedForLearningSheet(blankId)).toBe(true)

    expect(diagramStore.addMindMapChild(addUnderId)).toBe(true)

    expect(diagramStore.isLearningSheet).toBe(true)
    expect(diagramStore.isNodeBlankedForLearningSheet(blankId)).toBe(true)
    const afterAdd = diagramStore.data?.nodes.find((node) => node.id === blankId)
    expect(afterAdd?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect((afterAdd?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(branchText)

    diagramStore.restoreFromLearningSheetMode()
    expect(diagramStore.isLearningSheet).toBe(false)
    const restored = diagramStore.data?.nodes.find((node) => node.id === blankId)
    expect(restored?.text).toBe(branchText)
  })

  it('keeps underline-sized blanks and restore after deleting a sibling', () => {
    const diagramStore = useDiagramStore()
    loadMindMapWithBranch()
    const l1Ids = topicChildBranchIds()
    if (l1Ids.length < 2) {
      throw new Error('expected at least two top-level branches')
    }
    const [blankId, deleteId] = l1Ids
    const branchText = String(
      diagramStore.data?.nodes.find((node) => node.id === blankId)?.text ?? ''
    ).trim()

    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(blankId)
    const blankedBefore = diagramStore.data?.nodes.find((node) => node.id === blankId)
    const widthBefore = (blankedBefore?.data as { estimatedWidth?: number } | undefined)
      ?.estimatedWidth
    expect(widthBefore).toBeGreaterThanOrEqual(MIND_MAP_GEOMETRY.minWidth)

    expect(diagramStore.removeMindMapNodes([deleteId])).toBeGreaterThan(0)

    expect(diagramStore.isNodeBlankedForLearningSheet(blankId)).toBe(true)
    const afterDelete = diagramStore.data?.nodes.find((node) => node.id === blankId)
    expect(afterDelete?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect((afterDelete?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(
      branchText
    )
    const widthAfter = (afterDelete?.data as { estimatedWidth?: number } | undefined)
      ?.estimatedWidth
    expect(widthAfter).toBeGreaterThanOrEqual(widthBefore ?? MIND_MAP_GEOMETRY.minWidth)

    diagramStore.restoreFromLearningSheetMode()
    const restored = diagramStore.data?.nodes.find((node) => node.id === blankId)
    expect(restored?.text).toBe(branchText)
  })
})
