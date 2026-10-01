/**
 * Drag + persist the new-canvas classroom remote. Position is device-local
 * (110" IFP teachers move it to where they stand).
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'

import {
  CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
  CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
  CLASSROOM_REMOTE_DRAG_THRESHOLD_PX,
  CLASSROOM_REMOTE_EDGE_GAP_PX,
  CLASSROOM_REMOTE_MARGIN_PX,
  CLASSROOM_REMOTE_MIN_HEIGHT_PX,
  CLASSROOM_REMOTE_MIN_WIDTH_PX,
  CLASSROOM_REMOTE_STATUS_GAP_PX,
  CLASSROOM_REMOTE_STORAGE_KEY,
  type ClassroomRemoteFrame,
  type ClassroomRemotePersisted,
  type ClassroomRemoteTabId,
  DEFAULT_CLASSROOM_REMOTE_TAB,
  isClassroomRemoteTabId,
} from '@/canvas-ribbon/mindMapClassroomRemoteTypes'
import { useAuthStore } from '@/stores'
import { authFetch } from '@/utils/api'

const CLASSROOM_REMOTE_PREFS_PATH = '/api/auth/diagram-preferences'
const CLASSROOM_REMOTE_PREFS_DEBOUNCE_MS = 400

export function clampClassroomRemotePosition(
  left: number,
  top: number,
  width: number,
  height: number,
  viewportW: number,
  viewportH: number,
  margin = CLASSROOM_REMOTE_MARGIN_PX
): { left: number; top: number } {
  const maxLeft = Math.max(margin, viewportW - width - margin)
  const maxTop = Math.max(margin, viewportH - height - margin)
  return {
    left: Math.min(maxLeft, Math.max(margin, left)),
    top: Math.min(maxTop, Math.max(margin, top)),
  }
}

/** Minimum that still fits the tabs, capped when the viewport is smaller. */
export function classroomRemoteMinSize(
  viewportW: number,
  viewportH: number
): { width: number; height: number } {
  const maxWidth = Math.max(1, viewportW - CLASSROOM_REMOTE_EDGE_GAP_PX * 2)
  const maxHeight = Math.max(1, viewportH - CLASSROOM_REMOTE_EDGE_GAP_PX * 2)
  return {
    width: Math.min(CLASSROOM_REMOTE_MIN_WIDTH_PX, maxWidth),
    height: Math.min(CLASSROOM_REMOTE_MIN_HEIGHT_PX, maxHeight),
  }
}

/**
 * Resize from a fixed top-left. Width and height stay inside the viewport
 * edge gap and do not drop below the minimum unless the viewport is smaller.
 */
export function resizeClassroomRemoteFrame(
  left: number,
  top: number,
  width: number,
  height: number,
  viewportW: number,
  viewportH: number
): { width: number; height: number } {
  const min = classroomRemoteMinSize(viewportW, viewportH)
  const roomW = Math.max(1, viewportW - left - CLASSROOM_REMOTE_EDGE_GAP_PX)
  const roomH = Math.max(1, viewportH - top - CLASSROOM_REMOTE_EDGE_GAP_PX)
  const minW = Math.min(min.width, roomW)
  const minH = Math.min(min.height, roomH)
  return {
    width: Math.min(roomW, Math.max(minW, width)),
    height: Math.min(roomH, Math.max(minH, height)),
  }
}

/** Keep the panel on screen. May shift the origin when the viewport shrinks. */
export function clampClassroomRemoteFrame(
  frame: ClassroomRemoteFrame,
  viewportW: number,
  viewportH: number
): ClassroomRemoteFrame {
  const min = classroomRemoteMinSize(viewportW, viewportH)
  let width = Math.max(min.width, frame.width)
  let height = Math.max(min.height, frame.height)
  const maxWidth = Math.max(min.width, viewportW - CLASSROOM_REMOTE_EDGE_GAP_PX * 2)
  const maxHeight = Math.max(min.height, viewportH - CLASSROOM_REMOTE_EDGE_GAP_PX * 2)
  width = Math.min(width, maxWidth)
  height = Math.min(height, maxHeight)
  const pos = clampClassroomRemotePosition(
    frame.left,
    frame.top,
    width,
    height,
    viewportW,
    viewportH
  )
  return { left: pos.left, top: pos.top, width, height }
}

export function defaultClassroomRemotePosition(
  width: number,
  height: number,
  viewportW: number,
  viewportH: number
): { left: number; top: number } {
  return clampClassroomRemotePosition(
    viewportW - width - CLASSROOM_REMOTE_EDGE_GAP_PX,
    viewportH - height - CLASSROOM_REMOTE_STATUS_GAP_PX,
    width,
    height,
    viewportW,
    viewportH
  )
}

