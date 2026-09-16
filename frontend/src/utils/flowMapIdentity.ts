/**
 * Flow-map identity: live ``node.id`` is a UUID (topic stays ``flow-topic``).
 * Step / substep index is the current address only — same split as mindmap.
 */
import type { DiagramNode } from '@/types'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export const FLOW_TOPIC_NODE_ID = 'flow-topic'
export const FLOW_MAP_UID_DATA_KEY = 'flowMapUid'
export const FLOW_MAP_LEGACY_ID_DATA_KEY = 'flowMapLegacyId'
export const FLOW_STEP_INDEX_DATA_KEY = 'stepIndex'
export const FLOW_SUBSTEP_INDEX_DATA_KEY = 'substepIndex'
export const FLOW_PARENT_STEP_ID_DATA_KEY = 'parentStepId'

const FLOW_STEP_LEFTOVER = /^flow-step-(\d+)$/
const FLOW_SUBSTEP_LEFTOVER = /^flow-substep-(\d+)-(\d+)$/
const FLOW_SUBSTEP_STEP_LEFTOVER = /^flow-substep-(\d+)-/

export function isFlowMapTopicId(nodeId: string | undefined | null): boolean {
  return nodeId === FLOW_TOPIC_NODE_ID
}

export function isLeftoverFlowMapId(nodeId: string | undefined | null): boolean {
  if (!nodeId) return false
  return FLOW_STEP_LEFTOVER.test(nodeId) || FLOW_SUBSTEP_LEFTOVER.test(nodeId)
}

export function parseLeftoverFlowStepIndex(nodeId: string): number {
  const match = FLOW_STEP_LEFTOVER.exec(nodeId)
  return match ? parseInt(match[1], 10) : -1
}

export function parseLeftoverFlowSubstepRef(
  nodeId: string
): { stepIndex: number; subIndex: number } | null {
  const match = FLOW_SUBSTEP_LEFTOVER.exec(nodeId)
  if (!match) return null
  return { stepIndex: parseInt(match[1], 10), subIndex: parseInt(match[2], 10) }
}

export function leftoverFlowStepIndexFromId(nodeId: string | undefined | null): number {
  if (!nodeId) return -1
  const step = parseLeftoverFlowStepIndex(nodeId)
  if (step >= 0) return step
  const sub = FLOW_SUBSTEP_STEP_LEFTOVER.exec(nodeId)
  return sub ? parseInt(sub[1], 10) : -1
}

export function readFlowMapUid(node: { data?: Record<string, unknown> }): string | null {
  const uid = node.data?.[FLOW_MAP_UID_DATA_KEY]
  return typeof uid === 'string' && uid.trim() ? uid.trim() : null
}

export function readFlowStepIndex(node: { id?: string; data?: Record<string, unknown> }): number {
  const stamped = node.data?.[FLOW_STEP_INDEX_DATA_KEY]
  if (typeof stamped === 'number' && stamped >= 0) return stamped
  const group = node.data?.groupIndex
  if (typeof group === 'number' && group >= 0) return group
  return leftoverFlowStepIndexFromId(node.id)
}

export function readFlowSubstepIndex(node: {
  id?: string
  data?: Record<string, unknown>
}): number {
  const stamped = node.data?.[FLOW_SUBSTEP_INDEX_DATA_KEY]
  if (typeof stamped === 'number' && stamped >= 0) return stamped
  return parseLeftoverFlowSubstepRef(node.id ?? '')?.subIndex ?? -1
}

export function readFlowParentStepId(node: { data?: Record<string, unknown> }): string | null {
  const parent = node.data?.[FLOW_PARENT_STEP_ID_DATA_KEY]
  return typeof parent === 'string' && parent.trim() ? parent.trim() : null
}

export function isFlowMapStepNode(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): boolean {
  if (node.type === 'flow') return true
  return parseLeftoverFlowStepIndex(node.id ?? '') >= 0
}

