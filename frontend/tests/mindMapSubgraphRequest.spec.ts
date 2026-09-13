import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import { useAiContentLevelStore } from '@/stores/aiContentLevel'
import type { MindMapSubgraphContext } from '@/utils/mindMapSubgraphContext'
import { buildMindMapSubgraphGenerateBody } from '@/utils/mindMapSubgraphRequest'

const context: MindMapSubgraphContext = {
  topic: '光合作用',
  expandBranch: '光反应',
  referenceBranches: ['碳反应'],
  existingChildren: [],
  isMainBranch: true,
}

describe('buildMindMapSubgraphGenerateBody', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('attaches 专业内容 as generation_instructions when a level is set', () => {
    const store = useAiContentLevelStore()
    store.setLevel('primary')
    const body = buildMindMapSubgraphGenerateBody({
      context,
      language: 'zh',
      llm: 'qwen',
    })
    expect(body.expand_branch).toBe('光反应')
    expect(String(body.prompt)).toContain('要扩展的分支：光反应')
    expect(String(body.prompt)).not.toContain('小学')
    expect(String(body.generation_instructions)).toContain('小学')
    expect(String(body.generation_instructions)).toContain('用语：')
  })

  it('leaves generation_instructions off when the level is unset or general', () => {
    const body = buildMindMapSubgraphGenerateBody({
      context,
      language: 'zh',
      llm: 'qwen',
    })
    expect(body.generation_instructions).toBeUndefined()
  })
})
