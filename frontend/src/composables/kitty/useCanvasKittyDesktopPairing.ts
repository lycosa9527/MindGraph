/**
 * Desktop canvas: Kitty mobile-session indicator, ephemeral WS scope, desktop_focus publish.
 */
import { type ComputedRef, type Ref, computed, onUnmounted, watch } from 'vue'

import { scopeMatchesKittyMobileActive } from '@/composables/kitty/kittyDesktopMobileActiveHub'
import { useKittyDesktopFocusPublish } from '@/composables/kitty/useKittyDesktopFocus'
import { useKittyUserMobileActive } from '@/composables/kitty/useKittyUserMobileActive'
import { useOneSentenceStore } from '@/stores/oneSentence'

export function useCanvasKittyDesktopPairing(options: {
  currentDiagramId: ComputedRef<string | null>
  hasDiagramContent: ComputedRef<boolean>
  authIsAuthenticated: ComputedRef<boolean>
  isViewer: ComputedRef<boolean>
  kittyFeatureEnabled: ComputedRef<boolean>
  onLibraryScopeSwitchedCleanup: (previousScope: string) => void
}) {
  const oneSentence = useOneSentenceStore()

  /** Same SoT as canvas-owner / one-sentence: library id or shared ephemeral. */
  const kittyWsSessionScope = computed(
    () => options.currentDiagramId.value ?? oneSentence.diagramScope
  )

  const kittyUserMobilePollOn = computed(
    () =>
      options.kittyFeatureEnabled.value &&
      options.authIsAuthenticated.value &&
      !options.isViewer.value
  )

  const {
    active: userMobileKittyActive,
    scopes: userMobileKittyScopes,
    primaryScope: userMobileKittyPrimaryScope,
  } = useKittyUserMobileActive(kittyUserMobilePollOn)

  const desktopPairingScopeId = computed(() => kittyWsSessionScope.value)

  const showKittyDesktopIndicator = computed(() => {
    if (
      !options.kittyFeatureEnabled.value ||
      !options.authIsAuthenticated.value ||
      options.isViewer.value
    ) {
      return false
    }
    return scopeMatchesKittyMobileActive(desktopPairingScopeId.value, {
      active: userMobileKittyActive.value,
      scopes: userMobileKittyScopes.value,
      primaryScope: userMobileKittyPrimaryScope.value,
    })
  })

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

  watch(options.currentDiagramId, (nextId, prevId) => {
    if (nextId === prevId) return
    const oldScope =
      typeof prevId === 'string' && prevId.length > 0 ? prevId : oneSentence.diagramScope
    options.onLibraryScopeSwitchedCleanup(oldScope)
  })

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
    kittyEphemeralScope: computed(() => oneSentence.ephemeralScope),
    kittyWsSessionScope,
    showKittyDesktopIndicator,
  }
}
