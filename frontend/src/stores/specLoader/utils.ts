/**
 * Shared utilities for spec loaders
 * Contains common layout calculations and type definitions
 */
import type { DiagramType } from '@/types'
import type { DiagramNode } from '@/types'

import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_CONTEXT_RADIUS,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'

import {
  CONTEXT_FONT_SIZE,
  computeMinDiameterForNoWrap,
  computeTopicRadiusForCircleMap,
} from './textMeasurement'
import type { SpecLoaderResult } from './types'

/** Placeholder text for knocked-out nodes in learning sheet mode */
export const LEARNING_SHEET_PLACEHOLDER = '___'

/** Node types that should never be hidden (topic, center, boundary, etc.) */
const PROTECTED_NODE_TYPES = ['topic', 'center', 'boundary', 'label']

/**
 * Check if a node is hideable for learning sheet (exclude topic, center, boundary, label).
 */
function isHideableNode(node: DiagramNode, diagramType: DiagramType): boolean {
  if (PROTECTED_NODE_TYPES.includes(node.type)) {
    return false
  }
  if ((node.data as { isDimensionLabel?: boolean })?.isDimensionLabel === true) {
    return false
  }
  if (!node.text || !String(node.text).trim()) {
    return false
  }
  return true
}

/**
 * Seeded shuffle for deterministic random selection (same spec = same hidden set).
 */
