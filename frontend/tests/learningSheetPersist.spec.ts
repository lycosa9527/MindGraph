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

  it('stores a bilingual worksheet baseline without a PostgreSQL-rejected null', () => {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')
    const topic = diagramStore.data?.nodes.find((node) => node.id === 'topic')
    if (!topic) {
      throw new Error('expected a topic node')
    }
    const primary = String(topic.text ?? '')
    expect(diagramStore.updateNode('topic', { textSecondary: 'buoyancy' })).toBe(true)
    diagramStore.setLearningSheetMode(true)

    const spec = diagramStore.getSpecForSave()
    const baseline = spec?.learning_sheet_baseline as { textsById?: Record<string, string> } | undefined
    expect(baseline?.textsById?.topic).toBe(JSON.stringify([primary, 'buoyancy']))
    expect(JSON.stringify(spec)).not.toContain('\u0000')
  })

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

  it('keeps an in-mode edit on the canvas and warns that restore would overwrite it', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)

    expect(diagramStore.updateNode(branchId, { text: 'bbb' })).toBe(true)

    const edited = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(edited?.text).toBe('bbb')
    expect((edited?.data as { label?: string } | undefined)?.label).toBe('bbb')
    expect(diagramStore.learningSheetHasUserDiagramEdits()).toBe(true)
    expect(diagramStore.learningSheetRestoreOverwritesDiagram()).toBe(true)

    diagramStore.restoreFromLearningSheetMode()
    expect(diagramStore.data?.nodes.find((node) => node.id === branchId)?.text).toBe(branchText)
  })

  it('replaces a blanked node answer when the content is edited', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)
    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(true)

    expect(diagramStore.commitLearningSheetNodeContent(branchId, '')).toBe(false)
    expect(diagramStore.updateNode(branchId, { text: branchText })).toBe(true)
    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(true)
    expect(diagramStore.data?.nodes.find((node) => node.id === branchId)?.text).toBe(
      LEARNING_SHEET_BLANK_TEXT
    )
    expect(diagramStore.hiddenAnswers).toContain(branchText)
    const stillBlanked = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect((stillBlanked?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(
      branchText
    )

    expect(diagramStore.updateNode(branchId, { text: 'bbb' })).toBe(true)

    const edited = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(edited?.text).toBe('bbb')
    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(false)
    expect((edited?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBeUndefined()
    expect(diagramStore.hiddenAnswers).not.toContain(branchText)
    expect(diagramStore.hiddenAnswers).not.toContain('bbb')
    expect(diagramStore.learningSheetRestoreOverwritesDiagram()).toBe(true)

    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)
    const reblanked = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect((reblanked?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe('bbb')
    expect(diagramStore.hiddenAnswers).toContain('bbb')
    expect(diagramStore.hiddenAnswers).not.toContain(branchText)

    diagramStore.restoreFromLearningSheetMode()
    expect(diagramStore.data?.nodes.find((node) => node.id === branchId)?.text).toBe(branchText)
  })

  it('asks to confirm restore after content is cleared, even before wording changes', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.learningSheetRestoreOverwritesDiagram()).toBe(false)

    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)
    expect(diagramStore.learningSheetRestoreOverwritesDiagram()).toBe(true)
    expect(diagramStore.learningSheetHasUserDiagramEdits()).toBe(false)

    const spec = diagramStore.getSpecForSave()
    if (!spec || !diagramStore.type) {
      throw new Error('expected a saved learning sheet spec')
    }
    expect(spec.learning_sheet_baseline).toBeTruthy()
    diagramStore.loadFromSpec(spec, diagramStore.type)
    expect(diagramStore.learningSheetRestoreOverwritesDiagram()).toBe(true)
    diagramStore.restoreFromLearningSheetMode()
    expect(diagramStore.data?.nodes.find((node) => node.id === branchId)?.text).toBe(branchText)
  })

  it('keeps the other reference answers when one blanked node is edited', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()
    const other = diagramStore.data?.nodes.find(
      (node) => node.type === 'branch' && node.id !== branchId && String(node.text ?? '').trim()
    )
    if (!other) {
      throw new Error('expected a second branch node')
    }
    const otherText = String(other.text).trim()
    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)
    handleLearningSheetPickNodeClick(other.id)
    expect(diagramStore.hiddenAnswers).toContain(branchText)
    expect(diagramStore.hiddenAnswers).toContain(otherText)

    diagramStore.updateNode(branchId, { text: 'bbb' })

    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(false)
    expect(diagramStore.isNodeBlankedForLearningSheet(other.id)).toBe(true)
    expect(diagramStore.hiddenAnswers).not.toContain(branchText)
    expect(diagramStore.hiddenAnswers).not.toContain('bbb')
    expect(diagramStore.hiddenAnswers).toContain(otherText)
    const otherNode = diagramStore.data?.nodes.find((node) => node.id === other.id)
    expect((otherNode?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(otherText)
  })

  it('drops a stale answer key when a revealed node is edited', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)
    handleLearningSheetPickNodeClick(branchId)
    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(false)
    const revealed = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect((revealed?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(branchText)

    diagramStore.updateNode(branchId, { text: 'bbb' })

    const edited = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(edited?.text).toBe('bbb')
    expect((edited?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBeUndefined()
    expect(diagramStore.hiddenAnswers).not.toContain(branchText)

    diagramStore.applyLearningSheetView()
    const afterView = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(afterView?.text).toBe('bbb')
    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(false)
    expect(diagramStore.hiddenAnswers).not.toContain(branchText)
  })
})
