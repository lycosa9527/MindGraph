/**
 * Apply Kitty / voice WebSocket diagram_update payloads using the same Pinia store
 * primitives as the editor (Vue Flow nodes + diagram slice helpers).
 */
import type { DiagramNode, DiagramType } from '@/types'

import { useDiagramStore } from '@/stores/diagram'
import { recalculateCircleMapLayout } from '@/stores/specLoader'

function normalizedDiagramType(storeType: DiagramType | null): string {
  if (!storeType) return ''
  return storeType === 'mind_map' ? 'mindmap' : storeType
}

/** Map common backend underscore ids to live Vue Flow ids. */
export function resolveVoiceNodeId(
  diagramType: string,
  rawId: string,
  nodes: DiagramNode[]
): string | null {
  if (!rawId) return null
  if (nodes.some((n) => n.id === rawId)) return rawId

  const m = /^([a-zA-Z][\w-]*)_(\d+)$/.exec(rawId)
  if (!m) return null
  const [, prefix, idx] = m

  const candidates: string[] = []
  switch (diagramType) {
    case 'circle_map':
      if (prefix === 'context') candidates.push(`context-${idx}`)
      break
    case 'bubble_map':
      if (prefix === 'attribute' || prefix === 'bubble') candidates.push(`bubble-${idx}`)
      break
    case 'flow_map':
      if (prefix === 'step') candidates.push(`flow-step-${idx}`)
      if (prefix === 'flow') candidates.push(`flow-step-${idx}`)
      break
    case 'multi_flow_map':
      if (prefix === 'cause') candidates.push(`cause-${idx}`)
      if (prefix === 'effect') candidates.push(`effect-${idx}`)
      if (prefix === 'step') candidates.push(`cause-${idx}`)
      break
    case 'brace_map':
      if (prefix === 'part') candidates.push(`brace-part-${idx}`)
      if (prefix === 'subpart') candidates.push(`brace-subpart-${idx}`)
      break
    case 'tree_map':
      if (prefix === 'item' || prefix === 'category')
        candidates.push(`tree-leaf-${idx}-0`, `tree-cat-${idx}`)
      break
    case 'double_bubble_map':
      if (prefix === 'similarity' || prefix === 'node') candidates.push(`similarity-${idx}`)
      if (prefix === 'left' || prefix === 'left_difference') candidates.push(`left-diff-${idx}`)
      if (prefix === 'right' || prefix === 'right_difference') candidates.push(`right-diff-${idx}`)
      break
    case 'concept_map':
      if (prefix === 'concept') candidates.push(`concept-${idx}`)
      break
    case 'mindmap':
    case 'mind_map':
      if (prefix === 'branch') {
        for (const n of nodes) {
          if (n.id.startsWith('branch-') && n.id.endsWith(`-${idx}`)) candidates.push(n.id)
        }
      }
      break
    default:
      break
  }

  for (const c of candidates) {
    if (nodes.some((n) => n.id === c)) return c
  }
  return null
}

function topLevelMindmapBranchIds(nodes: DiagramNode[]): string[] {
  const sortIdx = (id: string): number => parseInt(id.split('-').pop() ?? '0', 10)
  const rights = nodes.filter((n) => n.id.startsWith('branch-r-1-')).sort(
    (a, b) => sortIdx(a.id) - sortIdx(b.id)
  )
  const lefts = nodes.filter((n) => n.id.startsWith('branch-l-1-')).sort(
    (a, b) => sortIdx(a.id) - sortIdx(b.id)
  )
  return [...rights.map((n) => n.id), ...lefts.map((n) => n.id)]
}

function mindmapChildIdAt(
  store: ReturnType<typeof useDiagramStore>,
  parentBranchId: string,
  childIndex: number
): string | null {
  const conns = store.data?.connections?.filter((c) => c.source === parentBranchId) ?? []
  const targets = conns.map((c) => c.target).sort()
  return targets[childIndex] ?? null
}

function conceptNodeIdByText(
  nodes: DiagramNode[],
  label: string,
  excludeIds = new Set<string>()
): string | null {
  const t0 = label.trim().toLowerCase()
  if (!t0) return null
  const hit = nodes.find(
    (n) =>
      !excludeIds.has(n.id) &&
      (n.text?.trim().toLowerCase() === t0 ||
        (typeof n.data?.label === 'string' && n.data.label.trim().toLowerCase() === t0))
  )
  return hit?.id ?? null
}

