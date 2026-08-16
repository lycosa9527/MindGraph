import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import {
  buildMindMapAudienceInstructions,
  mergeMindMapAudienceInstructions,
  resolveMindMapAudienceInstructions,
} from '@/composables/mindMap/audience/aiContentLevelInstructions'
import { withMindMapAudienceContext } from '@/composables/mindMap/audience/withMindMapAudienceContext'
import { useAiContentLevelStore } from '@/stores/aiContentLevel'

describe('mind-map 专业程度 audience instructions', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('does not constrain general content', () => {
    expect(buildMindMapAudienceInstructions('general', 'en')).toBeUndefined()
    expect(buildMindMapAudienceInstructions('general', 'zh')).toBeUndefined()
  })

  it('uses the same four slots for every constrained level', () => {
    const constrained = ['primary', 'junior', 'senior', 'university', 'adult', 'expert'] as const
    const zhBlocks = constrained.map((id) => buildMindMapAudienceInstructions(id, 'zh') ?? '')
    const enBlocks = constrained.map((id) => buildMindMapAudienceInstructions(id, 'en') ?? '')

    for (const block of zhBlocks) {
      expect(block).toContain('用语：')
      expect(block).toContain('句子：')
      expect(block).toContain('前提：')
      expect(block).toContain('深度：')
    }
    for (const block of enBlocks) {
      expect(block).toContain('Voice:')
      expect(block).toContain('Length:')
      expect(block).toContain('Assume:')
      expect(block).toContain('Depth:')
    }
    expect(new Set(zhBlocks).size).toBe(constrained.length)
    expect(new Set(enBlocks).size).toBe(constrained.length)
    expect(zhBlocks[0]).not.toBe(enBlocks[0])
  })

  it('uses distinct copy for primary, university, and expert', () => {
    const primary = buildMindMapAudienceInstructions('primary', 'en')
    const university = buildMindMapAudienceInstructions('university', 'en')
    const expert = buildMindMapAudienceInstructions('expert', 'en')
    expect(primary).toContain('primary-school')
    expect(university).toContain('university')
    expect(university).toContain('disciplinary')
    expect(expert).toContain('expert')
    expect(expert).toContain('domain terminology')
    expect(primary).not.toBe(university)
    expect(university).not.toBe(expert)

    expect(buildMindMapAudienceInstructions('primary', 'zh')).toContain('小学')
    expect(buildMindMapAudienceInstructions('university', 'zh')).toContain('大学')
    expect(buildMindMapAudienceInstructions('expert', 'zh')).toContain('专家')
  })

  it('ignores the store until the user explicitly picks a level', () => {
    const store = useAiContentLevelStore()
    store.level = 'university'
    store.userSet = false
    expect(resolveMindMapAudienceInstructions('en')).toBeUndefined()

    store.setLevel('university')
    expect(resolveMindMapAudienceInstructions('en')).toContain('university')
  })

  it('merges audience text ahead of caller instructions', () => {
    expect(mergeMindMapAudienceInstructions('audience', 'caller')).toBe('audience\n\ncaller')
    expect(mergeMindMapAudienceInstructions(undefined, 'caller')).toBe('caller')
    expect(mergeMindMapAudienceInstructions('audience', undefined)).toBe('audience')
  })

  it('attaches generation_instructions and educational_context when a level is set', () => {
    const store = useAiContentLevelStore()
    store.setLevel('primary')
    const next = withMindMapAudienceContext({ prompt: 'topic', language: 'zh' }, 'zh')
    expect(String(next.generation_instructions)).toContain('小学')
    const edu = next.educational_context as { raw_message?: string }
    expect(edu.raw_message).toContain('小学')
  })

  it('leaves payloads unchanged when the level is general', () => {
    const payload = { prompt: 'topic' }
    expect(withMindMapAudienceContext(payload, 'en')).toBe(payload)
  })
})
