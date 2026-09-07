import { afterEach, describe, expect, it } from 'vitest'

import {
  setFollowNodeStyleToolbar,
  useFollowNodeStyleToolbar,
} from '@/composables/canvasToolbar/useFollowNodeStyleToolbar'

const STORAGE_KEY = 'mindgraph.mindmap.followNodeStyleToolbar'

describe('useFollowNodeStyleToolbar', () => {
  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY)
    setFollowNodeStyleToolbar(true)
  })

  it('defaults to following the selected node', () => {
    const { followEnabled } = useFollowNodeStyleToolbar()
    expect(followEnabled.value).toBe(true)
  })

  it('persists off so the floating node style bar can stay hidden', () => {
    const { followEnabled, setFollowEnabled } = useFollowNodeStyleToolbar()
    setFollowEnabled(false)
    expect(followEnabled.value).toBe(false)
    expect(localStorage.getItem(STORAGE_KEY)).toBe('0')
  })
})
