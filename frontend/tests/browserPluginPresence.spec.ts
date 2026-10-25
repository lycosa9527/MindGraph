import { createApp, defineComponent, h, nextTick, watch } from 'vue'

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'

import {
  BROWSER_PLUGIN_PRESENCE_ATTR,
  BROWSER_PLUGIN_PRESENCE_EVENT,
  bindBrowserPluginPresence,
  isBrowserPluginInstalled,
  useBrowserPluginInstalled,
} from '@/composables/browserPluginPresence'

afterEach(() => {
  document.documentElement.removeAttribute(BROWSER_PLUGIN_PRESENCE_ATTR)
})

describe('browser plugin presence', () => {
  it('reads the extension marker from the document element', () => {
    expect(isBrowserPluginInstalled()).toBe(false)
    document.documentElement.setAttribute(BROWSER_PLUGIN_PRESENCE_ATTR, '1')
    expect(isBrowserPluginInstalled()).toBe(true)
    expect(isBrowserPluginInstalled(document.createElement('div'))).toBe(false)
  })

  it('notifies when the marker appears or the extension announces itself', async () => {
    const seen: boolean[] = []
    const stop = bindBrowserPluginPresence(() => {
      seen.push(isBrowserPluginInstalled())
    })
    document.documentElement.setAttribute(BROWSER_PLUGIN_PRESENCE_ATTR, '1')
    await new Promise((resolve) => {
      setTimeout(resolve, 0)
    })
    document.dispatchEvent(new CustomEvent(BROWSER_PLUGIN_PRESENCE_EVENT))
    stop()
    document.documentElement.removeAttribute(BROWSER_PLUGIN_PRESENCE_ATTR)
    expect(seen).toEqual([true, true])
    expect(isBrowserPluginInstalled()).toBe(false)
  })

  it('hides the install button state once the marker is on the page', async () => {
    document.documentElement.setAttribute(BROWSER_PLUGIN_PRESENCE_ATTR, '1')
    const seen: boolean[] = []
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp(
      defineComponent({
        setup() {
          const installed = useBrowserPluginInstalled()
          watch(installed, (value) => seen.push(value), { immediate: true })
          return () => h('div')
        },
      })
    )
    app.mount(host)
    await nextTick()
    document.documentElement.removeAttribute(BROWSER_PLUGIN_PRESENCE_ATTR)
    await new Promise((resolve) => {
      setTimeout(resolve, 0)
    })
    await nextTick()
    app.unmount()
    host.remove()
    expect(seen[0]).toBe(true)
    expect(seen.at(-1)).toBe(false)
  })

  it('hides the install prompts and leaves the settings download in place', () => {
    const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
    const read = (relative: string) => readFileSync(resolve(root, relative), 'utf8')
    for (const relative of [
      'src/components/mindgraph/InternationalLanding.vue',
      'src/components/panels/mindmate/MindmateInput.vue',
      'src/components/canvas/MindMapDocumentSummaryPanel.vue',
    ]) {
      const source = read(relative)
      expect(source).toContain('useBrowserPluginInstalled')
      expect(source).toContain('!browserPluginInstalled')
    }
    const settings = read('src/components/settings/SettingsAccountPanels.vue')
    expect(settings).toContain('openBrowserPluginPage')
    expect(settings).not.toContain('useBrowserPluginInstalled')
  })
})
