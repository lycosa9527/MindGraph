import { nextTick } from 'vue'

import type { MindMapDiagramStyleId } from '@/config/mindMapDiagramStyles'
import {
  getMindMapDiagramStyleById,
  mindMapDiagramStyleUsesLayeredBranchColors,
  mindMapNodeShapeFromPreset,
} from '@/config/mindMapDiagramStyles'
import { syncMindMapConnectionStrokeColors } from '@/config/mindMapGeometry'
import { type MindMapThemeId, getMindMapThemeById } from '@/config/mindMapThemes'
import {
  applyRainbowMindMapColors,
  isRainbowMindMapTheme,
  mindMapLayeredBranchColorsForNode,
  mindMapLayeredCenterTopicColors,
  syncRainbowMindMapConnectionColors,
} from '@/config/mindMapVibrantThemes'
import type { DiagramNode, NodeStyle } from '@/types'
import {
  DEFAULT_MIND_MAP_NUMBERING_NESTED,
  DEFAULT_MIND_MAP_NUMBERING_PREFIX,
  type MindMapNumberingGlyphStyle,
  type MindMapNumberingNestedStyle,
  invalidateMindMapBranchNumberMapCache,
  mindMapBranchNumberMapFromData,
  resolveMindMapBranchNumberingNested,
  resolveMindMapBranchNumberingPrefix,
} from '@/utils/mindMapBranchNumbering'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'

import {
  estimateNumberedBranchWidth,
  estimateTopicNodeHeight,
  estimateTopicNodeWidth,
  measureNumberedBranchHeight,
  measureNumberedBranchUnderlineHeight,
} from '../specLoader/mindMap'
import { emitCtxEvent } from './events'
import { snapshotMindMapCanvasBucket } from './mindMapCanvasModeSwitch'
import type { DiagramContext } from './types'

