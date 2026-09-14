import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAiContentLevelStore } from '@/stores/aiContentLevel'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import {
  LLM_EXPORT_ATTRIBUTION_KEY,
  attachLlmExportAttribution,
  clearLlmExportAttribution,
  formatLlmExportWatermarkText,
  parseLlmExportAttribution,
  readLlmExportAttribution,
  resolveLlmExportWatermarkText,
} from '@/utils/llmExportWatermark'

const LEVEL_TITLES: Record<string, string> = {
  'canvas.toolbar.professionalContent.level.general.title': '通用',
  'canvas.toolbar.professionalContent.level.primary.title': '小学',
  'canvas.toolbar.professionalContent.level.junior.title': '初中',
  'canvas.toolbar.professionalContent.level.senior.title': '高中',
  'canvas.toolbar.professionalContent.level.university.title': '大学',
  'canvas.toolbar.professionalContent.level.adult.title': '成人',
  'canvas.toolbar.professionalContent.level.expert.title': '专家',
}

const LEVEL_TITLES_EN: Record<string, string> = {
  'canvas.toolbar.professionalContent.level.general.title': 'General',
  'canvas.toolbar.professionalContent.level.primary.title': 'Primary',
  'canvas.toolbar.professionalContent.level.junior.title': 'Middle school',
  'canvas.toolbar.professionalContent.level.senior.title': 'High school',
  'canvas.toolbar.professionalContent.level.university.title': 'University',
  'canvas.toolbar.professionalContent.level.adult.title': 'Adult',
  'canvas.toolbar.professionalContent.level.expert.title': 'Expert',
}

describe('llmExportWatermark', () => {
  it('formats 豆包小学版 for Chinese locales', () => {
    const text = formatLlmExportWatermarkText(
      { model: 'doubao', level: 'primary' },
      (key) => LEVEL_TITLES[key] ?? key,
      'zh'
    )
    expect(text).toBe('豆包小学版')
  })

  it('formats Doubao Primary for English locales', () => {
    const text = formatLlmExportWatermarkText(
      { model: 'doubao', level: 'primary' },
      (key) => LEVEL_TITLES_EN[key] ?? key,
      'en'
    )
    expect(text).toBe('Doubao Primary')
  })

  it('uses Traditional 版 wording for zh-tw', () => {
    const text = formatLlmExportWatermarkText(
      { model: 'qwen', level: 'junior' },
      (key) => (key.endsWith('junior.title') ? '初中' : key),
      'zh-tw'
    )
    expect(text).toBe('千问初中版')
  })

  it('parses and clears attribution on a spec', () => {
    const spec = attachLlmExportAttribution({ topic: '水' }, 'doubao', 'primary')
    expect(parseLlmExportAttribution(spec[LLM_EXPORT_ATTRIBUTION_KEY])).toEqual({
      model: 'doubao',
      level: 'primary',
    })
    clearLlmExportAttribution(spec)
    expect(readLlmExportAttribution(spec)).toBeNull()
  })

  it('rejects incomplete attribution payloads', () => {
    expect(parseLlmExportAttribution({ model: 'doubao' })).toBeNull()
    expect(parseLlmExportAttribution({ model: 'gpt', level: 'primary' })).toBeNull()
    expect(resolveLlmExportWatermarkText({}, (key) => key, 'zh')).toBeNull()
  })
})

describe('llm export attribution on the canvas', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  it('stamps attribution onto a completed LLM spec and drops it on user edit', async () => {
    const aiLevel = useAiContentLevelStore()
    aiLevel.hydrateFromProfile('primary')
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')
    const llmStore = useLLMResultsStore()
    llmStore.startGeneration('sess-watermark', 'mindmap', ['doubao'], '水循环')

    const painted = await llmStore.handleModelSuccess(
      'doubao',
      { topic: '水循环', children: [{ text: '蒸发' }] },
      'mindmap',
      12,
      'sess-watermark'
    )
    expect(painted).toBe(true)
    expect(readLlmExportAttribution(diagramStore.data as Record<string, unknown>)).toEqual({
      model: 'doubao',
      level: 'primary',
    })
    expect(readLlmExportAttribution(diagramStore.getSpecForSave())).toEqual({
      model: 'doubao',
      level: 'primary',
    })

    const topic = diagramStore.data?.nodes.find((node) => node.id === 'topic')
    if (topic) {
      topic.text = 'Edited'
    }
    diagramStore.pushHistory('Edit topic')
    expect(readLlmExportAttribution(diagramStore.data as Record<string, unknown>)).toBeNull()
    expect(readLlmExportAttribution(diagramStore.getSpecForSave())).toBeNull()
  })
})
