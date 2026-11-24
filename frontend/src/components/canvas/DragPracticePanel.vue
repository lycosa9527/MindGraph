<script setup lang="ts">
/**
 * Right column of classroom drag-fill split (canvas | options).
 * Parent mounts this only while the split is open; root must stay in normal flow.
 */
import { computed, nextTick, onMounted, onUnmounted, watch } from 'vue'

import { RotateCcw, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { eventBus } from '@/composables/core/useEventBus'
import {
  type DragPracticeChip,
  dragPracticeActive,
  dragPracticeBlankCount,
  dragPracticeChips,
  dragPracticeCorrectCount,
  dragPracticeDraggingId,
  dragPracticePicking,
  dragPracticeTotalCount,
  dragPracticeUsedChipIds,
  exitDragPractice,
  restartDragPractice,
  startDragPracticeWithExistingBlanks,
} from '@/composables/mindMap/useDragPractice'

const remainingChips = computed(() =>
  dragPracticeChips.value.filter((chip) => !dragPracticeUsedChipIds.value.includes(chip.id))
)

const showPickContinue = computed(() => !dragPracticeActive.value && dragPracticePicking.value)

function emitPracticeFit(): void {
  eventBus.emit('view:fit_to_canvas_requested', { animate: true, userInitiated: true })
}

function requestFit(): void {
  void nextTick(() => {
    const canvas = document.querySelector('.canvas-page--drag-practice .diagram-canvas')
    if (!(canvas instanceof HTMLElement)) {
      requestAnimationFrame(emitPracticeFit)
      return
    }
    const initialWidth = canvas.clientWidth
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      observer.disconnect()
      window.clearTimeout(timer)
      emitPracticeFit()
    }
    const observer = new ResizeObserver(() => {
      if (canvas.clientWidth > 0 && canvas.clientWidth !== initialWidth) finish()
    })
    observer.observe(canvas)
    const timer = window.setTimeout(finish, 220)
  })
}

onMounted(requestFit)
onUnmounted(() => {
  requestAnimationFrame(() => {
    requestAnimationFrame(emitPracticeFit)
  })
})
watch(dragPracticeActive, requestFit)

function onDragStart(chip: DragPracticeChip, event: DragEvent): void {
  dragPracticeDraggingId.value = chip.id
  event.dataTransfer?.setData('text/plain', chip.text)
  event.dataTransfer?.setData('application/x-mg-drag-practice', chip.id)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy'
}

function onDragEnd(): void {
  dragPracticeDraggingId.value = null
}
</script>

<template>
  <aside
    class="drag-practice-pane"
    role="complementary"
    :aria-label="$t('canvas.dragPractice.title')"
  >
    <header class="drag-practice-pane__header">
      <div class="min-w-0 flex-1">
        <p class="drag-practice-pane__title">
          <I18nText k="canvas.dragPractice.panelTitle" />
        </p>
        <p class="drag-practice-pane__hint">
          <I18nText
            v-if="showPickContinue"
            k="canvas.dragPractice.pickHint"
            :params="{ count: dragPracticeBlankCount }"
          />
          <I18nText
            v-else
            k="canvas.dragPractice.hint"
          />
        </p>
      </div>
      <button
        type="button"
        class="drag-practice-pane__icon-btn"
        :aria-label="$t('common.close')"
        @click="exitDragPractice()"
      >
        <X
          class="h-4 w-4"
          :stroke-width="2"
        />
      </button>
    </header>

    <div
      v-if="showPickContinue"
      class="drag-practice-pane__body"
    >
      <button
        type="button"
        class="drag-practice-pane__primary"
        :disabled="dragPracticeBlankCount === 0"
        @click="startDragPracticeWithExistingBlanks()"
      >
        <I18nText k="canvas.dragPractice.start" />
      </button>
    </div>

    <template v-else>
      <div class="drag-practice-pane__progress">
        <I18nText
          k="canvas.dragPractice.progress"
          :params="{ done: dragPracticeCorrectCount, total: dragPracticeTotalCount }"
        />
      </div>

      <div class="drag-practice-pane__chips">
        <button
          v-for="chip in remainingChips"
          :key="chip.id"
          type="button"
          class="drag-practice-chip"
          :class="{
            'is-dragging': dragPracticeDraggingId === chip.id,
          }"
          draggable="true"
          @dragstart="onDragStart(chip, $event)"
          @dragend="onDragEnd"
        >
          {{ chip.text }}
        </button>
        <p
          v-if="remainingChips.length === 0"
          class="drag-practice-pane__empty"
        >
          <I18nText k="canvas.dragPractice.allDone" />
        </p>
      </div>

      <footer class="drag-practice-pane__footer">
        <button
          type="button"
          class="drag-practice-pane__restart"
          @click="restartDragPractice()"
        >
          <RotateCcw
            class="h-3.5 w-3.5"
            :stroke-width="2"
            aria-hidden="true"
          />
          <I18nText k="canvas.dragPractice.restart" />
        </button>
      </footer>
    </template>
  </aside>
