/**
 * Canvas MindMate diagram brief.
 * One sentence on what the diagram is for, then the topic and its real structure.
 */
import type { Connection, DiagramNode, DiagramType } from '@/types'
import {
  BRACE_DIMENSION_LABEL_ID,
  findBraceMapWholeId,
  isBraceMapWholeNode,
} from '@/utils/braceMapIdentity'
import {
  BRIDGE_DIMENSION_LABEL_ID,
  isBridgeMapPairNode,
  readBridgePairIndex,
  readBridgePairSide,
} from '@/utils/bridgeMapIdentity'
import {
  BUBBLE_TOPIC_NODE_ID,
  isBubbleMapAttributeNode,
  readBubbleGroupIndex,
} from '@/utils/bubbleMapIdentity'
import {
  CIRCLE_TOPIC_NODE_ID,
  isCircleMapContextNode,
  readCircleContextIndex,
} from '@/utils/circleMapIdentity'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import {
  FLOW_TOPIC_NODE_ID,
  isFlowMapStepNode,
  isFlowMapSubstepNode,
  readFlowParentStepId,
  readFlowStepIndex,
  readFlowSubstepIndex,
} from '@/utils/flowMapIdentity'
import { isMindMapTreeConnection } from '@/utils/mindMapLocation'
import { type MindMapOutlineNode, buildMindMapOutlineTree } from '@/utils/mindMapOutlineTree'
import {
  MULTI_FLOW_EVENT_NODE_ID,
  readMultiFlowIndex,
  readMultiFlowRole,
} from '@/utils/multiFlowMapIdentity'
import {
  TREE_DIMENSION_LABEL_ID,
  TREE_TOPIC_NODE_ID,
  treeMapColumnsOf,
} from '@/utils/treeMapIdentity'

export const MINDMATE_DIAGRAM_CONTEXT_MARKER = '[MindMate diagram]'

/** Dify assistant message cap (`AIAssistantRequest.message`). */
export const MINDMATE_ASSISTANT_MESSAGE_MAX = 5000

export type DiagramBriefTranslate = (key: string, params?: Record<string, unknown>) => string

const PURPOSE_TYPES = new Set([
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'concept_map',
  'mindmap',
])

function say(t: DiagramBriefTranslate, key: string, params?: Record<string, unknown>): string {
  return t(key, params).trim()
}

function joiner(t: DiagramBriefTranslate): string {
  return say(t, 'mindmate.diagramContext.childJoiner')
}

function wrap(t: DiagramBriefTranslate, text: string, children: string): string {
  return say(t, 'mindmate.diagramContext.childWrap', { text, children })
}

function displayText(node: DiagramNode | undefined, t: DiagramBriefTranslate): string {
  const primary = String(node?.text ?? '').trim()
  if (!primary) return ''
  const secondary = String(node?.textSecondary ?? '').trim()
  if (!secondary || secondary === primary) return primary
  return wrap(t, primary, secondary)
}

function byIndex(read: (node: DiagramNode) => number) {
  return (left: DiagramNode, right: DiagramNode): number => {
    const delta = read(left) - read(right)
    if (delta !== 0) return delta
    return left.id.localeCompare(right.id)
  }
}

function findNode(nodes: DiagramNode[], id: string): DiagramNode | undefined {
  return nodes.find((node) => node.id === id)
}

function purposeLine(diagramType: string, t: DiagramBriefTranslate): string {
  const normalized = diagramType === 'mind_map' ? 'mindmap' : diagramType
  const key = PURPOSE_TYPES.has(normalized)
    ? `mindmate.diagramContext.purpose.${normalized}`
    : 'mindmate.diagramContext.purpose.generic'
  return say(t, key)
}

function finish(diagramType: string, t: DiagramBriefTranslate, lines: string[]): string {
  const body = lines.map((line) => line.trim()).filter((line) => line.length > 0)
  return [purposeLine(diagramType, t), ...body].join('\n')
}

function itemsLine(
  t: DiagramBriefTranslate,
  key: string,
  items: string[],
  extra?: Record<string, unknown>
): string {
  const joined = items.filter((item) => item.length > 0).join(joiner(t))
  if (!joined) return ''
  return say(t, key, { ...extra, items: joined })
}

