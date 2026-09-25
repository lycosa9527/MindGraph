/**
 * Landing gallery cards and preset prompts shared by the MindGraph
 * landing page and the quick-access remote.
 */
import type { DiagramType } from '@/types'

export type LandingDiagramCard = {
  titleKey: string
  descKey: string
  type: DiagramType
}

/** Thinking Maps®–style eight (circle through bridge); not mind map / concept map. */
export const eightThinkingMapCards: readonly LandingDiagramCard[] = [
  {
    titleKey: 'landing.diagramGrid.circle_map.title',
    descKey: 'landing.diagramGrid.circle_map.desc',
    type: 'circle_map',
  },
  {
    titleKey: 'landing.diagramGrid.bubble_map.title',
    descKey: 'landing.diagramGrid.bubble_map.desc',
    type: 'bubble_map',
  },
  {
    titleKey: 'landing.diagramGrid.double_bubble_map.title',
    descKey: 'landing.diagramGrid.double_bubble_map.desc',
    type: 'double_bubble_map',
  },
  {
    titleKey: 'landing.diagramGrid.tree_map.title',
    descKey: 'landing.diagramGrid.tree_map.desc',
    type: 'tree_map',
  },
  {
    titleKey: 'landing.diagramGrid.brace_map.title',
    descKey: 'landing.diagramGrid.brace_map.desc',
    type: 'brace_map',
  },
  {
    titleKey: 'landing.diagramGrid.flow_map.title',
    descKey: 'landing.diagramGrid.flow_map.desc',
    type: 'flow_map',
  },
  {
    titleKey: 'landing.diagramGrid.multi_flow_map.title',
    descKey: 'landing.diagramGrid.multi_flow_map.desc',
    type: 'multi_flow_map',
  },
  {
    titleKey: 'landing.diagramGrid.bridge_map.title',
    descKey: 'landing.diagramGrid.bridge_map.desc',
    type: 'bridge_map',
  },
]

export const advancedDiagramCards: readonly LandingDiagramCard[] = [
  {
    titleKey: 'landing.diagramGrid.mindmap.title',
    descKey: 'landing.diagramGrid.mindmap.desc',
    type: 'mindmap',
  },
  {
    titleKey: 'landing.diagramGrid.concept_map.title',
    descKey: 'landing.diagramGrid.concept_map.desc',
    type: 'concept_map',
  },
]

/** Eight thinking maps plus mind map and concept map. */
export const quickAccessDiagramCards: readonly LandingDiagramCard[] = [
  ...eightThinkingMapCards,
  ...advancedDiagramCards,
]

export const LANDING_PROMPT_EXAMPLE_KEYS = [
  'landing.international.example1',
  'landing.international.example2',
  'landing.international.example3',
  'landing.international.example4',
  'landing.international.example5',
  'landing.international.example6',
] as const

export type LandingPromptExampleKey = (typeof LANDING_PROMPT_EXAMPLE_KEYS)[number]

export const LANDING_PROMPT_MAX_LENGTH = 10000
export const LANDING_LLM_MODEL = 'qwen'
