/**
 * Auto branch expansion from a File Center package.
 *
 * When the user commits a real label on a top-level mind map branch that has no
 * children yet, and the diagram's package has at least one indexed source, this
 * triggers a package-scoped subgraph suggestion (RAG retrieval is scoped server
 * side via the diagram's linked package). The user still confirms the AI
 * children through the existing subgraph preview bar.
 *
 * Cost guards: once per branch node id on success, debounced, skipped during collab.
 */
import { type Ref, computed, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables'
import { TOPIC_NODE_ID, shouldAutoExpandBranch } from '@/composables/editor/branchAutoExpandGuard'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { useMindMapSubgraphSuggest } from '@/composables/editor/useMindMapSubgraphSuggest'
import { usePackageDetail } from '@/composables/fileCenter/useFileCenter'
import { useFileCenterActivePackage } from '@/composables/fileCenter/useFileCenterActivePackage'
import { useDiagramStore } from '@/stores'
import { useLiveTranslationStore } from '@/stores/liveTranslation'

const DEBOUNCE_MS = 500

export function useMindMapRagBranchExpand(enabled: Ref<boolean>) {
  const diagramStore = useDiagramStore()
  const liveTranslationStore = useLiveTranslationStore()
  const { activePackageId, activeDiagramId } = useFileCenterActivePackage(enabled)
  const detailQuery = usePackageDetail(activePackageId, { enabled })
  const { generateSubgraph, isGenerating } = useMindMapSubgraphSuggest()

  const completedSourceCount = computed(
    () => (detailQuery.data.value?.documents ?? []).filter((d) => d.status === 'completed').length
  )

  // Branch node ids we have already auto-expanded successfully this session.
  const attempted = ref<Set<string>>(new Set())
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function isMindMap(): boolean {
    return diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
  }

  function isTopLevelBranch(nodeId: string): boolean {
    const connections = diagramStore.data?.connections ?? []
    return connections.some((c) => c.source === TOPIC_NODE_ID && c.target === nodeId)
  }

  function hasChildren(nodeId: string): boolean {
    const connections = diagramStore.data?.connections ?? []
    return connections.some((c) => c.source === nodeId)
  }

  function shouldAutoExpand(nodeId: string, text: string): boolean {
    const trimmed = (text ?? '').trim()
    return shouldAutoExpandBranch({
      enabled: enabled.value,
      isMindMap: isMindMap(),
      collabActive: diagramStore.collabSessionActive,
      isGenerating: isGenerating.value,
      alreadyAttempted: attempted.value.has(nodeId),
      completedSourceCount: completedSourceCount.value,
      trimmedText: trimmed,
      isPlaceholder: isPlaceholderText(trimmed),
      nodeId,
      isTopLevelBranch: isTopLevelBranch(nodeId),
      hasChildren: hasChildren(nodeId),
      diagramSaved: activeDiagramId.value !== null,
      liveTranslationActive: liveTranslationStore.enabled,
    })
  }

  function onTextUpdated(payload: { nodeId: string; text: string }): void {
    if (!payload?.nodeId) return
    if (!shouldAutoExpand(payload.nodeId, payload.text)) return

    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    const targetId = payload.nodeId
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      // Re-check guards after the debounce in case state changed.
      if (!shouldAutoExpand(targetId, payload.text)) return
      void generateSubgraph(targetId).then((ok) => {
        if (ok) {
          attempted.value.add(targetId)
        }
      })
    }, DEBOUNCE_MS)
  }

  const unsubscribeRef = ref<(() => void) | null>(null)

  function detachListener(): void {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    const unsub = unsubscribeRef.value
    if (unsub) {
      unsub()
      unsubscribeRef.value = null
    }
  }

  watch(
    enabled,
    (isEnabled) => {
      if (isEnabled) {
        if (!unsubscribeRef.value) {
          unsubscribeRef.value = eventBus.on('node:text_updated', onTextUpdated)
        }
      } else {
        detachListener()
        attempted.value = new Set()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    detachListener()
  })

  return { completedSourceCount }
}
