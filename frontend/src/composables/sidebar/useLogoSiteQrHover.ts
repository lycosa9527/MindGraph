/**
 * Hover timing for the public site QR overlay (sidebar and login brand).
 * Fine pointer devices only: hold 1.5s to open, leave 250ms to close.
 */
import { onBeforeUnmount, onMounted, readonly, ref } from 'vue'
import type { DeepReadonly, Ref } from 'vue'

const HOVER_OPEN_DELAY_MS = 1500
const HOVER_CLOSE_DELAY_MS = 250

export type LogoSiteQrHover = {
  visible: DeepReadonly<Ref<boolean>>
  onPointerEnter: () => void
  onPointerLeave: () => void
  close: () => void
  clearHoverCloseTimer: () => void
  scheduleHoverClose: () => void
}

export function useLogoSiteQrHover(canOpen: () => boolean = () => true): LogoSiteQrHover {
  const visible = ref(false)
  const prefersHover = ref(false)
  let hoverOpenTimer: ReturnType<typeof setTimeout> | null = null
  let hoverCloseTimer: ReturnType<typeof setTimeout> | null = null

  function clearHoverOpenTimer(): void {
    if (hoverOpenTimer !== null) {
      clearTimeout(hoverOpenTimer)
      hoverOpenTimer = null
    }
  }

  function clearHoverCloseTimer(): void {
    if (hoverCloseTimer !== null) {
      clearTimeout(hoverCloseTimer)
      hoverCloseTimer = null
    }
  }

  function scheduleHoverClose(): void {
    if (!prefersHover.value) {
      return
    }
    clearHoverCloseTimer()
    hoverCloseTimer = setTimeout(() => {
      visible.value = false
      hoverCloseTimer = null
    }, HOVER_CLOSE_DELAY_MS)
  }

  function onPointerEnter(): void {
    if (!prefersHover.value || !canOpen()) {
      return
    }
    clearHoverCloseTimer()
    clearHoverOpenTimer()
    hoverOpenTimer = setTimeout(() => {
      visible.value = true
      hoverOpenTimer = null
    }, HOVER_OPEN_DELAY_MS)
  }

  function onPointerLeave(): void {
    clearHoverOpenTimer()
    if (visible.value) {
      scheduleHoverClose()
    }
  }

  function close(): void {
    clearHoverOpenTimer()
    clearHoverCloseTimer()
    visible.value = false
  }

  onMounted(() => {
    prefersHover.value = window.matchMedia('(hover: hover) and (pointer: fine)').matches
  })

  onBeforeUnmount(() => {
    clearHoverOpenTimer()
    clearHoverCloseTimer()
  })

  return {
    visible: readonly(visible),
    onPointerEnter,
    onPointerLeave,
    close,
    clearHoverCloseTimer,
    scheduleHoverClose,
  }
}