export function isFlowMapSubstepNode(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): boolean {
  if (node.type === 'flowSubstep') return true
  return parseLeftoverFlowSubstepRef(node.id ?? '') != null
}

export function takeFlowMapStableId(claimed: Set<string>, preferred?: string | null): string {
  if (preferred && !isLeftoverFlowMapId(preferred) && !claimed.has(preferred)) {
    claimed.add(preferred)
    return preferred
  }
  let minted = safeRandomUUID()
  while (claimed.has(minted)) {
    minted = safeRandomUUID()
  }
  claimed.add(minted)
  return minted
}

export function stampFlowMapStepData(
  stepIndex: number,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    groupIndex: stepIndex,
    [FLOW_STEP_INDEX_DATA_KEY]: stepIndex,
  }
}

export function stampFlowMapSubstepData(
  stepIndex: number,
  substepIndex: number,
  parentStepId: string,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    groupIndex: stepIndex,
    [FLOW_STEP_INDEX_DATA_KEY]: stepIndex,
    [FLOW_SUBSTEP_INDEX_DATA_KEY]: substepIndex,
    [FLOW_PARENT_STEP_ID_DATA_KEY]: parentStepId,
  }
}

export function flowMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  const aliases: Record<string, string> = {}
  for (const node of nodes) {
    if (!node.id) continue
    aliases[node.id] = node.id
    const uid = readFlowMapUid(node)
    if (uid) aliases[uid] = node.id
    const legacy = node.data?.[FLOW_MAP_LEGACY_ID_DATA_KEY]
    if (typeof legacy === 'string' && legacy.trim()) {
      aliases[legacy.trim()] = node.id
    }
  }
  return aliases
}

export function flowMapChildBelongsToStep(
  child: { id?: string; type?: string; data?: Record<string, unknown> },
  step: { id?: string; type?: string; data?: Record<string, unknown> }
): boolean {
  if (!isFlowMapSubstepNode(child) || !isFlowMapStepNode(step)) return false
  const parentId = readFlowParentStepId(child)
  if (parentId) return parentId === step.id
  const stepIndex = readFlowStepIndex(step)
  return stepIndex >= 0 && readFlowStepIndex(child) === stepIndex
}

export function findFlowMapParentStep<
  T extends { id: string; type?: string; data?: Record<string, unknown> },
>(
  node: { id?: string; type?: string; data?: Record<string, unknown> },
  nodes: ReadonlyArray<T>
): T | undefined {
  if (isFlowMapStepNode(node)) {
    return nodes.find((candidate) => candidate.id === node.id)
  }
  if (!isFlowMapSubstepNode(node)) return undefined
  const parentId = readFlowParentStepId(node)
  if (parentId) {
    const parent = nodes.find((candidate) => candidate.id === parentId)
    if (parent) return parent
  }
  const stepIndex = readFlowStepIndex(node)
  if (stepIndex < 0) return undefined
  return nodes.find(
    (candidate) => isFlowMapStepNode(candidate) && readFlowStepIndex(candidate) === stepIndex
  )
}

export function resolveFlowMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = flowMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverFlowMapId(mapped)) return mapped
  const leftoverStep = parseLeftoverFlowStepIndex(cleaned)
  if (leftoverStep >= 0) {
    const step = nodes.find(
      (node) => isFlowMapStepNode(node) && readFlowStepIndex(node) === leftoverStep
    )
    return step && !isLeftoverFlowMapId(step.id) ? step.id : (step?.id ?? null)
  }
  const leftoverSub = parseLeftoverFlowSubstepRef(cleaned)
  if (leftoverSub) {
    const sub = nodes.find(
      (node) =>
        isFlowMapSubstepNode(node) &&
        readFlowStepIndex(node) === leftoverSub.stepIndex &&
        readFlowSubstepIndex(node) === leftoverSub.subIndex
    )
    return sub?.id ?? null
  }
  return null
}
