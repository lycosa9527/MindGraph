/**
 * useConceptMapRelationship - AI-generated relationship labels for concept map links
 *
 * When user creates a link between two concepts (or clears the label),
 * calls the API to generate the relationship label using the selected LLM.
 * Returns 3-5 options; user can pick via number keys (IME-style).
 *
 * Label agent: When a concept node's text changes, only regenerates edges that
 * have empty labels—avoids overwriting user-edited or AI-generated labels.
 */
import { ref } from 'vue'

import { isPlaceholderText } from '@/composables/useAutoComplete'
import { useLanguage } from '@/composables/useLanguage'
import { useNotifications } from '@/composables/useNotifications'
import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { authFetch } from '@/utils/api'

export const CONCEPT_MAP_GENERATING_KEY = Symbol('conceptMapRelationshipGenerating')
export const CONCEPT_MAP_OPTIONS_KEY = Symbol('conceptMapRelationshipOptions')

/** Template-default labels (from getDefaultTemplate) — safe to regenerate when concepts change */
const TEMPLATE_DEFAULT_LABELS = new Set([
  '关联',
  '包含',
  '导致',
  'related to',
  'includes',
  'causes',
])

/** Edge label is empty, placeholder, or template default—safe to regenerate */
function isLabelEmptyOrPlaceholder(label: string | undefined | null): boolean {
  if (!label || !label.trim()) return true
  const t = label.trim()
  if (
    t === '输入关系...' ||
    t === 'Enter relationship...' ||
    t.toLowerCase() === 'enter relationship...'
  ) {
    return true
  }
  return TEMPLATE_DEFAULT_LABELS.has(t) || TEMPLATE_DEFAULT_LABELS.has(t.toLowerCase())
}

export function useConceptMapRelationship() {
  const diagramStore = useDiagramStore()
  const relationshipStore = useConceptMapRelationshipStore()
  const llmResultsStore = useLLMResultsStore()
  const { isZh } = useLanguage()
  const notify = useNotifications()

  const generatingConnectionIds = ref<Set<string>>(new Set())

  function isGeneratingFor(connectionId: string): boolean {
    return generatingConnectionIds.value.has(connectionId)
  }

  function getNodeText(nodeId: string): string {
    const nodes = diagramStore.data?.nodes ?? []
    const node = nodes.find((n) => n.id === nodeId)
    return (node?.text ?? '').trim()
  }

  function getLinkDirection(connectionId: string): string {
    const conn = diagramStore.data?.connections?.find((c) => c.id === connectionId)
    const dir = conn?.arrowheadDirection ?? 'none'
    if (dir === 'target') return 'source_to_target'
    if (dir === 'source') return 'target_to_source'
    if (dir === 'both') return 'both'
    return 'none'
  }

  async function generateRelationship(
    connectionId: string,
    sourceId: string,
    targetId: string
  ): Promise<{ success: boolean; error?: string }> {
    const selectedModel = llmResultsStore.selectedModel
    if (!selectedModel) {
      return { success: false, error: 'No model selected' }
    }

    if (generatingConnectionIds.value.has(connectionId)) {
      return { success: false, error: 'Already generating' }
    }

    const conceptA = getNodeText(sourceId)
    const conceptB = getNodeText(targetId)

    if (isPlaceholderText(conceptA) || isPlaceholderText(conceptB)) {
      return { success: false, error: 'Placeholder text' }
    }

    generatingConnectionIds.value = new Set([...generatingConnectionIds.value, connectionId])

    try {
      const language = isZh.value ? 'zh' : 'en'
      const prompt = conceptA && conceptB ? `${conceptA} ${conceptB}` : 'relationship'
      const topic = diagramStore.getTopicNodeText() || ''

      const response = await authFetch('/api/generate_graph', {
        method: 'POST',
        body: JSON.stringify({
          prompt,
          diagram_type: 'concept_map',
          language,
          llm: selectedModel,
          request_type: 'autocomplete',
          concept_map_relationship_only: true,
          concept_a: conceptA,
          concept_b: conceptB,
          concept_map_topic: topic,
          link_direction: getLinkDirection(connectionId),
        }),
      })

      const result = await response.json()

      const connStillExists = diagramStore.data?.connections?.some((c) => c.id === connectionId)
      if (!connStillExists) {
        return { success: false, error: 'Connection deleted' }
      }

      if (result.success && result.relationship_label) {
        const labels = (result.relationship_labels as string[] | undefined) ?? [result.relationship_label]
        diagramStore.updateConnectionLabel(connectionId, result.relationship_label)
        diagramStore.pushHistory('AI relationship')
        if (labels.length >= 2) {
          relationshipStore.setOptions(connectionId, labels)
        } else {
          relationshipStore.clearAll()
        }
        return { success: true }
      }

      const errMsg = result.error || 'Failed to generate relationship'
      const title = isZh.value ? '关系生成失败' : 'Relationship generation failed'
      notify.error(`${title}: ${errMsg}`)
      return { success: false, error: errMsg }
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'Unknown error'
      const title = isZh.value ? '关系生成失败' : 'Relationship generation failed'
      notify.error(`${title}: ${errMsg}`)
      return { success: false, error: errMsg }
    } finally {
      generatingConnectionIds.value = new Set(
        [...generatingConnectionIds.value].filter((id) => id !== connectionId)
      )
    }
  }

  /**
   * Label agent: When a concept node's text changes, regenerate only edges with
   * empty labels. Skips edges that already have content (user or AI).
   */
  function regenerateForNodeIfNeeded(nodeId: string): void {
    if (!llmResultsStore.selectedModel) return
    const connections = diagramStore.data?.connections ?? []
    const affected = connections.filter(
      (c) => (c.source === nodeId || c.target === nodeId) && isLabelEmptyOrPlaceholder(c.label)
    )
    for (const conn of affected) {
      if (conn.id) {
        generateRelationship(conn.id, conn.source, conn.target)
      }
    }
  }

  function dismissOptionsForConnection(connectionId: string): void {
    relationshipStore.clearConnection(connectionId)
  }

  /** Clear all relationship options (on pane click) */
  function dismissAllOptions(): void {
    relationshipStore.clearAll()
  }

  /** Switch displayed label by number (1–5). Picker stays visible until canvas click. */
  function selectOption(connectionId: string, index: number): boolean {
    const opts = relationshipStore.options[connectionId]
    if (!opts || index < 0 || index >= opts.length) return false
    diagramStore.updateConnectionLabel(connectionId, opts[index])
    diagramStore.pushHistory('AI relationship')
    return true
  }

  return {
    generateRelationship,
    generatingConnectionIds,
    isGeneratingFor,
    regenerateForNodeIfNeeded,
    dismissOptionsForConnection,
    dismissAllOptions,
    selectOption,
  }
}
