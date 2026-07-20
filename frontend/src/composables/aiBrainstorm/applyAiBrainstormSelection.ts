/**
 * Apply AI Brainstorm selections to a mind map (stage-1 branches → stage-2 children).
 * Isolated from node-palette applySelection so the two modules stay independent.
 */
import { nextTick } from 'vue'

import { i18n } from '@/i18n'
import { getPlaceholderNodes } from '@/composables/nodePalette/placeholderHelpers'
import {
  type Stage2Parent,
  buildStageDataForParent,
  getStage2ParentsForDiagram,
  stage2StageNameForType,
} from '@/composables/nodePalette/stageHelpers'
import { useDiagramStore } from '@/stores'
import type { NodeSuggestion } from '@/types/panels'

export interface ApplyAiBrainstormContext {
  diagramStore: ReturnType<typeof useDiagramStore>
  diagramKey: string
  toApply: NodeSuggestion[]
  stage: string | undefined
  stageData: Record<string, unknown> | undefined
  mode: string
  updatePanel: (updates: {
    selected?: string[]
    stage?: string | null
    stage_data?: Record<string, unknown> | null
    mode?: string | null
    sourceTabs?: { id: string; name: string }[]
  }) => void
  clearSuggestions: () => void
  clearSession: (key: string) => void
  closePanel: () => void
  startSession: (opts?: { keepSessionId?: boolean }) => Promise<boolean>
  startSessionsForAllParents: (parents: Stage2Parent[]) => Promise<void>
}

function suggestionBelongsToParent(
  suggestion: NodeSuggestion,
  parentId: string | null,
  parentName: string
): boolean {
  if (parentId && suggestion.parent_id) {
    return suggestion.parent_id === parentId
  }
  const mode = (suggestion.mode ?? '').trim()
  return !parentName || mode === parentName || mode === ''
}

export async function applyAiBrainstormSelection(
  ctx: ApplyAiBrainstormContext
): Promise<boolean> {
  const {
    diagramStore,
    diagramKey,
    toApply,
    stage,
    stageData,
    mode,
    updatePanel,
    clearSuggestions,
    clearSession,
    closePanel,
    startSession,
    startSessionsForAllParents,
  } = ctx

  const nodes = diagramStore.data?.nodes ?? []
  const connections = diagramStore.data?.connections
  const stageDataTyped = (stageData ?? {}) as {
    branch_id?: string
    branch_name?: string
  }
  const parentId = stage === 'children' ? (stageDataTyped.branch_id ?? null) : null
  const parentNameNorm = (mode ?? '').trim()

  const toApplyFiltered =
    stage === 'children' && (parentId || parentNameNorm)
      ? toApply.filter((s) => suggestionBelongsToParent(s, parentId, parentNameNorm))
      : toApply

  const placeholders = getPlaceholderNodes('mindmap', nodes, mode, stage, parentId, connections)
  let suggestionIndex = 0
  for (const slot of placeholders) {
    if (suggestionIndex >= toApplyFiltered.length) break
    const suggestion = toApplyFiltered[suggestionIndex]
    if (suggestion) {
      diagramStore.updateNode(slot.id, { text: suggestion.text })
      suggestionIndex += 1
    }
  }

  const remainder = toApplyFiltered.slice(suggestionIndex)
  const isStage1 = stage === 'branches'

  if (remainder.length === 0 && !isStage1) {
    updatePanel({ selected: [] })
    clearSession(diagramKey)
    closePanel()
    return true
  }

  if (remainder.length === 0 && isStage1) {
    return transitionToStage2(ctx)
  }

  if (stage === 'children') {
    const branchId = stageDataTyped.branch_id
    const branchName = (stageDataTyped.branch_name ?? '').trim()
    let resolvedParentId =
      branchId ??
      nodes.find(
        (n) =>
          (n.id.startsWith('branch-l-') || n.id.startsWith('branch-r-')) &&
          (n.text ?? '').trim() === branchName
      )?.id
    if (!resolvedParentId && branchName && connections) {
      const fallbackParents = getStage2ParentsForDiagram('mindmap', nodes, connections)
      const match = fallbackParents.find((p) => (p.name ?? '').trim() === branchName)
      resolvedParentId = match?.id ?? fallbackParents[0]?.id ?? null
    }
    if (resolvedParentId) {
      const pid = resolvedParentId
      remainder.forEach((s) => {
        const text = (s.text ?? '').trim()
        if (text) diagramStore.addMindMapChild(pid, text)
      })
    }
  } else {
    remainder.forEach((s) => {
      const text = (s.text ?? '').trim()
      if (text) {
        diagramStore.addMindMapBranch('right', text, String(i18n.global.t('diagram.newChild')))
      }
    })
  }

  if (isStage1 && remainder.length > 0) {
    await nextTick()
    return transitionToStage2(ctx)
  }

  updatePanel({ selected: [] })
  clearSession(diagramKey)
  closePanel()
  return true
}

async function transitionToStage2(ctx: ApplyAiBrainstormContext): Promise<boolean> {
  const {
    diagramStore,
    diagramKey,
    updatePanel,
    clearSuggestions,
    clearSession,
    closePanel,
    startSession,
    startSessionsForAllParents,
  } = ctx
  const currentNodes = diagramStore.data?.nodes ?? []
  const parents = getStage2ParentsForDiagram(
    'mindmap',
    currentNodes,
    diagramStore.data?.connections
  )
  if (parents.length === 0) {
    updatePanel({ selected: [] })
    clearSession(diagramKey)
    closePanel()
    return true
  }

  const tabs = parents.map((p) => ({ id: p.id, name: p.name }))
  updatePanel({
    stage: stage2StageNameForType('mindmap'),
    stage_data: buildStageDataForParent(parents[0], 'mindmap'),
    mode: parents[0].name,
    selected: [],
    sourceTabs: tabs,
  })
  clearSuggestions()
  if (parents.length > 1) {
    await startSessionsForAllParents(parents)
  } else {
    await startSession({ keepSessionId: true })
  }
  return false
}
