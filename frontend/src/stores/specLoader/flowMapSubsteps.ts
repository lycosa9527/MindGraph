/**
 * Flow-map spec collect / resolve. Identity is UUID; index is address only.
 */
import {
  leftoverFlowStepIndexFromId,
  parseLeftoverFlowStepIndex,
  parseLeftoverFlowSubstepRef,
  readFlowParentStepId,
  readFlowStepIndex,
  readFlowSubstepIndex,
} from '@/utils/flowMapIdentity'

export interface FlowMapStepSpec {
  id?: string
  text: string
}

export interface FlowMapSubstepItem {
  id?: string
  text: string
}

export interface FlowSubstepEntry {
  step: string
  stepId?: string
  stepIndex?: number
  substeps: Array<string | FlowMapSubstepItem>
}

export type FlowMapSpecNode = {
  id: string
  type?: string
  text?: string
  data?: Record<string, unknown>
}

export function parseFlowStepIndex(nodeId: string): number {
  return parseLeftoverFlowStepIndex(nodeId)
}

export function flowStepIndexFromNodeId(nodeId: string | undefined | null): number {
  return leftoverFlowStepIndexFromId(nodeId)
}

export function parseFlowSubstepRef(
  nodeId: string
): { stepIndex: number; subIndex: number } | null {
  return parseLeftoverFlowSubstepRef(nodeId)
}

export function normalizeFlowSubstepItem(item: string | FlowMapSubstepItem): FlowMapSubstepItem {
  return typeof item === 'string' ? { text: item } : { id: item.id, text: item.text }
}

export function collectFlowMapSpecFromNodes(nodes: FlowMapSpecNode[]): {
  steps: FlowMapStepSpec[]
  substeps: FlowSubstepEntry[]
} {
  const stepNodes = orderFlowStepNodes(nodes)
  const steps = stepNodes.map((node) => ({
    id: node.id,
    text: node.text ?? '',
  }))
  const substepNodes = nodes.filter((node) => node.type === 'flowSubstep')
  const substeps = stepNodes.map((stepNode, sequentialIndex) => {
    const stepIndex = readFlowStepIndex(stepNode)
    const index = stepIndex >= 0 ? stepIndex : sequentialIndex
    const children = substepsForFlowStep(substepNodes, stepNode)
    return {
      step: stepNode.text ?? '',
      stepId: stepNode.id,
      stepIndex: index,
      substeps: children.map((child) => ({
        id: child.id,
        text: child.text ?? '',
      })),
    }
  })
  return { steps, substeps }
}

export function resolveFlowSubstepsForSteps(
  steps: Array<{ text: string; id?: string }>,
  substepsData: FlowSubstepEntry[]
): FlowMapSubstepItem[][] {
  const result: FlowMapSubstepItem[][] = steps.map(() => [])
  const assigned = new Set<number>()
  const usedEntries = new Set<number>()

  substepsData.forEach((entry, entryIndex) => {
    if (!entry || !Array.isArray(entry.substeps)) return
    if (entry.stepId) {
      const idx = steps.findIndex((step) => step.id && step.id === entry.stepId)
      if (idx >= 0 && !assigned.has(idx)) {
        result[idx] = entry.substeps.map(normalizeFlowSubstepItem)
        assigned.add(idx)
        usedEntries.add(entryIndex)
        return
      }
    }
    const idx = entry.stepIndex
    if (typeof idx !== 'number' || idx < 0 || idx >= steps.length || assigned.has(idx)) {
      return
    }
    result[idx] = entry.substeps.map(normalizeFlowSubstepItem)
    assigned.add(idx)
    usedEntries.add(entryIndex)
  })

  substepsData.forEach((entry, entryIndex) => {
    if (usedEntries.has(entryIndex) || !entry?.step || !Array.isArray(entry.substeps)) return
    const idx = steps.findIndex(
      (step, stepIdx) => step.text === entry.step && !assigned.has(stepIdx)
    )
    if (idx < 0) return
    result[idx] = entry.substeps.map(normalizeFlowSubstepItem)
    assigned.add(idx)
    usedEntries.add(entryIndex)
  })

  return result
}

function stepSpecId(step: string | { id?: string; text: string }): string | undefined {
  return typeof step === 'string' ? undefined : step.id
}

function stepSpecText(step: string | { id?: string; text: string }): string {
  return typeof step === 'string' ? step : step.text
}