export function applyVoiceDiagramUpdateCenter(
  store: ReturnType<typeof useDiagramStore>,
  data: Record<string, unknown>
): boolean {
  const dt = normalizedDiagramType(store.type)
  if (!store.data?.nodes) return false

  let ok = false
  if (dt === 'double_bubble_map') {
    const left = data.left as string | undefined
    const right = data.right as string | undefined
    if (left && right) {
      if (store.updateNode('left-topic', { text: left })) ok = true
      if (store.updateNode('right-topic', { text: right })) ok = true
    }
  } else if (dt === 'flow_map') {
    const title = (data.title as string) || (data.new_text as string) || (data.text as string)
    if (title !== undefined && store.updateNode('flow-topic', { text: title })) ok = true
  } else if (dt === 'multi_flow_map') {
    const ev =
      (data.event as string) || (data.new_text as string) || (data.text as string)
    if (ev !== undefined && store.updateNode('event', { text: ev })) ok = true
  } else if (dt === 'brace_map') {
    const whole =
      (data.whole as string) || (data.new_text as string) || (data.text as string)
    if (whole !== undefined && store.updateNode('brace-whole', { text: whole })) ok = true
  } else if (dt === 'bridge_map') {
    const dimension =
      (data.dimension as string) || (data.new_text as string) || (data.text as string)
    if (
      dimension !== undefined &&
      store.updateNode('dimension-label', { text: dimension })
    ) {
      ok = true
    }
  } else if (dt === 'tree_map') {
    const main =
      (data.new_text as string) || (data.text as string) || (data.topic as string)
    if (main !== undefined && store.updateNode('tree-topic', { text: main })) ok = true
  } else if (dt === 'mindmap' || dt === 'mind_map') {
    const topic =
      (data.new_text as string) || (data.text as string)
    if (topic !== undefined && store.updateNode('topic', { text: topic })) ok = true
  } else {
    const newText = (data.new_text as string) || (data.text as string)
    if (newText !== undefined && store.updateNode('topic', { text: newText })) ok = true
  }

  if (ok) store.pushHistory('Update center via voice')
  return ok
}

