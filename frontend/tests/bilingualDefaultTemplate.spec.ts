import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loadLocaleMessages } from '@/i18n'
import { useDiagramStore } from '@/stores/diagram'
import { getBilingualDefaultTemplate, getDefaultTemplate } from '@/stores/specLoader'
import { useUIStore } from '@/stores/ui'
import type { DiagramType } from '@/types'

function stubMatchMedia(): void {
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
}

function glossOf(text: string): string | undefined {
  const store = useDiagramStore()
  const node = store.data?.nodes.find((item) => item.text === text)
  return node?.textSecondary
}

describe('bilingual default template', () => {
  beforeEach(async () => {
    stubMatchMedia()
    setActivePinia(createPinia())
    await loadLocaleMessages('zh')
    await loadLocaleMessages('en')
    const ui = useUIStore()
    ui.language = 'zh'
    ui.bilingualUiEnabled = false
  })

  it('keeps a single-language blank canvas on one line', () => {
    const store = useDiagramStore()
    expect(store.loadDefaultTemplate('circle_map')).toBe(true)
    const topic = store.data?.nodes.find((node) => node.id === 'topic')
    expect(topic?.text).toBe('主题')
    expect(topic?.textSecondary ?? '').toBe('')
    expect(store.data?.languages).toBeUndefined()
  })

  it('pairs the interface language with the presenter language', () => {
    const ui = useUIStore()
    ui.language = 'zh'
    ui.bilingualUiEnabled = true
    ui.presenterUiLocale = 'en'

    const spec = getBilingualDefaultTemplate('circle_map', 'zh', 'en')
    expect(spec?.topic).toBe('主题')
    expect((spec?.secondary as { topic?: string } | undefined)?.topic).toBe('Topic')
    expect(spec?.languages).toEqual({ primary: 'zh', secondary: 'en' })

    const cases: Array<{ type: DiagramType; text: string; gloss: string }> = [
      { type: 'circle_map', text: '主题', gloss: 'Topic' },
      { type: 'circle_map', text: '联想1', gloss: 'Context 1' },
      { type: 'bubble_map', text: '属性1', gloss: 'Attribute 1' },
      { type: 'double_bubble_map', text: '主题A', gloss: 'Topic A' },
      { type: 'double_bubble_map', text: '相似点 1', gloss: 'Similarity 1' },
      { type: 'mindmap', text: '中心主题', gloss: 'Central Topic' },
      { type: 'mindmap', text: '分支1', gloss: 'Branch 1' },
      { type: 'mindmap', text: '子项1.1', gloss: 'Child 1.1' },
      { type: 'tree_map', text: '根主题', gloss: 'Root Topic' },
      { type: 'tree_map', text: '类别1', gloss: 'Category 1' },
      { type: 'tree_map', text: '项目1.1', gloss: 'Item 1.1' },
      { type: 'brace_map', text: '主题', gloss: 'Topic' },
      { type: 'brace_map', text: '部分1', gloss: 'Part 1' },
      { type: 'brace_map', text: '子部分1.1', gloss: 'Subpart 1.1' },
      { type: 'flow_map', text: '事件流程', gloss: 'Process' },
      { type: 'flow_map', text: '步骤1', gloss: 'Step 1' },
      { type: 'flow_map', text: '子步骤1.1', gloss: 'Substep 1.1' },
      { type: 'multi_flow_map', text: '事件', gloss: 'Main Event' },
      { type: 'multi_flow_map', text: '原因1', gloss: 'Cause 1' },
      { type: 'multi_flow_map', text: '结果1', gloss: 'Effect 1' },
      { type: 'bridge_map', text: '[点击设置]', gloss: '[Click to set]' },
      { type: 'bridge_map', text: '事物A1', gloss: 'Item A1' },
      { type: 'bridge_map', text: '事物B1', gloss: 'Item B1' },
      { type: 'concept_map', text: '焦点问题：请输入', gloss: 'Focus question: Enter' },
    ]

    const store = useDiagramStore()
    for (const row of cases) {
      expect(store.loadDefaultTemplate(row.type), row.type).toBe(true)
      expect(glossOf(row.text), `${row.type} ${row.text}`).toBe(row.gloss)
      expect(store.data?.languages).toEqual({ primary: 'zh', secondary: 'en' })
    }
  })

  it('does not reuse a presenter mirror after dual-language mode is off', () => {
    const ui = useUIStore()
    ui.language = 'zh'
    ui.bilingualUiEnabled = true
    ui.presenterUiLocale = 'en'
    const store = useDiagramStore()
    expect(store.loadDefaultTemplate('mindmap')).toBe(true)
    ui.bilingualUiEnabled = false
    expect(store.loadDefaultTemplate('mindmap')).toBe(true)
    const topic = store.data?.nodes.find((node) => node.id === 'topic')
    expect(topic?.textSecondary ?? '').toBe('')
    const cached = getDefaultTemplate('mindmap', 'zh')
    const branch = (cached?.children as Array<{ textSecondary?: string }> | undefined)?.[0]
    expect(branch?.textSecondary).toBeUndefined()
  })
})
