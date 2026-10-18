/**
 * Shared image frame for diagram nodes.
 * An inserted picture is a fixed 120×80 thumbnail above the label. Clicking it
 * opens the full image. The node box grows by that known frame.
 */
import type { CSSProperties } from 'vue'

import type { Connection, DiagramData } from '@/types'
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
