/**
 * Gate mounting the `/auth` COS `<video>` while body-level overlays are open.
 */
import { computed, onBeforeUnmount, onMounted, ref, type ComputedRef, type Ref } from 'vue'

import { documentHasAuthLoginHeroBlockingOverlay } from '@/utils/authLoginHeroVideoLayer'

export function useAuthLoginHeroDomOverlayBlocked(): Ref<boolean> {
  const blocked = ref(false)
  let observer: MutationObserver | null = null

  onMounted(() => {
    const sync = (): void => {
      blocked.value = documentHasAuthLoginHeroBlockingOverlay()
    }
    sync()
    observer = new MutationObserver(sync)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style'],
    })
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  return blocked
}

export function useAuthLoginHeroVideoMountAllowed(
  baseMayPlay: ComputedRef<boolean>
): ComputedRef<boolean> {
  const domOverlayBlocked = useAuthLoginHeroDomOverlayBlocked()
  return computed(() => baseMayPlay.value && !domOverlayBlocked.value)
}