export function applyVoiceDiagramAddNodes(
  store: ReturnType<typeof useDiagramStore>,
  payloads: unknown[]
): number {
  const dt = normalizedDiagramType(store.type)
  if (!store.data?.nodes) return 0

  let count = 0
  for (const raw of payloads) {
    if (typeof raw !== 'object' || raw === null) continue
    const p = raw as Record<string, unknown>
    const textRaw = p.text ?? p.new_text
    const text = typeof textRaw === 'string' ? textRaw : ''

    if (dt === 'mindmap' || dt === 'mind_map') {
      const branchIdx =
        typeof p.branch_index === 'number' ? p.branch_index : undefined
      const childIdx =
        typeof p.child_index === 'number' ? p.child_index : undefined
      if (branchIdx !== undefined && childIdx !== undefined && text) {
        const parents = topLevelMindmapBranchIds(store.data.nodes)
        const parentId = parents[branchIdx]
        if (parentId && store.addMindMapChild(parentId, text)) count++
      } else if (text) {
        if (store.addMindMapBranch('right', text)) count++
      }
      continue
    }

    if (dt === 'flow_map') {
      const stepIdx =
        typeof p.step_index === 'number' ? p.step_index : undefined
      const subIdx =
        typeof p.substep_index === 'number' ? p.substep_index : undefined
      if (stepIdx !== undefined && text) {
        const stepNode = store.data.nodes.find((n) => n.id === `flow-step-${stepIdx}`)
        const stepLabel = stepNode?.text?.trim() ?? ''
        if (subIdx !== undefined) {
          if (stepLabel && store.addFlowMapSubstep(stepLabel, text)) count++
        } else if (store.addFlowMapStep(text)) count++
      } else if (text && store.addFlowMapStep(text)) {
        count++
      }
      continue
    }

    if (dt === 'tree_map') {
      const catIdx =
        typeof p.category_index === 'number' ? p.category_index : undefined
      const itemIdx =
        typeof p.item_index === 'number' ? p.item_index : undefined
      if (catIdx !== undefined && text) {
        const catId = `tree-cat-${catIdx}`
        if (itemIdx !== undefined) {
          if (store.addTreeMapChild(catId, text)) count++
        } else if (store.addTreeMapCategory(text)) count++
      }
      continue
    }

    if (dt === 'brace_map') {
      const partIdx =
        typeof p.part_index === 'number' ? p.part_index : undefined
      const subIdxRaw = p.subpart_index ?? p.substep_index
      const subIdx =
        typeof subIdxRaw === 'number' ? subIdxRaw : undefined
      const braceRoot =
        store.data.nodes.find((n) => n.type === 'topic')?.id ?? 'brace-whole'
      if (partIdx !== undefined && subIdx !== undefined && text) {
        const parentId = `brace-part-${partIdx}`
        if (store.data.nodes.some((n) => n.id === parentId)) {
          if (store.addBraceMapPart(parentId, text)) count++
        }
      } else if (partIdx !== undefined && text) {
        const parentId =
          partIdx >= 0 ? `brace-part-${partIdx}` : braceRoot
        if (store.addBraceMapPart(parentId, text)) count++
      } else if (text && store.addBraceMapPart(braceRoot, text)) {
        count++
      }
      continue
    }

    if (dt === 'double_bubble_map') {
      const cat = String(p.category ?? '')
      if (cat === 'similarity' || cat === 'similarities') {
        if (store.addDoubleBubbleMapNode('similarity', text || '…')) count++
      } else if (
        cat === 'left_difference' ||
        cat === 'left_diff' ||
        cat === 'left'
      ) {
        const rightT = typeof p.right === 'string' ? p.right : text
        if (store.addDoubleBubbleMapNode('leftDiff', text || '…', rightT)) count++
      } else if (
        cat === 'right_difference' ||
        cat === 'right_diff' ||
        cat === 'right'
      ) {
        const leftT = typeof p.left === 'string' ? p.left : ''
        if (store.addDoubleBubbleMapNode('rightDiff', leftT || ' ', text || '…')) count++
      } else if (text) {
        if (store.addDoubleBubbleMapNode('similarity', text)) count++
      }
      continue
    }

    if (dt === 'circle_map' && text) {
      const idxs = store.data.nodes
        .map((n) => {
          const m = /^context-(\d+)$/.exec(n.id)
          return m ? parseInt(m[1], 10) : -1
        })
        .filter((i) => i >= 0)
      const next = (idxs.length ? Math.max(...idxs) + 1 : 0).toString()
      store.addNode({
        id: `context-${next}`,
        text,
        type: 'bubble',
        position: { x: 0, y: 0 },
      })
      store.data.nodes = recalculateCircleMapLayout(
        store.data.nodes,
        store.nodeDimensions
      )
      count++
      continue
    }

    if (dt === 'multi_flow_map' && text) {
      const cat = String(p.category ?? '')
      const isEffect =
        cat === 'effect' ||
        cat === 'effects' ||
        (typeof p.node_id === 'string' && p.node_id.startsWith('effect'))
      const idPrefix = isEffect ? 'effect' : 'cause'
      const existing = store.data.nodes.filter((n) => n.id.startsWith(`${idPrefix}-`))
      const nextNum = existing.length
      store.addNode({
        id: `${idPrefix}-${nextNum}`,
        text,
        type: 'branch',
        position: { x: 0, y: 0 },
        ...(isEffect ? { category: 'effects' } : { category: 'causes' }),
      } as DiagramNode & { category?: string })
      count++
      continue
    }

    if (dt === 'concept_map') {
      const fromL = typeof p.from === 'string' ? p.from : ''
      const toL = typeof p.to === 'string' ? p.to : ''
      const edgeLabel = typeof p.label === 'string' ? p.label : ''
      if (fromL && toL) {
        const exclude = new Set<string>()
        const sourceId = conceptNodeIdByText(store.data.nodes, fromL, exclude)
        if (sourceId) exclude.add(sourceId)
        const targetId = conceptNodeIdByText(store.data.nodes, toL, exclude)
        if (sourceId && targetId && store.addConnection(sourceId, targetId, edgeLabel)) {
          count++
        }
      }
      continue
    }

    if (text && (dt === 'bubble_map' || dt === 'bridge_map')) {
      if (dt === 'bubble_map') {
        const bubbles = store.data.nodes.filter(
          (n) => n.id.startsWith('bubble-') && (n.type === 'bubble' || n.type === 'child')
        )
        const next = bubbles.length.toString()
        store.addNode({
          id: `bubble-${next}`,
          text,
          type: 'bubble',
          position: { x: 0, y: 0 },
        })
        count++
      } else {
        store.addNode({
          id: `bridge-pair-${Date.now()}`,
          text,
          type: 'branch',
          position: { x: 0, y: 0 },
        })
        count++
      }
      continue
    }
  }

  if (count > 0) store.pushHistory(`Add ${count} node(s) via voice`)
  return count
}

