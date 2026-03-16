/**
 * Node Palette apply selection - applies selected suggestions to diagram
 */
import { nextTick } from 'vue'

import { useDiagramStore, usePanelsStore } from '@/stores'
import type { DiagramNode, DiagramType } from '@/types'
import type { NodeSuggestion } from '@/types/panels'

import {
  BRACE_MAP_DEFAULT_SUBPARTS,
  getParentIdFromStageData,
  STAGED_DIAGRAM_TYPES,
  suggestionBelongsToParent,
} from './constants'
import { getPlaceholderNodes } from './placeholderHelpers'
import {
  type Stage2Parent,
  buildStageDataForParent,
  getStage2ParentsForDiagram,
  stage2StageNameForType,
} from './stageHelpers'

function normalizeDiagramType(dt: DiagramType | null): DiagramType | null {
  return dt === 'mind_map' ? 'mindmap' : dt
}

export interface ApplySelectionContext {
  diagramStore: ReturnType<typeof useDiagramStore>
  panelsStore: ReturnType<typeof usePanelsStore>
  diagramType: DiagramType | null
  diagramKey: string
  toApply: NodeSuggestion[]
  stage: string | undefined
  stageData: Record<string, unknown> | undefined
  mode: string
  language: 'en' | 'zh'
  startSession: (opts?: { keepSessionId?: boolean }) => Promise<boolean>
  startSessionsForAllParents: (
    parents: Stage2Parent[],
    dt: DiagramType | null,
    dim: string
  ) => Promise<void>
}

