/**
 * Node-carousel slides for flow maps.
 * - firstLevel: overview → each step (step + its substeps focused)
 * - deep: overview → each step, then each of that step's substeps in order
 */
import { orderFlowStepNodes, substepsForFlowStep } from '@/stores/specLoader/flowMapSubsteps'
import type { DiagramNode } from '@/types'
import { FLOW_TOPIC_NODE_ID } from '@/utils/flowMapIdentity'
import type { MindMapSlide, MindMapSlideTraversalMode } from '@/utils/mindMapSlides'

function nodeText(node: DiagramNode | undefined): string {
  if (!node) return ''
  return String(node.text ?? (node.data as { label?: string } | undefined)?.label ?? '').trim()
}

function branchSlide(
  id: string,
  title: string,
  breadcrumb: string[],
  focusNodeIds: string[],
  branchNodeId: string
): MindMapSlide {
  return {
    id,
    kind: 'branch',
    title,
    branchNodeId,
    breadcrumb,
    focusNodeIds,
  }
}

export function buildFlowMapSlides(
  nodes: DiagramNode[],
  mode: MindMapSlideTraversalMode = 'firstLevel'
): MindMapSlide[] {
  if (!nodes.length) return []

  const topic = nodes.find((node) => node.id === FLOW_TOPIC_NODE_ID)
  const steps = orderFlowStepNodes(nodes)
  const substepNodes = nodes.filter((node) => node.type === 'flowSubstep')
  const rootTitle = nodeText(topic) || 'overview'
  const allIds = nodes.map((node) => node.id)
  const deep = mode === 'deep'

  const slides: MindMapSlide[] = [
    {
      id: 'overview',
      kind: 'overview',
      title: rootTitle,
      branchNodeId: topic?.id ?? steps[0]?.id,
      breadcrumb: [rootTitle],
      focusNodeIds: allIds,
    },
  ]

  for (const step of steps) {
    const stepTitle = nodeText(step) || step.id
    const kids = substepsForFlowStep(substepNodes, step)
    const stepFocus = [step.id, ...kids.map((kid) => kid.id)]
    slides.push(branchSlide(step.id, stepTitle, [rootTitle, stepTitle], stepFocus, step.id))
    if (!deep) continue
    for (const kid of kids) {
      const kidTitle = nodeText(kid) || kid.id
      slides.push(
        branchSlide(kid.id, kidTitle, [rootTitle, stepTitle, kidTitle], [step.id, kid.id], kid.id)
      )
    }
  }

  return slides
}
