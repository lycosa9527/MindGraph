/**
 * Reveal a seminar answer one character at a time.
 * A long backlog types faster so a quick model does not leave a minute of text waiting.
 */
import { resolveCollabAssistantEndContent } from '@/utils/mindmateSeminarDisplay'

const TYPE_MS = 20
const CATCH_UP_MS = 8
const CATCH_UP_AFTER = 40

function typeDelay(unshown: number): number {
  return unshown > CATCH_UP_AFTER ? CATCH_UP_MS : TYPE_MS
}

/** Advance one user-visible character, keeping a surrogate pair together. */
export function seminarTypewriterStep(text: string, shown: number): number {
  if (shown >= text.length) {
    return shown
  }
  const code = text.charCodeAt(shown)
  if (code >= 0xd800 && code <= 0xdbff && shown + 1 < text.length) {
    return shown + 2
  }
  return shown + 1
}

type CancelTimer = () => void

export function createSeminarTypewriter(options: {
  onPaint: (visible: string) => void
  onDone: () => void
  schedule?: (run: () => void, delayMs: number) => CancelTimer
}) {
  const schedule =
    options.schedule ??
    ((run: () => void, delayMs: number) => {
      const id = setTimeout(run, delayMs)
      return () => clearTimeout(id)
    })

  let target = ''
  let shown = 0
  let sealed = false
  let finished = false
  let cancel: CancelTimer | null = null

  function paint(): void {
    options.onPaint(target.slice(0, shown))
  }

  function finishIfCaughtUp(): boolean {
    if (shown < target.length) {
      return false
    }
    if (sealed && !finished) {
      finished = true
      options.onDone()
    }
    return true
  }

  function tick(): void {
    cancel = null
    if (finishIfCaughtUp()) {
      return
    }
    shown = seminarTypewriterStep(target, shown)
    paint()
    ensureTicking(false)
  }

  function ensureTicking(showFirst: boolean): void {
    if (showFirst && shown < target.length) {
      shown = seminarTypewriterStep(target, shown)
      paint()
    }
    if (finishIfCaughtUp()) {
      return
    }
    if (cancel) {
      return
    }
    cancel = schedule(tick, typeDelay(target.length - shown))
  }

  return {
    push(delta: string): void {
      if (!delta) {
        return
      }
      if (sealed && shown >= target.length) {
        target = ''
        shown = 0
        sealed = false
        finished = false
      }
      if (sealed) {
        return
      }
      const wasCaughtUp = shown >= target.length
      target += delta
      ensureTicking(wasCaughtUp)
    },
    seal(finalText: string): void {
      target = resolveCollabAssistantEndContent(target, finalText)
      sealed = true
      ensureTicking(shown === 0 && target.length > 0)
    },
    isActive(): boolean {
      return target.length > 0 || cancel !== null
    },
    reset(): void {
      if (cancel) {
        cancel()
        cancel = null
      }
      target = ''
      shown = 0
      sealed = false
      finished = false
    },
  }
}
