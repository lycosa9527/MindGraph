/**
 * Mind Classroom (思维讲堂) — frontend launch prefs only.
 */

export const MIND_CLASSROOM_MASTERY_IDS = ['first_look', 'review', 'teach'] as const
export type MindClassroomMasteryId = (typeof MIND_CLASSROOM_MASTERY_IDS)[number]
export const DEFAULT_MIND_CLASSROOM_MASTERY: MindClassroomMasteryId = 'first_look'

/** canvas_tour = walk the map; slide_deck = dual-pane AI slides */
export const MIND_CLASSROOM_PRESENTATION_IDS = ['canvas_tour', 'slide_deck'] as const
export type MindClassroomPresentationId = (typeof MIND_CLASSROOM_PRESENTATION_IDS)[number]
export const DEFAULT_MIND_CLASSROOM_PRESENTATION: MindClassroomPresentationId = 'canvas_tour'

/** Scope for 画布语音巡讲 only */
export const MIND_CLASSROOM_TOUR_SCOPE_IDS = ['main_branch', 'each_node'] as const
export type MindClassroomTourScopeId = (typeof MIND_CLASSROOM_TOUR_SCOPE_IDS)[number]
export const DEFAULT_MIND_CLASSROOM_TOUR_SCOPE: MindClassroomTourScopeId = 'main_branch'

export const MIND_CLASSROOM_TONE_IDS = [
  'classroom',
  'story',
  'dialogue',
  'socratic',
  'fast',
  'close_read',
  'examples',
  'exam_outline',
] as const
export type MindClassroomToneId = (typeof MIND_CLASSROOM_TONE_IDS)[number]
export const DEFAULT_MIND_CLASSROOM_TONE: MindClassroomToneId = 'classroom'

/** Visual presets for 幻灯片讲解 (few, distinct). */
export const MIND_CLASSROOM_SLIDE_STYLE_IDS = [
  'general',
  'chalkboard',
  'comic',
  'handdrawn',
] as const
export type MindClassroomSlideStyleId = (typeof MIND_CLASSROOM_SLIDE_STYLE_IDS)[number]
export const DEFAULT_MIND_CLASSROOM_SLIDE_STYLE: MindClassroomSlideStyleId = 'general'

/** @deprecated */
export type MindClassroomStyleId = MindClassroomPresentationId | 'concise' | 'ppt' | 'node_focus'

const MASTERY_STORAGE_KEY = 'mg-mind-classroom-mastery'
const PRESENTATION_STORAGE_KEY = 'mg-mind-classroom-presentation'
const TOUR_SCOPE_STORAGE_KEY = 'mg-mind-classroom-tour-scope'
const SLIDE_STYLE_STORAGE_KEY = 'mg-mind-classroom-slide-style'
const LEGACY_STYLE_STORAGE_KEY = 'mg-mind-classroom-style'
const TONE_STORAGE_KEY = 'mg-mind-classroom-tone'

export function isMindClassroomMasteryId(value: unknown): value is MindClassroomMasteryId {
  return (
    typeof value === 'string' && (MIND_CLASSROOM_MASTERY_IDS as readonly string[]).includes(value)
  )
}

export function isMindClassroomPresentationId(
  value: unknown
): value is MindClassroomPresentationId {
  return (
    typeof value === 'string' &&
    (MIND_CLASSROOM_PRESENTATION_IDS as readonly string[]).includes(value)
  )
}

export function isMindClassroomTourScopeId(value: unknown): value is MindClassroomTourScopeId {
  return (
    typeof value === 'string' &&
    (MIND_CLASSROOM_TOUR_SCOPE_IDS as readonly string[]).includes(value)
  )
}

export function isMindClassroomToneId(value: unknown): value is MindClassroomToneId {
  return typeof value === 'string' && (MIND_CLASSROOM_TONE_IDS as readonly string[]).includes(value)
}

export function isMindClassroomSlideStyleId(value: unknown): value is MindClassroomSlideStyleId {
  return (
    typeof value === 'string' &&
    (MIND_CLASSROOM_SLIDE_STYLE_IDS as readonly string[]).includes(value)
  )
}

/** Map retired style ids from localStorage to the current set. */
function mapLegacySlideStyle(raw: string | null): MindClassroomSlideStyleId | null {
  if (!raw) return null
  if (isMindClassroomSlideStyleId(raw)) return raw
  if (raw === 'whiteboard' || raw === 'clean' || raw === 'oriental') return 'general'
  if (raw === 'journal') return 'handdrawn'
  return null
}

function mapLegacyStyleToPresentation(raw: string | null): MindClassroomPresentationId | null {
  if (raw === 'concise' || raw === 'node_focus') return 'canvas_tour'
  if (raw === 'ppt') return 'slide_deck'
  if (isMindClassroomPresentationId(raw)) return raw
  return null
}

function mapLegacyToTourScope(raw: string | null): MindClassroomTourScopeId | null {
  if (raw === 'node_focus') return 'each_node'
  if (raw === 'concise' || raw === 'ppt' || raw === 'canvas_tour') return 'main_branch'
  return null
}

