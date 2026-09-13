/**
 * ESP32 演讲模式 Start: open presentation if needed, then start slides
 * after the existing rail/fullscreen settle — no second fit pipeline.
 */

export type SlideRemoteDesktopPlayOptions = {
  isRailOpen: () => boolean
  openRail: () => void
  shouldUseSlidesTool: () => boolean
  setSlidesTool: () => void
}

export function createSlideRemoteDesktopPlay(options: SlideRemoteDesktopPlayOptions): {
  requestPlay: () => void
  consumePending: () => boolean
  clearPending: () => void
} {
  let pending = false

  function consumePending(): boolean {
    if (!pending) {
      return false
    }
    pending = false
    if (!options.shouldUseSlidesTool()) {
      return false
    }
    options.setSlidesTool()
    return true
  }

  function requestPlay(): void {
    const alreadyPending = pending
    pending = true
    if (!options.isRailOpen()) {
      options.openRail()
      return
    }
    if (alreadyPending) {
      return
    }
    consumePending()
  }

  function clearPending(): void {
    pending = false
  }

  return { requestPlay, consumePending, clearPending }
}
