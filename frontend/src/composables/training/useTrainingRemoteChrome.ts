import { onUnmounted, ref, watch, type Ref } from 'vue'

type OrientationLock = { unlock: () => Promise<void> }
type WakeLockSentinel = {
  released?: boolean
  release: () => Promise<void>
  addEventListener: (type: 'release', handler: () => void) => void
  removeEventListener: (type: 'release', handler: () => void) => void
}

function orientationQuery(): MediaQueryList | null {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return null
  }
  return window.matchMedia('(orientation: portrait)')
}

async function lockLandscape(): Promise<void> {
  const screenObj = window.screen as Screen & {
    orientation?: { lock?: (mode: string) => Promise<void> }
  }
  const lock = screenObj.orientation?.lock
  if (!lock) return
  try {
    await lock.call(screenObj.orientation, 'landscape')
  } catch {
    // iOS and some browsers reject orientation lock.
  }
}

async function unlockOrientation(): Promise<void> {
  const screenObj = window.screen as Screen & {
    orientation?: OrientationLock
  }
  if (!screenObj.orientation?.unlock) return
  try {
    await screenObj.orientation.unlock()
  } catch {
    // Unlock is optional.
  }
}

async function requestWake(): Promise<WakeLockSentinel | null> {
  const nav = navigator as Navigator & {
    wakeLock?: { request: (type: 'screen') => Promise<WakeLockSentinel> }
  }
  if (!nav.wakeLock) return null
  try {
    return await nav.wakeLock.request('screen')
  } catch {
    return null
  }
}

export function useTrainingRemoteChrome(live: () => boolean): { isPortrait: Ref<boolean> } {
  const media = orientationQuery()
  const isPortrait = ref(Boolean(media?.matches))
  let wake: WakeLockSentinel | null = null

  function onOrientation(): void {
    isPortrait.value = Boolean(media?.matches)
  }

  function onWakeReleased(): void {
    wake = null
    if (live() && document.visibilityState === 'visible') {
      void syncChrome()
    }
  }

  async function dropWake(): Promise<void> {
    if (!wake) return
    const held = wake
    wake = null
    held.removeEventListener('release', onWakeReleased)
    await held.release().catch(() => undefined)
  }

  async function syncChrome(): Promise<void> {
    if (!live() || document.visibilityState === 'hidden') {
      await dropWake()
      if (!live()) await unlockOrientation()
      return
    }
    await lockLandscape()
    if (wake && !wake.released) return
    await dropWake()
    const next = await requestWake()
    if (!next) return
    wake = next
    next.addEventListener('release', onWakeReleased)
  }

  function onShown(): void {
    if (document.visibilityState === 'visible') {
      void syncChrome()
    }
  }

  media?.addEventListener('change', onOrientation)
  window.addEventListener('orientationchange', onOrientation)
  document.addEventListener('visibilitychange', onShown)
  watch(live, () => {
    void syncChrome()
  }, { immediate: true })

  onUnmounted(() => {
    media?.removeEventListener('change', onOrientation)
    window.removeEventListener('orientationchange', onOrientation)
    document.removeEventListener('visibilitychange', onShown)
    void dropWake()
    void unlockOrientation()
  })

  return { isPortrait }
}