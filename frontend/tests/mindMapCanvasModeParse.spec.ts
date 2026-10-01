import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import {
  effectiveMindMapCanvasMode,
  isMindMapV2FamilyMode,
  layoutMindMapCanvasMode,
  readShowcaseMindMapCanvasMode,
} from '@/utils/mindMapCanvasMode'

describe('mind map leftover V3 mode helpers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps the archived classic layout key and treats leftover v3 as v2', () => {
    expect(isMindMapV2FamilyMode('v2')).toBe(true)
    expect(isMindMapV2FamilyMode('v3')).toBe(true)
    expect(isMindMapV2FamilyMode('legacy')).toBe(false)
    expect(layoutMindMapCanvasMode('v3')).toBe('v2')
    expect(layoutMindMapCanvasMode('legacy')).toBe('legacy')
  })

  it('maps stored classic and leftover v3 onto the new canvas', () => {
    expect(effectiveMindMapCanvasMode('v3')).toBe('v2')
    expect(effectiveMindMapCanvasMode('v2')).toBe('v2')
    expect(effectiveMindMapCanvasMode('legacy')).toBe('v2')
  })

  it('keeps showcase on the new canvas', () => {
    expect(readShowcaseMindMapCanvasMode()).toBe('v2')
  })
})