export async function applySelectionToDiagram(ctx: ApplySelectionContext): Promise<boolean> {
  const {
    diagramStore,
    panelsStore,
    diagramType,
    diagramKey,
    toApply,
    stage,
    stageData,
    mode,
    language,
    startSession,
    startSessionsForAllParents,
  } = ctx

  const diagramTypeVal = normalizeDiagramType(diagramType)
  const nodes = diagramStore.data?.nodes ?? []
  const connections = diagramStore.data?.connections

  const stageDataTyped = stageData as {
    part_id?: string
    category_id?: string
    branch_id?: string
    step_id?: string
    branch_name?: string
    step_name?: string
    category_name?: string
    part_name?: string
  }
  const parentId =
    diagramTypeVal === 'brace_map' && stage === 'subparts'
      ? (stageDataTyped.part_id ?? null)
      : diagramTypeVal === 'tree_map' && stage === 'children'
        ? (stageDataTyped.category_id ?? null)
        : diagramTypeVal === 'mindmap' && stage === 'children'
          ? (stageDataTyped.branch_id ?? null)
          : diagramTypeVal === 'flow_map' && stage === 'substeps'
            ? (stageDataTyped.step_id ?? null)
            : null

  if (diagramTypeVal === 'multi_flow_map') {
    return applyMultiFlowMap(ctx, parentId, connections)
  }

  if (diagramTypeVal === 'double_bubble_map') {
    return applyDoubleBubbleMap(ctx, parentId, connections)
  }

  const stage2Names = ['children', 'substeps', 'subparts']
  const isStage2WithParents =
    STAGED_DIAGRAM_TYPES.includes(diagramTypeVal as (typeof STAGED_DIAGRAM_TYPES)[number]) &&
    stage &&
    stage2Names.includes(stage)
  const parents =
    isStage2WithParents && connections
      ? getStage2ParentsForDiagram(diagramTypeVal, nodes, connections)
      : []

  if (isStage2WithParents && parents.length > 1) {
    return applyStage2MultipleParents(ctx, parents, connections)
  }

  const currentParentId = getParentIdFromStageData(
    diagramTypeVal ?? '',
    stage,
    stageDataTyped as Record<string, unknown>
  )
  const currentParentNameNorm = (mode ?? '').trim()
  const toApplyFiltered =
    (diagramTypeVal === 'mindmap' ||
      diagramTypeVal === 'flow_map' ||
      diagramTypeVal === 'tree_map' ||
      diagramTypeVal === 'brace_map') &&
    stage &&
    ['children', 'substeps', 'subparts'].includes(stage) &&
    (currentParentId || currentParentNameNorm)
      ? toApply.filter((s) =>
          suggestionBelongsToParent(s, currentParentId, currentParentNameNorm)
        )
      : toApply

  const placeholders = getPlaceholderNodes(
    diagramTypeVal,
    nodes,
    mode,
    stage,
    parentId,
    connections
  )
  let suggestionIndex = 0

  for (const slot of placeholders) {
    if (suggestionIndex >= toApplyFiltered.length) break
    const suggestion = toApplyFiltered[suggestionIndex]

    if (slot.id === 'dimension-label') {
      diagramStore.updateNode('dimension-label', { text: suggestion.text })
    } else if (diagramTypeVal === 'bridge_map' && /^pair-\d+-left$/.test(slot.id)) {
      const pairIndex = slot.id.replace('pair-', '').replace('-left', '')
      const rightId = `pair-${pairIndex}-right`
      const parts = suggestion.text.split('|').map((p) => p.trim())
      const leftText = parts[0] ?? suggestion.text
      const rightText = parts[1] ?? ''
      diagramStore.updateNode(slot.id, { text: leftText })
      diagramStore.updateNode(rightId, { text: rightText })
    } else {
      diagramStore.updateNode(slot.id, { text: suggestion.text })
    }
    suggestionIndex++
  }

  const remainder = toApplyFiltered.slice(suggestionIndex)
  const isStaged = STAGED_DIAGRAM_TYPES.includes(
    diagramTypeVal as (typeof STAGED_DIAGRAM_TYPES)[number]
  )
  const isStage1WithParents =
    isStaged &&
    (stage === 'branches' || stage === 'steps' || stage === 'categories' || stage === 'parts')
  const isDimensionsStage = stage === 'dimensions'

  if (remainder.length === 0 && !isDimensionsStage && !isStage1WithParents) {
    panelsStore.updateNodePalette({ selected: [] })
    panelsStore.clearNodePaletteSession(diagramKey)
    panelsStore.closeNodePalette()
    return true
  }

  if (isDimensionsStage && toApply.length === 1) {
    return applyDimensionStage(ctx)
  }

  if (remainder.length === 0 && isStage1WithParents) {
    return applyStage1ToStage2Transition(ctx, stage)
  }

  applyRemainder(ctx, remainder, nodes, connections)

  const isStage1 = ['branches', 'steps', 'categories', 'parts'].includes(stage ?? '')
  const stagedTypesForStage2 = ['mindmap', 'flow_map', 'tree_map', 'brace_map']
  if (
    isStage1 &&
    diagramTypeVal &&
    stagedTypesForStage2.includes(diagramTypeVal) &&
    remainder.length > 0
  ) {
    await nextTick()
    const currentNodes = diagramStore.data?.nodes ?? []
    const nextParents = getStage2ParentsForDiagram(
      diagramTypeVal,
      currentNodes,
      diagramStore.data?.connections
    )
    if (nextParents.length > 0) {
      const dimRaw =
        (stageData as { dimension?: string })?.dimension ??
        (diagramStore.data as Record<string, unknown>)?.dimension
      const dim = typeof dimRaw === 'string' ? dimRaw : ''
      panelsStore.updateNodePalette({
        stage: stage2StageNameForType(diagramTypeVal),
        stage_data: buildStageDataForParent(nextParents[0], diagramTypeVal, {
          dimension: dim,
        }),
        mode: nextParents[0].name,
        selected: [],
      })
      panelsStore.setNodePaletteSuggestions([])
      if (nextParents.length > 1) {
        await startSessionsForAllParents(nextParents, diagramTypeVal, dim)
      } else {
        await startSession({ keepSessionId: true })
      }
      return false
    }
  }

  panelsStore.updateNodePalette({ selected: [] })
  panelsStore.clearNodePaletteSession(diagramKey)
  panelsStore.closeNodePalette()
  return true
}

