/**
 * Manual confirm draft for an image / hand-drawn diagram import.
 * The vision call returns a typed spec. The dialog edits this draft, then
 * the canvas loads `specFromDraft`.
 */
export const VISION_IMPORT_TYPES = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'mindmap',
  'concept_map',
] as const

export type VisionImportType = (typeof VISION_IMPORT_TYPES)[number]

export type ManualFormKind = 'list' | 'double' | 'flow' | 'multi' | 'outline' | 'bridge' | 'concept'

export interface FlowStepDraft {
  text: string
  substeps: string
}

export interface HanddrawnManualDraft {
  diagramType: VisionImportType
  topic: string
  items: string
  right: string
  similarities: string
  leftDifferences: string
  rightDifferences: string
  effects: string
  outline: string
  pairs: string
  relating: string
  relationships: string
  steps: FlowStepDraft[]
}

interface OutlineNode {
  text: string
  children: OutlineNode[]
}

interface TextNode {
  text?: unknown
  name?: unknown
  label?: unknown
  children?: unknown
  subparts?: unknown
  parts?: unknown
}

const TYPE_SET = new Set<string>(VISION_IMPORT_TYPES)

export function isVisionImportType(value: string): value is VisionImportType {
  return TYPE_SET.has(value)
}

export function manualFormKind(diagramType: VisionImportType): ManualFormKind {
  if (diagramType === 'double_bubble_map') return 'double'
  if (diagramType === 'flow_map') return 'flow'
  if (diagramType === 'multi_flow_map') return 'multi'
  if (diagramType === 'bridge_map') return 'bridge'
  if (diagramType === 'concept_map') return 'concept'
  if (diagramType === 'mindmap' || diagramType === 'tree_map' || diagramType === 'brace_map') {
    return 'outline'
  }
  return 'list'
}