</template>

<style scoped>
.drag-practice-pane {
  box-sizing: border-box;
  display: flex;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid #e5e7eb;
  background: #f7f8fa;
  /* Guard: never float over the canvas */
  position: relative !important;
  inset: auto !important;
  top: auto !important;
  right: auto !important;
  bottom: auto !important;
  left: auto !important;
  z-index: auto !important;
  margin: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  backdrop-filter: none !important;
}

.drag-practice-pane__header {
  display: flex;
  flex-shrink: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 18px 16px 12px;
  border-bottom: 1px solid #eceff3;
  background: #fff;
}

.drag-practice-pane__title {
  margin: 0;
  color: #1f2937;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
}

.drag-practice-pane__hint {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.45;
}

.drag-practice-pane__icon-btn {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
}

.drag-practice-pane__icon-btn:hover {
  background: #f3f4f6;
  color: #374151;
}

.drag-practice-pane__body {
  padding: 16px;
}

.drag-practice-pane__progress {
  flex-shrink: 0;
  padding: 10px 16px 0;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.drag-practice-pane__chips {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-content: start;
  min-height: 0;
  overflow: auto;
  padding: 12px 16px;
}

.drag-practice-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid #93c5fd;
  border-radius: 10px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.3;
  text-align: center;
  cursor: grab;
  user-select: none;
  transition:
    transform 0.12s ease,
    box-shadow 0.12s ease,
    opacity 0.12s ease;
}

.drag-practice-chip:hover {
  box-shadow: 0 2px 8px rgb(15 23 42 / 0.08);
  transform: translateY(-1px);
}

.drag-practice-chip.is-dragging {
  opacity: 0.5;
  cursor: grabbing;
}

.drag-practice-pane__empty {
  grid-column: 1 / -1;
  margin: 12px 0;
  color: #047857;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}

.drag-practice-pane__footer {
  flex-shrink: 0;
  padding: 12px 16px 16px;
  border-top: 1px solid #eceff3;
  background: #fff;
}

.drag-practice-pane__primary,
.drag-practice-pane__restart {
  display: inline-flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.drag-practice-pane__primary {
  border: 1px solid #60a5fa;
  background: #3b82f6;
  color: #fff;
}

.drag-practice-pane__primary:hover {
  background: #2563eb;
}

.drag-practice-pane__primary:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.drag-practice-pane__restart {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}

.drag-practice-pane__restart:hover {
  background: #dbeafe;
}

:global(html.dark) .drag-practice-pane {
  border-left-color: #44403c;
  background: #1c1917;
}

:global(html.dark) .drag-practice-pane__header,
:global(html.dark) .drag-practice-pane__footer {
  border-color: #44403c;
  background: #292524;
}

:global(html.dark) .drag-practice-pane__title {
  color: #f5f5f4;
}

:global(html.dark) .drag-practice-pane__hint,
:global(html.dark) .drag-practice-pane__progress {
  color: #a8a29e;
}

:global(html.dark) .drag-practice-pane__restart {
  border-color: #1e3a8a;
  background: #1e3a5f;
  color: #bfdbfe;
}
</style>
