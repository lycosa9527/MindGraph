/**
 * Node-carousel slides for double-bubble maps.
 * Fixed order: overview → both topics → each similarity → each difference pair.
 */
import type { DiagramNode } from '@/types'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import type { MindMapSlide } from '@/utils/mindMapSlides'

function nodeText(node: DiagramNode | undefined): string {
  if (!node) return ''
  return String(node.text ?? (node.data as { label?: string } | undefined)?.label ?? '').trim()
}

function byIndex(list: DiagramNode[]): DiagramNode[] {
  return [...list].sort((a, b) => readDoubleBubbleIndex(a) - readDoubleBubbleIndex(b))
}

function overviewTitle(left: DiagramNode | undefined, right: DiagramNode | undefined): string {
  const a = nodeText(left)
  const b = nodeText(right)
  if (a && b) return `${a} / ${b}`
  return a || b || 'overview'
}

function branchSlide(
  id: string,
  title: string,
  breadcrumb: string[],
  focusNodeIds: string[],
  branchNodeId: string
): MindMapSlide {
  return {
    id,
    kind: 'branch',
    title,
    branchNodeId,
    breadcrumb,
    focusNodeIds,
  }
}

export function buildDoubleBubbleSlides(nodes: DiagramNode[]): MindMapSlide[] {
  if (!nodes.length) return []

  const left = nodes.find((node) => node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID)
  const right = nodes.find((node) => node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID)
  const similarities = byIndex(nodes.filter((node) => readDoubleBubbleRole(node) === 'similarity'))
  const leftDiffs = byIndex(nodes.filter((node) => readDoubleBubbleRole(node) === 'leftDiff'))
  const rightDiffs = byIndex(nodes.filter((node) => readDoubleBubbleRole(node) === 'rightDiff'))
  const rootTitle = overviewTitle(left, right)
  const allIds = nodes.map((node) => node.id)

  const slides: MindMapSlide[] = [
    {
      id: 'overview',
      kind: 'overview',
      title: rootTitle,
      branchNodeId: left?.id ?? right?.id,
      breadcrumb: [rootTitle],
      focusNodeIds: allIds,
    },
  ]

  if (left) {
    slides.push(
      branchSlide(
        left.id,
        nodeText(left) || left.id,
        [rootTitle, nodeText(left)],
        [left.id],
        left.id
      )
    )
  }
  if (right) {
    slides.push(
      branchSlide(
        right.id,
        nodeText(right) || right.id,
        [rootTitle, nodeText(right)],
        [right.id],
        right.id
      )
    )
  }

  for (const sim of similarities) {
    const title = nodeText(sim) || sim.id
    slides.push(branchSlide(sim.id, title, [rootTitle, title], [sim.id], sim.id))
  }

  const pairCount = Math.max(leftDiffs.length, rightDiffs.length)
  for (let i = 0; i < pairCount; i += 1) {
    const leftDiff = leftDiffs[i]
    const rightDiff = rightDiffs[i]
    const focus = [leftDiff?.id, rightDiff?.id].filter((id): id is string => Boolean(id))
    if (!focus.length) continue
    const leftLabel = nodeText(leftDiff)
    const rightLabel = nodeText(rightDiff)
    const title =
      leftLabel && rightLabel
        ? `${leftLabel} / ${rightLabel}`
        : leftLabel || rightLabel || `diff-${i}`
    const branchId = leftDiff?.id ?? rightDiff?.id ?? `diff-${i}`
    slides.push(branchSlide(`diff-pair-${i}`, title, [rootTitle, title], focus, branchId))
  }

  return slides
}