function applyMultiFlowMap(
  ctx: ApplySelectionContext,
  parentId: string | null,
  connections: Array<{ source: string; target: string }> | undefined
): boolean {
  const { diagramStore, panelsStore, diagramType, diagramKey, toApply, stage } = ctx
  const diagramTypeVal = normalizeDiagramType(diagramType)
  const nodes = diagramStore.data?.nodes ?? []

  const toApplyCauses = toApply.filter((s) => (s.mode ?? 'causes') === 'causes')
  const toApplyEffects = toApply.filter((s) => (s.mode ?? 'causes') === 'effects')
  const causePlaceholders = getPlaceholderNodes(
    diagramTypeVal,
    nodes,
    'causes',
    stage,
    parentId,
    connections
  )
  const effectPlaceholders = getPlaceholderNodes(
    diagramTypeVal,
    nodes,
    'effects',
    stage,
    parentId,
    connections
  )
  let causeIdx = 0
  for (const slot of causePlaceholders) {
    if (causeIdx >= toApplyCauses.length) break
    const s = toApplyCauses[causeIdx]
    diagramStore.updateNode(slot.id, { text: s.text ?? '' })
    causeIdx++
  }
  let effectIdx = 0
  for (const slot of effectPlaceholders) {
    if (effectIdx >= toApplyEffects.length) break
    const s = toApplyEffects[effectIdx]
    diagramStore.updateNode(slot.id, { text: s.text ?? '' })
    effectIdx++
  }
  const remainderCauses = toApplyCauses.slice(causeIdx)
  const remainderEffects = toApplyEffects.slice(effectIdx)
  const addMultiFlowNodes = (suggestions: NodeSuggestion[], prefix: string, category: string) => {
    const existing = nodes
      .filter(
        (n): n is typeof n & { id: string } =>
          n.id != null &&
          n.id.startsWith(`${prefix}-`) &&
          /^\d+$/.test(n.id.replace(prefix + '-', ''))
      )
      .map((n) => parseInt(n.id.replace(prefix + '-', ''), 10))
    const nextIndex = existing.length > 0 ? Math.max(...existing) + 1 : 0
    suggestions.forEach((s, i) => {
      diagramStore.addNode({
        id: `${prefix}-${nextIndex + i}`,
        text: s.text ?? '',
        type: 'flow',
        position: { x: 0, y: 0 },
        style: {},
        category,
      } as DiagramNode & { category?: string })
    })
  }
  addMultiFlowNodes(remainderCauses, 'cause', 'causes')
  addMultiFlowNodes(remainderEffects, 'effect', 'effects')
  if (toApplyCauses.length > 0 || toApplyEffects.length > 0) {
    panelsStore.updateNodePalette({ selected: [] })
    panelsStore.clearNodePaletteSession(diagramKey)
    panelsStore.closeNodePalette()
    return true
  }
  return false
}

function applyDoubleBubbleMap(
  ctx: ApplySelectionContext,
  parentId: string | null,
  connections: Array<{ source: string; target: string }> | undefined
): boolean {
  const { diagramStore, panelsStore, diagramType, diagramKey, toApply, stage } = ctx
  const diagramTypeVal = normalizeDiagramType(diagramType)
  const nodes = diagramStore.data?.nodes ?? []

  const toApplySim = toApply.filter((s) => (s.mode ?? 'similarities') === 'similarities')
  const toApplyDiff = toApply.filter((s) => (s.mode ?? 'similarities') === 'differences')
  const simPlaceholders = getPlaceholderNodes(
    diagramTypeVal,
    nodes,
    'similarities',
    stage,
    parentId,
    connections
  )
  const diffPlaceholders = getPlaceholderNodes(
    diagramTypeVal,
    nodes,
    'differences',
    stage,
    parentId,
    connections
  )
  let simIdx = 0
  for (const slot of simPlaceholders) {
    if (simIdx >= toApplySim.length) break
    const s = toApplySim[simIdx]
    if (s.text && !s.text.includes('|')) {
      diagramStore.updateNode(slot.id, { text: s.text })
      simIdx++
    }
  }
  let diffIdx = 0
  for (const slot of diffPlaceholders) {
    if (diffIdx >= toApplyDiff.length) break
    const s = toApplyDiff[diffIdx]
    const ids = slot.id.split('|')
    const leftId = ids[0]
    const rightId = ids[1]
    const leftText = s.left ?? s.text.split('|').map((p) => p.trim())[0] ?? s.text
    const rightText = s.right ?? s.text.split('|').map((p) => p.trim())[1] ?? ''
    if (leftId) diagramStore.updateNode(leftId, { text: leftText })
    if (rightId && rightText) diagramStore.updateNode(rightId, { text: rightText })
    diffIdx++
  }
  const remainderSim = toApplySim.slice(simIdx)
  const remainderDiff = toApplyDiff.slice(diffIdx)
  for (const s of remainderSim) {
    const text = (s.text ?? '').trim()
    if (text && !text.includes('|')) diagramStore.addDoubleBubbleMapNode('similarity', text)
  }
  for (const s of remainderDiff) {
    const leftText = s.left ?? s.text.split('|').map((p) => p.trim())[0] ?? s.text
    const rightText = s.right ?? s.text.split('|').map((p) => p.trim())[1] ?? ''
    if (leftText || rightText) diagramStore.addDoubleBubbleMapNode('leftDiff', leftText, rightText)
  }
  if (toApplySim.length > 0 || toApplyDiff.length > 0) {
    panelsStore.updateNodePalette({ selected: [] })
    panelsStore.clearNodePaletteSession(diagramKey)
    panelsStore.closeNodePalette()
    return true
  }
  return false
}

