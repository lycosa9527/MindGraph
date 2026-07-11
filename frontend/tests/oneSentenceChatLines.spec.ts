import { describe, expect, it } from 'vitest'

import {
  ONE_SENTENCE_WELCOME_MIN_COUNT,
  pickOneSentenceGenerateDone,
  pickOneSentenceGenerating,
  pickOneSentenceWelcome,
} from '@/composables/canvasToolbar/oneSentenceChatLines'
import {
  poolGenerateDone,
  poolGenerating,
  poolWelcome,
} from '@/composables/canvasToolbar/oneSentenceChatPools'

describe('oneSentenceChatLines', () => {
  it('has at least 50 welcome lines per primary locale', () => {
    expect(poolWelcome('zh').length).toBeGreaterThanOrEqual(ONE_SENTENCE_WELCOME_MIN_COUNT)
    expect(poolWelcome('en').length).toBeGreaterThanOrEqual(ONE_SENTENCE_WELCOME_MIN_COUNT)
    expect(poolWelcome('zh-tw').length).toBeGreaterThanOrEqual(ONE_SENTENCE_WELCOME_MIN_COUNT)
  })

  it('picks non-empty welcome / generating / done lines', () => {
    expect(pickOneSentenceWelcome('zh').trim().length).toBeGreaterThan(0)
    expect(pickOneSentenceGenerating('zh').trim().length).toBeGreaterThan(0)
    expect(pickOneSentenceGenerateDone('zh').trim().length).toBeGreaterThan(0)
  })

  it('avoids immediate welcome repeats when pool is large', () => {
    const first = pickOneSentenceWelcome('zh')
    const second = pickOneSentenceWelcome('zh')
    if (poolWelcome('zh').length > 1) {
      expect(second).not.toBe(first)
    }
  })

  it('keeps generate-done and generating pools populated', () => {
    expect(poolGenerateDone('zh').length).toBeGreaterThanOrEqual(10)
    expect(poolGenerating('en').length).toBeGreaterThanOrEqual(10)
  })
})
