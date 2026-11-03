/**
 * Bridge Map Loader
 * Pairs run left to right. After five pairs the next one sits under the
 * last and the row runs back, so the bridge can U-turn.
 */
import { DEFAULT_CENTER_Y, DEFAULT_PADDING } from '@/composables/diagrams/layoutConfig'
import {
  mirrorRecordList,
  mirrorString,
  mirrorStringList,
  readSecondaryMirror,
} from '@/diagramBilingual/mirror'
import type { Connection, DiagramNode } from '@/types'
import {
  BRIDGE_DIMENSION_LABEL_ID,
  BRIDGE_MAP_UID_DATA_KEY,
  findBridgePairSide,
  isBridgeMapPairNode,
  readBridgePairIndex,
  stampBridgePairData,
  takeBridgeMapStableId,
} from '@/utils/bridgeMapIdentity'
import {
  BRIDGE_LABEL_TO_PAIR_GAP,
  measureBridgeDimensionLabelBox,
  resolveBridgePairOrigin,
} from '@/utils/bridgeMapLabelLayout'
import { BRIDGE_PAIR_FONT, bridgePairContentBox } from '@/utils/bridgeMapPairBox'
import { placeBridgeSerpentine } from '@/utils/bridgeMapSerpentine'

import { learningSheetLayoutSecondary } from './mindMapLearningSheet'
import type { SpecLoaderResult } from './types'

const BRIDGE_VERTICAL_GAP = 5
const BRIDGE_SHAPED_VERTICAL_GAP = 16
const BRIDGE_GAP_BETWEEN_PAIRS = 50

function pairFontSize(node: DiagramNode | undefined): number {
  const stored = node?.style?.fontSize
  const parsed = typeof stored === 'number' ? stored : Number.parseFloat(String(stored ?? ''))
  if (Number.isFinite(parsed) && parsed > 0) return parsed
  return BRIDGE_PAIR_FONT
}

/** Section box. A measured browser box wins. Otherwise the wrapped text box. */
function pairBox(
  node: DiagramNode | undefined,
  measured: { width: number; height: number } | undefined
): { width: number; height: number } {
  const gloss = node ? learningSheetLayoutSecondary(node) : ''
  const estimated = bridgePairContentBox(node?.text ?? '', gloss, pairFontSize(node))
  return {
    width: measured?.width != null && measured.width > 0 ? measured.width : estimated.width,
    height: measured?.height != null && measured.height > 0 ? measured.height : estimated.height,
  }
}

type BridgeAnalogy = {
  left: string
  right: string
  leftSecondary: string
  rightSecondary: string
}

function glossText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function pairSideGloss(
  pair: Record<string, unknown>,
  mirrorPair: Record<string, unknown> | undefined,
  side: 'left' | 'right'
): string {
  return (
    glossText(pair[`${side}_secondary`]) ||
    glossText(pair[`${side}Secondary`]) ||
    glossText(mirrorPair?.[side])
  )
}

function readBridgeAnalogies(spec: Record<string, unknown>): BridgeAnalogy[] {
  const raw = Array.isArray(spec.analogies)
    ? spec.analogies
    : Array.isArray(spec.pairs)
      ? spec.pairs
      : []
  const mirrorPairs = mirrorRecordList(readSecondaryMirror(spec), 'analogies')
  return raw.map((item, index) => {
    const pair = item && typeof item === 'object' ? (item as Record<string, unknown>) : {}
    const mirrorPair = mirrorPairs[index]
    return {
      left: glossText(pair.left) || glossText(pair.top),
      right: glossText(pair.right) || glossText(pair.bottom),
      leftSecondary: pairSideGloss(pair, mirrorPair, 'left'),
      rightSecondary: pairSideGloss(pair, mirrorPair, 'right'),
    }
  })
}

function readDimensionSecondary(spec: Record<string, unknown>): string {
  const mirror = readSecondaryMirror(spec)
  const relationship =
    glossText(spec.dimension_secondary) || mirrorString(mirror, 'dimension') || ''
  if (glossText(spec.dimension)) return relationship
  // The label shows the bridge word only when the relationship is blank.
  return relationship || mirrorString(mirror, 'relating_factor') || ''
}

function readAlternativeSecondary(spec: Record<string, unknown>): string[] {
  if (Array.isArray(spec.alternative_dimensions_secondary)) {
    const direct = spec.alternative_dimensions_secondary.map((item) => glossText(item))
    if (direct.some((item) => item.length > 0)) return direct
  }
  return mirrorStringList(readSecondaryMirror(spec), 'alternative_dimensions')
}

/** 5px while pair words stay bare text. A chosen shape opens the gap around the bridge line. */
export function bridgePairVerticalGap(nodes: DiagramNode[]): number {
  const shaped = nodes.some((node) => isBridgeMapPairNode(node) && Boolean(node.style?.nodeShape))
  return shaped ? BRIDGE_SHAPED_VERTICAL_GAP : BRIDGE_VERTICAL_GAP
}

/**
 * Post-render layout correction for bridge maps.
 * Uses actual DOM-measured heights from Pinia so each pair node sits the
 * correct distance above/below the bridge centre line.
 */
