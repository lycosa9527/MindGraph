/**
 * Node Palette placeholder helpers - detect and collect placeholder nodes for replacement
 */
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import type { DiagramType } from '@/types'

import { LEARNING_SHEET_PLACEHOLDER } from './constants'

export { LEARNING_SHEET_PLACEHOLDER }

export function isNodePlaceholder(text: string | undefined): boolean {
  if (!text || !text.trim()) return false
  const t = text.trim()
  return t === LEARNING_SHEET_PLACEHOLDER || isPlaceholderText(t)
}

function normalizeDiagramType(dt: DiagramType | null): DiagramType | null {
  return dt === 'mind_map' ? 'mindmap' : dt
}

/**
 * Get placeholder content nodes for replacement, sorted by diagram slot order.
 * @param parentId - For stage 2: only return placeholders of this parent (part_id, category_id, branch id)
 * @param connections - Used to filter placeholders by parent
 */
export function getPlaceholderNodes(
  diagramType: DiagramType | null,
  nodes: Array<{ id: string; text: string; type?: string }>,
  mode?: string | null,
  stage?: string | null,
  parentId?: string | null,
  connections?: Array<{ source: string; target: string }>
): Array<{ id: string; text: string }> {
  const dt = normalizeDiagramType(diagramType)
  if (!dt || !nodes.length) return []

  const isPlaceholder = (n: { text: string }) => isNodePlaceholder(n.text)

  switch (dt) {
    case 'circle_map':
      return nodes
        .filter(
          (n) =>
            (n.type === 'bubble' || n.type === 'context') &&
            n.id.startsWith('context-') &&
            isPlaceholder(n)
        )
        .sort(
          (a, b) =>
            parseInt(a.id.replace('context-', ''), 10) - parseInt(b.id.replace('context-', ''), 10)
        )
    case 'bubble_map':
      return nodes
        .filter(
          (n) =>
            (n.type === 'bubble' || n.type === 'attribute') &&
            n.id.startsWith('bubble-') &&
            isPlaceholder(n)
        )
        .sort(
          (a, b) =>
            parseInt(a.id.replace('bubble-', ''), 10) - parseInt(b.id.replace('bubble-', ''), 10)
        )
    case 'multi_flow_map': {
      const slot = mode === 'effects' ? 'effect' : 'cause'
      return nodes
        .filter((n) => n.id.startsWith(`${slot}-`) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace(`${slot}-`, ''), 10) - parseInt(b.id.replace(`${slot}-`, ''), 10)
        )
    }
    case 'double_bubble_map':
      if (mode === 'differences') {
        const leftNodes = nodes
          .filter((n) => /^left-diff-\d+$/.test(n.id) && isPlaceholder(n))
          .sort(
            (a, b) =>
              parseInt(a.id.replace('left-diff-', ''), 10) -
              parseInt(b.id.replace('left-diff-', ''), 10)
          )
        const rightNodes = nodes
          .filter((n) => /^right-diff-\d+$/.test(n.id) && isPlaceholder(n))
          .sort(
            (a, b) =>
              parseInt(a.id.replace('right-diff-', ''), 10) -
              parseInt(b.id.replace('right-diff-', ''), 10)
          )
        return leftNodes.map((l, i) => ({
          id: `${l.id}|${rightNodes[i]?.id ?? ''}`,
          text: l.text,
        }))
      }
      return nodes
        .filter((n) => /^similarity-\d+$/.test(n.id) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace('similarity-', ''), 10) -
            parseInt(b.id.replace('similarity-', ''), 10)
        )
    case 'flow_map': {
      if (stage === 'substeps') {
        let substepNodes = nodes.filter((n) => n.id.startsWith('flow-substep-') && isPlaceholder(n))
        if (parentId) {
          const stepMatch = parentId.match(/flow-step-(\d+)/)
          const stepIndex = stepMatch ? stepMatch[1] : null
          if (stepIndex !== null) {
            substepNodes = substepNodes.filter((n) => n.id.startsWith(`flow-substep-${stepIndex}-`))
          }
        }
        return substepNodes.sort((a, b) => a.id.localeCompare(b.id))
      }
      return nodes
        .filter((n) => n.id.startsWith('flow-step-') && isPlaceholder(n))
        .sort((a, b) => a.id.localeCompare(b.id))
    }
    case 'mindmap': {
      if (stage === 'children' && parentId && connections?.length) {
        const childIds = new Set(
          connections.filter((c) => c.source === parentId).map((c) => c.target)
        )
        const childBranches = nodes.filter(
          (n) =>
            (n.id.startsWith('branch-l-') || n.id.startsWith('branch-r-')) &&
            childIds.has(n.id) &&
            isPlaceholder(n)
        )
        return childBranches.sort((a, b) => a.id.localeCompare(b.id))
      }
      const firstLevelBranches = nodes.filter(
        (n) =>
          (n.id.startsWith('branch-l-1-') || n.id.startsWith('branch-r-1-')) && isPlaceholder(n)
      )
      return firstLevelBranches.sort((a, b) => a.id.localeCompare(b.id))
    }
    case 'bridge_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      return nodes
        .filter((n) => /^pair-\d+-left$/.test(n.id) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace('pair-', '').replace('-left', ''), 10) -
            parseInt(b.id.replace('pair-', '').replace('-left', ''), 10)
        )
    }
    case 'tree_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      if (stage === 'children') {
        let leafNodes = nodes.filter((n) => /^tree-leaf-\d+-\d+$/.test(n.id) && isPlaceholder(n))
        if (parentId && connections?.length) {
          const descendantIds = new Set<string>()
          const collect = (id: string) => {
            for (const c of connections) {
              if (c.source === id && !descendantIds.has(c.target)) {
                descendantIds.add(c.target)
                collect(c.target)
              }
            }
          }
          collect(parentId)
          leafNodes = leafNodes.filter((n) => descendantIds.has(n.id))
        }
        return leafNodes.sort((a, b) => a.id.localeCompare(b.id))
      }
      return nodes
        .filter((n) => /^tree-cat-\d+$/.test(n.id) && isPlaceholder(n))
        .sort(
          (a, b) =>
            parseInt(a.id.replace('tree-cat-', ''), 10) -
            parseInt(b.id.replace('tree-cat-', ''), 10)
        )
    }
    case 'brace_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      if (stage === 'subparts') {
        const isSubpartId = (id: string) =>
          id.startsWith('brace-subpart-') ||
          /^brace-\d+-\d+$/.test(id) ||
          /^brace-part-\d+-\d+$/.test(id)
        let subpartNodes = nodes.filter(
          (n) => isSubpartId(n.id) && n.type === 'brace' && isPlaceholder(n)
        )
        if (parentId && connections?.length) {
          const childIds = new Set(
            connections.filter((c) => c.source === parentId).map((c) => c.target)
          )
          subpartNodes = subpartNodes.filter((n) => childIds.has(n.id))
        }
        return subpartNodes.sort((a, b) => a.id.localeCompare(b.id))
      }
      const partNodes = nodes.filter(
        (n) =>
          (n.id.startsWith('brace-part-') || /^brace-1-\d+$/.test(n.id)) &&
          n.type === 'brace' &&
          isPlaceholder(n)
      )
      return partNodes.sort((a, b) => a.id.localeCompare(b.id))
    }
    case 'concept_map':
      return []
    default:
      return []
  }
}
