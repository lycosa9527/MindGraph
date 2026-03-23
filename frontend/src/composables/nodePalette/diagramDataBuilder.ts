/**
 * Node Palette diagram data builder - builds diagram_data for API from current diagram
 */
import { isPlaceholderText } from '@/composables/useAutoComplete'
import { stripConceptMapFocusQuestionPrefix } from '@/stores/diagram/diagramDefaultLabels'
import type { Connection, DiagramType } from '@/types'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

import { LEARNING_SHEET_PLACEHOLDER } from './constants'

/** Optional context for concept_map (focus question + root concept for palette prompts) */
export type BuildDiagramDataOptions = {
  connections?: Connection[] | undefined
  /** When set (e.g. from diagram spec), overrides topic-node parsing for focus body */
  focusQuestionFromSpec?: string
}

function normalizeDiagramType(dt: DiagramType | null): DiagramType | null {
  return dt === 'mind_map' ? 'mindmap' : dt
}

/**
 * Build diagram_data for Node Palette API from current diagram
 */
export function buildDiagramData(
  diagramType: DiagramType | null,
  nodes: Array<{ id: string; text: string; type?: string }>,
  options?: BuildDiagramDataOptions
): Record<string, unknown> {
  const dt = normalizeDiagramType(diagramType)
  if (!dt || !nodes.length) {
    return { topic: '' }
  }

  const topicNode = nodes.find((n) => n.type === 'topic' || n.type === 'center' || n.id === 'root')
  const topicText = topicNode?.text?.trim() ?? ''

  switch (dt) {
    case 'circle_map': {
      const contextNodes = nodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'context') && n.id.startsWith('context-')
      )
      return {
        topic: topicText,
        center: { text: topicText },
        context: contextNodes.map((n) => n.text),
      }
    }
    case 'bubble_map': {
      const attrNodes = nodes.filter((n) => n.type === 'bubble' || n.type === 'attribute')
      return {
        topic: topicText,
        center: { text: topicText },
        attributes: attrNodes.map((n) => ({ text: n.text })),
      }
    }
    case 'flow_map': {
      const flowTopic = nodes.find((n) => n.id === 'flow-topic')
      return {
        title: flowTopic?.text ?? topicText,
      }
    }
    case 'multi_flow_map': {
      const eventNode = nodes.find((n) => n.id === 'event')
      return {
        event: eventNode?.text ?? topicText,
      }
    }
    case 'double_bubble_map': {
      const leftNode = nodes.find((n) => n.id === 'left-topic')
      const rightNode = nodes.find((n) => n.id === 'right-topic')
      return {
        left: leftNode?.text ?? '',
        right: rightNode?.text ?? '',
      }
    }
    case 'brace_map': {
      const wholeNode = nodes.find(
        (n) =>
          n.id === 'brace-whole' || n.id === 'brace-0-0' || n.id === 'whole' || n.type === 'whole'
      )
      const dimNode = nodes.find((n) => n.id === 'dimension-label')
      return {
        whole: wholeNode?.text ?? topicText,
        dimension: dimNode?.text ?? '',
      }
    }
    case 'bridge_map': {
      const dimNode = nodes.find(
        (n) => n.id === 'dimension-label' || n.id === 'dimension' || n.type === 'dimension'
      )
      const pairIndices = new Set(
        nodes
          .filter((n) => /^pair-\d+-left$/.test(n.id ?? ''))
          .map((n) => parseInt((n.id ?? '').replace('pair-', '').replace('-left', ''), 10))
      )
      const analogies: Array<{ left: string; right: string }> = []
      for (const idx of [...pairIndices].sort((a, b) => a - b)) {
        const leftNode = nodes.find((n) => n.id === `pair-${idx}-left`)
        const rightNode = nodes.find((n) => n.id === `pair-${idx}-right`)
        const left = (leftNode?.text ?? '').trim()
        const right = (rightNode?.text ?? '').trim()
        if (
          left &&
          right &&
          !isPlaceholderText(left) &&
          !isPlaceholderText(right) &&
          left !== LEARNING_SHEET_PLACEHOLDER &&
          right !== LEARNING_SHEET_PLACEHOLDER
        ) {
          analogies.push({ left, right })
        }
      }
      return {
        dimension: dimNode?.text ?? '',
        analogies,
      }
    }
    case 'tree_map': {
      const dimNode = nodes.find((n) => n.id === 'dimension-label')
      return {
        topic: topicText,
        center: { text: topicText },
        dimension: dimNode?.text ?? '',
      }
    }
    case 'concept_map': {
      const topicNode = nodes.find((n) => n.id === 'topic' || n.type === 'topic')
      let focusQuestion = (options?.focusQuestionFromSpec ?? '').trim()
      if (!focusQuestion && topicNode?.text) {
        const raw = topicNode.text.trim()
        focusQuestion = stripConceptMapFocusQuestionPrefix(raw)
      }
      const rootId = getTopicRootConceptTargetId(options?.connections)
      const rootNode = rootId ? nodes.find((n) => n.id === rootId) : undefined
      const rootConcept = (rootNode?.text ?? '').trim()
      return {
        topic: topicText,
        center: { text: topicText },
        focus_question: focusQuestion,
        root_concept: rootConcept,
      }
    }
    case 'mindmap':
    default:
      return {
        topic: topicText,
        center: { text: topicText },
      }
  }
}