function blankDraft(diagramType: VisionImportType): HanddrawnManualDraft {
  return {
    diagramType,
    topic: '',
    items: '',
    right: '',
    similarities: '',
    leftDifferences: '',
    rightDifferences: '',
    effects: '',
    outline: '',
    pairs: '',
    relating: '',
    relationships: '',
    steps: [{ text: '', substeps: '' }],
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function clip(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function linesOf(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

function joinLines(values: unknown): string {
  if (!Array.isArray(values)) return ''
  return values
    .map((item) => {
      if (typeof item === 'string') return item.trim()
      const record = asRecord(item)
      if (!record) return ''
      return clip(record.text) || clip(record.name) || clip(record.label)
    })
    .filter((line) => line.length > 0)
    .join('\n')
}

function nodeText(node: TextNode): string {
  return clip(node.text) || clip(node.name) || clip(node.label)
}

function formatOutline(nodes: unknown, depth = 0): string {
  if (!Array.isArray(nodes)) return ''
  const pad = '  '.repeat(depth)
  const lines: string[] = []
  for (const item of nodes) {
    if (typeof item === 'string') {
      const text = item.trim()
      if (text) lines.push(pad + text)
      continue
    }
    const record = asRecord(item) as TextNode | null
    if (!record) continue
    const text = nodeText(record)
    if (!text) continue
    lines.push(pad + text)
    const nested = record.children ?? record.subparts ?? record.parts
    const childText = formatOutline(nested, depth + 1)
    if (childText) lines.push(childText)
  }
  return lines.join('\n')
}

function parseOutline(text: string): OutlineNode[] {
  const roots: OutlineNode[] = []
  const stack: { depth: number; node: OutlineNode }[] = []
  for (const raw of text.split(/\r?\n/)) {
    if (!raw.trim()) continue
    const indent = raw.match(/^ */)?.[0].length ?? 0
    const depth = Math.min(6, Math.floor(indent / 2))
    const node: OutlineNode = { text: raw.trim(), children: [] }
    while (stack.length > 0 && stack[stack.length - 1].depth >= depth) {
      stack.pop()
    }
    const parent = stack[stack.length - 1]
    if (!parent) roots.push(node)
    else parent.node.children.push(node)
    stack.push({ depth, node })
  }
  return roots
}

function outlineToChildren(nodes: OutlineNode[]): Array<Record<string, unknown>> {
  return nodes.map((node) => {
    const entry: Record<string, unknown> = { text: node.text }
    if (node.children.length > 0) {
      entry.children = outlineToChildren(node.children)
    }
    return entry
  })
}

function outlineToBraceParts(nodes: OutlineNode[]): Array<Record<string, unknown>> {
  return nodes.map((node) => {
    const entry: Record<string, unknown> = { name: node.text }
    const subparts = node.children
      .map((child) => child.text)
      .filter((text) => text.length > 0)
      .map((name) => ({ name }))
    if (subparts.length > 0) entry.subparts = subparts
    return entry
  })
}

function flowStepsFromSpec(spec: Record<string, unknown>): FlowStepDraft[] {
  const rawSteps = Array.isArray(spec.steps) ? spec.steps : []
  const extra = Array.isArray(spec.substeps) ? spec.substeps : []
  const steps = rawSteps
    .map((step, index) => {
      if (typeof step === 'string') {
        const nested = asRecord(extra[index])
        const substeps = nested ? joinLines(nested.substeps) : ''
        return { text: step.trim(), substeps }
      }
      const record = asRecord(step)
      if (!record) return null
      const text = clip(record.text) || clip(record.name)
      if (!text) return null
      return { text, substeps: joinLines(record.substeps ?? record.children) }
    })
    .filter((step): step is FlowStepDraft => step !== null && step.text.length > 0)
  return steps.length > 0 ? steps : [{ text: '', substeps: '' }]
}

function pairsFromSpec(spec: Record<string, unknown>): string {
  const raw = Array.isArray(spec.analogies)
    ? spec.analogies
    : Array.isArray(spec.pairs)
      ? spec.pairs
      : []
  return raw
    .map((pair) => {
      const record = asRecord(pair)
      if (!record) return ''
      const left = clip(record.left)
      const right = clip(record.right)
      if (!left || !right) return ''
      return `${left} | ${right}`
    })
    .filter((line) => line.length > 0)
    .join('\n')
}

function relationshipsFromSpec(spec: Record<string, unknown>): string {
  if (!Array.isArray(spec.relationships)) return ''
  return spec.relationships
    .map((rel) => {
      const record = asRecord(rel)
      if (!record) return ''
      const from = clip(record.from)
      const to = clip(record.to)
      if (!from || !to) return ''
      const label = clip(record.label)
      return label ? `${from} | ${label} | ${to}` : `${from} | ${to}`
    })
    .filter((line) => line.length > 0)
    .join('\n')
}

export function draftFromSpec(
  diagramType: string,
  spec: Record<string, unknown>
): HanddrawnManualDraft | null {
  if (!isVisionImportType(diagramType)) return null
  const draft = blankDraft(diagramType)
  if (diagramType === 'circle_map') {
    draft.topic = clip(spec.topic)
    draft.items = joinLines(spec.context)
  } else if (diagramType === 'bubble_map') {
    draft.topic = clip(spec.topic)
    draft.items = joinLines(spec.attributes)
  } else if (diagramType === 'double_bubble_map') {
    draft.topic = clip(spec.left)
    draft.right = clip(spec.right)
    draft.similarities = joinLines(spec.similarities)
    draft.leftDifferences = joinLines(spec.left_differences)
    draft.rightDifferences = joinLines(spec.right_differences)
  } else if (diagramType === 'flow_map') {
    draft.topic = clip(spec.title) || clip(spec.topic)
    draft.steps = flowStepsFromSpec(spec)
  } else if (diagramType === 'multi_flow_map') {
    draft.topic = clip(spec.event) || clip(spec.topic)
    draft.items = joinLines(spec.causes)
    draft.effects = joinLines(spec.effects)
  } else if (diagramType === 'bridge_map') {
    draft.relating = clip(spec.relating_factor)
    draft.pairs = pairsFromSpec(spec)
  } else if (diagramType === 'concept_map') {
    draft.topic = clip(spec.topic)
    draft.items = joinLines(spec.concepts)
    draft.relationships = relationshipsFromSpec(spec)
  } else if (diagramType === 'brace_map') {
    const whole = spec.whole
    draft.topic = typeof whole === 'string' ? whole.trim() : clip(asRecord(whole)?.text)
    draft.outline = formatOutline(spec.parts)
  } else {
    draft.topic = clip(spec.topic)
    draft.outline = formatOutline(spec.children)
  }
  return draft
}

function parsePairs(text: string): Array<{ left: string; right: string }> {
  return linesOf(text)
    .map((line) => {
      const [left, right] = line.split('|').map((part) => part.trim())
      if (!left || !right) return null
      return { left, right }
    })
    .filter((pair): pair is { left: string; right: string } => pair !== null)
}

function parseRelationships(text: string): Array<{ from: string; to: string; label: string }> {
  return linesOf(text)
    .map((line) => {
      const parts = line.split('|').map((part) => part.trim())
      if (parts.length >= 3) {
        const [from, label, to] = parts
        if (!from || !to) return null
        return { from, to, label: label || '' }
      }
      const [from, to] = parts
      if (!from || !to) return null
      return { from, to, label: '' }
    })
    .filter((rel): rel is { from: string; to: string; label: string } => rel !== null)
}

export function specFromDraft(draft: HanddrawnManualDraft): Record<string, unknown> | null {
  const topic = draft.topic.trim()
  if (draft.diagramType === 'circle_map') {
    const context = linesOf(draft.items)
    if (!topic || context.length === 0) return null
    return { topic, context }
  }
  if (draft.diagramType === 'bubble_map') {
    const attributes = linesOf(draft.items)
    if (!topic || attributes.length === 0) return null
    return { topic, attributes }
  }
  if (draft.diagramType === 'double_bubble_map') {
    const right = draft.right.trim()
    const similarities = linesOf(draft.similarities)
    const leftDifferences = linesOf(draft.leftDifferences)
    const rightDifferences = linesOf(draft.rightDifferences)
    if (!topic || !right) return null
    if (similarities.length + leftDifferences.length + rightDifferences.length === 0) return null
    return {
      left: topic,
      right,
      similarities,
      left_differences: leftDifferences,
      right_differences: rightDifferences,
    }
  }
  if (draft.diagramType === 'flow_map') {
    const steps = draft.steps
      .map((step) => ({ text: step.text.trim(), substeps: linesOf(step.substeps) }))
      .filter((step) => step.text.length > 0)
    if (!topic || steps.length === 0) return null
    return {
      title: topic,
      steps: steps.map((step) => step.text),
      substeps: steps.map((step, stepIndex) => ({
        step: step.text,
        stepIndex,
        substeps: step.substeps,
      })),
    }
  }
  if (draft.diagramType === 'multi_flow_map') {
    const causes = linesOf(draft.items)
    const effects = linesOf(draft.effects)
    if (!topic || (causes.length === 0 && effects.length === 0)) return null
    return { event: topic, causes, effects }
  }
  if (draft.diagramType === 'bridge_map') {
    const analogies = parsePairs(draft.pairs)
    if (analogies.length === 0) return null
    return { relating_factor: draft.relating.trim(), analogies }
  }
  if (draft.diagramType === 'concept_map') {
    const concepts = linesOf(draft.items)
    const relationships = parseRelationships(draft.relationships)
    if (!topic || concepts.length === 0 || relationships.length === 0) return null
    return { topic, concepts, relationships }
  }
  if (draft.diagramType === 'brace_map') {
    const parts = outlineToBraceParts(parseOutline(draft.outline))
    if (!topic || parts.length === 0) return null
    return { whole: topic, parts }
  }
  const children = outlineToChildren(parseOutline(draft.outline))
  if (!topic || children.length === 0) return null
  return { topic, children }
}

function flattenDraft(draft: HanddrawnManualDraft): string[] {
  const fromOutline = parseOutline(draft.outline).flatMap(function walk(node): string[] {
    return [node.text, ...node.children.flatMap(walk)]
  })
  const fromSteps = draft.steps.flatMap((step) => [step.text.trim(), ...linesOf(step.substeps)])
  return [
    ...linesOf(draft.items),
    draft.right.trim(),
    ...linesOf(draft.similarities),
    ...linesOf(draft.leftDifferences),
    ...linesOf(draft.rightDifferences),
    ...linesOf(draft.effects),
    ...fromOutline,
    ...fromSteps,
    ...parsePairs(draft.pairs).flatMap((pair) => [pair.left, pair.right]),
    ...linesOf(draft.relationships),
  ].filter((line) => line.length > 0)
}

export function retargetDraft(
  draft: HanddrawnManualDraft,
  next: VisionImportType
): HanddrawnManualDraft {
  if (draft.diagramType === next) return draft
  const title = draft.topic.trim() || draft.relating.trim()
  const lines = flattenDraft(draft).filter((line) => line !== title)
  const nextDraft = blankDraft(next)
  if (next === 'bridge_map') {
    nextDraft.relating = title
    const pairs: string[] = []
    for (let index = 0; index + 1 < lines.length; index += 2) {
      pairs.push(`${lines[index]} | ${lines[index + 1]}`)
    }
    nextDraft.pairs = pairs.join('\n')
    return nextDraft
  }
  if (next === 'flow_map') {
    nextDraft.topic = title
    nextDraft.steps =
      lines.length > 0 ? lines.map((text) => ({ text, substeps: '' })) : nextDraft.steps
    return nextDraft
  }
  if (next === 'double_bubble_map') {
    nextDraft.topic = title
    nextDraft.right = lines[0] ?? ''
    nextDraft.similarities = lines.slice(1).join('\n')
    return nextDraft
  }
  if (next === 'multi_flow_map') {
    nextDraft.topic = title
    const mid = Math.ceil(lines.length / 2)
    nextDraft.items = lines.slice(0, mid).join('\n')
    nextDraft.effects = lines.slice(mid).join('\n')
    return nextDraft
  }
  if (next === 'concept_map') {
    nextDraft.topic = title
    nextDraft.items = lines.join('\n')
    return nextDraft
  }
  if (manualFormKind(next) === 'outline') {
    nextDraft.topic = title
    nextDraft.outline = lines.join('\n')
    return nextDraft
  }
  nextDraft.topic = title
  nextDraft.items = lines.join('\n')
  return nextDraft
}
