import { type Ref, createApp, defineComponent, h, nextTick, ref } from 'vue'

import { ElDatePicker } from 'element-plus'

import { describe, expect, it } from 'vitest'

import LsDeadlineField from '@/components/learningSpace/LsDeadlineField.vue'
import {
  DEADLINE_PICKER_PLACEHOLDER,
  deadlineModelToPicker,
  deadlinePickerToModel,
} from '@/utils/deadlineDateTime'

function mountDeadline(initial = ''): {
  app: ReturnType<typeof createApp>
  host: HTMLDivElement
  value: Ref<string>
} {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const value = ref(initial)
  const app = createApp(
    defineComponent({
      setup() {
        return () =>
          h(LsDeadlineField, {
            modelValue: value.value,
            'onUpdate:modelValue': (next: string) => {
              value.value = next
            },
          })
      },
    })
  )
  app.component('ElDatePicker', ElDatePicker)
  app.mount(host)
  return { app, host, value }
}

describe('deadlineDateTime', () => {
  it('maps the form value to the picker and back', () => {
    expect(deadlineModelToPicker('')).toBeNull()
    expect(deadlineModelToPicker('2026-10-24T11:12')).toBe('2026-10-24 11:12')
    expect(deadlineModelToPicker('2026-10-24T11:12:30')).toBe('2026-10-24 11:12')
    expect(deadlinePickerToModel(null)).toBe('')
    expect(deadlinePickerToModel('2026-10-24 09:05')).toBe('2026-10-24T09:05')
    expect(deadlinePickerToModel('2026/10/24 09:05')).toBe('')
  })

  it('shows the shared yyyy/mm/dd hh:mm hint', async () => {
    const mounted = mountDeadline()
    try {
      await nextTick()
      const input = mounted.host.querySelector('input')
      expect(input).toBeInstanceOf(HTMLInputElement)
      expect(input?.getAttribute('placeholder')).toBe(DEADLINE_PICKER_PLACEHOLDER)
    } finally {
      mounted.app.unmount()
      mounted.host.remove()
    }
  })

  it('keeps a chosen deadline on the form model', async () => {
    const mounted = mountDeadline('2026-10-24T11:12')
    try {
      await nextTick()
      const input = mounted.host.querySelector('input')
      expect(input).toBeInstanceOf(HTMLInputElement)
      expect((input as HTMLInputElement).value).toBe('2026/10/24 11:12')

      mounted.value.value = ''
      await nextTick()
      expect((input as HTMLInputElement).value).toBe('')
      expect(input?.getAttribute('placeholder')).toBe('yyyy/mm/dd hh:mm')
    } finally {
      mounted.app.unmount()
      mounted.host.remove()
    }
  })
})
