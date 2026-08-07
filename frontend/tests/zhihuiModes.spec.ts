import { describe, expect, it } from 'vitest'

import {
  ZHIHUI_MODELS,
  defaultModelId,
  isZhihuiImageModel,
} from '@/components/zhihui/zhihuiModes'
import { isZhihuiJobActive } from '@/stores/zhihuiHistory'

describe('zhihuiModes', () => {
  it('exposes Wan 2.7 for diagram mode', () => {
    expect(defaultModelId('diagram')).toBe('wan2.7-image')
    expect(ZHIHUI_MODELS.diagram[0]?.available).toBe(true)
  })

  it('keeps Qwen models for image mode', () => {
    expect(isZhihuiImageModel('qwen-image-3.0')).toBe(true)
    expect(isZhihuiImageModel('wan2.7-image')).toBe(false)
  })
})

describe('isZhihuiJobActive', () => {
  it('treats queued/planning/generating as active', () => {
    expect(isZhihuiJobActive('queued')).toBe(true)
    expect(isZhihuiJobActive('planning')).toBe(true)
    expect(isZhihuiJobActive('generating')).toBe(true)
    expect(isZhihuiJobActive('complete')).toBe(false)
    expect(isZhihuiJobActive('failed')).toBe(false)
    expect(isZhihuiJobActive('cancelled')).toBe(false)
  })
})
