import type { DiagramNode, NodeStyle } from '@/types'

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

  function applyStylePreset(preset: {
    backgroundColor: string
    textColor: string
    borderColor: string
    topicBackgroundColor: string
    topicTextColor: string
    topicBorderColor: string
  }): void {
    const nodes = data.value?.nodes
    if (!nodes) return

    const isTopic = (node: DiagramNode) => node.type === 'topic' || node.type === 'center'

    nodes.forEach((node) => {
      if (node.type === 'boundary') return

      const useTopic = isTopic(node)
      const mergedStyle: Partial<NodeStyle> = {
        ...(node.style || {}),
        backgroundColor: useTopic ? preset.topicBackgroundColor : preset.backgroundColor,
        textColor: useTopic ? preset.topicTextColor : preset.textColor,
        borderColor: useTopic ? preset.topicBorderColor : preset.borderColor,
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
    ctx.pushHistory('Apply style preset')
    emitEvent('diagram:style_changed', { preset: true })
  }

  return {
    saveNodeStyle,
    getNodeStyle,
    clearNodeStyle,
    clearAllNodeStyles,
    applyStylePreset,
  }
}
