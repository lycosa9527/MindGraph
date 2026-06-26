import type { MindMapDiagramStyleId } from '@/config/mindMapDiagramStyles'
import {
  getMindMapDiagramStyleById,
  mindMapDiagramStyleUsesLayeredBranchColors,
  mindMapNodeShapeFromPreset,
} from '@/config/mindMapDiagramStyles'
import {
  applyRainbowMindMapColors,
  isRainbowMindMapTheme,
  mindMapLayeredBranchColorsForNode,
  mindMapLayeredCenterTopicColors,
  syncRainbowMindMapConnectionColors,
} from '@/config/mindMapVibrantThemes'
import { syncMindMapConnectionStrokeColors } from '@/config/mindMapGeometry'
import {
  getMindMapThemeById,
  type MindMapThemeId,
} from '@/config/mindMapThemes'
import type { DiagramNode, NodeStyle } from '@/types'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'
import { readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'

import {
  estimateNodeWidth as estimateMindMapBranchWidth,
  estimateTopicNodeHeight,
  estimateTopicNodeWidth,
  measureBranchNodeHeight as measureMindMapBranchHeight,
  measureBranchNodeUnderlineHeight as measureMindMapBranchUnderlineHeight,
} from '../specLoader/mindMap'
import { emitEvent } from './events'
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

    emitEvent('diagram:style_changed', { nodeId, style: data.value._node_styles[nodeId] })
  }

  function getNodeStyle(nodeId: string): NodeStyle | undefined {
    return data.value?._node_styles?.[nodeId]
  }

  function clearNodeStyle(nodeId: string): void {
    if (data.value?._node_styles?.[nodeId]) {
      delete data.value._node_styles[nodeId]
      emitEvent('diagram:style_changed', { nodeId, style: null })
    }
  }

  function clearAllNodeStyles(): void {
    if (data.value) {
      data.value._node_styles = {}
      emitEvent('diagram:style_changed', { all: true })
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
      const newShape = resolveNodeShape(mergedStyle, true)
      const freshHeight =
        newShape === 'underline'
          ? measureMindMapBranchUnderlineHeight(text, node.id, mergedStyle)
          : measureMindMapBranchHeight(text, node.id, mergedStyle)
      data.value.nodes[nodeIndex] = {
        ...node,
        data: {
          ...node.data,
          estimatedWidth: estimateMindMapBranchWidth(text, node.id, mergedStyle),
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
      const centerTopic = layeredBranches && useTopic ? mindMapLayeredCenterTopicColors(preset) : null

      const mergedStyle: Partial<NodeStyle> = {
        ...(node.style || {}),
        backgroundColor: useTopic
          ? centerTopic?.topicBackgroundColor ?? preset.topicBackgroundColor
          : branchColors?.backgroundColor ?? preset.backgroundColor,
        textColor: useTopic
          ? centerTopic?.topicTextColor ?? preset.topicTextColor
          : branchColors?.textColor ?? preset.textColor,
        borderColor: useTopic
          ? centerTopic?.topicBorderColor ?? preset.topicBorderColor
          : branchColors?.borderColor ?? preset.borderColor,
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
      readMindMapV2VisualDesignActive() &&
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
    emitEvent('diagram:style_changed', { preset: true })
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
    emitEvent('diagram:style_changed', { preset: true, diagramStyleId: options.diagramStyleId })
  }

  return {
    saveNodeStyle,
    getNodeStyle,
    clearNodeStyle,
    clearAllNodeStyles,
    applyStylePreset,
    applyMindMapAppearance,
  }
}
