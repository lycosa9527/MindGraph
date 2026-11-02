import { createApp, defineComponent, h, ref } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  builderCanvasRibbonHosted,
  builderRibbonToolOwner,
} from '@/composables/training/builderCanvasRibbon'
import { useBuilderCanvasRibbonMerge } from '@/composables/training/useBuilderCanvasRibbonMerge'

const routePath = vi.hoisted(() => ({ value: '/training/builder/1' }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: routePath.value }),
}))

describe('useBuilderCanvasRibbonMerge', () => {
  beforeEach(() => {
    routePath.value = '/training/builder/1'
    builderRibbonToolOwner.value = 'course'
    builderCanvasRibbonHosted.value = false
  })

  function mountRibbon(classicOpen = false) {
    const classic = ref(classicOpen)
    const selectTab = vi.fn()
    const setActiveTab = vi.fn()
    const setClassic = vi.fn((open: boolean) => {
      classic.value = open
    })
    let api: ReturnType<typeof useBuilderCanvasRibbonMerge> | undefined
    const app = createApp(
      defineComponent({
        setup() {
          api = useBuilderCanvasRibbonMerge({ classic, selectTab, setActiveTab, setClassic })
          return () => h('div')
        },
      })
    )
    const el = document.createElement('div')
    app.mount(el)
    if (!api) throw new Error('expected ribbon merge')
    return {
      api,
      classic,
      selectTab,
      setActiveTab,
      setClassic,
      stop: () => app.unmount(),
    }
  }

  it('opens canvas tools on the first canvas tab click', () => {
    const { api, selectTab, setActiveTab, setClassic, stop } = mountRibbon()
    expect(builderCanvasRibbonHosted.value).toBe(true)
    api.onRibbonTab('edit')
    expect(setActiveTab).toHaveBeenCalledWith('edit')
    expect(setClassic).toHaveBeenCalledWith(true)
    expect(selectTab).not.toHaveBeenCalled()
    expect(builderRibbonToolOwner.value).toBe('canvas')
    expect(api.quietCanvasTabs.value).toBe(false)
    stop()
    expect(builderCanvasRibbonHosted.value).toBe(false)
    expect(builderRibbonToolOwner.value).toBe('course')
  })

  it('returns to course tools when the open canvas tab collapses', () => {
    const { api, classic, selectTab, stop } = mountRibbon(true)
    builderRibbonToolOwner.value = 'canvas'
    selectTab.mockImplementation(() => {
      classic.value = false
    })
    api.onRibbonTab('edit')
    expect(selectTab).toHaveBeenCalledWith('edit')
    expect(builderRibbonToolOwner.value).toBe('course')
    expect(api.quietCanvasTabs.value).toBe(true)
    stop()
  })

  it('keeps the open toolbar when a second canvas leaves', () => {
    const first = mountRibbon()
    builderRibbonToolOwner.value = 'canvas'
    const second = mountRibbon()
    second.stop()
    expect(builderCanvasRibbonHosted.value).toBe(true)
    expect(builderRibbonToolOwner.value).toBe('canvas')
    first.stop()
    expect(builderCanvasRibbonHosted.value).toBe(false)
    expect(builderRibbonToolOwner.value).toBe('course')
  })

  it('keeps canvas tab clicks local outside the course builder', () => {
    routePath.value = '/editor'
    const { api, selectTab, setActiveTab, stop } = mountRibbon()
    expect(builderCanvasRibbonHosted.value).toBe(false)
    api.onRibbonTab('file')
    expect(selectTab).toHaveBeenCalledWith('file')
    expect(setActiveTab).not.toHaveBeenCalled()
    expect(builderRibbonToolOwner.value).toBe('course')
    stop()
  })
})
