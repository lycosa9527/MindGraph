/**
 * Shared utilities for spec loaders
 * Contains common layout calculations and type definitions
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_CONTEXT_RADIUS,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'
import type { DiagramNode, DiagramType } from '@/types'
import { nodesInLearningSheetReadingOrder } from '@/utils/learningSheetAnswerOrder'
import { measureThinkingMapLabelBlockPx } from '@/utils/mindMapTextWrap'

import { estimateNodeWidth, measureBranchNodeHeight } from './mindMap'
import {
  CONTEXT_FONT_SIZE,
  computeTopicRadiusForCircleMap,
  growRadiusForSecondary,
} from './textMeasurement'
import type { SpecLoaderResult } from './types'

/** Visible text for knocked-out nodes — empty; layout estimates preserve node size. */
export const LEARNING_SHEET_BLANK_TEXT = ''

/** Legacy knocked-out placeholder from older specs (still recognized on load). */
export const LEARNING_SHEET_LEGACY_PLACEHOLDER = '___'

/** @deprecated Use LEARNING_SHEET_BLANK_TEXT */
export const LEARNING_SHEET_PLACEHOLDER = LEARNING_SHEET_BLANK_TEXT

export function isLearningSheetBlankDisplayText(text: string | undefined | null): boolean {
  const trimmed = String(text ?? '').trim()
  return trimmed === '' || trimmed === LEARNING_SHEET_LEGACY_PLACEHOLDER
}

/** Node types that should never be hidden (topic, center, boundary, etc.) */
const PROTECTED_NODE_TYPES = ['topic', 'center', 'boundary', 'label']

/**
 * Check if a node is hideable for learning sheet (exclude topic, center, boundary, label).
 */
