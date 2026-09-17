import { describe, expect, it, vi } from 'vitest'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: {
      customLlmEnabled: true,
      customLlmModel: '校本大模型',
    },
  }),
}))

import { useOrgCustomLlm } from '@/composables/llm/useOrgCustomLlm'

describe('useOrgCustomLlm', () => {
  it('exposes one canvas slot and the school model name', () => {
    const { canvasModels, displayNameForModel, customLlmEnabled } = useOrgCustomLlm()
    expect(customLlmEnabled.value).toBe(true)
    expect(canvasModels.value).toEqual(['qwen'])
    expect(displayNameForModel('qwen')).toBe('校本大模型')
  })
})