export function applyVoiceDiagramUpdateNodes(
  store: ReturnType<typeof useDiagramStore>,
  updates: unknown[]
): number {
  const dt = normalizedDiagramType(store.type)
  if (!store.data?.nodes) return 0

  let nOk = 0
  for (const raw of updates) {
    if (typeof raw !== 'object' || raw === null) continue
    const o = raw as Record<string, unknown>
    const rawId = (o.node_id as string) || (o.id as string)
    const text = (o.text as string) ?? (o.new_text as string)
    if (!rawId || text === undefined) continue
    const resolved =
      resolveVoiceNodeId(dt, rawId, store.data.nodes) ??
      resolveVoiceNodeId(dt, String(rawId), store.data.nodes)
    const id = resolved ?? rawId
    if (store.updateNode(id, { text })) nOk++
  }
  if (nOk > 0) store.pushHistory(`Update ${nOk} node(s) via voice`)
  return nOk
}

export function applyVoiceDiagramRemoveNodes(
  store: ReturnType<typeof useDiagramStore>,
  payload: unknown[]
): number {
  const dt = normalizedDiagramType(store.type)
  if (!store.data?.nodes) return 0

  let removed = 0

  for (const raw of payload) {
    if (typeof raw === 'number') continue

    if (typeof raw === 'object' && raw !== null) {
      const o = raw as Record<string, unknown>

      if (dt === 'concept_map' && typeof o.relationship_index === 'number') {
        const idx = o.relationship_index
        const conns = store.data.connections
        if (conns && idx >= 0 && idx < conns.length) {
          conns.splice(idx, 1)
          removed++
        }
        continue
      }

      if (
        dt === 'tree_map' &&
        typeof o.category_index === 'number' &&
        typeof o.item_index === 'number'
      ) {
        const leafId = `tree-leaf-${o.category_index}-${o.item_index}`
        removed += store.removeTreeMapNodes([leafId])
        continue
      }

      if (dt === 'brace_map' && typeof o.part_index === 'number') {
        const pi = o.part_index
        const si = typeof o.subpart_index === 'number' ? o.subpart_index : null
        if (si !== null) {
          removed += store.removeBraceMapNodes([`brace-subpart-${pi}-${si}`])
        } else {
          removed += store.removeBraceMapNodes([`brace-part-${pi}`])
        }
        continue
      }

      if (
        (dt === 'mindmap' || dt === 'mind_map') &&
        typeof o.branch_index === 'number' &&
        typeof o.child_index === 'number'
      ) {
        const parents = topLevelMindmapBranchIds(store.data.nodes)
        const pid = parents[o.branch_index]
        if (pid) {
          const cid = mindmapChildIdAt(store, pid, o.child_index)
          if (cid) removed += store.removeMindMapNodes([cid])
        }
        continue
      }
    }

    const rawId =
      typeof raw === 'string'
        ? raw
        : typeof raw === 'object' && raw !== null
          ? ((raw as Record<string, unknown>).node_id as string) ||
            ((raw as Record<string, unknown>).id as string)
          : null
    if (!rawId) continue

    const resolved =
      resolveVoiceNodeId(dt, rawId, store.data.nodes) ?? rawId

    if (dt === 'mindmap' || dt === 'mind_map') {
      removed += store.removeMindMapNodes([resolved])
      continue
    }
    if (dt === 'tree_map') {
      removed += store.removeTreeMapNodes([resolved])
      continue
    }
    if (dt === 'brace_map') {
      removed += store.removeBraceMapNodes([resolved])
      continue
    }
    if (dt === 'double_bubble_map') {
      removed += store.removeDoubleBubbleMapNodes([resolved])
      continue
    }

    if (store.removeNode(resolved)) {
      removed++
      if (dt === 'circle_map') {
        store.data.nodes = recalculateCircleMapLayout(
          store.data.nodes,
          store.nodeDimensions
        )
      }
    }
  }

  if (removed > 0) store.pushHistory(`Voice delete (${removed})`)
  return removed
}
