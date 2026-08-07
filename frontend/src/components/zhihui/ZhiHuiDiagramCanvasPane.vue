<script setup lang="ts">
/**
 * Read-only mindmap preview for 图示生图 (scoped DiagramSession + viewBus).
 *
 * Topic / overview slides → fit whole diagram.
 * Branch slides → expand path, select branch+children, fit to those nodes.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import DiagramCanvasHost from '@/components/diagram/DiagramCanvasHost.vue'
import DiagramSessionProvider from '@/components/diagram/DiagramSessionProvider.vue'
import { useLanguage } from '@/composables'
import { ANIMATION } from '@/config/uiConfig'
import type { DiagramSession } from '@/stores/diagram'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

const FOCUS_TRANSITION_MS = 920
const FOCUS_RETRY_MS = 120
const FOCUS_RETRY_MAX = 12

const props = defineProps<{
  diagramId: string | null
  /** Empty / null → whole-diagram topic framing; otherwise branch hints (id or text). */
  focusNodeIds?: string[] | null
  /** When true, always treat as topic overview (first PPT slide). */
  topicOverview?: boolean
  /** Bump on conversation hydrate so restore re-pans even if focus hints match. */
  focusEpoch?: number
}>()

const { t } = useLanguage()
const savedStore = useSavedDiagramsStore()

const loading = ref(false)
const error = ref<string | null>(null)
const spec = ref<Record<string, unknown> | null>(null)
const diagramType = ref<string>('mind_map')
const sessionProviderRef = ref<{ session: DiagramSession } | null>(null)

let focusTimer: ReturnType<typeof setTimeout> | null = null
let focusRetryTimer: ReturnType<typeof setTimeout> | null = null

const vueFlowId = computed(
  () => `zhihui-diagram-${props.diagramId || 'none'}`
)

type FocusSession = DiagramSession & {
  selectNodes?: (nodeIds: string | string[]) => boolean
  getMindMapDescendantIds?: (rootNodeId: string) => Set<string>
  expandMindMapPathToNode?: (nodeId: string) => boolean
}

function clearFocusTimer(): void {
  if (focusTimer !== null) {
    clearTimeout(focusTimer)
    focusTimer = null
  }
  if (focusRetryTimer !== null) {
    clearTimeout(focusRetryTimer)
    focusRetryTimer = null
  }
}

function getSession(): FocusSession | null {
  return (sessionProviderRef.value?.session as FocusSession | undefined) ?? null
}

function resolveNodeId(session: FocusSession, hint: string): string | null {
  const cleaned = hint.trim()
  if (!cleaned) return null
  const nodes = session.data?.nodes ?? []
  if (nodes.some((node) => node.id === cleaned)) {
    return cleaned
  }
  const needle = cleaned.toLowerCase()
  const exact = nodes.find((node) => {
    const text = String(node.text || '')
      .trim()
      .toLowerCase()
    return text === needle
  })
  if (exact) return exact.id
  const partial = nodes.find((node) => {
    const text = String(node.text || '')
      .trim()
      .toLowerCase()
    return Boolean(text) && (text.includes(needle) || needle.includes(text))
  })
  return partial?.id ?? null
}

function expandFocusIds(session: FocusSession, hints: string[]): string[] {
  const expanded = new Set<string>()
  for (const hint of hints) {
    const rootId = resolveNodeId(session, hint)
    if (!rootId) continue
    session.expandMindMapPathToNode?.(rootId)
    const descendants = session.getMindMapDescendantIds?.(rootId)
    if (descendants && descendants.size > 0) {
      for (const id of descendants) {
        expanded.add(id)
      }
    } else {
      expanded.add(rootId)
    }
  }
  return [...expanded]
}

function applyTopicFit(session: FocusSession): void {
  session.viewBus.emit('view:fit_to_canvas_requested', {
    animate: true,
    userInitiated: true,
  })
}