export function recalculateBridgeMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) return nodes

  const centerY = DEFAULT_CENTER_Y

  const boxFor = (id: string): { width: number; height: number } =>
    pairBox(
      nodes.find((item) => item.id === id),
      nodeDimensions[id]
    )

  const pairNodes = nodes.filter((n) => isBridgeMapPairNode(n))
  const otherNodes = nodes.filter((n) => !isBridgeMapPairNode(n))

  if (pairNodes.length === 0) return nodes

  const maxPairIndex = pairNodes.reduce((max, n) => {
    const idx = readBridgePairIndex(n)
    return idx > max ? idx : max
  }, -1)

  const origin = resolveBridgePairOrigin(nodes, nodeDimensions, centerY)
  const result = otherNodes.map((n) => {
    if (n.id === BRIDGE_DIMENSION_LABEL_ID && origin.label) {
      return { ...n, position: { x: origin.label.x, y: origin.label.y } }
    }
    return { ...n }
  })

  const verticalGap = bridgePairVerticalGap(pairNodes)
  const sequence: Array<{
    left: DiagramNode
    right: DiagramNode
    upperWidth: number
    upperHeight: number
    lowerWidth: number
    lowerHeight: number
  }> = []
  for (let i = 0; i <= maxPairIndex; i += 1) {
    const leftNode = findBridgePairSide(pairNodes, i, 'left')
    const rightNode = findBridgePairSide(pairNodes, i, 'right')
    if (!leftNode || !rightNode) continue
    const leftBox = boxFor(leftNode.id)
    const rightBox = boxFor(rightNode.id)
    sequence.push({
      left: leftNode,
      right: rightNode,
      upperWidth: leftBox.width,
      upperHeight: leftBox.height,
      lowerWidth: rightBox.width,
      lowerHeight: rightBox.height,
    })
  }
  const placed = placeBridgeSerpentine(
    sequence,
    origin.pairStartX,
    centerY,
    verticalGap,
    BRIDGE_GAP_BETWEEN_PAIRS
  )
  sequence.forEach((pair, index) => {
    const place = placed[index]
    result.push({
      ...pair.left,
      position: { x: place.x, y: place.upperY },
    })
    result.push({
      ...pair.right,
      position: { x: place.x, y: place.lowerY },
    })
  })

  return result
}

/**
 * Load bridge map spec into diagram nodes and connections
 *
 * @param spec - Bridge map spec with analogies or pairs
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadBridgeMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  // Bridge maps use analogies array with left/right properties.
  // Old specs used pairs with top/bottom. Glosses come from the pair or the secondary mirror.
  const analogies = readBridgeAnalogies(spec)

  const centerY = DEFAULT_CENTER_Y
  const verticalGap = bridgePairVerticalGap([])

  // Use dimension if available, otherwise fall back to relating_factor.
  // Always create the label — LabelNode shows placeholder text when empty.
  const dimension =
    (spec.dimension as string | undefined)?.trim() ||
    (spec.relating_factor as string | undefined)?.trim() ||
    ''
  const dimensionSecondary = readDimensionSecondary(spec)
  // Pairs start after the wrapped dimension label so a long value cannot cover the first pair.
  const labelBox = measureBridgeDimensionLabelBox(dimension, dimensionSecondary)
  const startX = DEFAULT_PADDING + labelBox.width + BRIDGE_LABEL_TO_PAIR_GAP

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []
  const claimedIds = new Set<string>([BRIDGE_DIMENSION_LABEL_ID])

  const placed = placeBridgeSerpentine(
    analogies.map((analogy) => {
      const leftBox = bridgePairContentBox(analogy.left, analogy.leftSecondary)
      const rightBox = bridgePairContentBox(analogy.right, analogy.rightSecondary)
      return {
        upperWidth: leftBox.width,
        upperHeight: leftBox.height,
        lowerWidth: rightBox.width,
        lowerHeight: rightBox.height,
      }
    }),
    startX,
    centerY,
    verticalGap,
    BRIDGE_GAP_BETWEEN_PAIRS
  )

  analogies.forEach((analogy, index) => {
    const place = placed[index]
    const leftId = takeBridgeMapStableId(claimedIds)
    const rightId = takeBridgeMapStableId(claimedIds)

    nodes.push({
      id: leftId,
      text: analogy.left,
      ...(analogy.leftSecondary ? { textSecondary: analogy.leftSecondary } : {}),
      type: 'branch',
      position: { x: place.x, y: place.upperY },
      data: stampBridgePairData(index, 'left', { [BRIDGE_MAP_UID_DATA_KEY]: leftId }),
    })

    nodes.push({
      id: rightId,
      text: analogy.right,
      ...(analogy.rightSecondary ? { textSecondary: analogy.rightSecondary } : {}),
      type: 'branch',
      position: { x: place.x, y: place.lowerY },
      data: stampBridgePairData(index, 'right', { [BRIDGE_MAP_UID_DATA_KEY]: rightId }),
    })
  })

  // Add dimension label node on the left side
  const labelY = centerY - labelBox.height / 2
  const labelX = DEFAULT_PADDING

  nodes.push({
    id: BRIDGE_DIMENSION_LABEL_ID,
    text: dimension,
    ...(dimensionSecondary ? { textSecondary: dimensionSecondary } : {}),
    type: 'label',
    position: { x: labelX, y: labelY },
    data: {
      diagramType: 'bridge_map',
      isDimensionLabel: true,
    },
  })

  // Store dimension, relating_factor, and alternative_dimensions in metadata for BridgeOverlay
  const metadata: Record<string, unknown> = {}
  if (spec.dimension) {
    metadata.dimension = spec.dimension
  }
  if (spec.relating_factor) {
    metadata.relating_factor = spec.relating_factor
  }
  if (spec.alternative_dimensions) {
    metadata.alternative_dimensions = spec.alternative_dimensions
  }
  const alternativeSecondary = readAlternativeSecondary(spec)
  if (alternativeSecondary.some((item) => item.length > 0)) {
    metadata.alternative_dimensions_secondary = alternativeSecondary
  }

  return { nodes, connections, metadata }
}