function circleBrief(nodes: DiagramNode[], t: DiagramBriefTranslate): string[] {
  const topic = displayText(findNode(nodes, CIRCLE_TOPIC_NODE_ID), t)
  const contexts = nodes
    .filter((node) => isCircleMapContextNode(node))
    .slice()
    .sort(byIndex(readCircleContextIndex))
    .map((node) => displayText(node, t))
  return [
    topic ? say(t, 'mindmate.diagramContext.field.center', { text: topic }) : '',
    itemsLine(t, 'mindmate.diagramContext.field.contexts', contexts),
  ]
}

function bubbleBrief(nodes: DiagramNode[], t: DiagramBriefTranslate): string[] {
  const topicNode =
    findNode(nodes, BUBBLE_TOPIC_NODE_ID) ??
    nodes.find((node) => node.type === 'topic' || node.type === 'center')
  const topic = displayText(topicNode, t)
  const attributes = nodes
    .filter((node) => isBubbleMapAttributeNode(node))
    .slice()
    .sort(byIndex(readBubbleGroupIndex))
    .map((node) => displayText(node, t))
  return [
    topic ? say(t, 'mindmate.diagramContext.field.topic', { text: topic }) : '',
    itemsLine(t, 'mindmate.diagramContext.field.attributes', attributes),
  ]
}

function doubleBubbleBrief(nodes: DiagramNode[], t: DiagramBriefTranslate): string[] {
  const left = displayText(findNode(nodes, DOUBLE_BUBBLE_LEFT_TOPIC_ID), t)
  const right = displayText(findNode(nodes, DOUBLE_BUBBLE_RIGHT_TOPIC_ID), t)
  const pick = (role: 'similarity' | 'leftDiff' | 'rightDiff') =>
    nodes
      .filter((node) => readDoubleBubbleRole(node) === role)
      .slice()
      .sort(byIndex(readDoubleBubbleIndex))
      .map((node) => displayText(node, t))
  const lines: string[] = []
  if (left && right) {
    lines.push(say(t, 'mindmate.diagramContext.field.compare', { left, right }))
  } else if (left || right) {
    lines.push(say(t, 'mindmate.diagramContext.field.topic', { text: left || right }))
  }
  lines.push(itemsLine(t, 'mindmate.diagramContext.field.similarities', pick('similarity')))
  if (left) {
    lines.push(
      itemsLine(t, 'mindmate.diagramContext.field.diffs', pick('leftDiff'), { name: left })
    )
  }
  if (right) {
    lines.push(
      itemsLine(t, 'mindmate.diagramContext.field.diffs', pick('rightDiff'), { name: right })
    )
  }
  return lines
}

function treeBrief(nodes: DiagramNode[], t: DiagramBriefTranslate): string[] {
  const topic = displayText(
    findNode(nodes, TREE_TOPIC_NODE_ID) ?? nodes.find((node) => node.type === 'topic'),
    t
  )
  const dimension = displayText(findNode(nodes, TREE_DIMENSION_LABEL_ID), t)
  const categories = treeMapColumnsOf(nodes).map((column, index) => {
    const name = displayText(column.category, t)
    const leaves = column.leaves
      .map((leaf) => displayText(leaf, t))
      .filter(Boolean)
      .join(joiner(t))
    const text = name && leaves ? wrap(t, name, leaves) : name || leaves
    if (!text) return ''
    return say(t, 'mindmate.diagramContext.field.category', { n: index + 1, text })
  })
  return [
    topic ? say(t, 'mindmate.diagramContext.field.topic', { text: topic }) : '',
    dimension ? say(t, 'mindmate.diagramContext.field.dimension', { text: dimension }) : '',
    ...categories,
  ]
}

function braceLabel(
  node: DiagramNode,
  connections: Connection[],
  byId: Map<string, DiagramNode>,
  t: DiagramBriefTranslate,
  seen: Set<string>
): string {
  if (seen.has(node.id)) return ''
  seen.add(node.id)
  const children = connections
    .filter((connection) => connection.source === node.id)
    .map((connection) => byId.get(connection.target))
    .filter((child): child is DiagramNode => child != null && child.id !== BRACE_DIMENSION_LABEL_ID)
  const nested = children
    .map((child) => braceLabel(child, connections, byId, t, seen))
    .filter(Boolean)
  const name = displayText(node, t)
  if (!name) return nested.join(joiner(t))
  if (nested.length === 0) return name
  return wrap(t, name, nested.join(joiner(t)))
}

