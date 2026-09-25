/**
 * Pure frame math, prompt edits, and open-target choice for the quick-access remote.
 */
import {
  LANDING_PROMPT_EXAMPLE_KEYS,
  type LandingPromptExampleKey,
} from '@/config/landingQuickAccess'
import type { DiagramType } from '@/types'

export const QUICK_ACCESS_REMOTE_STORAGE_KEY = 'mg.quick-access-remote.v1'
export const QUICK_ACCESS_PROMPT_OVERRIDES_KEY = 'mg.quick-access-remote.prompts.v1'
export const QUICK_ACCESS_REMOTE_TABS = ['diagrams', 'prompts'] as const
export type QuickAccessRemoteTabId = (typeof QUICK_ACCESS_REMOTE_TABS)[number]

export const QUICK_ACCESS_EDGE_GAP_PX = 16
export const QUICK_ACCESS_MARGIN_PX = 8
export const QUICK_ACCESS_MIN_WIDTH_PX = 220
export const QUICK_ACCESS_MIN_HEIGHT_PX = 200
export const QUICK_ACCESS_DEFAULT_WIDTH_PX = 280
export const QUICK_ACCESS_DEFAULT_HEIGHT_PX = 420
export const QUICK_ACCESS_DEFAULT_LEFT_PX = 272
export const QUICK_ACCESS_DRAG_THRESHOLD_PX = 4

const TAB_SET = new Set<string>(QUICK_ACCESS_REMOTE_TABS)

export function isQuickAccessRemoteTabId(
  value: string | null | undefined
): value is QuickAccessRemoteTabId {
  return typeof value === 'string' && TAB_SET.has(value)
}

export type QuickAccessRemoteFrame = {
  left: number
  top: number
  width: number
  height: number
}

export type QuickAccessRemotePersisted = QuickAccessRemoteFrame & {
  hidden: boolean
  tab: QuickAccessRemoteTabId
}

export type QuickAccessDiagramOpen = 'push' | 'replace' | 'reload'

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Minimum that still fits the tabs, capped when the viewport is smaller. */
export function quickAccessMinSize(
  viewportW: number,
  viewportH: number
): { width: number; height: number } {
  const maxWidth = Math.max(1, viewportW - QUICK_ACCESS_EDGE_GAP_PX * 2)
  const maxHeight = Math.max(1, viewportH - QUICK_ACCESS_EDGE_GAP_PX * 2)
  return {
    width: Math.min(QUICK_ACCESS_MIN_WIDTH_PX, maxWidth),
    height: Math.min(QUICK_ACCESS_MIN_HEIGHT_PX, maxHeight),
  }
}

/**
 * Resize from a fixed top-left. Width and height stay inside the viewport
 * edge gap and do not drop below the minimum unless the viewport is smaller.
 */
export function resizeQuickAccessFrame(
  left: number,
  top: number,
  width: number,
  height: number,
  viewportW: number,
  viewportH: number
): { width: number; height: number } {
  const min = quickAccessMinSize(viewportW, viewportH)
  const roomW = Math.max(1, viewportW - left - QUICK_ACCESS_EDGE_GAP_PX)
  const roomH = Math.max(1, viewportH - top - QUICK_ACCESS_EDGE_GAP_PX)
  const minW = Math.min(min.width, roomW)
  const minH = Math.min(min.height, roomH)
  return {
    width: Math.min(roomW, Math.max(minW, width)),
    height: Math.min(roomH, Math.max(minH, height)),
  }
}

export function clampQuickAccessPosition(
  left: number,
  top: number,
  width: number,
  height: number,
  viewportW: number,
  viewportH: number
): { left: number; top: number } {
  const maxLeft = Math.max(QUICK_ACCESS_MARGIN_PX, viewportW - width - QUICK_ACCESS_MARGIN_PX)
  const maxTop = Math.max(QUICK_ACCESS_MARGIN_PX, viewportH - height - QUICK_ACCESS_MARGIN_PX)
  return {
    left: Math.min(maxLeft, Math.max(QUICK_ACCESS_MARGIN_PX, left)),
    top: Math.min(maxTop, Math.max(QUICK_ACCESS_MARGIN_PX, top)),
  }
}

/** Keep the panel on screen. May shift the origin when the viewport shrinks. */
export function clampQuickAccessFrame(
  frame: QuickAccessRemoteFrame,
  viewportW: number,
  viewportH: number
): QuickAccessRemoteFrame {
  const min = quickAccessMinSize(viewportW, viewportH)
  let width = Math.max(min.width, frame.width)
  let height = Math.max(min.height, frame.height)
  const maxWidth = Math.max(min.width, viewportW - QUICK_ACCESS_EDGE_GAP_PX * 2)
  const maxHeight = Math.max(min.height, viewportH - QUICK_ACCESS_EDGE_GAP_PX * 2)
  width = Math.min(width, maxWidth)
  height = Math.min(height, maxHeight)
  const pos = clampQuickAccessPosition(frame.left, frame.top, width, height, viewportW, viewportH)
  return { left: pos.left, top: pos.top, width, height }
}