export function parseClassroomRemotePersisted(
  raw: string | null | undefined
): ClassroomRemotePersisted | null {
  if (typeof raw !== 'string' || raw.length === 0) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as Partial<ClassroomRemotePersisted>
    if (typeof parsed.left !== 'number' || !Number.isFinite(parsed.left)) {
      return null
    }
    if (typeof parsed.top !== 'number' || !Number.isFinite(parsed.top)) {
      return null
    }
    const tab = isClassroomRemoteTabId(parsed.tab) ? parsed.tab : DEFAULT_CLASSROOM_REMOTE_TAB
    const width =
      typeof parsed.width === 'number' && Number.isFinite(parsed.width) && parsed.width > 0
        ? parsed.width
        : CLASSROOM_REMOTE_DEFAULT_WIDTH_PX
    const height =
      typeof parsed.height === 'number' && Number.isFinite(parsed.height) && parsed.height > 0
        ? parsed.height
        : CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX
    return {
      left: parsed.left,
      top: parsed.top,
      width,
      height,
      hidden: parsed.hidden === true,
      tab,
    }
  } catch {
    return null
  }
}

function readStoredRemote(): ClassroomRemotePersisted | null {
  if (typeof localStorage === 'undefined') {
    return null
  }
  try {
    return parseClassroomRemotePersisted(localStorage.getItem(CLASSROOM_REMOTE_STORAGE_KEY))
  } catch {
    return null
  }
}

function writeStoredRemote(next: ClassroomRemotePersisted): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  try {
    localStorage.setItem(CLASSROOM_REMOTE_STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* quota / private mode */
  }
}

function viewportSize(): { width: number; height: number } {
  if (typeof window === 'undefined') {
    return { width: 1280, height: 720 }
  }
  return { width: window.innerWidth, height: window.innerHeight }
}

const sharedHidden = ref(readStoredRemote()?.hidden === true)
let remotePersistTimer = 0
let remotePersistInFlight = false

function persistHiddenLocal(): void {
  const stored = readStoredRemote()
  if (stored) {
    writeStoredRemote({ ...stored, hidden: sharedHidden.value })
    return
  }
  const view = viewportSize()
  const fallback = defaultClassroomRemotePosition(
    CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
    CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
    view.width,
    view.height
  )
  writeStoredRemote({
    left: fallback.left,
    top: fallback.top,
    width: CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
    height: CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
    hidden: sharedHidden.value,
    tab: DEFAULT_CLASSROOM_REMOTE_TAB,
  })
}

export function useClassroomRemoteVisibility() {
  const authStore = useAuthStore()

  function hydrateFromUser(): void {
    if (!authStore.user) {
      return
    }
    sharedHidden.value = authStore.user.classroomRemoteVisible === false
    persistHiddenLocal()
  }

  function patchAuthUser(visible: boolean): void {
    if (!authStore.user) {
      return
    }
    authStore.patchPersistedUser({ classroomRemoteVisible: visible })
  }

  async function persistNow(): Promise<void> {
    if (!authStore.isAuthenticated) {
      return
    }
    remotePersistInFlight = true
    const visible = !sharedHidden.value
    try {
      const response = await authFetch(CLASSROOM_REMOTE_PREFS_PATH, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ classroom_remote_visible: visible }),
      })
      if (!response.ok) {
        return
      }
      const data = (await response.json().catch(() => ({}))) as {
        classroom_remote_visible?: boolean
      }
      const saved = data.classroom_remote_visible !== false
      sharedHidden.value = !saved
      persistHiddenLocal()
      patchAuthUser(saved)
    } finally {
      remotePersistInFlight = false
    }
  }

  function schedulePersist(): void {
    if (!authStore.isAuthenticated) {
      return
    }
    if (remotePersistTimer !== 0) {
      window.clearTimeout(remotePersistTimer)
    }
    remotePersistTimer = window.setTimeout(() => {
      remotePersistTimer = 0
      void persistNow()
    }, CLASSROOM_REMOTE_PREFS_DEBOUNCE_MS)
  }

  hydrateFromUser()
  watch(
    () => authStore.user?.id,
    () => {
      if (remotePersistInFlight || remotePersistTimer !== 0) {
        return
      }
      hydrateFromUser()
    }
  )

  function setHidden(next: boolean): void {
    sharedHidden.value = next
    persistHiddenLocal()
    patchAuthUser(!next)
    schedulePersist()
  }

  function toggleHidden(): void {
    setHidden(!sharedHidden.value)
  }

  return { hidden: sharedHidden, setHidden, toggleHidden }
}

