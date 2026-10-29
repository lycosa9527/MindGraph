/**
 * Two-finger vertical swipe scrolls a long modal's scrollbar.
 *
 * The dialog body is a capped overflow port (see index.css): the mouse wheel
 * and a trackpad already move it. A one-finger drag that starts on a button
 * often never reaches that port. A second finger scrolls the nearest pane
 * that still has room, which is the dialog body once an inner pane is at
 * its end.
 */

const MODAL_TWO_FINGER_SCROLL_SELECTOR = [
  '.el-dialog',
  '.el-drawer',
  '.el-message-box',
  '.swiss-glass-card',
  '.swiss-glass-card-overlay',
  '.mm-canvas-center-modal',
].join(',')

const AXIS_LOCK_PX = 8

export type TwoFingerLock = 'undecided' | 'vertical' | 'horizontal'

type Finger = {
  clientX: number
  clientY: number
  target: EventTarget | null
}

type Session = {
  root: HTMLElement
  originX: number
  originY: number
  lastY: number
  lock: TwoFingerLock
  scrolled: boolean
}

type TouchListLike = {
  length: number
  item: (index: number) => Finger | null
}

let session: Session | null = null
let listening = false
let swallowNextClick = false
let removeInstall: (() => void) | null = null

function modalSurfaceRoot(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof Element)) return null
  let found: HTMLElement | null = null
  let node: Element | null = target
  while (node) {
    if (node instanceof HTMLElement && node.matches(MODAL_TWO_FINGER_SCROLL_SELECTOR)) {
      found = node
    }
    node = node.parentElement
  }
  return found
}

function isVerticallyScrollable(el: HTMLElement): boolean {
  const overflowY = getComputedStyle(el).overflowY
  if (overflowY !== 'auto' && overflowY !== 'scroll' && overflowY !== 'overlay') return false
  return el.scrollHeight - el.clientHeight > 1
}

export function hasVerticalScrollRoom(el: HTMLElement, delta: number): boolean {
  if (delta > 0) return el.scrollTop + el.clientHeight < el.scrollHeight - 1
  if (delta < 0) return el.scrollTop > 0
  return false
}

export function classifyTwoFingerAxis(
  dx: number,
  dy: number,
  current: TwoFingerLock
): TwoFingerLock {
  if (current !== 'undecided') return current
  if (Math.hypot(dx, dy) < AXIS_LOCK_PX) return 'undecided'
  if (Math.abs(dx) > Math.abs(dy)) return 'horizontal'
  return 'vertical'
}

function scrollableChain(target: EventTarget | null, root: HTMLElement): HTMLElement[] {
  if (!(target instanceof Element) || !root.contains(target)) return []
  const chain: HTMLElement[] = []
  let node: Element | null = target
  while (node) {
    if (node instanceof HTMLElement && isVerticallyScrollable(node)) chain.push(node)
    if (node === root) break
    node = node.parentElement
  }
  return node === root ? chain : []
}

function elementDepth(el: HTMLElement): number {
  let depth = 0
  let node: HTMLElement | null = el
  while (node) {
    depth += 1
    node = node.parentElement
  }
  return depth
}

export function mergeScrollChains(first: HTMLElement[], second: HTMLElement[]): HTMLElement[] {
  const seen = new Set<HTMLElement>()
  const merged: HTMLElement[] = []
  for (const el of [...first, ...second]) {
    if (seen.has(el)) continue
    seen.add(el)
    merged.push(el)
  }
  merged.sort((left, right) => elementDepth(right) - elementDepth(left))
  return merged
}

export function pickVerticalScroller(chain: HTMLElement[], delta: number): HTMLElement | null {
  for (const el of chain) {
    if (hasVerticalScrollRoom(el, delta)) return el
  }
  return null
}

