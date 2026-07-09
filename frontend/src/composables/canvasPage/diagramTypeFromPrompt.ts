import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import type { DiagramType } from '@/types'

/** Longest-first aliases aligned with backend ``kitty_diagram_vocabulary`` (zh + en). */
const DIAGRAM_TYPE_ALIASES: ReadonlyArray<{ alias: string; slug: DiagramType }> = [
  { alias: 'double bubble map', slug: 'double_bubble_map' },
  { alias: 'double_bubble_map', slug: 'double_bubble_map' },
  { alias: 'multi-flow map', slug: 'multi_flow_map' },
  { alias: 'multi flow map', slug: 'multi_flow_map' },
  { alias: 'multi_flow_map', slug: 'multi_flow_map' },
  { alias: '多重流程图', slug: 'multi_flow_map' },
  { alias: '复流程图', slug: 'multi_flow_map' },
  { alias: '双气泡图', slug: 'double_bubble_map' },
  { alias: '双气泡', slug: 'double_bubble_map' },
  { alias: '思维导图', slug: 'mindmap' },
  { alias: 'mind map', slug: 'mindmap' },
  { alias: 'mind-map', slug: 'mindmap' },
  { alias: 'mind_map', slug: 'mindmap' },
  { alias: 'mindmap', slug: 'mindmap' },
  { alias: 'circle map', slug: 'circle_map' },
  { alias: 'circle_map', slug: 'circle_map' },
  { alias: '圆圈图', slug: 'circle_map' },
  { alias: 'bubble map', slug: 'bubble_map' },
  { alias: 'bubble_map', slug: 'bubble_map' },
  { alias: '气泡图', slug: 'bubble_map' },
  { alias: 'tree map', slug: 'tree_map' },
  { alias: 'tree_map', slug: 'tree_map' },
  { alias: '树形图', slug: 'tree_map' },
  { alias: 'brace map', slug: 'brace_map' },
  { alias: 'brace_map', slug: 'brace_map' },
  { alias: '括号图', slug: 'brace_map' },
  { alias: 'flow map', slug: 'flow_map' },
  { alias: 'flow_map', slug: 'flow_map' },
  { alias: '流程图', slug: 'flow_map' },
  { alias: 'bridge map', slug: 'bridge_map' },
  { alias: 'bridge_map', slug: 'bridge_map' },
  { alias: '桥形图', slug: 'bridge_map' },
  { alias: '类比图', slug: 'bridge_map' },
  { alias: 'concept map', slug: 'concept_map' },
  { alias: 'concept_map', slug: 'concept_map' },
  { alias: '概念图', slug: 'concept_map' },
]

const SORTED_ALIASES = [...DIAGRAM_TYPE_ALIASES].sort((a, b) => b.alias.length - a.alias.length)

const VALID_SLUGS = new Set<string>(VALID_DIAGRAM_TYPES)

export type KittyTopicSeed = {
  topic?: string
  left?: string
  right?: string
}

/** Canonical slug for comparisons (mind_map ≡ mindmap). */
export function normalizeCanvasDiagramSlug(raw: string | null | undefined): DiagramType | null {
  if (!raw) return null
  const text = String(raw).trim()
  if (!text) return null
  if (text === 'mind_map' || text === 'mindmap') return 'mindmap'
  if (VALID_SLUGS.has(text)) return text as DiagramType
  const lowered = text.toLowerCase().replace(/-/g, '_')
  if (lowered === 'mind_map' || lowered === 'mindmap') return 'mindmap'
  for (const row of SORTED_ALIASES) {
    if (row.alias.toLowerCase() === lowered) return row.slug
  }
  return null
}

export function canvasDiagramSlugsEquivalent(
  a: string | null | undefined,
  b: string | null | undefined
): boolean {
  const na = normalizeCanvasDiagramSlug(a)
  const nb = normalizeCanvasDiagramSlug(b)
  return na !== null && nb !== null && na === nb
}

