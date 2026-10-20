/**
 * Shared image frame for diagram nodes.
 * An inserted picture is a fixed 120×80 thumbnail above the label. Clicking it
 * opens the full image. The node box grows by that known frame.
 */
import type { CSSProperties } from 'vue'

import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import type { Connection, DiagramData, DiagramNode } from '@/types'
import { readMindMapAdornments, readNodeAdornment } from '@/utils/mindMapAdornments'

/** Fixed thumbnail width, in CSS pixels. */
export const NODE_IMAGE_THUMB_WIDTH = 120
/** Fixed thumbnail height, in CSS pixels. */
export const NODE_IMAGE_THUMB_HEIGHT = 80
/** Gap between the thumbnail and the label, matching `.mm-adornments`. */
export const NODE_IMAGE_GAP = 4
/** Horizontal padding so the thumbnail fits inside the node border box. */
export const NODE_IMAGE_FRAME_MIN_WIDTH = NODE_IMAGE_THUMB_WIDTH + 16
/** Inset when the node has no padding of its own. */
export const NODE_IMAGE_FRAME_PADDING = '10px 12px'
/**
 * Pill inset. The side room keeps the 120×80 thumbnail inside the capsule
 * curve instead of poking through the rounded ends.
 */
export const NODE_IMAGE_PILL_PADDING = '14px 28px'

/** Node ids whose adornment currently shows an image (path keys resolved to ids). */
export function nodeIdsWithImage(
  nodes: readonly { id: string }[],
  data: DiagramData | Record<string, unknown> | null | undefined,
  connections?: readonly Connection[]
): Set<string> {
  const ids = new Set<string>()
  if (!data) return ids
  for (const node of nodes) {
    if (readNodeAdornment(data, node.id, connections)?.imageUrl) ids.add(node.id)
  }
  return ids
}

/**
 * Border-box width that fits the thumbnail inside mind-map padding.
 * Oval uses the wider inset so the picture stays inside the curve.
 */
export function mindMapImageFrameWidth(): number {
  const padX = Math.max(MIND_MAP_GEOMETRY.paddingX, MIND_MAP_GEOMETRY.paddingXOval)
  return NODE_IMAGE_THUMB_WIDTH + padX * 2 + MIND_MAP_GEOMETRY.borderWidth * 2
}

/** Topic column width, widened when the topic itself shows a picture. */
export function mindMapTopicWidthWithImage(width: number, topicHasImage: boolean): number {
  if (!topicHasImage) return width
  return Math.max(width, mindMapImageFrameWidth())
}

function positiveSize(value: unknown): number | undefined {
  return typeof value === 'number' && value > 0 ? value : undefined
}

/**
 * Layout sizes that leave the thumbnail clear of siblings and children.
 * Measured boxes that already include the picture are kept. The text estimate
 * is never added on top of a size that already contains the frame.
 */
export function expandMindMapLayoutSizesForImages(
  nodes: readonly DiagramNode[],
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number>,
  imageNodeIds: ReadonlySet<string> | undefined
): { nodeWidths: Record<string, number>; nodeHeights: Record<string, number> } {
  if (!imageNodeIds || imageNodeIds.size === 0) {
    return { nodeWidths, nodeHeights }
  }
  const widths = { ...nodeWidths }
  const heights = { ...nodeHeights }
  const frameWidth = mindMapImageFrameWidth()
  const textFallback = MIND_MAP_GEOMETRY.minHeight
  for (const node of nodes) {
    if (!imageNodeIds.has(node.id)) continue
    const textWidth = positiveSize(node.data?.estimatedWidth)
    const textHeight = positiveSize(node.data?.estimatedHeight)
    const baseWidth = widths[node.id] ?? textWidth ?? frameWidth
    const baseHeight = heights[node.id] ?? textHeight ?? textFallback
    widths[node.id] = Math.max(baseWidth, frameWidth)
    heights[node.id] = Math.max(
      baseHeight,
      (textHeight ?? textFallback) + NODE_IMAGE_THUMB_HEIGHT + NODE_IMAGE_GAP
    )
  }
  return { nodeWidths: widths, nodeHeights: heights }
}

export function thinkingMapNodeHasImage(
  data: DiagramData | Record<string, unknown> | null | undefined,
  nodeId: string,
  connections?: readonly Connection[]
): boolean {
  return Boolean(readNodeAdornment(data, nodeId, connections)?.imageUrl)
}

/** Node ids (thinking maps store adornments by id) that currently show an image. */
export function thinkingMapImageNodeIds(
  data: DiagramData | Record<string, unknown> | null | undefined
): Set<string> {
  const ids = new Set<string>()
  for (const [key, adornment] of Object.entries(readMindMapAdornments(data))) {
    if (adornment.imageUrl) ids.add(key)
  }
  return ids
}

function isPillRadius(radius: CSSProperties['borderRadius']): boolean {
  const value = String(radius ?? '')
    .trim()
    .toLowerCase()
  return value === '9999px' || value === '999px'
}

/**
 * Size the bordered box to the thumbnail plus the label.
 * A pill keeps its capsule radius and gains side padding so the picture
 * stays inside the curve. A learning-sheet blank frame applied after this still wins.
 */
export function releaseNodeBoxForImage(style: CSSProperties, hasImage: boolean): CSSProperties {
  if (!hasImage) return style
  const next: CSSProperties = {
    ...style,
    width: 'max-content',
    height: 'max-content',
    maxWidth: 'none',
    maxHeight: 'none',
    overflow: 'visible',
  }
  delete next.minWidth
  delete next.minHeight
  if (isPillRadius(next.borderRadius)) {
    next.padding = NODE_IMAGE_PILL_PADDING
    next.borderRadius = '9999px'
  } else if (next.padding == null || next.padding === '') {
    next.padding = NODE_IMAGE_FRAME_PADDING
  }
  return next
}