function applyStage2MultipleParents(
  ctx: ApplySelectionContext,
  parents: Stage2Parent[],
  connections: Array<{ source: string; target: string }> | undefined
): boolean {
  const { diagramStore, panelsStore, diagramType, diagramKey, toApply, stage, stageData } = ctx
  const diagramTypeVal = normalizeDiagramType(diagramType)
  const nodes = diagramStore.data?.nodes ?? []

  const dimRaw =
    (stageData as { dimension?: string })?.dimension ??
    (diagramStore.data as Record<string, unknown>)?.dimension ??
    ''
  const dim = typeof dimRaw === 'string' ? dimRaw : ''
  const currentModeNorm = (ctx.mode ?? '').trim()
  const currentParentId = getParentIdFromStageData(
    diagramTypeVal ?? '',
    stage,
    stageData as Record<string, unknown>
  )
  const parentIds = new Set(parents.map((p) => p.id))
  const parentNames = new Set(parents.map((p) => (p.name ?? '').trim()))
  let appliedAny = false
  for (const parent of parents) {
    const parentNameNorm = (parent.name ?? '').trim()
    const toApplyParent = toApply.filter((s) =>
      suggestionBelongsToParent(s, parent.id, parentNameNorm)
    )
    if (toApplyParent.length === 0) continue
    const placeholdersParent = getPlaceholderNodes(
      diagramTypeVal,
      nodes,
      parent.name,
      stage,
      parent.id,
      connections
    )
    let idx = 0
    for (const slot of placeholdersParent) {
      if (idx >= toApplyParent.length) break
      const s = toApplyParent[idx]
      if (slot.id === 'dimension-label') {
        diagramStore.updateNode('dimension-label', { text: s.text })
      } else if (diagramTypeVal === 'bridge_map' && /^pair-\d+-left$/.test(slot.id)) {
        const pairIndex = slot.id.replace('pair-', '').replace('-left', '')
        const rightId = `pair-${pairIndex}-right`
        const parts = (s.text ?? '').split('|').map((p) => p.trim())
        diagramStore.updateNode(slot.id, { text: parts[0] ?? s.text })
        diagramStore.updateNode(rightId, { text: parts[1] ?? '' })
      } else {
        diagramStore.updateNode(slot.id, { text: s.text })
      }
      idx++
    }
    const remainderParent = toApplyParent.slice(idx)
    const stageDataForParent = buildStageDataForParent(parent, diagramTypeVal, {
      dimension: dim,
    })
    for (const s of remainderParent) {
      const text = (s.text ?? '').trim()
      if (!text) continue
      if (diagramTypeVal === 'mindmap') {
        diagramStore.addMindMapChild(parent.id, text)
      } else if (diagramTypeVal === 'flow_map') {
        const stepText = nodes.find((n) => n.id === parent.id)?.text ?? parent.name
        diagramStore.addFlowMapSubstep(stepText, text)
      } else if (diagramTypeVal === 'tree_map') {
        diagramStore.addTreeMapChild(parent.id, text)
      } else if (diagramTypeVal === 'brace_map') {
        const partId = stageDataForParent.part_id as string | undefined
        diagramStore.addBraceMapPart(partId ?? 'topic', text)
      }
      appliedAny = true
    }
    appliedAny = appliedAny || idx > 0
  }
  const unmatched = toApply.filter(
    (s) =>
      !(s.parent_id && parentIds.has(s.parent_id)) &&
      !parentNames.has((s.mode ?? '').trim())
  )
  if (unmatched.length > 0) {
    const stageDataTyped = stageData as {
      branch_id?: string
      step_id?: string
      category_id?: string
      part_id?: string
    }
    const stageParentId =
      stageDataTyped.branch_id ??
      stageDataTyped.step_id ??
      stageDataTyped.category_id ??
      stageDataTyped.part_id
    const fallbackParent =
      (currentParentId ? parents.find((p) => p.id === currentParentId) : undefined) ??
      parents.find((p) => (p.name ?? '').trim() === currentModeNorm) ??
      (stageParentId ? parents.find((p) => p.id === stageParentId) : undefined) ??
      parents[0]
    if (fallbackParent) {
      for (const s of unmatched) {
        const text = (s.text ?? '').trim()
        if (!text) continue
        if (diagramTypeVal === 'mindmap') {
          diagramStore.addMindMapChild(fallbackParent.id, text)
        } else if (diagramTypeVal === 'flow_map') {
          const stepText =
            nodes.find((n) => n.id === fallbackParent.id)?.text ?? fallbackParent.name
          diagramStore.addFlowMapSubstep(stepText, text)
        } else if (diagramTypeVal === 'tree_map') {
          diagramStore.addTreeMapChild(fallbackParent.id, text)
        } else if (diagramTypeVal === 'brace_map') {
          const stageDataForParent = buildStageDataForParent(fallbackParent, diagramTypeVal, {
            dimension: dim,
          })
          const partId = stageDataForParent.part_id as string | undefined
          diagramStore.addBraceMapPart(partId ?? 'topic', text)
        }
        appliedAny = true
      }
    }
  }
  if (appliedAny) {
    panelsStore.updateNodePalette({ selected: [] })
    panelsStore.clearNodePaletteSession(diagramKey)
    panelsStore.closeNodePalette()
    return true
  }
  return false
}

