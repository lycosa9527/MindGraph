import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useOrgGenerationCacheNoticeStore } from '@/stores/orgGenerationCacheNotice'
import { noteOrgGenerationCacheResult, withOrgGenerationCacheBypass } from '@/utils/orgGenerationCache'

describe('org generation cache notice', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows the notice on cached payloads and adds skip_cache next time', () => {
    noteOrgGenerationCacheResult({ cached: true })
    expect(useOrgGenerationCacheNoticeStore().visible).toBe(true)
    expect(withOrgGenerationCacheBypass({ prompt: '光合作用' })).toEqual({
      prompt: '光合作用',
      skip_cache: true,
    })
  })

  it('hides the notice after a fresh result', () => {
    noteOrgGenerationCacheResult({ cached: true })
    noteOrgGenerationCacheResult({ cached: false })
    expect(useOrgGenerationCacheNoticeStore().visible).toBe(false)
    expect(withOrgGenerationCacheBypass({ prompt: '光合作用' })).toEqual({ prompt: '光合作用' })
  })

  it('keeps the notice when a parallel model returns without a cached flag', () => {
    noteOrgGenerationCacheResult({ cached: true })
    noteOrgGenerationCacheResult({})
    expect(useOrgGenerationCacheNoticeStore().visible).toBe(true)
    expect(withOrgGenerationCacheBypass({ prompt: '光合作用' }).skip_cache).toBe(true)
  })
})
