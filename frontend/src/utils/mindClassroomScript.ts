/**
 * Build Mind Classroom lecture steps from the mind-map outline + user prefs.
 */
import type { AiContentLevelId } from '@/config/aiContentLevels'
import type {
  MindClassroomMasteryId,
  MindClassroomPresentationId,
  MindClassroomToneId,
  MindClassroomTourScopeId,
} from '@/config/mindClassroom'
import type { Connection, DiagramNode } from '@/types'
import {
  type MindMapSlide,
  type MindMapSlideTraversalMode,
  buildMindMapSlides,
} from '@/utils/mindMapSlides'

export interface MindClassroomLectureStep {
  id: string
  kind: 'overview' | 'branch' | 'closing'
  title: string
  caption: string
  /** Bullet lines shown on slide-deck cards */
  bullets: string[]
  focusNodeIds: string[]
  branchNodeId?: string
  dwellMs: number
  /** Visual theme index for slide cards */
  themeIndex: number
}

export interface MindClassroomScriptOptions {
  mastery: MindClassroomMasteryId
  presentation: MindClassroomPresentationId
  tourScope: MindClassroomTourScopeId
  tone: MindClassroomToneId
  audienceLevel: AiContentLevelId
  audienceTitle: string
  t: (key: string, params?: Record<string, unknown>) => string
}

const SLIDE_THEME_COUNT = 5

function traversalForOptions(opts: MindClassroomScriptOptions): MindMapSlideTraversalMode {
  if (opts.presentation === 'slide_deck') {
    // Slide decks always stay concise; tour scope only applies to canvas walkthroughs.
    return 'firstLevel'
  }
  return opts.tourScope === 'each_node' ? 'deep' : 'firstLevel'
}

function childBulletList(slide: MindMapSlide, nodeById: Map<string, DiagramNode>): string[] {
  if (!slide.branchNodeId) return []
  return slide.focusNodeIds
    .filter((id) => id !== slide.branchNodeId)
    .map((id) => String(nodeById.get(id)?.text ?? '').trim())
    .filter(Boolean)
    .slice(0, 6)
}

function childTitlesHint(bullets: string[], opts: MindClassroomScriptOptions): string {
  if (!bullets.length) return opts.t('canvas.mindClassroom.lecture.script.leafNode')
  return bullets.join('、')
}

function baseDwellMs(
  caption: string,
  mastery: MindClassroomMasteryId,
  tone: MindClassroomToneId
): number {
  const chars = caption.length
  let ms = 2800 + Math.min(9000, chars * 55)
  if (mastery === 'first_look') ms += 800
  if (mastery === 'teach') ms += 400
  if (tone === 'fast') ms = Math.max(2200, ms * 0.65)
  if (tone === 'close_read') ms += 1200
  if (tone === 'socratic') ms += 600
  return Math.round(ms)
}

function narrateOverview(
  slide: MindMapSlide,
  opts: MindClassroomScriptOptions,
  childHint: string
): string {
  return opts.t(`canvas.mindClassroom.lecture.script.overview.${opts.tone}`, {
    topic: slide.title,
    mastery: opts.t(`canvas.mindClassroom.settings.mastery.${opts.mastery}.title`),
    audience: opts.audienceTitle,
    branches: childHint || opts.t('canvas.mindClassroom.lecture.script.noBranches'),
  })
}

function narrateBranch(
  slide: MindMapSlide,
  opts: MindClassroomScriptOptions,
  childHint: string,
  index: number,
  total: number
): string {
  return opts.t(`canvas.mindClassroom.lecture.script.branch.${opts.tone}`, {
    title: slide.title,
    children: childHint,
    index,
    total,
    audience: opts.audienceTitle,
  })
}

function narrateClosing(topic: string, opts: MindClassroomScriptOptions): string {
  return opts.t(`canvas.mindClassroom.lecture.script.closing.${opts.mastery}`, {
    topic,
    audience: opts.audienceTitle,
  })
}

export function buildMindClassroomLectureSteps(
  nodes: DiagramNode[],
  connections: Connection[],
  getDescendantIds: (rootNodeId: string) => Set<string>,
  opts: MindClassroomScriptOptions
): MindClassroomLectureStep[] {
  if (!nodes.length) return []

  const slides = buildMindMapSlides(nodes, connections, getDescendantIds, traversalForOptions(opts))
  if (!slides.length) return []

  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const overview = slides[0]
  const branches = slides.slice(1)
  const steps: MindClassroomLectureStep[] = []
  let themeCursor = 0

  if (overview) {
    const overviewBullets =
      overview.kind === 'overview'
        ? branches
            .map((b) => b.title)
            .filter(Boolean)
            .slice(0, 6)
        : childBulletList(overview, nodeById)
    const caption = narrateOverview(
      overview,
      opts,
      overviewBullets.join('、') || opts.t('canvas.mindClassroom.lecture.script.noBranches')
    )
    steps.push({
      id: `overview-${overview.id}`,
      kind: 'overview',
      title: overview.title,
      caption,
      bullets: overviewBullets,
      focusNodeIds: overview.focusNodeIds,
      branchNodeId: overview.branchNodeId,
      dwellMs: baseDwellMs(caption, opts.mastery, opts.tone),
      themeIndex: themeCursor++ % SLIDE_THEME_COUNT,
    })
  }

  const branchTotal = branches.length
  branches.forEach((slide, i) => {
    const bullets = childBulletList(slide, nodeById)
    const caption = narrateBranch(slide, opts, childTitlesHint(bullets, opts), i + 1, branchTotal)
    const focusIds =
      opts.tourScope === 'each_node' && slide.branchNodeId
        ? [slide.branchNodeId]
        : slide.focusNodeIds
    steps.push({
      id: `branch-${slide.id}`,
      kind: 'branch',
      title: slide.title,
      caption,
      bullets,
      focusNodeIds: focusIds.length ? focusIds : slide.focusNodeIds,
      branchNodeId: slide.branchNodeId,
      dwellMs: baseDwellMs(caption, opts.mastery, opts.tone),
      themeIndex: themeCursor++ % SLIDE_THEME_COUNT,
    })
  })

  if (overview && steps.length > 1) {
    const caption = narrateClosing(overview.title, opts)
    steps.push({
      id: 'closing',
      kind: 'closing',
      title: overview.title,
      caption,
      bullets: branches
        .map((b) => b.title)
        .filter(Boolean)
        .slice(0, 5),
      focusNodeIds: overview.focusNodeIds,
      branchNodeId: overview.branchNodeId,
      dwellMs: baseDwellMs(caption, opts.mastery, opts.tone),
      themeIndex: themeCursor % SLIDE_THEME_COUNT,
    })
  }

  return steps
}