function braceBrief(
  nodes: DiagramNode[],
  connections: Connection[],
  t: DiagramBriefTranslate
): string[] {
  const wholeId = findBraceMapWholeId(nodes, connections)
  const whole =
    (wholeId ? findNode(nodes, wholeId) : undefined) ??
    nodes.find((node) => isBraceMapWholeNode(node))
  const dimension = displayText(findNode(nodes, BRACE_DIMENSION_LABEL_ID), t)
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const parts = whole
    ? connections
        .filter((connection) => connection.source === whole.id)
        .map((connection) => byId.get(connection.target))
        .filter((node): node is DiagramNode => node != null && node.id !== BRACE_DIMENSION_LABEL_ID)
        .map((node, index) => {
          const text = braceLabel(node, connections, byId, t, new Set(whole ? [whole.id] : []))
          return text ? say(t, 'mindmate.diagramContext.field.part', { n: index + 1, text }) : ''
        })
    : []
  const wholeText = displayText(whole, t)
  return [
    wholeText ? say(t, 'mindmate.diagramContext.field.whole', { text: wholeText }) : '',
    dimension ? say(t, 'mindmate.diagramContext.field.braceDimension', { text: dimension }) : '',
    ...parts,
  ]
}

function flowBrief(nodes: DiagramNode[], t: DiagramBriefTranslate): string[] {
  const topic = displayText(findNode(nodes, FLOW_TOPIC_NODE_ID), t)
  const steps = nodes
    .filter((node) => isFlowMapStepNode(node))
    .slice()
    .sort(byIndex(readFlowStepIndex))
  const lines = steps.map((step, index) => {
    const subs = nodes
      .filter((node) => {
        if (!isFlowMapSubstepNode(node)) return false
        const parent = readFlowParentStepId(node)
        if (parent) return parent === step.id
        return readFlowStepIndex(node) === readFlowStepIndex(step)
      })
      .slice()
      .sort(byIndex(readFlowSubstepIndex))
      .map((node) => displayText(node, t))
      .filter(Boolean)
    const name = displayText(step, t)
    const nested = subs.join(joiner(t))
    const text = name && nested ? wrap(t, name, nested) : name || nested
    if (!text) return ''
    return say(t, 'mindmate.diagramContext.field.step', { n: index + 1, text })
  })
  return [topic ? say(t, 'mindmate.diagramContext.field.process', { text: topic }) : '', ...lines]
}

function multiFlowBrief(nodes: DiagramNode[], t: DiagramBriefTranslate): string[] {
  const event = displayText(findNode(nodes, MULTI_FLOW_EVENT_NODE_ID), t)
  const pick = (role: 'cause' | 'effect') =>
    nodes
      .filter((node) => readMultiFlowRole(node) === role)
      .slice()
      .sort(byIndex(readMultiFlowIndex))
      .map((node) => displayText(node, t))
  return [
    event ? say(t, 'mindmate.diagramContext.field.event', { text: event }) : '',
    itemsLine(t, 'mindmate.diagramContext.field.causes', pick('cause')),
    itemsLine(t, 'mindmate.diagramContext.field.effects', pick('effect')),
  ]
}

function bridgeBrief(nodes: DiagramNode[], t: DiagramBriefTranslate): string[] {
  const relation = displayText(findNode(nodes, BRIDGE_DIMENSION_LABEL_ID), t)
  const indexes = [
    ...new Set(
      nodes.filter((node) => isBridgeMapPairNode(node)).map((node) => readBridgePairIndex(node))
    ),
  ]
    .filter((index) => index >= 0)
    .sort((left, right) => left - right)
  const analogies = indexes.map((index, order) => {
    const left = displayText(
      nodes.find(
        (node) =>
          isBridgeMapPairNode(node) &&
          readBridgePairIndex(node) === index &&
          readBridgePairSide(node) === 'left'
      ),
      t
    )
    const right = displayText(
      nodes.find(
        (node) =>
          isBridgeMapPairNode(node) &&
          readBridgePairIndex(node) === index &&
          readBridgePairSide(node) === 'right'
      ),
      t
    )
    if (!left && !right) return ''
    return say(t, 'mindmate.diagramContext.field.analogy', {
      n: order + 1,
      left,
      right,
    })
  })
  return [
    relation ? say(t, 'mindmate.diagramContext.field.bridgeRelation', { text: relation }) : '',
    ...analogies,
  ]
}