async function applyDimensionStage(ctx: ApplySelectionContext): Promise<boolean> {
  const { diagramStore, panelsStore, diagramType, toApply, startSession } = ctx
  const diagramTypeVal = normalizeDiagramType(diagramType)
  const nodes = diagramStore.data?.nodes ?? []

  const selectedDimension = toApply[0]?.text ?? ''
  const dimensionLabelExists = nodes.some((n) => n.id === 'dimension-label')
  if (dimensionLabelExists) {
    diagramStore.updateNode('dimension-label', { text: selectedDimension })
  } else if (
    diagramTypeVal === 'tree_map' ||
    diagramTypeVal === 'brace_map' ||
    diagramTypeVal === 'bridge_map'
  ) {
    const topicNode = nodes.find(
      (n) => n.type === 'topic' || n.type === 'center' || n.id === 'tree-topic' || n.id === 'root'
    )
    const topicY = (topicNode?.position as { y?: number })?.y ?? 0
    const topicX = (topicNode?.position as { x?: number })?.x ?? 0
    const topicWidth = 120
    const labelWidth = 100
    diagramStore.addNode({
      id: 'dimension-label',
      text: selectedDimension,
      type: 'label',
      position: {
        x: topicX + topicWidth / 2 - labelWidth / 2,
        y: topicY + 50 + 20,
      },
    } as DiagramNode)
    const d = diagramStore.data as Record<string, unknown> | null
    if (d) d.dimension = selectedDimension
  }
  const nextStage =
    diagramTypeVal === 'tree_map'
      ? 'categories'
      : diagramTypeVal === 'brace_map'
        ? 'parts'
        : 'pairs'
  panelsStore.updateNodePalette({
    stage: nextStage,
    stage_data: { dimension: selectedDimension },
    mode: nextStage,
    selected: [],
  })
  panelsStore.setNodePaletteSuggestions([])
  await nextTick()
  await startSession({ keepSessionId: true })
  return false
}

