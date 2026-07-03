import { describe, expect, it } from 'vitest'

import { isNodePlaceholder } from '@/composables/nodePalette/placeholderHelpers'
import {
  LEARNING_SHEET_BLANK_TEXT,
  LEARNING_SHEET_LEGACY_PLACEHOLDER,
  isLearningSheetBlankDisplayText,
} from '@/stores/specLoader/utils'

describe('learningSheetBlankDisplayText', () => {
  it('treats empty and legacy underscore placeholder as blank', () => {
    expect(isLearningSheetBlankDisplayText('')).toBe(true)
    expect(isLearningSheetBlankDisplayText('   ')).toBe(true)
    expect(isLearningSheetBlankDisplayText(LEARNING_SHEET_BLANK_TEXT)).toBe(true)
    expect(isLearningSheetBlankDisplayText(LEARNING_SHEET_LEGACY_PLACEHOLDER)).toBe(true)
  })

  it('does not treat normal node text as blank', () => {
    expect(isLearningSheetBlankDisplayText('photosynthesis')).toBe(false)
    expect(isLearningSheetBlankDisplayText('__')).toBe(false)
    expect(isLearningSheetBlankDisplayText('____')).toBe(false)
  })

  it('combines blank detection with generic placeholder text in palette helpers', () => {
    expect(isNodePlaceholder(LEARNING_SHEET_LEGACY_PLACEHOLDER)).toBe(true)
    expect(isNodePlaceholder('Click to edit')).toBe(true)
    expect(isNodePlaceholder('valid topic')).toBe(false)
  })
})