function readFingers(event: Event): Finger[] {
  const touches = (event as Event & { touches?: TouchListLike }).touches
  if (!touches || touches.length < 1) return []
  const fingers: Finger[] = []
  const count = Math.min(touches.length, 2)
  for (let index = 0; index < count; index += 1) {
    const touch = touches.item(index)
    if (!touch) continue
    fingers.push({
      clientX: touch.clientX,
      clientY: touch.clientY,
      target: touch.target,
    })
  }
  return fingers
}

function touchCount(event: Event): number {
  const touches = (event as Event & { touches?: TouchListLike }).touches
  return touches?.length ?? 0
}

function centroid(fingers: Finger[]): { x: number; y: number } {
  return {
    x: (fingers[0].clientX + fingers[1].clientX) / 2,
    y: (fingers[0].clientY + fingers[1].clientY) / 2,
  }
}

function detachMoveListeners(): void {
  if (!listening) return
  document.removeEventListener('touchmove', onTouchMove, true)
  document.removeEventListener('touchend', onTouchEnd, true)
  document.removeEventListener('touchcancel', onTouchEnd, true)
  listening = false
}

function onClickCapture(event: MouseEvent): void {
  if (!swallowNextClick) return
  swallowNextClick = false
  if (!(event.target instanceof Element) || !modalSurfaceRoot(event.target)) return
  event.preventDefault()
  event.stopPropagation()
}

function clearSession(suppressClick: boolean): void {
  const scrolled = session?.scrolled === true
  session = null
  detachMoveListeners()
  if (suppressClick && scrolled) swallowNextClick = true
}

function onTouchMove(event: Event): void {
  if (!session) return
  if (touchCount(event) !== 2) {
    clearSession(true)
    return
  }
  const fingers = readFingers(event)
  if (fingers.length < 2) return
  const point = centroid(fingers)
  const stepY = session.lastY - point.y
  session.lastY = point.y
  session.lock = classifyTwoFingerAxis(
    point.x - session.originX,
    point.y - session.originY,
    session.lock
  )
  // preventDefault on touchmove cancels the click that follows. Wait until
  // the gesture is clearly vertical so a small jitter does not swallow it.
  if (session.lock !== 'vertical') return
  event.preventDefault()
  event.stopPropagation()
  const chain = mergeScrollChains(
    scrollableChain(fingers[0].target, session.root),
    scrollableChain(fingers[1].target, session.root)
  )
  const scroller = pickVerticalScroller(chain, stepY)
  if (scroller) {
    const before = scroller.scrollTop
    scroller.scrollTop = before + stepY
    if (scroller.scrollTop !== before) session.scrolled = true
  }
}

function onTouchEnd(event: Event): void {
  if (touchCount(event) >= 2) return
  clearSession(true)
}

function onTouchStart(event: Event): void {
  const count = touchCount(event)
  if (count < 2) swallowNextClick = false
  if (count !== 2) {
    if (count < 2) clearSession(false)
    return
  }
  const fingers = readFingers(event)
  if (fingers.length < 2) return
  const root = modalSurfaceRoot(fingers[0].target)
  const other = modalSurfaceRoot(fingers[1].target)
  if (!root || root !== other) return
  const point = centroid(fingers)
  session = {
    root,
    originX: point.x,
    originY: point.y,
    lastY: point.y,
    lock: 'undecided',
    scrolled: false,
  }
  if (listening) return
  document.addEventListener('touchmove', onTouchMove, { capture: true, passive: false })
  document.addEventListener('touchend', onTouchEnd, true)
  document.addEventListener('touchcancel', onTouchEnd, true)
  listening = true
}

/** Document listener. One finger is unchanged; two fingers scroll an open modal. */
export function installModalTwoFingerScroll(): () => void {
  if (removeInstall) return removeInstall
  document.addEventListener('touchstart', onTouchStart, { capture: true, passive: true })
  document.addEventListener('click', onClickCapture, true)
  removeInstall = () => {
    document.removeEventListener('touchstart', onTouchStart, true)
    document.removeEventListener('click', onClickCapture, true)
    clearSession(false)
    swallowNextClick = false
    removeInstall = null
  }
  return removeInstall
}