export function useNodeStylesSlice(ctx: DiagramContext) {
  const { data } = ctx

  function saveNodeStyle(nodeId: string, style: Partial<NodeStyle>): void {
    if (!data.value) return

    if (!data.value._node_styles) {
      data.value._node_styles = {}
    }

    data.value._node_styles[nodeId] = {
      ...(data.value._node_styles[nodeId] || {}),
      ...style,
    }

    emitCtxEvent(ctx, 'diagram:style_changed', { nodeId, style: data.value._node_styles[nodeId] })
  }

  function getNodeStyle(nodeId: string): NodeStyle | undefined {
    return data.value?._node_styles?.[nodeId]
  }

  function clearNodeStyle(nodeId: string): void {
    if (data.value?._node_styles?.[nodeId]) {
      delete data.value._node_styles[nodeId]
      emitCtxEvent(ctx, 'diagram:style_changed', { nodeId, style: null })
    }
  }

  function clearAllNodeStyles(): void {
    if (data.value) {
      data.value._node_styles = {}
      emitCtxEvent(ctx, 'diagram:style_changed', { all: true })
    }
  }

  function isTopicNode(node: DiagramNode): boolean {
    return node.type === 'topic' || node.type === 'center'
  }

  function refreshMindMapNodeEstimatesAfterShapeChange(node: DiagramNode, nodeIndex: number): void {
    if (!data.value?.nodes) return
    const text = node.text ?? ''
    const mergedStyle = node.style

    if (node.id === 'topic') {
      data.value.nodes[nodeIndex] = {
        ...node,
        data: {
          ...node.data,
          estimatedWidth: estimateTopicNodeWidth(text, mergedStyle),
          estimatedHeight: estimateTopicNodeHeight(text, mergedStyle),
        },
      }
      ctx.mindMapTopicActualWidth.value = null
    } else {
      const numberMap = mindMapBranchNumberMapFromData(data.value)
      const prefix = numberMap.get(node.id) ?? ''
      const newShape = resolveNodeShape(mergedStyle, true)
      const freshHeight =
        newShape === 'underline'
          ? measureNumberedBranchUnderlineHeight(text, prefix, node.id, mergedStyle)
          : measureNumberedBranchHeight(text, prefix, node.id, mergedStyle)
      data.value.nodes[nodeIndex] = {
        ...node,
        data: {
          ...node.data,
          estimatedWidth: estimateNumberedBranchWidth(text, prefix, node.id, mergedStyle),
          estimatedHeight: freshHeight,
        },
      }
    }

    delete ctx.nodeDimensions.value[node.id]
    delete ctx.mindMapNodeWidths.value[node.id]
    delete ctx.mindMapNodeHeights.value[node.id]
  }

  function applyMindMapDiagramStyleShapes(diagramStyleId: MindMapDiagramStyleId): void {
    const nodes = data.value?.nodes
    if (!nodes?.length) return

    const preset = getMindMapDiagramStyleById(diagramStyleId)
    let shapeChanged = false

    nodes.forEach((node, nodeIndex) => {
      if (node.type === 'boundary') return
      const shape = mindMapNodeShapeFromPreset(node, preset)
      const currentShape = node.style?.nodeShape
      if (currentShape === shape) return

      shapeChanged = true
      const mergedStyle: Partial<NodeStyle> = {
        ...(node.style || {}),
        nodeShape: shape,
      }
      const updated = { ...node, style: mergedStyle }
      nodes[nodeIndex] = updated
      refreshMindMapNodeEstimatesAfterShapeChange(updated, nodeIndex)
    })

    if (shapeChanged) {
      // Shape regime change: leave sticky L1-Enter preserve so Y can full-restack.
      ctx.mindMapPreserveIncomingY.value = false
      ctx.mindMapPreserveIncomingYNodeId.value = null
      ctx.scheduleMindMapRecalc()
    }
  }

  function applyStylePreset(
    preset: {
      backgroundColor: string
      textColor: string
      borderColor: string
      topicBackgroundColor: string
      topicTextColor: string
      topicBorderColor: string
    },
    options?: {
      mindMapThemeId?: MindMapThemeId
      diagramStyleId?: MindMapDiagramStyleId
      skipHistory?: boolean
    }
  ): void {
    const nodes = data.value?.nodes
    if (!nodes) return

    const layeredBranches = mindMapDiagramStyleUsesLayeredBranchColors(
      options?.diagramStyleId ?? data.value?._mindmap_diagram_style
    )

    nodes.forEach((node) => {
      if (node.type === 'boundary') return

      const useTopic = isTopicNode(node)
      let branchColors: Partial<NodeStyle> | null = null
      if (!useTopic && layeredBranches) {
        branchColors = mindMapLayeredBranchColorsForNode(node.id, preset.borderColor)
      }
      const centerTopic =
        layeredBranches && useTopic ? mindMapLayeredCenterTopicColors(preset) : null

      const mergedStyle: Partial<NodeStyle> = {
        ...(node.style || {}),
        backgroundColor: useTopic
          ? (centerTopic?.topicBackgroundColor ?? preset.topicBackgroundColor)
          : (branchColors?.backgroundColor ?? preset.backgroundColor),
        textColor: useTopic
          ? (centerTopic?.topicTextColor ?? preset.topicTextColor)
          : (branchColors?.textColor ?? preset.textColor),
        borderColor: useTopic
          ? (centerTopic?.topicBorderColor ?? preset.topicBorderColor)
          : (branchColors?.borderColor ?? preset.borderColor),
      }
      const nodeIndex = nodes.findIndex((n) => n.id === node.id)
      if (nodeIndex !== -1) {
        const current = nodes[nodeIndex]
        nodes[nodeIndex] = {
          ...current,
          style: mergedStyle,
        }
      }
    })
    const diagramType = data.value?.type
    if (
      isSessionMindMapV2VisualDesignActive(ctx.mindMapCanvasMode.value) &&
      data.value?.connections &&
      (diagramType === 'mindmap' || diagramType === 'mind_map')
    ) {
      if (options?.mindMapThemeId && isRainbowMindMapTheme(options.mindMapThemeId)) {
        syncRainbowMindMapConnectionColors(data.value.connections, nodes)
      } else {
        const strokeColor = layeredBranches ? preset.borderColor : preset.topicBorderColor
        syncMindMapConnectionStrokeColors(data.value.connections, strokeColor)
      }
      if (options?.mindMapThemeId) {
        data.value._mindmap_theme = options.mindMapThemeId
      }
    }
    if (!options?.skipHistory) {
      ctx.pushHistory('Apply style preset')
    }
    emitCtxEvent(ctx, 'diagram:style_changed', { preset: true })
  }

  function applyMindMapAppearance(options: {
    themeId: MindMapThemeId
    diagramStyleId: MindMapDiagramStyleId
  }): void {
    const nodes = data.value?.nodes
    const connections = data.value?.connections
    if (!nodes?.length) return

    if (data.value) {
      data.value._mindmap_diagram_style = options.diagramStyleId
      data.value._mindmap_theme = options.themeId
    }

    if (isRainbowMindMapTheme(options.themeId)) {
      applyRainbowMindMapColors(nodes, connections ?? [])
    } else {
      const theme = getMindMapThemeById(options.themeId)
      applyStylePreset(theme, {
        mindMapThemeId: options.themeId,
        diagramStyleId: options.diagramStyleId,
        skipHistory: true,
      })
    }

    applyMindMapDiagramStyleShapes(options.diagramStyleId)
    ctx.pushHistory('Apply mind map appearance')
    emitCtxEvent(ctx, 'diagram:style_changed', {
      preset: true,
      diagramStyleId: options.diagramStyleId,
    })
  }

  function refreshMindMapNumberingEstimates(options?: { preserveIncomingY?: boolean }): void {
    const nodes = data.value?.nodes
    if (!nodes?.length) return
    invalidateMindMapBranchNumberMapCache()
    ctx.beginMindMapNumberingLayoutHold()
    const numberMap = mindMapBranchNumberMapFromData(data.value)
    const nextWidths = { ...ctx.mindMapNodeWidths.value }
    const nextHeights = { ...ctx.mindMapNodeHeights.value }
    nodes.forEach((node, nodeIndex) => {
      if (node.id === 'topic' || node.type === 'topic' || node.type === 'center') return
      const rawText = node.text ?? ''
      const prefix = numberMap.get(node.id) ?? ''
      const mergedStyle = node.style
      const newShape = resolveNodeShape(mergedStyle, true)
      const freshWidth = estimateNumberedBranchWidth(rawText, prefix, node.id, mergedStyle)
      const freshHeight =
        newShape === 'underline'
          ? measureNumberedBranchUnderlineHeight(rawText, prefix, node.id, mergedStyle)
          : measureNumberedBranchHeight(rawText, prefix, node.id, mergedStyle)
      nodes[nodeIndex] = {
        ...node,
        data: {
          ...node.data,
          estimatedWidth: freshWidth,
          estimatedHeight: freshHeight,
        },
      }
      nextWidths[node.id] = freshWidth
      nextHeights[node.id] = freshHeight
      delete ctx.nodeDimensions.value[node.id]
    })
    ctx.mindMapNodeWidths.value = nextWidths
    ctx.mindMapNodeHeights.value = nextHeights
    if (!options?.preserveIncomingY) {
      ctx.mindMapPreserveIncomingY.value = false
      ctx.mindMapPreserveIncomingYNodeId.value = null
    }
    ctx.scheduleMindMapRecalc()
    void nextTick(() => {
      ctx.scheduleMindMapRecalc()
    })
  }

  function persistNumberingCanvasBucket(): void {
    if (!data.value) return
    if (!isSessionMindMapV2VisualDesignActive(ctx.mindMapCanvasMode.value)) return
    snapshotMindMapCanvasBucket(data.value, 'v2')
  }

  function setMindMapBranchNumbering(enabled: boolean): void {
    if (!data.value) return
    data.value._mindmap_branch_numbering = enabled
    if (enabled) {
      if (!data.value._mindmap_branch_numbering_prefix) {
        data.value._mindmap_branch_numbering_prefix = DEFAULT_MIND_MAP_NUMBERING_PREFIX
      }
      if (!data.value._mindmap_branch_numbering_nested) {
        data.value._mindmap_branch_numbering_nested = DEFAULT_MIND_MAP_NUMBERING_NESTED
      }
    }
    persistNumberingCanvasBucket()
    refreshMindMapNumberingEstimates()
    ctx.pushHistory(enabled ? 'Enable branch numbering' : 'Hide branch numbering')
    emitCtxEvent(ctx, 'diagram:style_changed', { numbering: enabled })
  }

  function setMindMapBranchNumberingPrefix(style: MindMapNumberingGlyphStyle): void {
    if (!data.value) return
    const next = resolveMindMapBranchNumberingPrefix(style)
    const alreadyOn = data.value._mindmap_branch_numbering === true
    if (alreadyOn && data.value._mindmap_branch_numbering_prefix === next) return
    data.value._mindmap_branch_numbering = true
    data.value._mindmap_branch_numbering_prefix = next
    persistNumberingCanvasBucket()
    refreshMindMapNumberingEstimates()
    ctx.pushHistory('Change numbering prefix style')
    emitCtxEvent(ctx, 'diagram:style_changed', { numberingPrefix: style })
  }

  function setMindMapBranchNumberingNested(style: MindMapNumberingNestedStyle): void {
    if (!data.value) return
    const next = resolveMindMapBranchNumberingNested(style)
    const alreadyOn = data.value._mindmap_branch_numbering === true
    if (alreadyOn && data.value._mindmap_branch_numbering_nested === next) return
    data.value._mindmap_branch_numbering = true
    data.value._mindmap_branch_numbering_nested = next
    persistNumberingCanvasBucket()
    refreshMindMapNumberingEstimates()
    ctx.pushHistory('Change numbering nested style')
    emitCtxEvent(ctx, 'diagram:style_changed', { numberingNested: style })
  }

  return {
    saveNodeStyle,
    getNodeStyle,
    clearNodeStyle,
    clearAllNodeStyles,
    applyStylePreset,
    applyMindMapAppearance,
    setMindMapBranchNumbering,
    setMindMapBranchNumberingPrefix,
    setMindMapBranchNumberingNested,
    refreshMindMapNumberingEstimates,
  }
}