function isHideableNode(node: DiagramNode, _diagramType: DiagramType): boolean {
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

/** Default share of hideable nodes knocked out by the random learning-sheet action. */
export const LEARNING_SHEET_RANDOM_BLANK_RATIO = 0.2

function learningSheetRandomSeed(nodes: DiagramNode[]): number {
  let seed = nodes.length
  for (const node of nodes) {
    seed += node.id.length
    if (node.type === 'topic' || node.type === 'center') {
      seed += String(node.text ?? '').length
    }
  }
  return seed
}

/**
 * Pick hideable node ids for an in-place random blank.
 * Does not rebuild layout — callers blank the live nodes and keep their boxes.
 */
export function pickLearningSheetRandomNodeIds(
  nodes: DiagramNode[],
  diagramType: DiagramType,
  percentage: number = LEARNING_SHEET_RANDOM_BLANK_RATIO
): string[] {
  const pct = Math.max(0, Math.min(1, percentage))
  if (pct <= 0 || nodes.length === 0) return []
  const hideable = nodes.filter((node) => isHideableNode(node, diagramType))
  if (hideable.length === 0) return []
  const shuffled = seededShuffle(hideable, learningSheetRandomSeed(nodes))
  const countToHide = Math.max(1, Math.floor(shuffled.length * pct))
  return shuffled.slice(0, countToHide).map((node) => node.id)
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

  if (!isLearningSheet || !result.nodes.length) {
    return result
  }

  const branchNumbering = spec._mindmap_branch_numbering === true

  if (pct <= 0) {
    const hiddenAnswersFromNodes: string[] = []
    const orderedNodes = nodesInLearningSheetReadingOrder(
      result.nodes,
      result.connections,
      diagramType,
      branchNumbering
    )
    for (const node of orderedNodes) {
      const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      const text = String(node.text ?? '').trim()
      const isBlanked = nodeData?.hidden === true || isLearningSheetBlankDisplayText(text)
      if (!isBlanked) continue
      const answer =
        typeof nodeData?.hiddenAnswer === 'string' && nodeData.hiddenAnswer.trim()
          ? nodeData.hiddenAnswer.trim()
          : isLearningSheetBlankDisplayText(text)
            ? ''
            : text
      if (answer && !hiddenAnswersFromNodes.includes(answer)) {
        hiddenAnswersFromNodes.push(answer)
      }
    }
    const metadata = {
      ...result.metadata,
      hiddenAnswers: hiddenAnswersFromNodes,
      isLearningSheet: true,
    }
    return { ...result, metadata }
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

  const isMindMap = diagramType === 'mindmap' || diagramType === 'mind_map'
  const nodes = result.nodes.map((node, idx) => {
    if (!indicesToHide.has(idx)) {
      return node
    }
    const originalText = String(node.text || '').trim()
    const nodeData = node.data as { estimatedWidth?: number; estimatedHeight?: number } | undefined
    const layoutEstimates = isMindMap
      ? {
          estimatedWidth:
            typeof nodeData?.estimatedWidth === 'number' && nodeData.estimatedWidth > 0
              ? nodeData.estimatedWidth
              : estimateNodeWidth(originalText, node.id, node.style),
          estimatedHeight:
            typeof nodeData?.estimatedHeight === 'number' && nodeData.estimatedHeight > 0
              ? nodeData.estimatedHeight
              : measureBranchNodeHeight(originalText, node.id, node.style),
        }
      : {}
    return {
      ...node,
      text: LEARNING_SHEET_BLANK_TEXT,
      data: {
        ...node.data,
        ...layoutEstimates,
        hidden: true,
        hiddenAnswer: originalText,
      },
    }
  })

  const hiddenAnswers: string[] = []
  const orderedNodes = nodesInLearningSheetReadingOrder(
    nodes,
    result.connections,
    diagramType,
    branchNumbering
  )
  for (const node of orderedNodes) {
    const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
    const answer = typeof nodeData?.hiddenAnswer === 'string' ? nodeData.hiddenAnswer.trim() : ''
    if (answer && !hiddenAnswers.includes(answer)) {
      hiddenAnswers.push(answer)
    }
  }

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
 * Long labels wrap at the topic column; the circle grows to the wrapped block.
 *
 * @param text - Topic text
 * @returns Diameter in pixels
 */
export function getTopicCircleDiameter(text: string, secondary?: string): number {
  return (
    2 *
    computeTopicRadiusForCircleMap((text || '').trim() || ' ', {
      secondary,
    })
  )
}

/**
 * Calculate adaptive circle size based on text measurement.
 * Uses DOM-based measurement (or fallback estimation) so the diameter is
 * correct for any script: Latin, CJK, Arabic, Thai, Devanagari, etc.
 *
 * @param text - Text content of the node
 * @param isTopic - Whether this is a topic node (larger) or context node
 * @returns Diameter in pixels
 */
export const CONTEXT_MAX_TEXT_WIDTH = 140
const CONTEXT_PADDING_X = 16
const CONTEXT_PADDING_Y = 8
const CONTEXT_BORDER_SLACK = 24
const MIN_CONTEXT_DIAMETER = 70

/**
 * Estimate circle diameter for a context node, accounting for text wrapping.
 * Mirrors the brace-map pattern: fixed max text width → balanced lines →
 * compute text-block diagonal → add border/slack for final circle diameter.
 */
export function estimateContextCircleDiameter(text: string, secondary?: string): number {
  const finish = (diameter: number): number => {
    if (!secondary?.trim()) return diameter
    return growRadiusForSecondary(diameter / 2, secondary, CONTEXT_FONT_SIZE) * 2
  }
  const trimmed = (text || '').trim()
  if (!trimmed) return finish(MIN_CONTEXT_DIAMETER)

  const block = measureThinkingMapLabelBlockPx(trimmed, CONTEXT_FONT_SIZE, CONTEXT_MAX_TEXT_WIDTH)
  const contentW = block.width + CONTEXT_PADDING_X
  const contentH = block.height + CONTEXT_PADDING_Y

  const diagonal = Math.ceil(Math.sqrt(contentW * contentW + contentH * contentH))
  return finish(Math.max(MIN_CONTEXT_DIAMETER, diagonal + CONTEXT_BORDER_SLACK))
}

export function calculateAdaptiveCircleSize(text: string, isTopic: boolean = false): number {
  const MIN_TOPIC = 120

  if (!text || !text.trim()) {
    return isTopic ? MIN_TOPIC : MIN_CONTEXT_DIAMETER
  }

  if (isTopic) {
    return getTopicCircleDiameter(text)
  }

  return estimateContextCircleDiameter(text)
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
 * Optional radii from DOM (Pinia nodeDimensions) or precomputed values.
 * When omitted, calculateCircleMapLayout derives radii from topic/context text.
 */
export interface CircleMapLayoutRadiusOverrides {
  /** Topic circle radius (px), e.g. max(measured width, height) / 2 */
  topicR?: number
  /** Uniform context circle radius (px), max over context nodes */
  uniformContextR?: number
  /** Topic outline extent used for ring clearance. Defaults to topicR. */
  topicPackR?: number
  /** Context outline extent used for ring clearance. Defaults to uniformContextR. */
  contextPackR?: number
  topicSecondary?: string
  contextSecondary?: string[]
}

/**
 * Calculate circle map layout: fixed font, circles from text, ring no-overlap.
 * Center = canvas center; context nodes evenly spaced on a ring (360/n deg).
 * Order: topic first → uniformContextR from texts → childrenRadius → outer circle.
 * Shared by loadCircleMapSpec and recalculateCircleMapLayout.
 *
 * @param nodeCount - Number of context nodes
 * @param contextTexts - Array of context node texts for adaptive sizing
 * @param topicText - Topic text for radius calculation
 * @param overrides - When set (e.g. from ResizeObserver / Pinia), prefer real DOM radii over text metrics
 * @returns Layout calculation result with positions and radii
 */
export function calculateCircleMapLayout(
  nodeCount: number,
  contextTexts: string[] = [],
  topicText: string = '',
  overrides?: CircleMapLayoutRadiusOverrides | null
): CircleMapLayoutResult {
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y

  // (g) Topic: DOM overrides win; else text-adaptive radius
  const topicR =
    overrides?.topicR != null && Number.isFinite(overrides.topicR) && overrides.topicR > 0
      ? Math.max(DEFAULT_TOPIC_RADIUS, overrides.topicR)
      : Math.max(
          DEFAULT_TOPIC_RADIUS,
          computeTopicRadiusForCircleMap(topicText || ' ', {
            secondary: overrides?.topicSecondary,
          })
        )

  // (b) Uniform context R: overrides win; else min diameter per text → max → radius
  let uniformContextR: number
  if (contextTexts.length === 0) {
    uniformContextR = DEFAULT_CONTEXT_RADIUS
  } else if (
    overrides?.uniformContextR != null &&
    Number.isFinite(overrides.uniformContextR) &&
    overrides.uniformContextR > 0
  ) {
    uniformContextR = Math.max(DEFAULT_CONTEXT_RADIUS, overrides.uniformContextR)
  } else {
    let maxRadius = DEFAULT_CONTEXT_RADIUS
    for (let index = 0; index < contextTexts.length; index += 1) {
      const t = contextTexts[index]
      const d = estimateContextCircleDiameter(t || ' ', overrides?.contextSecondary?.[index])
      maxRadius = Math.max(maxRadius, d / 2)
    }
    uniformContextR = maxRadius
  }

  // (c) Ring radius: no-overlap context–context (with small gap), no-overlap context–topic, minimum.
  // All layers share the same center (centerX, centerY). Slightly lengthen childrenRadius so
  // adjacent second-layer circles have a small edge-to-edge gap.
  const topicPack = overrides?.topicPackR ?? topicR
  const contextPack = overrides?.contextPackR ?? uniformContextR
  const noOverlapContext =
    nodeCount > 0 ? (contextPack + CIRCLE_MAP_CONTEXT_GAP / 2) / Math.sin(Math.PI / nodeCount) : 0
  const noOverlapTopic = topicPack + contextPack + CIRCLE_MAP_TOPIC_CONTEXT_GAP
  const childrenRadius = Math.max(noOverlapContext, noOverlapTopic, CIRCLE_MAP_MIN_CHILDREN_RADIUS)

  // (d) Outer circle: just enclose context ring; margin avoids overlap with boundary stroke
  // Round outerCircleR to snap grid so boundary position (centerX-R, centerY-R) lands on grid.
  // This prevents Vue Flow snap-to-grid from shifting the outer circle off-center.
  const rawOuterR = childrenRadius + contextPack + CIRCLE_MAP_OUTER_MARGIN
  const outerCircleR = Math.round(rawOuterR / CIRCLE_MAP_SNAP_GRID) * CIRCLE_MAP_SNAP_GRID

  return { centerX, centerY, topicR, uniformContextR, childrenRadius, outerCircleR }
}
