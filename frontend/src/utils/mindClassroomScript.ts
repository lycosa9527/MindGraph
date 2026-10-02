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
import { buildMindMapTreeChildrenMap } from '@/utils/mindMapLocation'
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
  /** Wan slide image when presentation is slide_deck */
  imageUrl?: string
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
const DWELL_MS_PER_CHAR = 280
const DWELL_FLOOR_MS = 2200
const TTS_SAFETY_MS_PER_CHAR = 400
const TTS_SAFETY_FLOOR_MS = 20_000
const TTS_SAFETY_CEILING_MS = 1_800_000

export function lectureCaptionDwellMs(caption: string): number {
  const chars = caption.trim().length
  return Math.max(DWELL_FLOOR_MS, 2400 + chars * DWELL_MS_PER_CHAR)
}

export function lectureTtsSafetyMs(caption: string, dwellMs: number): number {
  const chars = caption.trim().length
  return Math.min(
    TTS_SAFETY_CEILING_MS,
    Math.max(dwellMs + 8_000, chars * TTS_SAFETY_MS_PER_CHAR + TTS_SAFETY_FLOOR_MS)
  )
}

function traversalForOptions(opts: MindClassroomScriptOptions): MindMapSlideTraversalMode {
  if (opts.presentation === 'slide_deck') {
    // Slide decks always stay concise; tour scope only applies to canvas walkthroughs.
    return 'firstLevel'
  }
  return opts.tourScope === 'each_node' ? 'deep' : 'firstLevel'
}

export function shouldExpandLectureBranchSubtree(
  tourScope: MindClassroomTourScopeId,
  presentation?: MindClassroomPresentationId | null
): boolean {
  // Slide decks always walk first-level branches; tour scope only applies to canvas tours.
  if (presentation === 'slide_deck') return true
  return tourScope !== 'each_node'
}

function uniqueNodeIds(ids: Iterable<string>): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const id of ids) {
    if (!id || seen.has(id)) continue
    seen.add(id)
    out.push(id)
  }
  return out
}

function lectureTopicNodeId(
  step: Pick<MindClassroomLectureStep, 'focusNodeIds' | 'branchNodeId'>,
  nodes: readonly DiagramNode[] = []
): string | undefined {
  if (step.branchNodeId) return step.branchNodeId
  if (step.focusNodeIds[0]) return step.focusNodeIds[0]
  return nodes.find((node) => node.type === 'topic' || node.id === 'topic')?.id
}

/**
 * Overview / closing talk about the whole map. Frame the topic plus first-level
 * main branches so the camera does not zoom onto the topic node alone.
 */
function expandWholeMapMainBranchFocus(
  step: Pick<MindClassroomLectureStep, 'focusNodeIds' | 'branchNodeId'>,
  getDescendantIds: (rootNodeId: string) => Set<string>,
  getChildIds?: (rootNodeId: string) => Iterable<string>
): string[] {
  const listed = uniqueNodeIds(step.focusNodeIds)
  // Server already named the whole diagram (circle ring, both comparison sides, causes).
  if (listed.length > 1) return listed
  const topicId = lectureTopicNodeId(step)
  if (!topicId) return [...step.focusNodeIds]
  if (getChildIds) {
    const children = uniqueNodeIds(getChildIds(topicId))
    if (children.length) {
      return uniqueNodeIds([topicId, ...children])
    }
  }
  const descendants = getDescendantIds(topicId)
  if (descendants.size > 1) {
    return [...descendants]
  }
  return uniqueNodeIds([topicId, ...step.focusNodeIds])
}

/**
 * Canvas dim/fit ids for a lecture step.
 *
 * Remote jobs store only the branch head (backend: FE expands children).
 * Overview / closing frame the topic plus first-level main branches.
 * Main-branch / slide-deck tours keep the whole subtree lit; each-node stays
 * on that node. Selection / pulse glow still uses ``branchNodeId`` only.
 */
export function expandLectureFocusNodeIds(
  step: Pick<MindClassroomLectureStep, 'kind' | 'focusNodeIds' | 'branchNodeId'>,
  tourScope: MindClassroomTourScopeId,
  getDescendantIds: (rootNodeId: string) => Set<string>,
  presentation?: MindClassroomPresentationId | null,
  getChildIds?: (rootNodeId: string) => Iterable<string>
): string[] {
  if (step.kind === 'overview' || step.kind === 'closing') {
    return expandWholeMapMainBranchFocus(step, getDescendantIds, getChildIds)
  }
  if (step.kind !== 'branch' || !shouldExpandLectureBranchSubtree(tourScope, presentation)) {
    return [...step.focusNodeIds]
  }
  const roots = step.branchNodeId ? [step.branchNodeId] : step.focusNodeIds
  const expanded = new Set<string>()
  for (const root of roots) {
    const descendants = getDescendantIds(root)
    if (descendants.size > 0) {
      for (const id of descendants) {
        expanded.add(id)
      }
    } else {
      expanded.add(root)
    }
  }
  return expanded.size > 0 ? [...expanded] : [...step.focusNodeIds]
}