function conceptBrief(
  nodes: DiagramNode[],
  connections: Connection[],
  focusQuestion: string | undefined,
  t: DiagramBriefTranslate
): string[] {
  const topicNode = findNode(nodes, 'topic') ?? nodes.find((node) => node.type === 'topic')
  const focus = (focusQuestion ?? '').trim() || displayText(topicNode, t)
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const links: string[] = []
  const seenLinks = new Set<string>()
  for (const connection of connections) {
    const from = displayText(byId.get(connection.source), t)
    const to = displayText(byId.get(connection.target), t)
    if (!from || !to) continue
    const label = String(connection.label ?? '').trim()
    const line = label
      ? say(t, 'mindmate.diagramContext.field.link', { from, label, to })
      : say(t, 'mindmate.diagramContext.field.linkPlain', { from, to })
    if (!line || seenLinks.has(line)) continue
    seenLinks.add(line)
    links.push(line)
  }
  return [
    focus ? say(t, 'mindmate.diagramContext.field.focus', { text: focus }) : '',
    links.length ? say(t, 'mindmate.diagramContext.field.linksHeading') : '',
    ...links,
  ]
}

function mindMapLabel(
  node: MindMapOutlineNode,
  byId: Map<string, DiagramNode>,
  t: DiagramBriefTranslate
): string {
  const name = displayText(byId.get(node.id), t)
  const nested = node.children
    .map((child) => mindMapLabel(child, byId, t))
    .filter((label) => label.length > 0)
  if (!name) return nested.join(joiner(t))
  if (nested.length === 0) return name
  return wrap(t, name, nested.join(joiner(t)))
}

function mindMapBrief(
  nodes: DiagramNode[],
  connections: Connection[],
  t: DiagramBriefTranslate
): string[] {
  const treeConnections = connections.filter((connection) => isMindMapTreeConnection(connection))
  const outline = buildMindMapOutlineTree(nodes, treeConnections)
  const root = outline[0]
  if (!root) return []
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const topic = displayText(byId.get(root.id), t)
  const branches = root.children.map((child, index) => {
    const text = mindMapLabel(child, byId, t)
    return text ? say(t, 'mindmate.diagramContext.field.branch', { n: index + 1, text }) : ''
  })
  return [topic ? say(t, 'mindmate.diagramContext.field.topic', { text: topic }) : '', ...branches]
}

/** Purpose sentence plus the diagram's own topic, roles, and nested text. */
export function buildMindmateDiagramBrief(
  diagramType: DiagramType | string | null | undefined,
  nodes: DiagramNode[],
  connections: Connection[],
  translate: DiagramBriefTranslate,
  focusQuestion?: string
): string {
  if (!diagramType || nodes.length === 0) return ''
  const visible = nodes.filter((node) => node.type !== 'summary' && !node.id.startsWith('smry:'))
  let lines: string[]
  switch (diagramType) {
    case 'circle_map':
      lines = circleBrief(visible, translate)
      break
    case 'bubble_map':
      lines = bubbleBrief(visible, translate)
      break
    case 'double_bubble_map':
      lines = doubleBubbleBrief(visible, translate)
      break
    case 'tree_map':
      lines = treeBrief(visible, translate)
      break
    case 'brace_map':
      lines = braceBrief(visible, connections, translate)
      break
    case 'flow_map':
      lines = flowBrief(visible, translate)
      break
    case 'multi_flow_map':
      lines = multiFlowBrief(visible, translate)
      break
    case 'bridge_map':
      lines = bridgeBrief(visible, translate)
      break
    case 'concept_map':
      lines = conceptBrief(visible, connections, focusQuestion, translate)
      break
    default:
      lines = mindMapBrief(visible, connections, translate)
      break
  }
  return finish(diagramType, translate, lines)
}

/** Keep the teacher's question and clip the outline so the request stays within the cap. */
export function withMindmateDiagramBrief(prompt: string, brief: string): string {
  const question = prompt.trim()
  const context = brief.trim()
  if (!question) return ''
  if (!context) return question.slice(0, MINDMATE_ASSISTANT_MESSAGE_MAX)
  const body = `${MINDMATE_DIAGRAM_CONTEXT_MARKER}\n${context}`
  const separator = '\n\n'
  const budget = MINDMATE_ASSISTANT_MESSAGE_MAX - question.length - separator.length
  if (budget <= 0) return question.slice(0, MINDMATE_ASSISTANT_MESSAGE_MAX)
  const clipped = body.length <= budget ? body : body.slice(0, budget)
  return `${clipped}${separator}${question}`
}
