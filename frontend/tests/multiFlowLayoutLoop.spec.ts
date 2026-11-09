import { createApp, defineComponent, h, nextTick, ref, watch } from 'vue'

import { describe, expect, it } from 'vitest'

import { useThinkingMapTypographyRemeasure } from '@/composables/diagram/useThinkingMapTypographyRemeasure'
import { useMultiFlowLayoutSlice } from '@/stores/diagram/multiFlowLayout'
import type { DiagramContext } from '@/stores/diagram/types'

function layoutCtx(): DiagramContext {
  return {
    type: ref('multi_flow_map'),
    topicNodeWidth: ref<number | null>(null),
  } as DiagramContext
}

describe('multi-flow layout does not rebuild on an unchanged measure', () => {
  it('ignores a zero event width so the arrows keep a topic gap', () => {
    const ctx = layoutCtx()
    const { setTopicNodeWidth } = useMultiFlowLayoutSlice(ctx)

    setTopicNodeWidth(0)
    setTopicNodeWidth(Number.NaN)

    expect(ctx.topicNodeWidth.value).toBeNull()

    setTopicNodeWidth(128)
    expect(ctx.topicNodeWidth.value).toBe(128)
  })

  it('does not write the ref when the event reports the same width again', () => {
    const ctx = layoutCtx()
    const { setTopicNodeWidth } = useMultiFlowLayoutSlice(ctx)
    let writes = 0
    watch(
      ctx.topicNodeWidth,
      () => {
        writes += 1
      },
      { flush: 'sync' }
    )

    setTopicNodeWidth(128)
    setTopicNodeWidth(128)

    expect(writes).toBe(1)
  })
})

describe('thinking-map typography remeasure', () => {
  it('does not remeasure when layout replaces the style object with the same fonts', async () => {
    const style = ref<{ fontSize?: number; fontWeight?: string } | undefined>({
      fontSize: 16,
      fontWeight: 'bold',
    })
    let calls = 0
    const Probe = defineComponent({
      setup() {
        useThinkingMapTypographyRemeasure({
          enabled: () => true,
          style: () => style.value,
          remeasure: () => {
            calls += 1
          },
        })
        return () => h('div')
      },
    })
    const app = createApp(Probe)
    app.mount(document.createElement('div'))
    await nextTick()

    style.value = { fontSize: 16, fontWeight: 'bold' }
    await nextTick()
    expect(calls).toBe(0)

    style.value = { fontSize: 22, fontWeight: 'bold' }
    await nextTick()
    expect(calls).toBe(1)

    app.unmount()
  })
})