function seededShuffle<T>(array: T[], seed: number): T[] {
  const arr = [...array]
  let s = seed
  for (let i = arr.length - 1; i > 0; i--) {
    s = (s * 9301 + 49297) % 233280
    const j = Math.floor((s / 233280) * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

/**
 * Apply learning sheet hidden nodes: randomly knock out a percentage of child nodes,
 * replace text with placeholder, collect answers. Same business logic as backend.
 *
 * @param spec - API spec (may contain is_learning_sheet, hidden_node_percentage)
 * @param result - SpecLoaderResult from type-specific loader
 * @param diagramType - Diagram type
 * @returns Modified result with hidden nodes and hiddenAnswers in metadata
 */
export function applyLearningSheetHiddenNodes(
  spec: Record<string, unknown>,
  result: SpecLoaderResult,
  diagramType: DiagramType
): SpecLoaderResult {
  const isLearningSheet = spec.is_learning_sheet === true
  const rawPct = spec.hidden_node_percentage
  const pct = typeof rawPct === 'number' ? Math.max(0, Math.min(1, rawPct)) : 0
  const existingHiddenAnswers = Array.isArray(spec.hiddenAnswers) ? spec.hiddenAnswers : []

  if (!isLearningSheet || !result.nodes.length) {
    if (isLearningSheet && existingHiddenAnswers.length > 0) {
      const metadata = { ...result.metadata, hiddenAnswers: existingHiddenAnswers, isLearningSheet: true }
      return { ...result, metadata }
    }
    return result
  }

  if (pct <= 0 && existingHiddenAnswers.length > 0) {
    const metadata = { ...result.metadata, hiddenAnswers: existingHiddenAnswers, isLearningSheet: true }
    return { ...result, metadata }
  }

  if (pct <= 0) {
    return result
  }

  const hideableIndices: number[] = []
  result.nodes.forEach((node, idx) => {
    if (isHideableNode(node, diagramType)) {
      hideableIndices.push(idx)
    }
  })

  if (hideableIndices.length === 0) {
    return result
  }

  const seed = JSON.stringify(spec).length + (spec.topic ? String(spec.topic).length : 0)
  const shuffled = seededShuffle(hideableIndices, seed)
  const countToHide = Math.max(1, Math.floor(shuffled.length * pct))
  const indicesToHide = new Set(shuffled.slice(0, countToHide))

  const hiddenAnswers: string[] = []
  const nodes = result.nodes.map((node, idx) => {
    if (!indicesToHide.has(idx)) {
      return node
    }
    const originalText = String(node.text || '').trim()
    hiddenAnswers.push(originalText)
    return {
      ...node,
      text: LEARNING_SHEET_PLACEHOLDER,
      data: {
        ...node.data,
        hidden: true,
        hiddenAnswer: originalText,
      },
    }
  })

  const metadata = { ...result.metadata, hiddenAnswers, isLearningSheet: true }
  return { ...result, nodes, metadata }
}

/**
 * Circle map layout calculation result
 */
export interface CircleMapLayoutResult {
  centerX: number
  centerY: number
  topicR: number
  uniformContextR: number
  childrenRadius: number
  outerCircleR: number
}

/**
 * Get topic circle diameter from text (circle map center node).
 * Uses same measurement as layout (computeTopicRadiusForCircleMap) so size is consistent.
 * Single-line text only; circle adapts to text length.
 *
 * @param text - Topic text
 * @returns Diameter in pixels
 */
export function getTopicCircleDiameter(text: string): number {
  return 2 * computeTopicRadiusForCircleMap((text || '').trim() || ' ')
}

/**
 * Calculate adaptive circle size based on text length
 * For context nodes in circle maps, adapts size to fit text content
 *
 * @param text - Text content of the node
 * @param isTopic - Whether this is a topic node (larger) or context node
 * @returns Diameter in pixels
 */
export function calculateAdaptiveCircleSize(text: string, isTopic: boolean = false): number {
  if (!text || !text.trim()) {
    return isTopic ? 120 : 70
  }

  const textLength = text.trim().length

  if (isTopic) {
    // Topic nodes: use measurement-based diameter (single-line, adapts to text length)
    return getTopicCircleDiameter(text)
  } else {
    // Context nodes: smaller circles, adapt based on text length
    if (textLength <= 6) {
      return 70
    } else if (textLength <= 12) {
      return 85
    } else if (textLength <= 18) {
      return 100
    } else if (textLength <= 24) {
      return 115
    } else {
      // For very long text, calculate based on estimated width
      // Approximate: ~7px per character at 14px font size
      const estimatedWidth = textLength * 7
      // Add padding (30px) and ensure minimum size
      return Math.max(130, Math.min(estimatedWidth + 30, 200))
    }
  }
}

/** Gap between topic and context ring (px). Larger = more space between center and middle layer. */
const CIRCLE_MAP_TOPIC_CONTEXT_GAP = 65
/** Extra edge-to-edge gap between adjacent context circles (px). Second-layer spacing. */
const CIRCLE_MAP_CONTEXT_GAP = 8
/** Margin outside context ring for outer boundary (px). Keeps boundary clear of context circles. */
const CIRCLE_MAP_OUTER_MARGIN = 18
/** Minimum childrenRadius (px). */
const CIRCLE_MAP_MIN_CHILDREN_RADIUS = 130

/** Snap grid size (px) - must match Vue Flow snap grid so boundary position lands on grid. */
const CIRCLE_MAP_SNAP_GRID = 10

/**
 * Calculate circle map layout: fixed font, circles from text, ring no-overlap.
 * Center = canvas center; context nodes evenly spaced on a ring (360/n deg).
 * Order: topic first → uniformContextR from texts → childrenRadius → outer circle.
 * Shared by loadCircleMapSpec and recalculateCircleMapLayout.
 *
 * @param nodeCount - Number of context nodes
 * @param contextTexts - Array of context node texts for adaptive sizing
 * @param topicText - Topic text for radius calculation
 * @returns Layout calculation result with positions and radii
 */
export function calculateCircleMapLayout(
  nodeCount: number,
  contextTexts: string[] = [],
  topicText: string = ''
): CircleMapLayoutResult {
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y

  // (g) Topic: text-adaptive radius = text bounding box diagonal/2 + inner padding, min only (no max)
  const topicRFromText = computeTopicRadiusForCircleMap(topicText || ' ')
  const topicR = Math.max(DEFAULT_TOPIC_RADIUS, topicRFromText)

  // (b) Uniform context R: fixed CONTEXT_FONT_SIZE → min diameter per text → max → radius
  let uniformContextR: number
  if (contextTexts.length === 0) {
    uniformContextR = DEFAULT_CONTEXT_RADIUS
  } else {
    let maxRadius = DEFAULT_CONTEXT_RADIUS
    for (const t of contextTexts) {
      const d = computeMinDiameterForNoWrap(t || ' ', CONTEXT_FONT_SIZE, false)
      maxRadius = Math.max(maxRadius, d / 2)
    }
    uniformContextR = maxRadius
  }

  // (c) Ring radius: no-overlap context–context (with small gap), no-overlap context–topic, minimum.
  // All layers share the same center (centerX, centerY). Slightly lengthen childrenRadius so
  // adjacent second-layer circles have a small edge-to-edge gap.
  const noOverlapContext =
    nodeCount > 0
      ? (uniformContextR + CIRCLE_MAP_CONTEXT_GAP / 2) / Math.sin(Math.PI / nodeCount)
      : 0
  const noOverlapTopic = topicR + uniformContextR + CIRCLE_MAP_TOPIC_CONTEXT_GAP
  const childrenRadius = Math.max(noOverlapContext, noOverlapTopic, CIRCLE_MAP_MIN_CHILDREN_RADIUS)

  // (d) Outer circle: just enclose context ring; margin avoids overlap with boundary stroke
  // Round outerCircleR to snap grid so boundary position (centerX-R, centerY-R) lands on grid.
  // This prevents Vue Flow snap-to-grid from shifting the outer circle off-center.
  const rawOuterR = childrenRadius + uniformContextR + CIRCLE_MAP_OUTER_MARGIN
  const outerCircleR = Math.round(rawOuterR / CIRCLE_MAP_SNAP_GRID) * CIRCLE_MAP_SNAP_GRID

  return { centerX, centerY, topicR, uniformContextR, childrenRadius, outerCircleR }
}
