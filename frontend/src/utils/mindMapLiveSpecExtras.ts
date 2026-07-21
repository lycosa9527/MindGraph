/**
 * Mind-map fields that must travel with nodes/connections across Pinia →
 * workshop Redis / Kitty live_spec. loadFromSpec rebuilds trees from text and
 * only restores visuals from these top-level extras (not wire node.style).
 */

const MINDMAP_LIVE_SPEC_EXTRA_KEYS = [
  '_node_styles',
  '_mindmap_theme',
  '_mindmap_diagram_style',
  '_mindmap_canvas',
  '_collapsed_paths',
] as const

export type MindMapLiveSpecExtraKey = (typeof MINDMAP_LIVE_SPEC_EXTRA_KEYS)[number]

export function isMindMapDiagramType(diagramType: string | null | undefined): boolean {
  return diagramType === 'mindmap' || diagramType === 'mind_map'
}

/** Pick durable mind-map extras from Pinia/diagram data for live-spec payloads. */
export function pickMindMapLiveSpecExtras(
  data: Record<string, unknown> | null | undefined
): Partial<Record<MindMapLiveSpecExtraKey, unknown>> {
  if (!data) return {}
  const out: Partial<Record<MindMapLiveSpecExtraKey, unknown>> = {}
  for (const key of MINDMAP_LIVE_SPEC_EXTRA_KEYS) {
    const value = data[key]
    if (value !== undefined && value !== null) {
      out[key] = value
    }
  }
  return out
}

/** Attach mind-map extras onto a live-spec / hub diagram_data object. */
export function attachMindMapLiveSpecExtras(
  target: Record<string, unknown>,
  data: Record<string, unknown> | null | undefined
): Record<string, unknown> {
  Object.assign(target, pickMindMapLiveSpecExtras(data))
  return target
}

/** Fingerprint extras so style/collapse-only edits still publish/sync. */
export function mindMapLiveSpecExtrasFingerprint(
  data: Record<string, unknown> | null | undefined
): string {
  if (!data) return ''
  const picked = pickMindMapLiveSpecExtras(data)
  if (Object.keys(picked).length === 0) return ''
  return JSON.stringify(picked)
}

/**
 * Presentation extras kept across whole-diagram LLM / vision replaces.
 * Omits `_node_styles` and `_collapsed_paths` — those key off positional ids /
 * paths that do not survive a full tree rebuild.
 */
const MINDMAP_PRESENTATION_EXTRA_KEYS = [
  '_mindmap_theme',
  '_mindmap_diagram_style',
  '_mindmap_canvas',
] as const

/**
 * Merge current canvas theme / diagram style / canvas buckets into an incoming
 * mindmap spec before bare `loadFromSpec` (auto-complete, model switch, doc
 * summary, hand-drawn photo). Mirrors flow_map orientation preservation.
 */
export function mergeMindMapPresentationExtrasIntoSpec(
  spec: Record<string, unknown>,
  currentData: Record<string, unknown> | null | undefined
): Record<string, unknown> {
  if (!currentData) return spec
  let merged: Record<string, unknown> | null = null
  for (const key of MINDMAP_PRESENTATION_EXTRA_KEYS) {
    const current = currentData[key]
    if (current === undefined || current === null) continue
    if (!merged) merged = { ...spec }
    merged[key] = current
  }
  return merged ?? spec
}
