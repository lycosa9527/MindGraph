import {
  type DoubleBubbleRole,
  isDoubleBubbleRoleNode,
  readDoubleBubbleIndex,
} from '@/utils/doubleBubbleMapIdentity'

import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import type { DiagramContext } from './types'

type SpecItem = string | { id?: string; text?: string }

function secondaryRecord(spec: Record<string, unknown>): Record<string, unknown> | null {
  const raw = spec.secondary
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return raw as Record<string, unknown>
}

function appendGlossSlot(spec: Record<string, unknown>, key: string): void {
  const secondary = secondaryRecord(spec)
  if (!secondary || !Array.isArray(secondary[key])) return
  secondary[key] = [...secondary[key], '']
}

function dropGlossSlots(spec: Record<string, unknown>, key: string, drop: Set<number>): void {
  const secondary = secondaryRecord(spec)
  if (!secondary || !Array.isArray(secondary[key]) || drop.size === 0) return
  secondary[key] = secondary[key].filter((_, index) => !drop.has(index))
}

function dropSizeSlots(spec: Record<string, unknown>, key: string, drop: Set<number>): void {
  const raw = spec._doubleBubbleMapNodeSizes
  if (!raw || typeof raw !== 'object' || Array.isArray(raw) || drop.size === 0) return
  const sizes = raw as Record<string, unknown>
  if (!Array.isArray(sizes[key])) return
  sizes[key] = sizes[key].filter((_, index) => !drop.has(index))
}

function asItems(raw: unknown): SpecItem[] {
  return Array.isArray(raw) ? (raw as SpecItem[]) : []
}

export interface DoubleBubbleDeleteOutcome {
  deleted: number
  withheldSimilarity: boolean
  withheldDifference: boolean
}

/** Smallest requested index stays when a delete would empty that column. */
function dropIndicesKeepingOne(
  total: number,
  requested: Set<number>
): { drop: Set<number>; withheld: boolean } {
  const drop = new Set<number>()
  for (const index of requested) {
    if (index >= 0 && index < total) drop.add(index)
  }
  if (drop.size === 0 || total - drop.size >= 1) {
    return { drop, withheld: false }
  }
  let keep = -1
  for (const index of drop) {
    if (keep < 0 || index < keep) keep = index
  }
  if (keep >= 0) drop.delete(keep)
  return { drop, withheld: true }
}

export function doubleBubbleDeleteKeepWarningKey(outcome: {
  withheldSimilarity: boolean
  withheldDifference: boolean
}):
  | 'canvas.toolbar.keepOneSimilarity'
  | 'canvas.toolbar.keepOneDifference'
  | 'canvas.toolbar.keepOneSimilarityAndDifference'
  | null {
  if (outcome.withheldSimilarity && outcome.withheldDifference) {
    return 'canvas.toolbar.keepOneSimilarityAndDifference'
  }
  if (outcome.withheldSimilarity) return 'canvas.toolbar.keepOneSimilarity'
  if (outcome.withheldDifference) return 'canvas.toolbar.keepOneDifference'
  return null
}

export function useDoubleBubbleMapOpsSlice(ctx: DiagramContext) {
  function addDoubleBubbleMapNode(
    group: DoubleBubbleRole,
    defaultText: string,
    pairText?: string
  ): boolean {
    const spec = ctx.getDoubleBubbleSpecFromData()
    if (!spec) return false

    const similarities = asItems(spec.similarities)
    const leftDifferences = asItems(spec.leftDifferences)
    const rightDifferences = asItems(spec.rightDifferences)

    if (group === 'similarity') {
      spec.similarities = [...similarities, { text: defaultText }]
      appendGlossSlot(spec, 'similarities')
    } else {
      spec.leftDifferences = [...leftDifferences, { text: defaultText }]
      spec.rightDifferences = [...rightDifferences, { text: pairText ?? defaultText }]
      appendGlossSlot(spec, 'leftDifferences')
      appendGlossSlot(spec, 'rightDifferences')
    }

    return ctx.loadFromSpec(spec, 'double_bubble_map', { mergePreviousNodeStyles: true })
  }

  function removeDoubleBubbleMapNodes(nodeIds: string[]): DoubleBubbleDeleteOutcome {
    const empty: DoubleBubbleDeleteOutcome = {
      deleted: 0,
      withheldSimilarity: false,
      withheldDifference: false,
    }
    if (isDiagramPresentationReadOnly(ctx)) return empty
    const spec = ctx.getDoubleBubbleSpecFromData()
    if (!spec) return empty

    if (collabForeignLockBlocksAnyId(ctx, nodeIds)) {
      emitCollabDeleteBlocked()
      return empty
    }

    const nodes = ctx.data.value?.nodes ?? []
    const removeIds = new Set(nodeIds)
    const removeByRole = (role: DoubleBubbleRole): Set<number> => {
      const indices = new Set<number>()
      for (const node of nodes) {
        if (!removeIds.has(node.id) || !isDoubleBubbleRoleNode(node, role)) continue
        const index = readDoubleBubbleIndex(node)
        if (index >= 0) indices.add(index)
      }
      return indices
    }

    const similarities = asItems(spec.similarities)
    const leftDifferences = asItems(spec.leftDifferences)
    const rightDifferences = asItems(spec.rightDifferences)
    const simDrop = dropIndicesKeepingOne(similarities.length, removeByRole('similarity'))
    const leftDrop = dropIndicesKeepingOne(leftDifferences.length, removeByRole('leftDiff'))
    const rightDrop = dropIndicesKeepingOne(rightDifferences.length, removeByRole('rightDiff'))
    const deleted = simDrop.drop.size + leftDrop.drop.size + rightDrop.drop.size
    const outcome: DoubleBubbleDeleteOutcome = {
      deleted,
      withheldSimilarity: simDrop.withheld,
      withheldDifference: leftDrop.withheld || rightDrop.withheld,
    }
    if (deleted === 0) return outcome

    spec.similarities = similarities.filter((_, i) => !simDrop.drop.has(i))
    spec.leftDifferences = leftDifferences.filter((_, i) => !leftDrop.drop.has(i))
    spec.rightDifferences = rightDifferences.filter((_, i) => !rightDrop.drop.has(i))
    dropGlossSlots(spec, 'similarities', simDrop.drop)
    dropGlossSlots(spec, 'leftDifferences', leftDrop.drop)
    dropGlossSlots(spec, 'rightDifferences', rightDrop.drop)
    dropSizeSlots(spec, 'simRadii', simDrop.drop)
    dropSizeSlots(spec, 'leftDiffRadii', leftDrop.drop)
    dropSizeSlots(spec, 'rightDiffRadii', rightDrop.drop)

    ctx.loadFromSpec(spec, 'double_bubble_map', { mergePreviousNodeStyles: true })
    return outcome
  }

  return { addDoubleBubbleMapNode, removeDoubleBubbleMapNodes }
}
