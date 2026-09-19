/**
 * Drag + persist the new-canvas classroom remote. Position is device-local
 * (110" IFP teachers move it to where they stand).
 */
import { type Ref, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
  CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
  CLASSROOM_REMOTE_DRAG_THRESHOLD_PX,
  CLASSROOM_REMOTE_EDGE_GAP_PX,
  CLASSROOM_REMOTE_MARGIN_PX,
  CLASSROOM_REMOTE_STATUS_GAP_PX,
  CLASSROOM_REMOTE_STORAGE_KEY,
  type ClassroomRemotePersisted,
  type ClassroomRemoteTabId,
  DEFAULT_CLASSROOM_REMOTE_TAB,
  isClassroomRemoteTabId,
} from '@/canvas-ribbon/mindMapClassroomRemoteTypes'

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
    return {
      left: parsed.left,
      top: parsed.top,
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

const sharedHidden = ref(readStoredRemote()?.hidden === true)

export function useClassroomRemoteVisibility() {
  function persistHidden(): void {
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
      hidden: sharedHidden.value,
      tab: DEFAULT_CLASSROOM_REMOTE_TAB,
    })
  }

  function setHidden(next: boolean): void {
    sharedHidden.value = next
    persistHidden()
  }

  function toggleHidden(): void {
    setHidden(!sharedHidden.value)
  }

  return { hidden: sharedHidden, setHidden, toggleHidden }
}

function viewportSize(): { width: number; height: number } {
  if (typeof window === 'undefined') {
    return { width: 1280, height: 720 }
  }
  return { width: window.innerWidth, height: window.innerHeight }
}

export function useClassroomRemotePosition(panelRef: Ref<HTMLElement | null>) {
  const stored = readStoredRemote()
  const fallback = defaultClassroomRemotePosition(
    CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
    CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
    viewportSize().width,
    viewportSize().height
  )
  const left = ref(stored?.left ?? fallback.left)
  const top = ref(stored?.top ?? fallback.top)
  const activeTab = ref<ClassroomRemoteTabId>(stored?.tab ?? DEFAULT_CLASSROOM_REMOTE_TAB)
  const dragging = ref(false)

  let pointerId: number | null = null
  let startClientX = 0
  let startClientY = 0
  let startLeft = 0
  let startTop = 0
  let moved = false

  function panelSize(): { width: number; height: number } {
    const el = panelRef.value
    if (!el) {
      return {
        width: CLASSROOM_REMOTE_DEFAULT_WIDTH_PX,
        height: CLASSROOM_REMOTE_DEFAULT_HEIGHT_PX,
      }
    }
    return { width: el.offsetWidth, height: el.offsetHeight }
  }

  function persist(): void {
    writeStoredRemote({
      left: left.value,
      top: top.value,
      hidden: sharedHidden.value,
      tab: activeTab.value,
    })
  }

  function clampToViewport(): void {
    const size = panelSize()
    const view = viewportSize()
    const next = clampClassroomRemotePosition(
      left.value,
      top.value,
      size.width,
      size.height,
      view.width,
      view.height
    )
    left.value = next.left
    top.value = next.top
  }

  function resetToDefault(): void {
    const size = panelSize()
    const view = viewportSize()
    const next = defaultClassroomRemotePosition(size.width, size.height, view.width, view.height)
    left.value = next.left
    top.value = next.top
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
    const size = panelSize()
    const view = viewportSize()
    const next = clampClassroomRemotePosition(
      startLeft + dx,
      startTop + dy,
      size.width,
      size.height,
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
  })

  return {
    left,
    top,
    activeTab,
    dragging,
    setActiveTab,
    clampToViewport,
    resetToDefault,
    onHandlePointerDown,
    onHandlePointerMove,
    onHandlePointerUp,
  }
}
