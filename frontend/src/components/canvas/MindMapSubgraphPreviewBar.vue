<script setup lang="ts">
/**
 * Accept / discard bar shown while a mind-map subgraph AI preview is active.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import { Check, X } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'

const PREVIEW_BAR_GAP_PX = 12

const props = defineProps<{
  anchorNodeId: string | null
  containerRef: HTMLElement | null
  visible: boolean
  layoutTick?: number
}>()

const emit = defineEmits<{
  accept: []
  discard: []
}>()

const { t } = useLanguage()

const position = ref({ left: 0, top: 0, visible: false })
let rafId = 0

function measure() {
  const container = props.containerRef
  const nodeId = props.anchorNodeId
  if (!props.visible || !container || !nodeId) {
    position.value = { left: 0, top: 0, visible: false }
    return
  }

  const nodeEl = container.querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
  if (!nodeEl) {
    position.value = { left: 0, top: 0, visible: false }
    return
  }

  const rect = nodeEl.getBoundingClientRect()
  position.value = {
    left: rect.left + rect.width / 2,
    top: rect.bottom + PREVIEW_BAR_GAP_PX,
    visible: true,
  }
}

function scheduleMeasure() {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    void nextTick(measure)
  })
}

watch(
  () => [props.visible, props.anchorNodeId, props.containerRef, props.layoutTick] as const,
  scheduleMeasure,
  { immediate: true }
)

onUnmounted(() => {
  cancelAnimationFrame(rafId)
})

const barStyle = computed(() => ({
  left: `${position.value.left}px`,
  top: `${position.value.top}px`,
}))
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && position.visible"
      class="mindmap-subgraph-preview-bar pointer-events-auto"
      :style="barStyle"
      @mousedown.stop
      @click.stop
    >
      <span class="mspb-label">{{ t('canvas.subgraphPreview.hint') }}</span>
      <button
        type="button"
        class="mspb-btn mspb-btn--accept"
        @click="emit('accept')"
      >
        <Check class="mspb-icon" />
        {{ t('canvas.subgraphPreview.accept') }}
      </button>
      <button
        type="button"
        class="mspb-btn mspb-btn--discard"
        @click="emit('discard')"
      >
        <X class="mspb-icon" />
        {{ t('canvas.subgraphPreview.discard') }}
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.mindmap-subgraph-preview-bar {
  position: fixed;
  z-index: 5001;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 9999px;
  border: 1px solid rgba(147, 197, 253, 0.9);
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.97), rgba(255, 255, 255, 0.97));
  backdrop-filter: blur(12px);
  box-shadow:
    0 4px 20px rgba(59, 130, 246, 0.15),
    0 1px 3px rgba(15, 23, 42, 0.06);
}

.mspb-label {
  font-size: 12px;
  font-weight: 500;
  color: #1e40af;
  white-space: nowrap;
  padding-right: 2px;
}

.mspb-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  border-radius: 9999px;
  border: none;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}

.mspb-btn:active {
  transform: scale(0.97);
}

.mspb-btn--accept {
  background: #2563eb;
  color: #fff;
}

.mspb-btn--accept:hover {
  background: #1d4ed8;
}

.mspb-btn--discard {
  background: rgba(241, 245, 249, 0.95);
  color: #475569;
  border: 1px solid #e2e8f0;
}

.mspb-btn--discard:hover {
  background: #f1f5f9;
}

.mspb-icon {
  width: 14px;
  height: 14px;
}
</style>
