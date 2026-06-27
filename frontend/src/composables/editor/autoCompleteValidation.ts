/**
 * Pure auto-complete validation rules (no store/i18n dependencies).
 */

export type AutoCompleteValidationReason =
  | 'generation_in_progress'
  | 'select_diagram_type'
  | 'no_diagram_data'
  | 'concept_map_realtime'
  | 'double_bubble_need_both_topics'
  | 'enter_topic_first'

export type AutoCompleteValidationResult =
  | { valid: true }
  | { valid: false; reason: AutoCompleteValidationReason }

export interface AutoCompleteValidationInput {
  isGenerating: boolean
  diagramType: string | null
  hasDiagramData: boolean
  bridgeAnalogiesCount: number
  fixedDimension: string | null
  generationInstructions: string
  mainTopic: string | null
  doubleBubbleLeftValid: boolean
  doubleBubbleRightValid: boolean
}

export const AUTO_COMPLETE_VALIDATION_I18N: Record<AutoCompleteValidationReason, string> = {
  generation_in_progress: 'autoComplete.generationInProgress',
  select_diagram_type: 'autoComplete.selectDiagramType',
  no_diagram_data: 'autoComplete.noDiagramData',
  concept_map_realtime: 'autoComplete.conceptMapRealtime',
  double_bubble_need_both_topics: 'autoComplete.doubleBubbleNeedBothTopics',
  enter_topic_first: 'autoComplete.enterTopicFirst',
}

/**
 * Decide whether full-diagram auto-complete can run from precomputed diagram inputs.
 */
export function validateAutoCompleteRules(
  input: AutoCompleteValidationInput
): AutoCompleteValidationResult {
  if (input.isGenerating) {
    return { valid: false, reason: 'generation_in_progress' }
  }

  if (!input.diagramType) {
    return { valid: false, reason: 'select_diagram_type' }
  }

  if (!input.hasDiagramData) {
    return { valid: false, reason: 'no_diagram_data' }
  }

  if (input.diagramType === 'concept_map') {
    return { valid: false, reason: 'concept_map_realtime' }
  }

  if (input.diagramType === 'double_bubble_map') {
    if (!input.doubleBubbleLeftValid || !input.doubleBubbleRightValid) {
      return { valid: false, reason: 'double_bubble_need_both_topics' }
    }
  }

  if (input.diagramType === 'bridge_map') {
    if (input.bridgeAnalogiesCount > 0 || input.fixedDimension) {
      return { valid: true }
    }
  }

  if (input.diagramType === 'tree_map' || input.diagramType === 'brace_map') {
    if (input.fixedDimension) {
      return { valid: true }
    }
  }

  if (input.generationInstructions.trim()) {
    return { valid: true }
  }

  if (!input.mainTopic) {
    return { valid: false, reason: 'enter_topic_first' }
  }

  return { valid: true }
}
