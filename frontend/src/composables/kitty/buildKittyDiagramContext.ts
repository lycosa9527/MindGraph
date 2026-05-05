/**
 * Build Voice/Kitty WebSocket context from the diagram store (session_context parity).
 */
import { buildDiagramData } from '@/composables/nodePalette/diagramDataBuilder'
import type { KittyAgentContext } from '@/composables/kitty/useKittyAgent'
import { i18n } from '@/i18n'
import { useDiagramStore } from '@/stores/diagram'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

/** Sync Kitty voice language with UI locale: Chinese by default, English only for `en` UI. */
export function kittyInteractionLanguageFromUi(): 'zh' | 'en' {
  const locRaw = i18n.global.locale as { value?: string } | string
  const code =
    typeof locRaw === 'object' && locRaw !== null && 'value' in locRaw
      ? String((locRaw as { value: string }).value)
      : String(locRaw)
  const lower = code.toLowerCase()
  if (lower === 'en' || lower.startsWith('en-')) {
    return 'en'
  }
  return 'zh'
}

function nodeDisplayText(node: {
  text?: string
  data?: Record<string, unknown>
}): string {
  const raw = (node.text ?? '').trim()
  if (raw.length > 0) {
    return raw
  }
  const label = node.data?.label
  if (typeof label === 'string' && label.trim().length > 0) {
    return label.trim()
  }
  const alt = node.data?.text
  if (typeof alt === 'string') {
    return alt.trim()
  }
  return ''
}

export function buildKittyDiagramContext(
  diagramStore: ReturnType<typeof useDiagramStore>,
  activePanel: string
): KittyAgentContext {
  const savedDiagramsStore = useSavedDiagramsStore()
  const dt = (diagramStore.type ?? 'circle_map') as DiagramType
  const data = diagramStore.data
  const nodes = data?.nodes ?? []
  const vueNodes = nodes.map((n) => ({
    id: n.id,
    text: nodeDisplayText(n),
    type: n.type,
  }))
  const base = buildDiagramData(dt, vueNodes, {
    connections: data?.connections,
    focusQuestionFromSpec:
      typeof data?.focus_question === 'string' ? data.focus_question : undefined,
  })
  const children = nodes.map((n, index) => ({
    id: n.id,
    index,
    text: nodeDisplayText(n),
  }))
  const diagram_data: Record<string, unknown> = {
    ...base,
    diagram_type: dt,
    children,
    selected_nodes: [...diagramStore.selectedNodes],
  }
  if (dt === 'concept_map' && data?.connections?.length) {
    const textById = new Map(nodes.map((n) => [n.id, nodeDisplayText(n)]))
    diagram_data.relationships = data.connections.map((c) => ({
      from: textById.get(c.source) ?? c.source,
      to: textById.get(c.target) ?? c.target,
      label: typeof c.label === 'string' ? c.label : '',
    }))
  }
  if (typeof data?.focus_question === 'string' && data.focus_question.length > 0) {
    diagram_data.focus_question = data.focus_question
  }
  const displayTitle = String(diagramStore.effectiveTitle ?? diagramStore.title ?? '').trim()

  return {
    diagram_type: dt,
    active_panel: activePanel,
    selected_nodes: [...diagramStore.selectedNodes],
    diagram_data,
    diagram_library_id: savedDiagramsStore.activeDiagramId ?? null,
    diagram_display_title: displayTitle,
    interaction_language: kittyInteractionLanguageFromUi(),
  }
}

/**
 * Voice session context when Kitty is opened from the mobile hub (no canvas / diagram task).
 */
export function buildStandaloneKittyLandingContext(): KittyAgentContext {
  return {
    diagram_type: 'circle_map',
    active_panel: 'none',
    selected_nodes: [],
    diagram_data: {
      diagram_type: 'circle_map',
      children: [],
      center: { text: '' },
    },
    diagram_library_id: null,
    diagram_display_title: '',
    interaction_language: kittyInteractionLanguageFromUi(),
  }
}

/**
 * Prefer the live diagram in Pinia (e.g. after mobile canvas → Kitty hub); otherwise hub landing stub.
 */
export function buildKittyVoiceContextPreferStore(activePanel = 'none'): KittyAgentContext {
  const diagramStore = useDiagramStore()
  if (diagramStore.type != null && diagramStore.data != null) {
    return buildKittyDiagramContext(diagramStore, activePanel)
  }
  return buildStandaloneKittyLandingContext()
}
