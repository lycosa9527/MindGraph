import { describe, expect, it } from 'vitest'

import { addOverlay, blankPageStep } from '@/composables/training/trainingBuilderSteps'
import {
  TRAINING_TEXT_HEIGHT_DEFAULT,
  TRAINING_TEXT_SIZE_DEFAULT,
  TRAINING_TEXT_WIDTH_DEFAULT,
  bumpTextBubbleFont,
  clampTextHeight,
  clampTextSize,
  clampTextWidth,
  resizeTextBubble,
  setTextBubbleAlign,
  setTextBubbleInk,
  setTextBubbleStroke,
  textBubbleAlign,
  textBubbleDragReady,
  textBubbleFontSize,
  textBubbleHeight,
  textBubbleInk,
  textBubbleIsBold,
  textBubbleIsItalic,
  textBubbleStroke,
  textBubbleWidth,
  toggleTextBubbleBold,
  toggleTextBubbleItalic,
} from '@/config/trainingTextBubbles'
import type { TrainingStepOverlay } from '@/types/training'

describe('trainingTextBubbles', () => {
  it('places an empty bubble without a prompt modal', () => {
    const step = blankPageStep(0)
    addOverlay(step, 'text')
    expect(step.overlays?.[0]).toMatchObject({
      kind: 'text',
      x: 50,
      y: 42,
      w: TRAINING_TEXT_WIDTH_DEFAULT,
      h: TRAINING_TEXT_HEIGHT_DEFAULT,
      size: TRAINING_TEXT_SIZE_DEFAULT,
      text: '',
      step: 2,
    })
  })

  it('clamps size and resizes from the bottom-right edge', () => {
    expect(clampTextWidth(2)).toBe(12)
    expect(clampTextWidth(90)).toBe(72)
    expect(clampTextHeight(2)).toBe(8)
    expect(clampTextHeight(90)).toBe(56)
    expect(clampTextSize(11)).toBe(12)
    expect(clampTextSize(41)).toBe(40)
    expect(textBubbleWidth({ kind: 'text' })).toBe(TRAINING_TEXT_WIDTH_DEFAULT)
    expect(textBubbleHeight({ kind: 'text' })).toBe(TRAINING_TEXT_HEIGHT_DEFAULT)
    expect(textBubbleFontSize({ kind: 'text' })).toBe(TRAINING_TEXT_SIZE_DEFAULT)

    const overlay: TrainingStepOverlay = { kind: 'text', x: 50, y: 42, w: 20, h: 12 }
    resizeTextBubble(overlay, 66, 54)
    expect(overlay.w).toBe(26)
    expect(overlay.h).toBe(18)
  })

  it('toggles bold italic align and font size', () => {
    const overlay: TrainingStepOverlay = { kind: 'text', text: 'hi' }
    expect(textBubbleIsBold(overlay)).toBe(false)
    toggleTextBubbleBold(overlay)
    expect(textBubbleIsBold(overlay)).toBe(true)
    toggleTextBubbleItalic(overlay)
    expect(textBubbleIsItalic(overlay)).toBe(true)
    setTextBubbleAlign(overlay, 'center')
    expect(textBubbleAlign(overlay)).toBe('center')
    bumpTextBubbleFont(overlay, 4)
    expect(overlay.size).toBe(22)
    bumpTextBubbleFont(overlay, -40)
    expect(overlay.size).toBe(12)
  })

  it('normalizes ink and stroke hex colors', () => {
    const overlay: TrainingStepOverlay = { kind: 'text' }
    expect(textBubbleInk(overlay)).toBe('#1c1917')
    expect(textBubbleStroke(overlay)).toBe('#d6d3d1')
    setTextBubbleInk(overlay, '#f00')
    setTextBubbleStroke(overlay, 'not-a-color')
    expect(textBubbleInk(overlay)).toBe('#ff0000')
    expect(textBubbleStroke(overlay)).toBe('#d6d3d1')
    setTextBubbleStroke(overlay, '#1D4ED8')
    expect(textBubbleStroke(overlay)).toBe('#1d4ed8')
  })

  it('starts a text drag after a short pointer slop', () => {
    expect(textBubbleDragReady(40, 40, 44, 42)).toBe(false)
    expect(textBubbleDragReady(40, 40, 48, 46)).toBe(true)
    expect(textBubbleDragReady(10, 10, 10, 18)).toBe(true)
  })
})
