import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyAiBrainstormSelection } from '@/composables/aiBrainstorm/applyAiBrainstormSelection'
import type { NodeSuggestion } from '@/types/panels'

function makeSuggestion(
  partial: Partial<NodeSuggestion> & { id: string; text: string }
): NodeSuggestion {
  return {
    type: 'branch',
    ...partial,
  } as NodeSuggestion
}

describe('applyAiBrainstormSelection', () => {
  const addMindMapChild = vi.fn()
  const updateNode = vi.fn()
  const addMindMapBranch = vi.fn()
  const updatePanel = vi.fn()
  const clearSuggestions = vi.fn()
  const clearSession = vi.fn()
  const closePanel = vi.fn()
  const startSession = vi.fn().mockResolvedValue(true)
  const startSessionsForAllParents = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('applies stage-2 selections across all parent tabs, not only the active one', async () => {
    const diagramStore = {
      data: {
        nodes: [
          { id: 'topic', type: 'topic', text: 'Main' },
          { id: 'branch-r-1-1', type: 'branch', text: 'Alpha' },
          { id: 'branch-r-1-2', type: 'branch', text: 'Beta' },
        ],
        connections: [
          { source: 'topic', target: 'branch-r-1-1' },
          { source: 'topic', target: 'branch-r-1-2' },
        ],
      },
      updateNode,
      addMindMapChild,
      addMindMapBranch,
    }

    const closed = await applyAiBrainstormSelection({
      diagramStore: diagramStore as never,
      diagramKey: 'ai-brainstorm-mindmap-test',
      toApply: [
        makeSuggestion({
          id: 's1',
          text: 'Alpha child',
          parent_id: 'branch-r-1-1',
          mode: 'Alpha',
        }),
        makeSuggestion({
          id: 's2',
          text: 'Beta child',
          parent_id: 'branch-r-1-2',
          mode: 'Beta',
        }),
      ],
      stage: 'children',
      stageData: { branch_id: 'branch-r-1-1', branch_name: 'Alpha' },
      mode: 'Alpha',
      updatePanel,
      clearSuggestions,
      clearSession,
      closePanel,
      startSession,
      startSessionsForAllParents,
    })

    expect(closed).toBe(true)
    expect(addMindMapChild).toHaveBeenCalledWith('branch-r-1-1', 'Alpha child')
    expect(addMindMapChild).toHaveBeenCalledWith('branch-r-1-2', 'Beta child')
    expect(closePanel).toHaveBeenCalled()
    expect(clearSession).toHaveBeenCalled()
  })
})