async function applyStage1ToStage2Transition(
  ctx: ApplySelectionContext,
  _stage: string | undefined
): Promise<boolean> {
  const {
    diagramStore,
    panelsStore,
    diagramType,
    diagramKey,
    stageData,
    startSession,
    startSessionsForAllParents,
  } = ctx
  const diagramTypeVal = normalizeDiagramType(diagramType)
  const currentNodes = diagramStore.data?.nodes ?? []
  const parents = getStage2ParentsForDiagram(
    diagramTypeVal,
    currentNodes,
    diagramStore.data?.connections
  )
  if (parents.length > 0) {
    const dimRaw =
      (stageData as { dimension?: string })?.dimension ??
      (diagramStore.data as Record<string, unknown>)?.dimension
    const dim = typeof dimRaw === 'string' ? dimRaw : ''
    panelsStore.updateNodePalette({
      stage: stage2StageNameForType(diagramTypeVal),
      stage_data: buildStageDataForParent(parents[0], diagramTypeVal, {
        dimension: dim,
      }),
      mode: parents[0].name,
      selected: [],
    })
    panelsStore.setNodePaletteSuggestions([])
    if (parents.length > 1) {
      await startSessionsForAllParents(parents, diagramTypeVal, dim)
    } else {
      await startSession({ keepSessionId: true })
    }
    return false
  }
  panelsStore.updateNodePalette({ selected: [] })
  panelsStore.clearNodePaletteSession(diagramKey)
  panelsStore.closeNodePalette()
  return true
}