/**
 * Swap two collected steps in place. Child lists stay pinned to ``stepId``
 * (UUID travels with the step). Index-only leftover specs swap child lists.
 */
export function swapFlowMapCollectedSteps(
  steps: Array<string | { id?: string; text: string }>,
  substeps: FlowSubstepEntry[],
  leftIndex: number,
  rightIndex: number
): void {
  if (
    leftIndex < 0 ||
    rightIndex < 0 ||
    leftIndex >= steps.length ||
    rightIndex >= steps.length ||
    leftIndex === rightIndex
  ) {
    return
  }
  const left = steps[leftIndex]
  const right = steps[rightIndex]
  steps[leftIndex] = right
  steps[rightIndex] = left
  const leftId = stepSpecId(left)
  const rightId = stepSpecId(right)
  if (leftId || rightId) {
    for (const entry of substeps) {
      if (leftId && entry.stepId === leftId) {
        entry.stepIndex = rightIndex
        entry.step = stepSpecText(left)
      } else if (rightId && entry.stepId === rightId) {
        entry.stepIndex = leftIndex
        entry.step = stepSpecText(right)
      }
    }
    return
  }
  const leftEntry = substeps.find((entry) => entry.stepIndex === leftIndex)
  const rightEntry = substeps.find((entry) => entry.stepIndex === rightIndex)
  if (!leftEntry || !rightEntry) return
  const swapped = leftEntry.substeps
  leftEntry.substeps = rightEntry.substeps
  rightEntry.substeps = swapped
  leftEntry.step = stepSpecText(right)
  rightEntry.step = stepSpecText(left)
}

export function findFlowSubstepEntry(
  entries: FlowSubstepEntry[],
  stepText: string,
  stepIndex?: number,
  stepId?: string
): FlowSubstepEntry | undefined {
  if (stepId) {
    const byId = entries.find((entry) => entry.stepId === stepId)
    if (byId) return byId
  }
  if (typeof stepIndex === 'number' && stepIndex >= 0) {
    const byIndex = entries.find((entry) => entry.stepIndex === stepIndex)
    if (byIndex) return byIndex
    if (stepIndex < entries.length) return entries[stepIndex]
  }
  return entries.find((entry) => entry.step === stepText)
}

export type FlowLayoutStepNode = {
  id: string
  type?: string
  data?: Record<string, unknown>
  position?: { x: number; y: number }
}

export function flowStepSortKey(node: FlowLayoutStepNode): number {
  const stamped = readFlowStepIndex(node)
  if (stamped >= 0) return stamped
  return Number.MAX_SAFE_INTEGER
}

export function orderFlowStepNodes<T extends FlowLayoutStepNode>(nodes: T[]): T[] {
  return nodes
    .filter((node) => node.type === 'flow')
    .slice()
    .sort((left, right) => flowStepSortKey(left) - flowStepSortKey(right))
}

export function flowStepLookupIndex(stepNode: FlowLayoutStepNode): number {
  return readFlowStepIndex(stepNode)
}

export function substepsForFlowStep<T extends { id: string; data?: Record<string, unknown> }>(
  substepNodes: T[],
  stepNode: FlowLayoutStepNode
): T[] {
  const stepIdx = flowStepLookupIndex(stepNode)
  const matched = substepNodes.filter((node) => {
    const parentId = readFlowParentStepId(node)
    if (parentId) return parentId === stepNode.id
    return stepIdx >= 0 && readFlowStepIndex(node) === stepIdx
  })
  return matched.slice().sort((left, right) => {
    const leftIdx = readFlowSubstepIndex(left)
    const rightIdx = readFlowSubstepIndex(right)
    return (leftIdx >= 0 ? leftIdx : 0) - (rightIdx >= 0 ? rightIdx : 0)
  })
}

export function resolveFlowMapOrientation(
  topicNode: { data?: Record<string, unknown> },
  stepNodes: Array<{ position?: { x: number; y: number } }>
): 'horizontal' | 'vertical' {
  const stored = topicNode.data?.orientation
  if (stored === 'vertical' || stored === 'horizontal') return stored
  if (stepNodes.length < 2) return 'horizontal'
  const xs = stepNodes.map((step) => step.position?.x ?? 0)
  const ys = stepNodes.map((step) => step.position?.y ?? 0)
  const xSpread = Math.max(...xs) - Math.min(...xs)
  const ySpread = Math.max(...ys) - Math.min(...ys)
  return ySpread > xSpread ? 'vertical' : 'horizontal'
}