function applyBranchFit(session: FocusSession, nodeIds: string[]): void {
  session.selectNodes?.(nodeIds)
  session.viewBus.emit('view:fit_to_nodes_requested', {
    nodeIds,
    animate: true,
    duration: FOCUS_TRANSITION_MS,
    padding: nodeIds.length <= 1 ? 0.45 : 0.38,
    userInitiated: true,
  })
}

function runFocusPass(attempt: number): void {
  const session = getSession()
  if (!spec.value) return
  if (!session || !session.data?.nodes?.length) {
    if (attempt >= FOCUS_RETRY_MAX) return
    focusRetryTimer = window.setTimeout(() => {
      focusRetryTimer = null
      runFocusPass(attempt + 1)
    }, FOCUS_RETRY_MS)
    return
  }
  const hints = (props.focusNodeIds ?? []).map(String).filter((id) => id.trim())
  const isTopic = Boolean(props.topicOverview) || hints.length === 0
  if (isTopic) {
    applyTopicFit(session)
    return
  }
  const nodeIds = expandFocusIds(session, hints)
  if (nodeIds.length === 0) {
    applyTopicFit(session)
    return
  }
  void nextTick(() => {
    applyBranchFit(session, nodeIds)
  })
}

function applyFocus(): void {
  clearFocusTimer()
  focusTimer = window.setTimeout(() => {
    focusTimer = null
    runFocusPass(0)
  }, ANIMATION.FIT_VIEWPORT_DELAY)
}

let loadEpoch = 0

async function loadDiagram(id: string | null): Promise<void> {
  const epoch = ++loadEpoch
  clearFocusTimer()
  spec.value = null
  error.value = null
  if (!id) return
  loading.value = true
  try {
    const result = await savedStore.getDiagram(id)
    if (epoch !== loadEpoch || id !== props.diagramId) return
    if (!result.ok) {
      error.value = String(t('zhihui.diagram.loadFailed'))
      return
    }
    const raw = result.diagram.spec
    if (!raw || typeof raw !== 'object') {
      error.value = String(t('zhihui.diagram.loadFailed'))
      return
    }
    spec.value = raw as Record<string, unknown>
    diagramType.value = result.diagram.diagram_type || 'mind_map'
  } catch {
    if (epoch !== loadEpoch) return
    error.value = String(t('zhihui.diagram.loadFailed'))
  } finally {
    if (epoch === loadEpoch) {
      loading.value = false
    }
  }
}

watch(
  () => props.diagramId,
  (id) => {
    void loadDiagram(id)
  },
  { immediate: true }
)

watch(
  () =>
    [
      props.focusNodeIds?.join('\0') ?? '',
      props.topicOverview === true,
      props.focusEpoch ?? 0,
      Boolean(spec.value),
      loading.value,
    ] as const,
  async ([, , , hasSpec, isLoading]) => {
    if (!hasSpec || isLoading) return
    await nextTick()
    applyFocus()
  }
)

onBeforeUnmount(() => {
  clearFocusTimer()
})
</script>

<template>
  <div class="zhihui-diagram-canvas flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-stone-200 bg-white">
    <div
      v-if="!diagramId"
      class="flex flex-1 items-center justify-center px-4 text-center text-xs text-stone-400"
    >
      {{ t('zhihui.diagram.selectMindmapHint') }}
    </div>
    <div
      v-else-if="loading"
      class="flex flex-1 items-center justify-center text-xs text-stone-400"
    >
      {{ t('common.loading') }}
    </div>
    <div
      v-else-if="error"
      class="flex flex-1 items-center justify-center px-4 text-center text-xs text-rose-500"
    >
      {{ error }}
    </div>
    <div
      v-else-if="spec"
      class="min-h-0 flex-1"
    >
      <DiagramSessionProvider
        :key="vueFlowId"
        ref="sessionProviderRef"
        mode="readonly"
        :vue-flow-id="vueFlowId"
        :spec="spec"
        :diagram-type="diagramType"
      >
        <DiagramCanvasHost
          class="h-full w-full"
          :fit-view-on-init="true"
        />
      </DiagramSessionProvider>
    </div>
  </div>
</template>
