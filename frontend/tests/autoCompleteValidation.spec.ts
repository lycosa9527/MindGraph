import { describe, expect, it } from 'vitest'

import { validateAutoCompleteRules } from '@/composables/editor/autoCompleteValidation'

const baseInput = {
  isGenerating: false,
  diagramType: 'bubble_map',
  hasDiagramData: true,
  bridgeAnalogiesCount: 0,
  fixedDimension: null as string | null,
  generationInstructions: '',
  mainTopic: 'Photosynthesis',
  doubleBubbleLeftValid: false,
  doubleBubbleRightValid: false,
}

describe('validateAutoCompleteRules', () => {
  it('blocks concept maps', () => {
    const result = validateAutoCompleteRules({
      ...baseInput,
      diagramType: 'concept_map',
    })
    expect(result).toEqual({ valid: false, reason: 'concept_map_realtime' })
  })

  it('requires both double-bubble topics', () => {
    expect(
      validateAutoCompleteRules({
        ...baseInput,
        diagramType: 'double_bubble_map',
        doubleBubbleLeftValid: true,
        doubleBubbleRightValid: false,
      })
    ).toEqual({ valid: false, reason: 'double_bubble_need_both_topics' })

    expect(
      validateAutoCompleteRules({
        ...baseInput,
        diagramType: 'double_bubble_map',
        doubleBubbleLeftValid: true,
        doubleBubbleRightValid: true,
      })
    ).toEqual({ valid: true })
  })

  it('allows bridge map with dimension only', () => {
    expect(
      validateAutoCompleteRules({
        ...baseInput,
        diagramType: 'bridge_map',
        mainTopic: null,
        fixedDimension: 'as',
      })
    ).toEqual({ valid: true })
  })

  it('allows tree map with dimension only', () => {
    expect(
      validateAutoCompleteRules({
        ...baseInput,
        diagramType: 'tree_map',
        mainTopic: null,
        fixedDimension: 'Classification',
      })
    ).toEqual({ valid: true })
  })

  it('allows generation instructions without topic', () => {
    expect(
      validateAutoCompleteRules({
        ...baseInput,
        mainTopic: null,
        generationInstructions: 'Three branches about climate change',
      })
    ).toEqual({ valid: true })
  })

  it('requires a valid topic when no other inputs apply', () => {
    expect(
      validateAutoCompleteRules({
        ...baseInput,
        mainTopic: null,
      })
    ).toEqual({ valid: false, reason: 'enter_topic_first' })
  })

  it('blocks when generation is already in progress', () => {
    expect(
      validateAutoCompleteRules({
        ...baseInput,
        isGenerating: true,
      })
    ).toEqual({ valid: false, reason: 'generation_in_progress' })
  })
})
