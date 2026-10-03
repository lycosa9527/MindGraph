/**
 * Stamp `textSecondary` for loaders that still emit primary strings only.
 * Circle, bubble, double-bubble, and mind map stamp during their own load.
 */
import { orderFlowStepNodes, substepsForFlowStep } from '@/stores/specLoader/flowMapSubsteps'
import type { DiagramNode, DiagramType } from '@/types'

import { mirrorRecordList, mirrorString, mirrorStringList, readSecondaryMirror } from './mirror'

function setGloss(node: DiagramNode | undefined, gloss: string | undefined): void {
  if (!node || node.textSecondary || !gloss) return
  node.textSecondary = gloss
}

function preorderTexts(nodes: unknown, into: string[]): void {
  if (!Array.isArray(nodes)) return
  for (const node of nodes) {
    if (!node || typeof node !== 'object') continue
    const record = node as Record<string, unknown>
    const text =
      (typeof record.text === 'string' && record.text) ||
      (typeof record.name === 'string' && record.name) ||
      ''
    into.push(text.trim())
    const children = record.children ?? record.subparts ?? record.parts
    preorderTexts(children, into)
  }
}

function attachFlow(nodes: DiagramNode[], mirror: Record<string, unknown>): void {
  setGloss(
    nodes.find((node) => node.id === 'flow-topic' || node.type === 'topic'),
    mirrorString(mirror, 'title') ?? mirrorString(mirror, 'topic')
  )
  const steps = mirrorStringList(mirror, 'steps')
  const stepNodes = orderFlowStepNodes(nodes)
  stepNodes.forEach((node, index) => setGloss(node, steps[index]))
  const groups = mirrorRecordList(mirror, 'substeps')
  const substepNodes = nodes.filter((node) => node.type === 'flowSubstep')
  stepNodes.forEach((stepNode, index) => {
    const lines = mirrorStringList(groups[index] ?? null, 'substeps')
    substepsForFlowStep(substepNodes, stepNode).forEach((child, lineIndex) => {
      setGloss(child, lines[lineIndex])
    })
  })
}

function attachMultiFlow(nodes: DiagramNode[], mirror: Record<string, unknown>): void {
  setGloss(
    nodes.find((node) => node.id === 'event' || node.type === 'topic'),
    mirrorString(mirror, 'event') ?? mirrorString(mirror, 'topic')
  )
  const causes = mirrorStringList(mirror, 'causes')
  const effects = mirrorStringList(mirror, 'effects')
  const roleOf = (node: DiagramNode): string => {
    const data = node.data as { multiFlowRole?: string } | undefined
    return data?.multiFlowRole ?? ''
  }
  const causeNodes = nodes.filter((node) => roleOf(node) === 'cause' || node.id.startsWith('cause'))
  const effectNodes = nodes.filter(
    (node) => roleOf(node) === 'effect' || node.id.startsWith('effect')
  )
  causeNodes.forEach((node, index) => setGloss(node, causes[index]))
  effectNodes.forEach((node, index) => setGloss(node, effects[index]))
}

function attachLabeledTree(
  nodes: DiagramNode[],
  mirror: Record<string, unknown>,
  topicKey: string,
  childKey: string
): void {
  setGloss(
    nodes.find((node) => node.type === 'topic' || node.type === 'whole'),
    mirrorString(mirror, topicKey)
  )
  setGloss(
    nodes.find((node) => node.id === 'dimension-label'),
    mirrorString(mirror, 'dimension') ?? mirrorString(mirror, 'relating_factor')
  )
  const glosses: string[] = []
  preorderTexts(mirror[childKey], glosses)
  const branches = nodes.filter((node) => node.type === 'branch' || node.type === 'brace')
  branches.forEach((node, index) => setGloss(node, glosses[index]))
}

function attachConcept(nodes: DiagramNode[], mirror: Record<string, unknown>): void {
  setGloss(
    nodes.find((node) => node.id === 'topic' || node.type === 'topic'),
    mirrorString(mirror, 'topic')
  )
  const concepts = mirrorStringList(mirror, 'concepts')
  const conceptNodes = nodes.filter((node) => node.id.startsWith('concept-'))
  conceptNodes.forEach((node, index) => setGloss(node, concepts[index]))
}

function attachBridge(nodes: DiagramNode[], mirror: Record<string, unknown>): void {
  setGloss(
    nodes.find((node) => node.id === 'dimension-label' || node.type === 'label'),
    mirrorString(mirror, 'dimension') ?? mirrorString(mirror, 'relating_factor')
  )
  const pairs = mirrorRecordList(mirror, 'analogies')
  const branches = nodes.filter((node) => node.type === 'branch')
  pairs.forEach((pair, index) => {
    setGloss(branches[index * 2], mirrorString(pair, 'left'))
    setGloss(branches[index * 2 + 1], mirrorString(pair, 'right'))
  })
}

export function attachRemainingSecondary(
  diagramType: DiagramType,
  nodes: DiagramNode[],
  spec: Record<string, unknown>
): void {
  const mirror = readSecondaryMirror(spec)
  if (!mirror) return
  if (diagramType === 'flow_map') attachFlow(nodes, mirror)
  else if (diagramType === 'multi_flow_map') attachMultiFlow(nodes, mirror)
  else if (diagramType === 'tree_map') attachLabeledTree(nodes, mirror, 'topic', 'children')
  else if (diagramType === 'brace_map') attachLabeledTree(nodes, mirror, 'whole', 'parts')
  else if (diagramType === 'bridge_map') attachBridge(nodes, mirror)
  else if (diagramType === 'concept_map') attachConcept(nodes, mirror)
}
