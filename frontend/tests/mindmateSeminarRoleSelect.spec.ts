import { createApp, defineComponent, nextTick, ref } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import MindmateSeminarRoleSelect from '@/components/mindmate/MindmateSeminarRoleSelect.vue'
import {
  clearSeminarCustomRoles,
  rememberSeminarCustomRole,
  seminarCustomRoles,
} from '@/utils/seminarCustomRoles'

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
  }),
}))

interface Harness {
  host: HTMLDivElement
  role: { value: string }
  unmount: () => void
}

function mountSelect(initial = 'observer'): Harness {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const role = ref(initial)
  const HarnessComponent = defineComponent({
    components: { MindmateSeminarRoleSelect },
    setup() {
      return { role }
    },
    template:
      '<MindmateSeminarRoleSelect :model-value="role" @update:model-value="role = $event" />',
  })
  const app = createApp(HarnessComponent)
  app.mount(host)
  return {
    host,
    role,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

function optionButtons(): HTMLButtonElement[] {
  return Array.from(document.body.querySelectorAll<HTMLButtonElement>('.mm-role-select__option'))
}

function menuElement(): HTMLElement | null {
  return document.body.querySelector<HTMLElement>('.mm-role-select__menu')
}

describe('MindmateSeminarRoleSelect', () => {
  beforeEach(() => {
    clearSeminarCustomRoles()
  })

  it('opens the menu and picks a shared custom role', async () => {
    rememberSeminarCustomRole('青铜')
    const harness = mountSelect('observer')
    const trigger = harness.host.querySelector<HTMLButtonElement>('.mm-role-select__trigger')
    expect(trigger).toBeTruthy()
    trigger?.click()
    await nextTick()
    expect(menuElement()).toBeTruthy()
    const options = optionButtons()
    const custom = options.find((button) => button.textContent?.includes('青铜'))
    expect(custom).toBeTruthy()
    custom?.click()
    await nextTick()
    expect(harness.role.value).toBe('青铜')
    expect(harness.host.querySelector('.mm-role-select__label')?.textContent).toBe('青铜')
    expect(menuElement()).toBeNull()
    harness.unmount()
  })

  it('creates a custom role from the footer and selects it immediately', async () => {
    const harness = mountSelect('observer')
    harness.host.querySelector<HTMLButtonElement>('.mm-role-select__trigger')?.click()
    await nextTick()
    document.body.querySelector<HTMLButtonElement>('.mm-role-select__add')?.click()
    await nextTick()
    const input = document.body.querySelector<HTMLInputElement>('.mm-role-select__edit-input')
    expect(input).toBeTruthy()
    if (input) {
      input.value = '白银'
      input.dispatchEvent(new Event('input'))
    }
    await nextTick()
    document.body.querySelector<HTMLButtonElement>('.mm-role-select__edit-ok')?.click()
    await nextTick()
    expect(harness.role.value).toBe('白银')
    expect(seminarCustomRoles.value).toContain('白银')
    expect(harness.host.querySelector('.mm-role-select__label')?.textContent).toBe('白银')
    // Re-open: the created role stays listed as a selectable option.
    harness.host.querySelector<HTMLButtonElement>('.mm-role-select__trigger')?.click()
    await nextTick()
    const options = optionButtons()
    expect(options.some((button) => button.textContent?.includes('白银'))).toBe(true)
    harness.unmount()
    expect(menuElement()).toBeNull()
  })

  it('keeps showing the custom label for a model value set from outside', async () => {
    const harness = mountSelect('青铜')
    await nextTick()
    expect(harness.host.querySelector('.mm-role-select__label')?.textContent).toBe('青铜')
    expect(seminarCustomRoles.value).toContain('青铜')
    harness.unmount()
  })
})