export function defaultQuickAccessRemoteFrame(
  viewportW: number,
  viewportH: number
): QuickAccessRemoteFrame {
  const size = resizeQuickAccessFrame(
    QUICK_ACCESS_DEFAULT_LEFT_PX,
    QUICK_ACCESS_EDGE_GAP_PX,
    QUICK_ACCESS_DEFAULT_WIDTH_PX,
    QUICK_ACCESS_DEFAULT_HEIGHT_PX,
    viewportW,
    viewportH
  )
  return clampQuickAccessFrame(
    {
      left: QUICK_ACCESS_DEFAULT_LEFT_PX,
      top: viewportH - size.height - 24,
      width: size.width,
      height: size.height,
    },
    viewportW,
    viewportH
  )
}

export function parseQuickAccessRemotePersisted(
  raw: string | null | undefined
): QuickAccessRemotePersisted | null {
  if (typeof raw !== 'string' || raw.length === 0) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as Partial<QuickAccessRemotePersisted>
    if (!finite(parsed.left) || !finite(parsed.top)) {
      return null
    }
    const width = finite(parsed.width) ? parsed.width : QUICK_ACCESS_DEFAULT_WIDTH_PX
    const height = finite(parsed.height) ? parsed.height : QUICK_ACCESS_DEFAULT_HEIGHT_PX
    const tab = isQuickAccessRemoteTabId(parsed.tab) ? parsed.tab : 'diagrams'
    return {
      left: parsed.left,
      top: parsed.top,
      width,
      height,
      hidden: parsed.hidden !== false,
      tab,
    }
  } catch {
    return null
  }
}

/**
 * Blank canvas of `targetType`.
 * Push when the canvas is not open. Reload in place when that blank type is
 * already the URL. Otherwise replace the canvas query so the type watch loads it.
 */
export function resolveQuickAccessDiagramOpen(input: {
  onCanvas: boolean
  blankTypeQuery: DiagramType | null
  targetType: DiagramType
}): QuickAccessDiagramOpen {
  if (!input.onCanvas) {
    return 'push'
  }
  if (input.blankTypeQuery === input.targetType) {
    return 'reload'
  }
  return 'replace'
}

/** In-place replacement of a dirty canvas uses the existing leave confirm. */
export function quickAccessReplaceNeedsConfirm(onCanvas: boolean, dirty: boolean): boolean {
  return onCanvas && dirty
}

export type QuickAccessPromptOverrides = Partial<Record<LandingPromptExampleKey, string>>

const PROMPT_KEY_SET = new Set<string>(LANDING_PROMPT_EXAMPLE_KEYS)

function isPromptKey(value: string): value is LandingPromptExampleKey {
  return PROMPT_KEY_SET.has(value)
}

/** Saved prompt text for the six inspiration boxes. Blank and unknown keys are dropped. */
export function parseQuickAccessPromptOverrides(
  raw: string | null | undefined,
  maxLength: number
): QuickAccessPromptOverrides {
  if (typeof raw !== 'string' || raw.length === 0) {
    return {}
  }
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const overrides: QuickAccessPromptOverrides = {}
    for (const [key, value] of Object.entries(parsed)) {
      if (!isPromptKey(key) || typeof value !== 'string') {
        continue
      }
      const text = value.trim().slice(0, maxLength)
      if (text.length > 0) {
        overrides[key] = text
      }
    }
    return overrides
  } catch {
    return {}
  }
}

/** Custom text when the user has edited this box; otherwise the translated preset. */
export function resolveQuickAccessPromptText(
  key: LandingPromptExampleKey,
  fallback: string,
  overrides: QuickAccessPromptOverrides
): string {
  const custom = overrides[key]
  if (typeof custom === 'string' && custom.trim().length > 0) {
    return custom
  }
  return fallback
}

/**
 * Store an edit. A blank edit or text that matches the current preset
 * removes the override so the translated sentence shows again.
 */
export function nextQuickAccessPromptOverrides(
  overrides: QuickAccessPromptOverrides,
  key: LandingPromptExampleKey,
  draft: string,
  fallback: string,
  maxLength: number
): QuickAccessPromptOverrides {
  const text = draft.trim().slice(0, maxLength)
  const next: QuickAccessPromptOverrides = { ...overrides }
  if (text.length === 0 || text === fallback.trim()) {
    delete next[key]
    return next
  }
  next[key] = text
  return next
}