export function useClassroomRemotePosition() {
  const stored = readStoredRemote()
  const fallback = defaultClassroomRemotePosition(
    CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
    CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
    viewportSize().width,
    viewportSize().height
  )
  const left = ref(stored?.left ?? fallback.left)
  const top = ref(stored?.top ?? fallback.top)
  const width = ref(stored?.width ?? CLASSROOM_REMOTE_DEFAULT_WIDTH_PX)
  const height = ref(stored?.height ?? CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX)
  const activeTab = ref<ClassroomRemoteTabId>(stored?.tab ?? DEFAULT_CLASSROOM_REMOTE_TAB)
  const dragging = ref(false)
  const resizing = ref(false)

  let pointerId: number | null = null
  let resizePointerId: number | null = null
  let startClientX = 0
  let startClientY = 0
  let startLeft = 0
  let startTop = 0
  let startWidth = 0
  let startHeight = 0
  let moved = false

  function applyFrame(frame: ClassroomRemoteFrame): void {
    left.value = frame.left
    top.value = frame.top
    width.value = frame.width
    height.value = frame.height
  }

  function persist(): void {
    writeStoredRemote({
      left: left.value,
      top: top.value,
      width: width.value,
      height: height.value,
      hidden: sharedHidden.value,
      tab: activeTab.value,
    })
  }

  function clampToViewport(): void {
    const view = viewportSize()
    applyFrame(
      clampClassroomRemoteFrame(
        {
          left: left.value,
          top: top.value,
          width: width.value,
          height: height.value,
        },
        view.width,
        view.height
      )
    )
  }

  function resetToDefault(): void {
    const view = viewportSize()
    const size = resizeClassroomRemoteFrame(
      0,
      0,
      CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
      CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
      view.width,
      view.height
    )
    const next = defaultClassroomRemotePosition(size.width, size.height, view.width, view.height)
    applyFrame({ ...next, width: size.width, height: size.height })
    persist()
  }

  function setActiveTab(tab: ClassroomRemoteTabId): void {
    activeTab.value = tab
    requestAnimationFrame(() => {
      clampToViewport()
      persist()
    })
  }

  function onHandlePointerDown(event: PointerEvent): void {
    if (event.button !== 0 && event.pointerType === 'mouse') {
      return
    }
    const handle = event.currentTarget
    if (!(handle instanceof HTMLElement)) {
      return
    }
    pointerId = event.pointerId
    startClientX = event.clientX
    startClientY = event.clientY
    startLeft = left.value
    startTop = top.value
    moved = false
    dragging.value = true
    handle.setPointerCapture(event.pointerId)
    event.preventDefault()
    event.stopPropagation()
  }

  function onHandlePointerMove(event: PointerEvent): void {
    if (pointerId !== event.pointerId) {
      return
    }
    const dx = event.clientX - startClientX
    const dy = event.clientY - startClientY
    if (
      !moved &&
      Math.abs(dx) < CLASSROOM_REMOTE_DRAG_THRESHOLD_PX &&
      Math.abs(dy) < CLASSROOM_REMOTE_DRAG_THRESHOLD_PX
    ) {
      return
    }
    moved = true
    const view = viewportSize()
    const next = clampClassroomRemotePosition(
      startLeft + dx,
      startTop + dy,
      width.value,
      height.value,
      view.width,
      view.height
    )
    left.value = next.left
    top.value = next.top
  }

  function onHandlePointerUp(event: PointerEvent): void {
    if (pointerId !== event.pointerId) {
      return
    }
    const handle = event.currentTarget
    if (handle instanceof HTMLElement && handle.hasPointerCapture(event.pointerId)) {
      handle.releasePointerCapture(event.pointerId)
    }
    pointerId = null
    dragging.value = false
    if (moved) {
      persist()
    }
  }

  function onResizePointerDown(event: PointerEvent): void {
    if (event.button !== 0 && event.pointerType === 'mouse') {
      return
    }
    const handle = event.currentTarget
    if (!(handle instanceof HTMLElement)) {
      return
    }
    resizePointerId = event.pointerId
    startClientX = event.clientX
    startClientY = event.clientY
    startWidth = width.value
    startHeight = height.value
    resizing.value = true
    handle.setPointerCapture(event.pointerId)
    event.preventDefault()
    event.stopPropagation()
  }

  function onResizePointerMove(event: PointerEvent): void {
    if (resizePointerId !== event.pointerId) {
      return
    }
    const view = viewportSize()
    const next = resizeClassroomRemoteFrame(
      left.value,
      top.value,
      startWidth + (event.clientX - startClientX),
      startHeight + (event.clientY - startClientY),
      view.width,
      view.height
    )
    width.value = next.width
    height.value = next.height
  }

  function onResizePointerUp(event: PointerEvent): void {
    if (resizePointerId !== event.pointerId) {
      return
    }
    const handle = event.currentTarget
    if (handle instanceof HTMLElement && handle.hasPointerCapture(event.pointerId)) {
      handle.releasePointerCapture(event.pointerId)
    }
    resizePointerId = null
    resizing.value = false
    clampToViewport()
    persist()
  }

  function onWindowResize(): void {
    clampToViewport()
    persist()
  }

  watch(activeTab, () => {
    persist()
  })

  onMounted(() => {
    if (stored) {
      clampToViewport()
    } else {
      resetToDefault()
    }
    window.addEventListener('resize', onWindowResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', onWindowResize)
    if (dragging.value || resizing.value) {
      dragging.value = false
      resizing.value = false
      pointerId = null
      resizePointerId = null
      persist()
    }
  })

  return {
    left,
    top,
    width,
    height,
    activeTab,
    dragging,
    resizing,
    setActiveTab,
    clampToViewport,
    resetToDefault,
    onHandlePointerDown,
    onHandlePointerMove,
    onHandlePointerUp,
    onResizePointerDown,
    onResizePointerMove,
    onResizePointerUp,
  }
}