function isMindMapDiagram(diagramType: string | null | undefined): boolean {
  if (!diagramType) return true
  const slug = diagramType.trim().toLowerCase().replace(/-/g, '_')
  return slug === 'mindmap' || slug === 'mind_map'
}

function isLectureAnchor(node: DiagramNode): boolean {
  if (node.type === 'boundary') return false
  if (node.type === 'label') return Boolean(node.text?.trim())
  if (node.type === 'center' || node.type === 'topic' || node.type === 'whole' || node.type === 'event') {
    return true
  }
  return (
    node.id === 'topic' ||
    node.id === 'left-topic' ||
    node.id === 'right-topic' ||
    node.id === 'event' ||
    node.id === 'flow-topic' ||
    node.id === 'tree-topic' ||
    node.id === 'brace-whole'
  )
}

function contentNodeIds(nodes: readonly DiagramNode[]): string[] {
  return nodes
    .filter((node) => node.type !== 'boundary' && (Boolean(node.text?.trim()) || isLectureAnchor(node)))
    .map((node) => node.id)
}

function bridgeMateId(node: DiagramNode, nodes: readonly DiagramNode[]): string | undefined {
  const index = node.data?.pairIndex
  const side = node.data?.position
  if (typeof index !== 'number' || (side !== 'left' && side !== 'right')) return undefined
  const other = side === 'left' ? 'right' : 'left'
  return nodes.find((candidate) => candidate.data?.pairIndex === index && candidate.data?.position === other)?.id
}

function neighborIds(focusIds: readonly string[], connections: readonly Connection[]): string[] {
  const focus = new Set(focusIds)
  const extra: string[] = []
  for (const connection of connections) {
    if (focus.has(connection.source) && !focus.has(connection.target)) extra.push(connection.target)
    if (focus.has(connection.target) && !focus.has(connection.source)) extra.push(connection.source)
  }
  return extra
}

function diagramSlug(diagramType: string | null | undefined): string {
  return (diagramType ?? '').trim().toLowerCase().replace(/-/g, '_')
}

function isDiagramRoot(node: DiagramNode | undefined): boolean {
  if (!node) return false
  if (node.type === 'center' || node.type === 'topic' || node.type === 'whole' || node.type === 'event') {
    return true
  }
  return node.id === 'topic' || node.id === 'tree-topic' || node.id === 'brace-whole' || node.id === 'flow-topic'
}

function lectureSeedId(
  ids: readonly string[],
  nodes: readonly DiagramNode[],
  branchNodeId?: string
): string | undefined {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  if (branchNodeId && !isDiagramRoot(byId.get(branchNodeId))) return branchNodeId
  return ids.find((id) => !isDiagramRoot(byId.get(id)))
}

function childMap(connections: readonly Connection[]): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const connection of connections) {
    const list = map.get(connection.source) ?? []
    list.push(connection.target)
    map.set(connection.source, list)
  }
  return map
}

function parentMap(connections: readonly Connection[]): Map<string, string> {
  const map = new Map<string, string>()
  for (const connection of connections) {
    if (!map.has(connection.target)) map.set(connection.target, connection.source)
  }
  return map
}

function groupRootId(
  nodeId: string,
  nodesById: Map<string, DiagramNode>,
  parents: Map<string, string>
): string {
  let current = nodeId
  const seen = new Set<string>()
  while (current && !seen.has(current)) {
    seen.add(current)
    const parentId = parents.get(current)
    if (!parentId || isDiagramRoot(nodesById.get(parentId))) return current
    current = parentId
  }
  return nodeId
}

function descendantIdsFrom(rootId: string, children: Map<string, string[]>): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  const stack = [rootId]
  while (stack.length > 0) {
    const id = stack.pop()
    if (!id || seen.has(id)) continue
    seen.add(id)
    out.push(id)
    const kids = children.get(id) ?? []
    for (let index = kids.length - 1; index >= 0; index -= 1) {
      const kid = kids[index]
      if (kid) stack.push(kid)
    }
  }
  return out
}

function radialCenterIds(nodes: readonly DiagramNode[]): string[] {
  return nodes
    .filter((node) => node.type === 'center' || node.type === 'topic' || node.id === 'topic')
    .map((node) => node.id)
}