function applyRemainder(
  ctx: ApplySelectionContext,
  remainder: NodeSuggestion[],
  nodes: Array<{
    id: string
    text?: string
    type?: string
    position?: { x?: number; y?: number }
    style?: { width?: number }
    data?: Record<string, unknown>
  }>,
  connections: Array<{ source: string; target: string }> | undefined
): void {
  const { diagramStore, diagramType, stage, stageData, language } = ctx
  const diagramTypeVal = normalizeDiagramType(diagramType)
  const stageDataTyped = stageData as {
    branch_id?: string
    branch_name?: string
    step_id?: string
    step_name?: string
    category_id?: string
    category_name?: string
    part_id?: string
    part_name?: string
  }

  if (diagramTypeVal === 'circle_map') {
    const contextNodes = nodes.filter((n) => n.id.startsWith('context-'))
    const nextIndex = contextNodes.length
    remainder.forEach((suggestion, i) => {
      diagramStore.addNode({
        id: `context-${nextIndex + i}`,
        text: suggestion.text ?? '',
        type: 'bubble',
        position: { x: 0, y: 0 },
        style: {},
      } as DiagramNode)
    })
  } else if (diagramTypeVal === 'bubble_map') {
    const bubbleNodes = nodes.filter(
      (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
    )
    const nextIndex = bubbleNodes.length
    remainder.forEach((suggestion, i) => {
      diagramStore.addNode({
        id: `bubble-${nextIndex + i}`,
        text: suggestion.text ?? '',
        type: 'bubble',
        position: { x: 0, y: 0 },
        style: {},
      } as DiagramNode)
    })
  } else if (diagramTypeVal === 'double_bubble_map') {
    if (stage === 'differences') {
      remainder.forEach((suggestion) => {
        const leftText =
          suggestion.left ?? suggestion.text.split('|').map((p) => p.trim())[0] ?? suggestion.text
        const rightText =
          suggestion.right ?? suggestion.text.split('|').map((p) => p.trim())[1] ?? ''
        diagramStore.addDoubleBubbleMapNode('leftDiff', leftText, rightText)
      })
    } else {
      remainder.forEach((suggestion) => {
        diagramStore.addDoubleBubbleMapNode('similarity', suggestion.text)
      })
    }
  } else if (diagramTypeVal === 'mindmap') {
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
        const fallbackParents = getStage2ParentsForDiagram(diagramTypeVal, nodes, connections)
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
        if (text) diagramStore.addMindMapBranch('right', text, 'New Child')
      })
    }
  } else if (diagramTypeVal === 'flow_map') {
    if (stage === 'substeps') {
      const stepId = stageDataTyped.step_id
      const stepName = stageDataTyped.step_name
      const stepText = (stepId && nodes.find((n) => n.id === stepId)?.text) || stepName
      if (stepText) {
        remainder.forEach((s) => diagramStore.addFlowMapSubstep(stepText, s.text))
      }
    } else {
      const stepCount = nodes.filter((n) => n.type === 'flow').length
      remainder.forEach((s, i) => {
        const stepNum = stepCount + i + 1
        const defaultSubsteps: [string, string] =
          language === 'zh'
            ? [`子步骤${stepNum}.1`, `子步骤${stepNum}.2`]
            : [`Substep ${stepNum}.1`, `Substep ${stepNum}.2`]
        diagramStore.addFlowMapStep(s.text, defaultSubsteps)
      })
    }
  } else if (diagramTypeVal === 'tree_map') {
    if (stage === 'children' && stageData?.category_name && stageData?.category_id) {
      remainder.forEach((s) =>
        diagramStore.addTreeMapChild(stageData.category_id as string, s.text)
      )
    } else {
      remainder.forEach((s) => diagramStore.addTreeMapCategory(s.text))
    }
  } else if (diagramTypeVal === 'brace_map') {
    const targetIds = new Set(diagramStore.data?.connections?.map((c) => c.target) ?? [])
    const wholeId =
      nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id ??
      nodes.find((n) => n.type === 'topic')?.id ??
      nodes.find((n) => !targetIds.has(n.id ?? ''))?.id
    const subpartTexts = BRACE_MAP_DEFAULT_SUBPARTS[language]
    if (stage === 'subparts' && stageData?.part_name && stageData?.part_id) {
      remainder.forEach((s) => diagramStore.addBraceMapPart(stageData.part_id as string, s.text))
    } else {
      remainder.forEach((s) =>
        diagramStore.addBraceMapPart(wholeId ?? 'topic', s.text, subpartTexts)
      )
    }
  } else if (diagramTypeVal === 'bridge_map' && stage !== 'dimensions') {
    const pairNodes = nodes.filter(
      (n) =>
        (n as { data?: { pairIndex?: number } }).data?.pairIndex !== undefined &&
        !(n as { data?: { isDimensionLabel?: boolean } }).data?.isDimensionLabel
    )
    let maxPairIndex = -1
    pairNodes.forEach((n) => {
      const idx = (n as { data?: { pairIndex?: number } }).data?.pairIndex
      if (typeof idx === 'number' && idx > maxPairIndex) maxPairIndex = idx
    })
    const gapBetweenPairs = 50
    const verticalGap = 5
    const nodeWidth = 120
    const nodeHeight = 28
    const startX = 130
    let nextX = startX
    if (pairNodes.length > 0) {
      const rightmost = pairNodes.reduce((a, b) =>
        (a.position?.x ?? 0) > (b.position?.x ?? 0) ? a : b
      )
      nextX = (rightmost.position?.x ?? startX) + nodeWidth + gapBetweenPairs
    }
    const centerY = 300
    remainder.forEach((suggestion, i) => {
      const newPairIndex = maxPairIndex + 1 + i
      const parts = suggestion.text.split('|').map((p) => p.trim())
      const leftText = suggestion.left ?? parts[0] ?? suggestion.text
      const rightText = suggestion.right ?? parts[1] ?? ''
      const x = nextX + i * (nodeWidth + gapBetweenPairs)
      diagramStore.addNode({
        id: `pair-${newPairIndex}-left`,
        text: leftText,
        type: 'branch',
        position: { x, y: centerY - verticalGap - nodeHeight },
        data: {
          pairIndex: newPairIndex,
          position: 'left',
          diagramType: 'bridge_map',
        },
      } as DiagramNode)
      diagramStore.addNode({
        id: `pair-${newPairIndex}-right`,
        text: rightText,
        type: 'branch',
        position: { x, y: centerY + verticalGap },
        data: {
          pairIndex: newPairIndex,
          position: 'right',
          diagramType: 'bridge_map',
        },
      } as DiagramNode)
    })
  } else if (diagramTypeVal === 'concept_map') {
    const conceptNodes = nodes.filter((n) => n.id?.startsWith('concept-'))
    const nextIndex = conceptNodes.length
    remainder.forEach((suggestion, i) => {
      diagramStore.addNode({
        id: `concept-${nextIndex + i}`,
        text: suggestion.text ?? '',
        type: 'branch',
        position: { x: 100 + i * 30, y: 200 + i * 40 },
      } as DiagramNode)
    })
  } else {
    const maxX = nodes.length
      ? Math.max(...nodes.map((n) => (n.position?.x ?? 0) + (n.style?.width ?? 120)))
      : 400
    remainder.forEach((suggestion, index) => {
      diagramStore.addNode({
        id: `node-${Date.now()}-${index}`,
        text: suggestion.text ?? '',
        type: 'bubble',
        position: { x: maxX + 20 + index * 30, y: 300 + index * 20 },
        style: {
          backgroundColor: '#ffffff',
          borderColor: '#4a90e2',
          textColor: '#303133',
        },
      } as DiagramNode)
    })
  }
}
