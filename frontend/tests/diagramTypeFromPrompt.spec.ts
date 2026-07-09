import { describe, expect, it } from 'vitest'

import {
  canvasDiagramSlugsEquivalent,
  extractTopicSeedFromPrompt,
  resolveDiagramTypeFromPrompt,
} from '@/composables/canvasPage/diagramTypeFromPrompt'

describe('diagramTypeFromPrompt', () => {
  it('resolves circle map from Chinese prompt', () => {
    expect(resolveDiagramTypeFromPrompt('生成一个关于猫草的圆圈图')).toBe('circle_map')
  })

  it('resolves mind map aliases equivalently', () => {
    expect(canvasDiagramSlugsEquivalent('mind_map', 'mindmap')).toBe(true)
    expect(resolveDiagramTypeFromPrompt('生成思维导图关于光合作用')).toBe('mindmap')
  })

  it('extracts topic from 关于…的 pattern', () => {
    const seed = extractTopicSeedFromPrompt('生成一个关于猫草的圆圈图', 'circle_map')
    expect(seed.topic).toBe('猫草')
  })

  it('extracts double bubble pair', () => {
    const seed = extractTopicSeedFromPrompt('用双气泡图比较苹果和梨', 'double_bubble_map')
    expect(seed.left).toBe('苹果')
    expect(seed.right).toBe('梨')
  })

  it('returns null type when no diagram mentioned', () => {
    expect(resolveDiagramTypeFromPrompt('猫草')).toBeNull()
  })
})