function columnFrameIds(nodes: readonly DiagramNode[], seed: string): string[] {
  const roleOf = (node: DiagramNode): string => {
    const value = node.data?.doubleBubbleRole
    return typeof value === 'string' ? value : ''
  }
  const seedNode = nodes.find((node) => node.id === seed)
  const role = seedNode ? roleOf(seedNode) : ''
  if (role === 'similarity') {
    const middle = nodes.filter((node) => roleOf(node) === 'similarity').map((node) => node.id)
    return middle.length > 0 ? middle : [seed]
  }
  const right = role === 'rightDiff' || seed === 'right-topic'
  const topicId = right ? 'right-topic' : 'left-topic'
  const diffRole = right ? 'rightDiff' : 'leftDiff'
  const ids = [
    topicId,
    ...nodes.filter((node) => roleOf(node) === diffRole).map((node) => node.id),
  ]
  return uniqueNodeIds(ids.filter((id) => nodes.some((node) => node.id === id)))
}

function bridgeFrameIds(seed: string, nodes: readonly DiagramNode[]): string[] {
  const node = nodes.find((item) => item.id === seed)
  const mate = node ? bridgeMateId(node, nodes) : undefined
  const factors = nodes
    .filter((item) => item.type === 'label' && Boolean(item.text?.trim()))
    .map((item) => item.id)
  return uniqueNodeIds([seed, ...(mate ? [mate] : []), ...factors])
}

function groupFrameIds(
  seed: string,
  diagram: { connections: readonly Connection[]; nodes: readonly DiagramNode[] }
): string[] {
  const nodesById = new Map(diagram.nodes.map((node) => [node.id, node]))
  const root = groupRootId(seed, nodesById, parentMap(diagram.connections))
  const members = descendantIdsFrom(root, childMap(diagram.connections)).filter((id) => {
    const node = nodesById.get(id)
    return Boolean(node) && node?.type !== 'label' && node?.type !== 'boundary'
  })
  return members.length > 0 ? members : [seed]
}

/**
 * After the overview, each step settles on the next reading group.
 * A ring orbits the center. A tree, brace, or flow step is one column.
 */
function frameDiagramSpecialty(
  ids: string[],
  stepKind: MindClassroomLectureStep['kind'],
  diagram: {
    connections: readonly Connection[]
    nodes: readonly DiagramNode[]
    diagramType?: string | null
  },
  branchNodeId?: string
): string[] {
  if (isMindMapDiagram(diagram.diagramType)) return ids
  if (stepKind === 'overview' || stepKind === 'closing') {
    return ids.length > 1 ? ids : contentNodeIds(diagram.nodes)
  }
  const seed = lectureSeedId(ids, diagram.nodes, branchNodeId)
  if (!seed) return ids
  const seedNode = diagram.nodes.find((node) => node.id === seed)
  if (seedNode?.type === 'label') return contentNodeIds(diagram.nodes)
  const slug = diagramSlug(diagram.diagramType)
  if (slug === 'circle_map' || slug === 'bubble_map') {
    return uniqueNodeIds([seed, ...radialCenterIds(diagram.nodes)])
  }
  if (slug === 'tree_map' || slug === 'brace_map' || slug === 'flow_map') {
    return groupFrameIds(seed, diagram)
  }
  if (slug === 'double_bubble_map') return columnFrameIds(diagram.nodes, seed)
  if (slug === 'multi_flow_map') {
    const events = diagram.nodes
      .filter((node) => node.type === 'event' || node.id === 'event')
      .map((node) => node.id)
    return uniqueNodeIds([seed, ...events])
  }
  if (slug === 'bridge_map') return bridgeFrameIds(seed, diagram.nodes)
  if (slug === 'concept_map') {
    return uniqueNodeIds([seed, ...neighborIds([seed], diagram.connections)])
  }
  return ids
}

/** Fit ids for a live canvas lecture step (resolves topic when the job omitted it). */
export function lectureStepFitNodeIds(
  step: Pick<MindClassroomLectureStep, 'kind' | 'focusNodeIds' | 'branchNodeId'>,
  tourScope: MindClassroomTourScopeId,
  getDescendantIds: (rootNodeId: string) => Set<string>,
  presentation: MindClassroomPresentationId | null | undefined,
  diagram: {
    connections: readonly Connection[]
    nodes: readonly DiagramNode[]
    diagramType?: string | null
  }
): string[] {
  const childrenMap = buildMindMapTreeChildrenMap(diagram.connections)
  const topicId =
    step.kind === 'overview' || step.kind === 'closing'
      ? lectureTopicNodeId(step, diagram.nodes)
      : undefined
  const framed = expandLectureFocusNodeIds(
    {
      kind: step.kind,
      focusNodeIds: step.focusNodeIds.length ? step.focusNodeIds : topicId ? [topicId] : [],
      branchNodeId: step.branchNodeId || topicId,
    },
    tourScope,
    getDescendantIds,
    presentation,
    (rootId) => childrenMap.get(rootId) ?? []
  )
  return frameDiagramSpecialty(framed, step.kind, diagram, step.branchNodeId)
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
  let ms = lectureCaptionDwellMs(caption)
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
