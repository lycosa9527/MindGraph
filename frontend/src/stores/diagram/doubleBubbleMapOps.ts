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

function asItems(raw: unknown): SpecItem[] {
  return Array.isArray(raw) ? (raw as SpecItem[]) : []
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

  function removeDoubleBubbleMapNodes(nodeIds: string[]): number {
    if (isDiagramPresentationReadOnly(ctx)) return 0
    const spec = ctx.getDoubleBubbleSpecFromData()
    if (!spec) return 0

    if (collabForeignLockBlocksAnyId(ctx, nodeIds)) {
      emitCollabDeleteBlocked()
      return 0
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

    const simIndices = removeByRole('similarity')
    const leftDiffIndices = removeByRole('leftDiff')
    const rightDiffIndices = removeByRole('rightDiff')

    spec.similarities = asItems(spec.similarities).filter((_, i) => !simIndices.has(i))
    spec.leftDifferences = asItems(spec.leftDifferences).filter((_, i) => !leftDiffIndices.has(i))
    spec.rightDifferences = asItems(spec.rightDifferences).filter(
      (_, i) => !rightDiffIndices.has(i)
    )
    dropGlossSlots(spec, 'similarities', simIndices)
    dropGlossSlots(spec, 'leftDifferences', leftDiffIndices)
    dropGlossSlots(spec, 'rightDifferences', rightDiffIndices)

    ctx.loadFromSpec(spec, 'double_bubble_map', { mergePreviousNodeStyles: true })
    return simIndices.size + leftDiffIndices.size + rightDiffIndices.size
  }

  return { addDoubleBubbleMapNode, removeDoubleBubbleMapNodes }
}
