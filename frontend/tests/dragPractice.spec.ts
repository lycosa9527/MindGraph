import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/composables/diagram/useDiagramSession', () => {
  const nodes = [
    {
      id: 'a',
      text: '预处理',
      type: 'branch',
      parentId: 'topic',
      data: {},
    },
    {
      id: 'b',
      text: '特征提取',
      type: 'branch',
      parentId: 'topic',
      data: {},
    },
    {
      id: 'topic',
      text: '主题',
      type: 'topic',
      data: {},
    },
  ]
  return {
    useDiagramSession: () => ({
      data: { nodes },
      type: 'mind_map',
      isLearningSheet: false,
      isNodeBlankedForLearningSheet: () => false,
      setLearningSheetMode: vi.fn(),
      setLearningSheetShowAnswers: vi.fn(),
      restoreNodeFromLearningSheet: vi.fn(),
      emptyNodeForLearningSheet: vi.fn(),
      applyRandomLearningSheetBlanks: vi.fn(),
      pushHistory: vi.fn(),
    }),
  }
})

vi.mock('@/stores/learningAssignmentCanvas', () => ({
  useLearningAssignmentCanvasStore: () => ({ showLearningSheet: true }),
}))

vi.mock('@/utils/claimThinkingCoinEvent', () => ({
  claimThinkingCoinEvent: vi.fn(),
}))

vi.mock('@/composables/core/notifications', () => ({
  notify: {
    warningKey: vi.fn(),
    successKey: vi.fn(),
    infoKey: vi.fn(),
  },
}))

vi.mock('@/stores/specLoader/utils', () => ({
  pickLearningSheetRandomNodeIds: (_nodes: unknown, _type: unknown, ratio?: number) => {
    if (ratio === 1) return ['a', 'b']
    return ['a']
  },
}))

describe('useDragPractice', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('starts play from its own blanks without learning-sheet mode', async () => {
    const mod = await import('@/composables/mindMap/useDragPractice')
    mod.resetDragPracticeUi()
    mod.startDragPracticeFromRandom()
    expect(mod.dragPracticeActive.value).toBe(true)
    expect(mod.dragPracticeBlankIds.value).toEqual(['a'])
    expect(mod.dragPracticeChips.value).toHaveLength(1)

    const chip = mod.dragPracticeChips.value[0]
    const matched = mod.dragPracticeDropOnNode('a', chip.text)
    expect(matched).toBe(true)
    expect(mod.dragPracticeFilledIds.value).toContain('a')
  })

  it('custom pick toggles blanks then starts play', async () => {
    const mod = await import('@/composables/mindMap/useDragPractice')
    mod.resetDragPracticeUi()
    mod.startDragPracticeFromCustomPick()
    expect(mod.dragPracticePicking.value).toBe(true)

    mod.toggleDragPracticeBlank('a')
    mod.toggleDragPracticeBlank('b')
    expect(mod.dragPracticeBlankIds.value).toEqual(expect.arrayContaining(['a', 'b']))

    const ok = mod.startDragPracticeWithExistingBlanks()
    expect(ok).toBe(true)
    expect(mod.dragPracticeActive.value).toBe(true)
    expect(mod.dragPracticePicking.value).toBe(false)
    expect(mod.dragPracticeChips.value).toHaveLength(2)

    const wrong = mod.dragPracticeDropOnNode('b', '不对')
    expect(wrong).toBe(false)
  })

  it('accepts a sibling answer on another blank in the same parent group', async () => {
    const mod = await import('@/composables/mindMap/useDragPractice')
    mod.resetDragPracticeUi()
    mod.startDragPracticeFromFullBlank()
    const chipB = mod.dragPracticeChips.value.find((row) => row.text === '特征提取')
    const chipA = mod.dragPracticeChips.value.find((row) => row.text === '预处理')
    expect(mod.dragPracticeDropOnNode('a', '特征提取', chipB?.id)).toBe(true)
    expect(mod.dragPracticeFilledIds.value).toEqual(['a'])
    expect(mod.dragPracticePlacedText.value.a).toBe('特征提取')
    expect(mod.dragPracticeUsedChipIds.value).toEqual([chipB?.id])
    expect(mod.dragPracticeDropOnNode('b', '预处理', chipA?.id)).toBe(true)
    expect(mod.dragPracticePlacedText.value.b).toBe('预处理')
    expect(mod.dragPracticeFilledIds.value).toEqual(['a', 'b'])
  })

  it('exit clears overlay blanks without learning-sheet APIs', async () => {
    const session = await import('@/composables/diagram/useDiagramSession')
    const store = session.useDiagramSession()
    const mod = await import('@/composables/mindMap/useDragPractice')
    mod.resetDragPracticeUi()
    mod.startDragPracticeFromFullBlank()
    expect(mod.dragPracticeActive.value).toBe(true)
    mod.exitDragPractice()
    expect(mod.dragPracticeActive.value).toBe(false)
    expect(mod.dragPracticeBlankIds.value).toEqual([])
    expect(store.setLearningSheetMode).not.toHaveBeenCalled()
    expect(store.emptyNodeForLearningSheet).not.toHaveBeenCalled()
  })
})
