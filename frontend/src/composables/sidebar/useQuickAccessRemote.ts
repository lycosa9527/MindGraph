/**
 * Device-local position, size, and tab for the quick-access remote.
 * Open state and custom inspiration prompts follow the account.
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'

import {
  QUICK_ACCESS_DRAG_THRESHOLD_PX,
  QUICK_ACCESS_PROMPT_OVERRIDES_KEY,
  QUICK_ACCESS_REMOTE_STORAGE_KEY,
  QUICK_ACCESS_SPEC_REPLAY_MS,
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
  quickAccessReplayPhase,
  resizeQuickAccessFrame,
} from '@/composables/sidebar/quickAccessRemoteModel'
import { loadQuickAccessSpecs } from '@/composables/sidebar/quickAccessSpecSync'
import {
  LANDING_PROMPT_MAX_LENGTH,
  type LandingPromptExampleKey,
} from '@/config/landingQuickAccess'
import { useAuthStore } from '@/stores/auth'
import type { ModelLoadPhase } from '@/stores/llmResults'
import { authFetch } from '@/utils/api'

const QUICK_ACCESS_PREFS_PATH = '/api/auth/diagram-preferences'
const QUICK_ACCESS_PREFS_DEBOUNCE_MS = 400

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

function waitAbortable(ms: number, signal: AbortSignal): Promise<boolean> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve(false)
      return
    }
    const timer = window.setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve(true)
    }, ms)
    const onAbort = (): void => {
      window.clearTimeout(timer)
      resolve(false)
    }
    signal.addEventListener('abort', onAbort, { once: true })
  })
}

/** Drive the prompt ring for three seconds. False when the run is cancelled. */
export async function playQuickAccessSpecReplay(
  setPhase: (phase: ModelLoadPhase) => void,
  signal: AbortSignal
): Promise<boolean> {
  const started = Date.now()
  while (Date.now() - started < QUICK_ACCESS_SPEC_REPLAY_MS) {
    if (signal.aborted) {
      return false
    }
    setPhase(quickAccessReplayPhase(Date.now() - started))
    const remaining = QUICK_ACCESS_SPEC_REPLAY_MS - (Date.now() - started)
    const slice = Math.min(100, remaining)
    if (slice <= 0) {
      break
    }
    const waited = await waitAbortable(slice, signal)
    if (!waited) {
      return false
    }
  }
  return !signal.aborted
}

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

let promptPersistTimer = 0
let promptPersistInFlight = false

function patchPromptUser(overrides: QuickAccessPromptOverrides): void {
  const authStore = useAuthStore()
  if (!authStore.user) {
    return
  }
  authStore.patchPersistedUser({ quickAccessPromptOverrides: { ...overrides } })
}

async function persistPromptsNow(): Promise<void> {
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return
  }
  promptPersistInFlight = true
  try {
    const response = await authFetch(QUICK_ACCESS_PREFS_PATH, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quick_access_prompt_overrides: promptOverrides.value }),
    })
    if (!response.ok) {
      return
    }
    const data = (await response.json().catch(() => ({}))) as {
      quick_access_prompt_overrides?: QuickAccessPromptOverrides
    }
    const saved = parseQuickAccessPromptOverrides(
      JSON.stringify(data.quick_access_prompt_overrides ?? {}),
      LANDING_PROMPT_MAX_LENGTH
    )
    promptOverrides.value = saved
    persistPromptOverrides()
    patchPromptUser(saved)
  } finally {
    promptPersistInFlight = false
  }
}

function schedulePromptPersist(): void {
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return
  }
  if (promptPersistTimer !== 0) {
    window.clearTimeout(promptPersistTimer)
  }
  promptPersistTimer = window.setTimeout(() => {
    promptPersistTimer = 0
    void persistPromptsNow()
  }, QUICK_ACCESS_PREFS_DEBOUNCE_MS)
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
  patchPromptUser(promptOverrides.value)
  schedulePromptPersist()
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

let visiblePersistTimer = 0
let visiblePersistInFlight = false

function patchAuthUser(visible: boolean): void {
  const authStore = useAuthStore()
  if (!authStore.user) {
    return
  }
  authStore.patchPersistedUser({ quickAccessRemoteVisible: visible })
}

async function persistVisibleNow(): Promise<void> {
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return
  }
  visiblePersistInFlight = true
  const visible = !hidden.value
  try {
    const response = await authFetch(QUICK_ACCESS_PREFS_PATH, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quick_access_remote_visible: visible }),
    })
    if (!response.ok) {
      return
    }
    const data = (await response.json().catch(() => ({}))) as {
      quick_access_remote_visible?: boolean
    }
    const saved = data.quick_access_remote_visible === true
    hidden.value = !saved
    persist()
    patchAuthUser(saved)
  } finally {
    visiblePersistInFlight = false
  }
}

function scheduleVisiblePersist(): void {
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return
  }
  if (visiblePersistTimer !== 0) {
    window.clearTimeout(visiblePersistTimer)
  }
  visiblePersistTimer = window.setTimeout(() => {
    visiblePersistTimer = 0
    void persistVisibleNow()
  }, QUICK_ACCESS_PREFS_DEBOUNCE_MS)
}

function publishVisible(): void {
  persist()
  patchAuthUser(!hidden.value)
  scheduleVisiblePersist()
}

export function toggleQuickAccessRemote(): void {
  hidden.value = !hidden.value
  publishVisible()
}

export function hideQuickAccessRemote(): void {
  hidden.value = true
  publishVisible()
}

export function useQuickAccessRemoteAccount(): void {
  const authStore = useAuthStore()

  function hydrateFromUser(): void {
    if (!authStore.user) {
      return
    }
    if (!visiblePersistInFlight && visiblePersistTimer === 0) {
      hidden.value = authStore.user.quickAccessRemoteVisible !== true
      persist()
    }
    if (!promptPersistInFlight && promptPersistTimer === 0) {
      promptOverrides.value = parseQuickAccessPromptOverrides(
        JSON.stringify(authStore.user.quickAccessPromptOverrides ?? {}),
        LANDING_PROMPT_MAX_LENGTH
      )
      persistPromptOverrides()
    }
    void loadQuickAccessSpecs()
  }

  hydrateFromUser()
  watch(
    () =>
      [
        authStore.user?.id,
        authStore.user?.quickAccessRemoteVisible === true,
        JSON.stringify(authStore.user?.quickAccessPromptOverrides ?? {}),
      ] as const,
    () => {
      hydrateFromUser()
    }
  )
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
