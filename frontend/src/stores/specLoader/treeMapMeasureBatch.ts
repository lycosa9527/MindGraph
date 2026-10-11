/**
 * One document layout for every tree-map label width.
 * Widths that sit near the character estimate are reused by measureTextWidth.
 * A width outside that band is left uncached so the live measurer can reject it.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { secondaryFontSize } from '@/diagramBilingual/measure'
import type { DiagramNode } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  TREE_TOPIC_NODE_ID,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
} from '@/utils/treeMapIdentity'
import {
  TREE_MAP_DIMENSION_LABEL_FONT_PX,
  thinkingMapDimensionLabelDisplayText,
} from '@/utils/treeMapLabelLayout'
import {
  TREE_MAP_BRANCH_FONT_SIZE,
  TREE_MAP_LEAF_FONT_SIZE,
  type TreeMapNodeMeasureOptions,
} from '@/utils/treeMapNodeBox'

import {
  type NowrapMeasureSpec,
  measureNowrapBatch,
  plainTextNowrapKey,
  withPlainTextMeasureLookup,
} from './plainTextMeasureBatch'
import { estimateTextWidthFallbackPx } from './textMeasurementFallback'
import { TREE_MAP_TOPIC_FONT_SIZE } from './treeMapTopicLayout'

export function treeMapBranchMeasureOptions(
  node: DiagramNode,
  role: 'category' | 'leaf'
): TreeMapNodeMeasureOptions {
  const fallback = role === 'category' ? TREE_MAP_BRANCH_FONT_SIZE : TREE_MAP_LEAF_FONT_SIZE
  return {
    role,
    fontSize: typeof node.style?.fontSize === 'number' ? node.style.fontSize : fallback,
    fontWeight: (node.style?.fontWeight as string | undefined) ?? 'normal',
    fontFamily: node.style?.fontFamily,
    secondary: node.textSecondary,
    underline: node.style?.nodeShape === 'underline',
  }
}

function normalizedWeight(fontWeight: string | undefined): 'normal' | 'bold' {
  return fontWeight === 'bold' || fontWeight === '700' ? 'bold' : 'normal'
}

function pushNowrap(
  specs: NowrapMeasureSpec[],
  text: string,
  fontSize: number,
  fontWeight: string,
  fontFamily: string
): void {
  const label = text.trim() || ' '
  specs.push({
    key: plainTextNowrapKey(label, fontSize, fontWeight, fontFamily),
    text: label,
    fontSize,
    fontWeight,
    fontFamily,
  })
}

function pushBranchSpecs(
  specs: NowrapMeasureSpec[],
  text: string,
  options: TreeMapNodeMeasureOptions
): void {
  const family = options.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily
  pushNowrap(specs, text, options.fontSize, normalizedWeight(options.fontWeight), family)
  const gloss = (options.secondary ?? '').trim()
  if (!gloss) return
  pushNowrap(
    specs,
    gloss,
    secondaryFontSize(options.fontSize),
    options.fontWeight ?? 'normal',
    options.fontFamily ?? DIAGRAM_NODE_FONT_STACK
  )
}

function pushTopicSpecs(
  specs: NowrapMeasureSpec[],
  text: string,
  style: DiagramNode['style'],
  secondary: string | undefined
): void {
  const fontSize = typeof style?.fontSize === 'number' ? style.fontSize : TREE_MAP_TOPIC_FONT_SIZE
  const fontWeight = (style?.fontWeight as string | undefined) ?? 'bold'
  pushNowrap(
    specs,
    text,
    fontSize,
    normalizedWeight(fontWeight),
    style?.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily
  )
  const gloss = (secondary ?? '').trim()
  if (!gloss) return
  pushNowrap(
    specs,
    gloss,
    secondaryFontSize(fontSize),
    fontWeight,
    style?.fontFamily ?? DIAGRAM_NODE_FONT_STACK
  )
}

function pushDimensionSpecs(
  specs: NowrapMeasureSpec[],
  dimension: string,
  secondary: string | undefined
): void {
  const display = thinkingMapDimensionLabelDisplayText(dimension, 'tree')
  pushNowrap(
    specs,
    display,
    TREE_MAP_DIMENSION_LABEL_FONT_PX,
    'normal',
    MIND_MAP_GEOMETRY.fontFamily
  )
  const gloss = (secondary ?? '').trim()
  if (!gloss) return
  pushNowrap(
    specs,
    gloss,
    secondaryFontSize(TREE_MAP_DIMENSION_LABEL_FONT_PX),
    'normal',
    DIAGRAM_NODE_FONT_STACK
  )
}

export function collectTreeMapNodeMeasureSpecs(nodes: readonly DiagramNode[]): NowrapMeasureSpec[] {
  const specs: NowrapMeasureSpec[] = []
  for (const node of nodes) {
    if (node.id === TREE_TOPIC_NODE_ID) {
      pushTopicSpecs(specs, node.text ?? '', node.style, node.textSecondary)
      continue
    }
    if (node.id === 'dimension-label') {
      pushDimensionSpecs(specs, node.text ?? '', node.textSecondary)
      continue
    }
    if (isTreeMapCategoryNode(node)) {
      pushBranchSpecs(specs, node.text ?? '', treeMapBranchMeasureOptions(node, 'category'))
      continue
    }
    if (isTreeMapLeafNode(node)) {
      pushBranchSpecs(specs, node.text ?? '', treeMapBranchMeasureOptions(node, 'leaf'))
    }
  }
  return specs
}

interface SpecBranch {
  text?: string
  textSecondary?: string
  children?: SpecBranch[]
}

export function collectTreeMapSpecMeasureSpecs(spec: Record<string, unknown>): NowrapMeasureSpec[] {
  const specs: NowrapMeasureSpec[] = []
  const root = (spec.root ?? null) as SpecBranch | null
  const topicText = root?.text ?? (typeof spec.topic === 'string' ? spec.topic : '')
  if (topicText || root) {
    pushTopicSpecs(specs, topicText, undefined, root?.textSecondary)
  }
  const categories =
    root?.children ?? (Array.isArray(spec.children) ? (spec.children as SpecBranch[]) : [])
  for (const category of categories) {
    pushBranchSpecs(specs, category.text ?? '', {
      role: 'category',
      fontSize: TREE_MAP_BRANCH_FONT_SIZE,
      secondary: category.textSecondary,
    })
    for (const leaf of category.children ?? []) {
      pushBranchSpecs(specs, leaf.text ?? '', {
        role: 'leaf',
        fontSize: TREE_MAP_LEAF_FONT_SIZE,
        secondary: leaf.textSecondary,
      })
    }
  }
  if (spec.dimension !== undefined) {
    const secondary =
      typeof spec.dimensionSecondary === 'string' ? spec.dimensionSecondary : undefined
    pushDimensionSpecs(specs, typeof spec.dimension === 'string' ? spec.dimension : '', secondary)
  }
  return specs
}

function uniqueSpecs(specs: readonly NowrapMeasureSpec[]): NowrapMeasureSpec[] {
  const seen = new Set<string>()
  const unique: NowrapMeasureSpec[] = []
  for (const spec of specs) {
    if (seen.has(spec.key)) continue
    seen.add(spec.key)
    unique.push(spec)
  }
  return unique
}

function acceptedWidths(specs: readonly NowrapMeasureSpec[]): Map<string, number> {
  const measured = measureNowrapBatch(specs)
  const accepted = new Map<string, number>()
  for (const spec of specs) {
    const width = measured.get(spec.key)
    if (width == null || width <= 0) continue
    const fallback = estimateTextWidthFallbackPx(spec.text, spec.fontSize, {
      isTopic: spec.fontWeight === 'bold',
    })
    if (width >= fallback * 0.5 && width <= fallback * 1.85) {
      accepted.set(spec.key, width)
    }
  }
  return accepted
}

export function withTreeMapTextMeasureCache<T>(
  specs: readonly NowrapMeasureSpec[],
  run: () => T
): T {
  const unique = uniqueSpecs(specs)
  if (unique.length === 0) return run()
  return withPlainTextMeasureLookup(acceptedWidths(unique), new Map(), run)
}
