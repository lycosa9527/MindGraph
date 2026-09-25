/**
 * Device-local position, size, tab, and open state for the quick-access remote.
 */
import { onMounted, onUnmounted, ref } from 'vue'

import {
  QUICK_ACCESS_DRAG_THRESHOLD_PX,
  QUICK_ACCESS_PROMPT_OVERRIDES_KEY,
  QUICK_ACCESS_REMOTE_STORAGE_KEY,
  type QuickAccessPromptOverrides,
  type QuickAccessRemoteFrame,
  type QuickAccessRemotePersisted,
  type QuickAccessRemoteTabId,
  clampQuickAccessFrame,
  clampQuickAccessPosition,
  defaultQuickAccessRemoteFrame,
  nextQuickAccessPromptOverrides,
  parseQuickAccessPromptOverrides,
  parseQuickAccessRemotePersisted,
  resizeQuickAccessFrame,
} from '@/composables/sidebar/quickAccessRemoteModel'
import {
  LANDING_PROMPT_MAX_LENGTH,
  type LandingPromptExampleKey,
} from '@/config/landingQuickAccess'

function viewportSize(): { width: number; height: number } {
  if (typeof window === 'undefined') {
    return { width: 1280, height: 720 }
  }
  return { width: window.innerWidth, height: window.innerHeight }
}

function readStored(): QuickAccessRemotePersisted | null {
  if (typeof localStorage === 'undefined') {
    return null
  }
  try {
    return parseQuickAccessRemotePersisted(localStorage.getItem(QUICK_ACCESS_REMOTE_STORAGE_KEY))
  } catch {
    return null
  }
}

function initialState(): QuickAccessRemotePersisted {
  const view = viewportSize()
  const stored = readStored()
  if (!stored) {
    return {
      ...defaultQuickAccessRemoteFrame(view.width, view.height),
      hidden: true,
      tab: 'diagrams',
    }
  }
  return {
    ...clampQuickAccessFrame(stored, view.width, view.height),
    hidden: stored.hidden,
    tab: stored.tab,
  }
}

const initial = initialState()
const hidden = ref(initial.hidden)
const left = ref(initial.left)
const top = ref(initial.top)
const width = ref(initial.width)
const height = ref(initial.height)
const activeTab = ref<QuickAccessRemoteTabId>(initial.tab)

export const quickAccessRemoteHidden = hidden
export const quickAccessPromptBusy = ref(false)

function readPromptOverrides(): QuickAccessPromptOverrides {
  if (typeof localStorage === 'undefined') {
    return {}
  }
  try {
    return parseQuickAccessPromptOverrides(
      localStorage.getItem(QUICK_ACCESS_PROMPT_OVERRIDES_KEY),
      LANDING_PROMPT_MAX_LENGTH
    )
  } catch {
    return {}
  }
}

const promptOverrides = ref<QuickAccessPromptOverrides>(readPromptOverrides())

function persistPromptOverrides(): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  try {
    localStorage.setItem(QUICK_ACCESS_PROMPT_OVERRIDES_KEY, JSON.stringify(promptOverrides.value))
  } catch {
    /* quota / private mode */
  }
}

export function commitQuickAccessPromptEdit(
  key: LandingPromptExampleKey,
  draft: string,
  fallback: string
): void {
  promptOverrides.value = nextQuickAccessPromptOverrides(
    promptOverrides.value,
    key,
    draft,
    fallback,
    LANDING_PROMPT_MAX_LENGTH
  )
  persistPromptOverrides()
}

export { promptOverrides as quickAccessPromptOverrides }

function persist(): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  const next: QuickAccessRemotePersisted = {
    left: left.value,
    top: top.value,
    width: width.value,
    height: height.value,
    hidden: hidden.value,
    tab: activeTab.value,
  }
  try {
    localStorage.setItem(QUICK_ACCESS_REMOTE_STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* quota / private mode */
  }
}

export function toggleQuickAccessRemote(): void {
  hidden.value = !hidden.value
  persist()
}

export function hideQuickAccessRemote(): void {
  hidden.value = true
  persist()
}

export function setQuickAccessRemoteTab(tab: QuickAccessRemoteTabId): void {
  activeTab.value = tab
  persist()
}

function applyFrame(frame: QuickAccessRemoteFrame): void {
  left.value = frame.left
  top.value = frame.top
  width.value = frame.width
  height.value = frame.height
}

export function useQuickAccessRemoteChrome() {
  const dragging = ref(false)
  const resizing = ref(false)

  let dragPointerId: number | null = null
  let resizePointerId: number | null = null
  let startClientX = 0
  let startClientY = 0
  let startLeft = 0
  let startTop = 0
  let startWidth = 0
  let startHeight = 0
  let dragMoved = false

  function clampToViewport(): void {
    const view = viewportSize()
    applyFrame(
      clampQuickAccessFrame(
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

  function onHandlePointerDown(event: PointerEvent): void {
    if (event.button !== 0 && event.pointerType === 'mouse') {
      return
    }
    const handle = event.currentTarget
    if (!(handle instanceof HTMLElement)) {
      return
    }
    dragPointerId = event.pointerId
    startClientX = event.clientX
    startClientY = event.clientY
    startLeft = left.value
    startTop = top.value
    dragMoved = false
    dragging.value = true
    handle.setPointerCapture(event.pointerId)
    event.preventDefault()
  }

  function onHandlePointerMove(event: PointerEvent): void {
    if (dragPointerId !== event.pointerId) {
      return
    }
    const dx = event.clientX - startClientX
    const dy = event.clientY - startClientY
    if (
      !dragMoved &&
      Math.abs(dx) < QUICK_ACCESS_DRAG_THRESHOLD_PX &&
      Math.abs(dy) < QUICK_ACCESS_DRAG_THRESHOLD_PX
    ) {
      return
    }
    dragMoved = true
    const view = viewportSize()
    const next = clampQuickAccessPosition(
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
    if (dragPointerId !== event.pointerId) {
      return
    }
    const handle = event.currentTarget
    if (handle instanceof HTMLElement && handle.hasPointerCapture(event.pointerId)) {
      handle.releasePointerCapture(event.pointerId)
    }
    dragPointerId = null
    dragging.value = false
    if (dragMoved) {
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
    const next = resizeQuickAccessFrame(
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

  onMounted(() => {
    clampToViewport()
    window.addEventListener('resize', onWindowResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', onWindowResize)
    if (dragging.value || resizing.value) {
      dragging.value = false
      resizing.value = false
      dragPointerId = null
      resizePointerId = null
      persist()
    }
  })

  return {
    hidden,
    left,
    top,
    width,
    height,
    activeTab,
    dragging,
    resizing,
    onHandlePointerDown,
    onHandlePointerMove,
    onHandlePointerUp,
    onResizePointerDown,
    onResizePointerMove,
    onResizePointerUp,
  }
}
