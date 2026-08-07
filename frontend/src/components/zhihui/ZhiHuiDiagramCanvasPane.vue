<script setup lang="ts">
/**
 * Read-only mindmap preview for 图示生图 (scoped DiagramSession + viewBus).
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import DiagramCanvasHost from '@/components/diagram/DiagramCanvasHost.vue'
import DiagramSessionProvider from '@/components/diagram/DiagramSessionProvider.vue'
import { useLanguage } from '@/composables'
import { ANIMATION } from '@/config/uiConfig'
import type { DiagramSession } from '@/stores/diagram'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

const props = defineProps<{
  diagramId: string | null
  focusNodeIds?: string[] | null
}>()

const { t } = useLanguage()
const savedStore = useSavedDiagramsStore()

const loading = ref(false)
const error = ref<string | null>(null)
const spec = ref<Record<string, unknown> | null>(null)
const diagramType = ref<string>('mind_map')
const sessionProviderRef = ref<{ session: DiagramSession } | null>(null)

let focusTimer: ReturnType<typeof setTimeout> | null = null

const vueFlowId = computed(
  () => `zhihui-diagram-${props.diagramId || 'none'}`
)

function clearFocusTimer(): void {
  if (focusTimer !== null) {
    clearTimeout(focusTimer)
    focusTimer = null
  }
}

async function loadDiagram(id: string | null): Promise<void> {
  clearFocusTimer()
  spec.value = null
  error.value = null
  if (!id) return
  loading.value = true
  try {
    const result = await savedStore.getDiagram(id)
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
    error.value = String(t('zhihui.diagram.loadFailed'))
  } finally {
    loading.value = false
  }
}

function applyFocus(ids: string[]): void {
  clearFocusTimer()
  focusTimer = window.setTimeout(() => {
    const session = sessionProviderRef.value?.session as
      | (DiagramSession & { selectNodes?: (nodeIds: string | string[]) => boolean })
      | null
      | undefined
    if (!session) return
    session.selectNodes?.(ids)
    session.viewBus.emit('view:fit_to_nodes_requested', { nodeIds: [...ids] })
  }, ANIMATION.FIT_VIEWPORT_DELAY)
}

watch(
  () => props.diagramId,
  (id) => {
    void loadDiagram(id)
  },
  { immediate: true }
)

watch(
  () => [props.focusNodeIds, spec.value] as const,
  async ([ids]) => {
    if (!ids || ids.length === 0 || !spec.value) return
    await nextTick()
    applyFocus(ids.map(String))
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
