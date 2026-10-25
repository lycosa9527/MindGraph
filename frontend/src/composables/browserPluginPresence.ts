/**
 * Reads the marker chrome-extension/presence-mark.js writes on MindGraph pages.
 * Keep the attribute and event names in sync with that script.
 */
import { type Ref, onBeforeUnmount, onMounted, readonly, ref } from 'vue'

export const BROWSER_PLUGIN_PRESENCE_ATTR = 'data-mindgraph-extension'
export const BROWSER_PLUGIN_PRESENCE_EVENT = 'mindgraph-extension-installed'

export function isBrowserPluginInstalled(
  root: Element | null = typeof document === 'undefined' ? null : document.documentElement
): boolean {
  return root?.getAttribute(BROWSER_PLUGIN_PRESENCE_ATTR) === '1'
}

/** Listen until the extension marks this document. Returns the unsubscribe. */
export function bindBrowserPluginPresence(onChange: () => void): () => void {
  document.addEventListener(BROWSER_PLUGIN_PRESENCE_EVENT, onChange)
  const root = document.documentElement
  const observer = new MutationObserver(onChange)
  observer.observe(root, {
    attributes: true,
    attributeFilter: [BROWSER_PLUGIN_PRESENCE_ATTR],
  })
  return () => {
    document.removeEventListener(BROWSER_PLUGIN_PRESENCE_EVENT, onChange)
    observer.disconnect()
  }
}

export function useBrowserPluginInstalled(): Readonly<Ref<boolean>> {
  const installed = ref(isBrowserPluginInstalled())
  let stop: (() => void) | null = null

  onMounted(() => {
    installed.value = isBrowserPluginInstalled()
    stop = bindBrowserPluginPresence(() => {
      installed.value = isBrowserPluginInstalled()
    })
  })

  onBeforeUnmount(() => {
    stop?.()
    stop = null
  })

  return readonly(installed)
}