export function loadMindClassroomMastery(): MindClassroomMasteryId {
  if (typeof localStorage === 'undefined') return DEFAULT_MIND_CLASSROOM_MASTERY
  try {
    const raw = localStorage.getItem(MASTERY_STORAGE_KEY)
    return isMindClassroomMasteryId(raw) ? raw : DEFAULT_MIND_CLASSROOM_MASTERY
  } catch {
    return DEFAULT_MIND_CLASSROOM_MASTERY
  }
}

export function saveMindClassroomMastery(mastery: MindClassroomMasteryId): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(MASTERY_STORAGE_KEY, mastery)
  } catch {
    /* ignore */
  }
}

export function loadMindClassroomPresentation(): MindClassroomPresentationId {
  if (typeof localStorage === 'undefined') return DEFAULT_MIND_CLASSROOM_PRESENTATION
  try {
    const next = localStorage.getItem(PRESENTATION_STORAGE_KEY)
    if (isMindClassroomPresentationId(next)) return next
    const legacyRaw = localStorage.getItem(LEGACY_STYLE_STORAGE_KEY)
    const legacy = mapLegacyStyleToPresentation(legacyRaw)
    if (legacy) {
      localStorage.setItem(PRESENTATION_STORAGE_KEY, legacy)
      return legacy
    }
    // migrate old ppt / node_focus stored under presentation key
    if (next === 'ppt') {
      localStorage.setItem(PRESENTATION_STORAGE_KEY, 'slide_deck')
      localStorage.setItem(TOUR_SCOPE_STORAGE_KEY, 'main_branch')
      return 'slide_deck'
    }
    if (next === 'node_focus') {
      localStorage.setItem(PRESENTATION_STORAGE_KEY, 'canvas_tour')
      localStorage.setItem(TOUR_SCOPE_STORAGE_KEY, 'each_node')
      return 'canvas_tour'
    }
    return DEFAULT_MIND_CLASSROOM_PRESENTATION
  } catch {
    return DEFAULT_MIND_CLASSROOM_PRESENTATION
  }
}

export function saveMindClassroomPresentation(presentation: MindClassroomPresentationId): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(PRESENTATION_STORAGE_KEY, presentation)
  } catch {
    /* ignore */
  }
}

export function loadMindClassroomTourScope(): MindClassroomTourScopeId {
  if (typeof localStorage === 'undefined') return DEFAULT_MIND_CLASSROOM_TOUR_SCOPE
  try {
    const next = localStorage.getItem(TOUR_SCOPE_STORAGE_KEY)
    if (isMindClassroomTourScopeId(next)) return next
    const legacy =
      mapLegacyToTourScope(localStorage.getItem(PRESENTATION_STORAGE_KEY)) ??
      mapLegacyToTourScope(localStorage.getItem(LEGACY_STYLE_STORAGE_KEY))
    if (legacy) {
      localStorage.setItem(TOUR_SCOPE_STORAGE_KEY, legacy)
      return legacy
    }
    return DEFAULT_MIND_CLASSROOM_TOUR_SCOPE
  } catch {
    return DEFAULT_MIND_CLASSROOM_TOUR_SCOPE
  }
}

export function saveMindClassroomTourScope(scope: MindClassroomTourScopeId): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(TOUR_SCOPE_STORAGE_KEY, scope)
  } catch {
    /* ignore */
  }
}

/** @deprecated Prefer loadMindClassroomPresentation. */
export function loadMindClassroomStyle(): MindClassroomPresentationId {
  return loadMindClassroomPresentation()
}

/** @deprecated Prefer saveMindClassroomPresentation. */
export function saveMindClassroomStyle(style: MindClassroomPresentationId): void {
  saveMindClassroomPresentation(style)
}

export function loadMindClassroomTone(): MindClassroomToneId {
  if (typeof localStorage === 'undefined') return DEFAULT_MIND_CLASSROOM_TONE
  try {
    const raw = localStorage.getItem(TONE_STORAGE_KEY)
    return isMindClassroomToneId(raw) ? raw : DEFAULT_MIND_CLASSROOM_TONE
  } catch {
    return DEFAULT_MIND_CLASSROOM_TONE
  }
}

export function saveMindClassroomTone(tone: MindClassroomToneId): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(TONE_STORAGE_KEY, tone)
  } catch {
    /* ignore */
  }
}

export function loadMindClassroomSlideStyle(): MindClassroomSlideStyleId {
  if (typeof localStorage === 'undefined') return DEFAULT_MIND_CLASSROOM_SLIDE_STYLE
  try {
    const raw = localStorage.getItem(SLIDE_STYLE_STORAGE_KEY)
    const mapped = mapLegacySlideStyle(raw)
    if (mapped) {
      if (raw !== mapped) localStorage.setItem(SLIDE_STYLE_STORAGE_KEY, mapped)
      return mapped
    }
    return DEFAULT_MIND_CLASSROOM_SLIDE_STYLE
  } catch {
    return DEFAULT_MIND_CLASSROOM_SLIDE_STYLE
  }
}

export function saveMindClassroomSlideStyle(style: MindClassroomSlideStyleId): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(SLIDE_STYLE_STORAGE_KEY, style)
  } catch {
    /* ignore */
  }
}