/**
 * Detect requested diagram type from free-form user text (一句话 / Kitty).
 * Returns null when no supported type is mentioned.
 */
export function resolveDiagramTypeFromPrompt(text: string): DiagramType | null {
  const body = String(text ?? '').trim()
  if (!body) return null
  const lowered = body.toLowerCase()
  for (const row of SORTED_ALIASES) {
    const aliasLower = row.alias.toLowerCase()
    if (body.includes(row.alias) || lowered.includes(aliasLower)) {
      return row.slug
    }
  }
  return null
}

function stripDiagramTypePhrases(text: string): string {
  let out = text
  for (const row of SORTED_ALIASES) {
    out = out.split(row.alias).join(' ')
    const re = new RegExp(row.alias.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    out = out.replace(re, ' ')
  }
  return out
}

function cleanTopicFragment(raw: string): string {
  return raw
    .replace(/[「」"'“”‘’]/g, '')
    .replace(/[，。！？、,.!?;:：；]+$/g, '')
    .trim()
}

function extractDoubleBubblePair(text: string): { left?: string; right?: string } {
  const compare = text.match(/比较\s*[「"']?([^「」"'“”和与]+)[「"']?\s*(?:和|与)\s*[「"']?([^「」"'“”]+)/)
  if (compare) {
    const left = cleanTopicFragment(compare[1])
    const right = cleanTopicFragment(compare[2])
    if (left && right) return { left, right }
  }
  const reverse = text.match(/[「"']?([^「」"'“”和与]+)[「"']?\s*(?:和|与)\s*[「"']?([^「」"'“”]+)[「"']?\s*(?:的)?(?:对比|比较|双气泡)/)
  if (reverse) {
    const left = cleanTopicFragment(reverse[1])
    const right = cleanTopicFragment(reverse[2])
    if (left && right) return { left, right }
  }
  return {}
}

/**
 * Pull topic / double-bubble subjects from a user prompt after diagram-type phrases are removed.
 */
export function extractTopicSeedFromPrompt(text: string, diagramType: DiagramType): KittyTopicSeed {
  const body = String(text ?? '').trim()
  if (!body) return {}

  if (diagramType === 'double_bubble_map') {
    const pair = extractDoubleBubblePair(body)
    if (pair.left && pair.right) {
      return { left: pair.left.slice(0, 240), right: pair.right.slice(0, 240) }
    }
  }

  const about = body.match(/关于\s*[「"']?([^「」"'“”\n]+?)[「"']?\s*的/)
  if (about) {
    const topic = cleanTopicFragment(about[1])
    if (topic) return { topic: topic.slice(0, 480) }
  }

  const aboutShort = body.match(/关于\s*[「"']?([^「」"'“”\n，。！？]+)/)
  if (aboutShort) {
    const topic = cleanTopicFragment(aboutShort[1])
    if (topic) return { topic: topic.slice(0, 480) }
  }

  const theme = body.match(/主题(?:是|为|：|:)\s*[「"']?([^「」"'“”\n]+)/)
  if (theme) {
    const topic = cleanTopicFragment(theme[1])
    if (topic) return { topic: topic.slice(0, 480) }
  }

  const titled = body.match(/(?:title|titled)\s+(.+?)(?:\.|$)/i)
  if (titled) {
    const topic = cleanTopicFragment(titled[1])
    if (topic) return { topic: topic.slice(0, 480) }
  }

  let stripped = stripDiagramTypePhrases(body)
  stripped = stripped
    .replace(/【用户要求】[\s\S]*/g, ' ')
    .replace(/user requirements:/gi, ' ')
    .replace(/生成|创建|制作|绘制|画|做|打开|新建|一个|一张|请|帮我|关于|的|用/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  const topic = cleanTopicFragment(stripped)
  if (topic.length >= 1 && topic.length <= 480) {
    return { topic }
  }
  return {}
}
