<script setup lang="ts">
/**
 * Canvas-level four-directional + overlay (Teleport) — avoids per-node mount/clipping issues.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Teleport } from 'vue'

import { useLanguage } from '@/composables'
import { useMindMapDirectionalAddPosition } from '@/composables/canvasToolbar/useMindMapDirectionalAddPosition'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores/diagram'

const props = defineProps<{
  containerRef: HTMLElement | null
}>()

const diagramStore = useDiagramStore()
const { t } = useLanguage()

const editingNodeId = ref<string | null>(null)

const isMindMap = computed(
  () => diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
)

const selectedNodeId = computed(() => {
  const ids = diagramStore.selectedNodes
  return isMindMap.value && ids.length === 1 ? ids[0] : null
})

const overlayEnabled = computed(
  () =>
    isMindMap.value &&
    !!selectedNodeId.value &&
    editingNodeId.value !== selectedNodeId.value
)

const containerRef = computed(() => props.containerRef)

const { handles, visible, scheduleMeasure } = useMindMapDirectionalAddPosition({
  containerRef,
  selectedNodeId,
  enabled: overlayEnabled,
})

watch(
  () => diagramStore.data?.nodes?.map((n) => `${n.id}:${n.position?.x}:${n.position?.y}`).join('|'),
  () => scheduleMeasure()
)

function tooltipFor(direction: 'top' | 'bottom' | 'left' | 'right', nodeId: string): string {
  if (nodeId === 'topic') {
    return direction === 'left' ? t('mindMap.add.leftBranch') : t('mindMap.add.rightBranch')
  }
  const isLeftBranch = nodeId.startsWith('branch-l-')
  if (direction === 'top') return t('mindMap.add.siblingAbove')
  if (direction === 'bottom') return t('mindMap.add.siblingBelow')
  if (direction === 'left') {
    return isLeftBranch ? t('mindMap.add.addChild') : t('mindMap.add.insertParent')
  }
  return isLeftBranch ? t('mindMap.add.insertParent') : t('mindMap.add.addChild')
}

function handleClick(
  direction: 'top' | 'bottom' | 'left' | 'right',
  event: MouseEvent
): void {
  event.stopPropagation()
  event.preventDefault()
  const nodeId = selectedNodeId.value
  if (!nodeId) return
  diagramStore.performMindMapDirectionalAdd(nodeId, direction)
}

let unsubOpen: (() => void) | undefined
let unsubClose: (() => void) | undefined

onMounted(() => {
  unsubOpen = eventBus.on('node_editor:opening', ({ nodeId }) => {
    editingNodeId.value = nodeId
  })
  unsubClose = eventBus.on('node_editor:closed', ({ nodeId }) => {
    if (editingNodeId.value === nodeId) editingNodeId.value = null
    scheduleMeasure()
  })
  eventBus.on('view:zoom_changed', scheduleMeasure)
  eventBus.on('view:fit_completed', scheduleMeasure)
  eventBus.on('diagram:node_added', () => {
    scheduleMeasure()
    setTimeout(scheduleMeasure, 80)
    setTimeout(scheduleMeasure, 200)
  })
  window.addEventListener('scroll', scheduleMeasure, true)
  window.addEventListener('resize', scheduleMeasure)
})

onUnmounted(() => {
  unsubOpen?.()
  unsubClose?.()
  window.removeEventListener('scroll', scheduleMeasure, true)
  window.removeEventListener('resize', scheduleMeasure)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && overlayEnabled && handles.length"
      class="mind-map-add-overlay"
      aria-hidden="false"
    >
      <button
        v-for="handle in handles"
        :key="handle.direction"
        type="button"
        class="mind-map-add-overlay__btn"
        :style="{ left: `${handle.left}px`, top: `${handle.top}px` }"
        :title="tooltipFor(handle.direction, selectedNodeId ?? '')"
        :aria-label="tooltipFor(handle.direction, selectedNodeId ?? '')"
        @click="handleClick(handle.direction, $event)"
        @mousedown.stop
        @pointerdown.stop
      >
        +
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.mind-map-add-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 4500;
}

.mind-map-add-overlay__btn {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin: 0;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 50%;
  background: #fff;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  cursor: pointer;
  pointer-events: auto;
  transform: translate(-50%, -50%);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
  transition:
    transform 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease;
}

.mind-map-add-overlay__btn:hover {
  transform: translate(-50%, -50%) scale(1.08);
  background: #e2e8f0;
  border-color: #94a3b8;
  color: #475569;
}
</style>
