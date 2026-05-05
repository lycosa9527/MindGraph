/**
 * Desktop canvas: Kitty mobile-session indicator, ephemeral WS scope, desktop_focus publish.
 */
import { computed, onUnmounted, ref, watch, type ComputedRef, type Ref } from 'vue'

import { useKittyDesktopFocusPublish } from '@/composables/kitty/useKittyDesktopFocusPublish'
import { useKittyMobileLaneArmed } from '@/composables/kitty/useKittyMobileLaneArmed'

export function useCanvasKittyDesktopPairing(options: {
  currentDiagramId: ComputedRef<string | null>
  hasDiagramContent: ComputedRef<boolean>
  authIsAuthenticated: ComputedRef<boolean>
  isViewer: ComputedRef<boolean>
  kittyFeatureEnabled: ComputedRef<boolean>
  onLibraryScopeSwitchedCleanup: (previousScope: string) => void
}) {
  const kittyEphemeralScope = ref(crypto.randomUUID())
  const kittyWsSessionScope = computed(
    () => options.currentDiagramId.value ?? kittyEphemeralScope.value
  )

  const kittyMobileLanePollOn = computed(
    () =>
      options.kittyFeatureEnabled.value &&
      options.authIsAuthenticated.value &&
      !options.isViewer.value &&
      options.currentDiagramId.value != null &&
      options.currentDiagramId.value !== ''
  )

  const { armed: mobileKittySessionVisible } = useKittyMobileLaneArmed(
    options.currentDiagramId as Ref<string | null>,
    kittyMobileLanePollOn
  )

  const showKittyDesktopIndicator = computed(
    () =>
      options.kittyFeatureEnabled.value &&
      options.authIsAuthenticated.value &&
      !options.isViewer.value &&
      options.currentDiagramId.value != null &&
      options.currentDiagramId.value !== '' &&
      mobileKittySessionVisible.value
  )

  const kittyDesktopFocusPublishOn = computed(
    () =>
      options.kittyFeatureEnabled.value &&
      options.authIsAuthenticated.value &&
      !options.isViewer.value &&
      options.hasDiagramContent.value
  )

  useKittyDesktopFocusPublish({
    libraryDiagramId: options.currentDiagramId as Ref<string | null | undefined>,
    enabled: kittyDesktopFocusPublishOn,
  })

  watch(
    options.currentDiagramId,
    (nextId, prevId) => {
      if (nextId === prevId) return
      const oldScope =
        typeof prevId === 'string' && prevId.length > 0 ? prevId : kittyEphemeralScope.value
      if (nextId == null || nextId === '') {
        kittyEphemeralScope.value = crypto.randomUUID()
      }
      options.onLibraryScopeSwitchedCleanup(oldScope)
    }
  )

  onUnmounted(() => {
    const scope = kittyWsSessionScope.value
    const activeLib = options.currentDiagramId.value
    const cleanupKittyRedis =
      options.authIsAuthenticated.value &&
      options.kittyFeatureEnabled.value &&
      !(activeLib != null && activeLib !== '' && scope === activeLib)
    if (cleanupKittyRedis) {
      fetch(`/api/kitty/cleanup/${encodeURIComponent(scope)}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
      }).catch(() => {})
    }
  })

  return {
    kittyEphemeralScope,
    kittyWsSessionScope,
    showKittyDesktopIndicator,
  }
}
