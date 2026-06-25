<script setup lang="ts">
/**
 * Coach mark below Export when a learning sheet has blanked nodes.
 * Mounted from CanvasPage (not inside the toolbar) so overflow cannot hide it.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import { X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useDiagramStore } from '@/stores'

const EXPORT_BUTTON_SELECTORS = [
  '[data-learning-sheet-export-anchor]',
  '.mm-btn--export',
  '[data-canvas-export-anchor]',
]

const STORAGE_KEY = 'mindgraph.learningSheet.exportNudge.neverRemind'

const { t } = useLanguage()
const diagramStore = useDiagramStore()

const neverRemind = ref(readNeverRemind())
const sessionDismissed = ref(false)
const dontRemindChecked = ref(false)
const anchorRect = ref<DOMRect | null>(null)

function readNeverRemind(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

const blankCount = computed(() => {
  const nodes = diagramStore.data?.nodes
  if (!nodes?.length) return 0
  return nodes.filter((n) => diagramStore.isNodeBlankedForLearningSheet(n.id)).length
})

const visible = computed(
  () => blankCount.value > 0 && !neverRemind.value && !sessionDismissed.value
)

const nudgeStyle = computed(() => {
  const rect = anchorRect.value
  if (!rect) {
    return {
      top: '64px',
      left: '50%',
      transform: 'translateX(-50%)',
    }
  }
  const centerX = rect.left + rect.width / 2
  return {
    top: `${rect.bottom + 6}px`,
    left: `${centerX}px`,
    transform: 'translateX(-50%)',
  }
})

let rafId = 0
let pollTimer: ReturnType<typeof setInterval> | null = null

function findExportButton(): HTMLElement | null {
  for (const selector of EXPORT_BUTTON_SELECTORS) {
    const el = document.querySelector(selector)
    if (el instanceof HTMLElement) return el
  }
  return null
}

function updateAnchorRect(): void {
  anchorRect.value = findExportButton()?.getBoundingClientRect() ?? null
}

function scheduleAnchorUpdate(): void {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(updateAnchorRect)
}

function bindPositionListeners(): void {
  window.addEventListener('resize', scheduleAnchorUpdate)
  window.addEventListener('scroll', scheduleAnchorUpdate, true)
}

function unbindPositionListeners(): void {
  window.removeEventListener('resize', scheduleAnchorUpdate)
  window.removeEventListener('scroll', scheduleAnchorUpdate, true)
  cancelAnimationFrame(rafId)
}

function stopAnchorPoll(): void {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startAnchorPoll(): void {
  stopAnchorPoll()
  let attempts = 0
  pollTimer = setInterval(() => {
    scheduleAnchorUpdate()
    attempts += 1
    if (anchorRect.value || attempts >= 30) {
      stopAnchorPoll()
    }
  }, 100)
}

async function bindAnchorWhenVisible(): Promise<void> {
  await nextTick()
  scheduleAnchorUpdate()
  bindPositionListeners()
  startAnchorPoll()
  window.setTimeout(scheduleAnchorUpdate, 200)
  window.setTimeout(scheduleAnchorUpdate, 600)
}

watch(blankCount, (count, prev) => {
  if (count > 0 && (prev === 0 || prev === undefined)) {
    neverRemind.value = readNeverRemind()
    if (!neverRemind.value) {
      sessionDismissed.value = false
      dontRemindChecked.value = false
    }
  }
})

watch(
  visible,
  async (show) => {
    if (!show) {
      unbindPositionListeners()
      stopAnchorPoll()
      return
    }
    await bindAnchorWhenVisible()
  },
  { immediate: true }
)

watch(
  () => diagramStore.isLearningSheet,
  (active, wasActive) => {
    if (!active && wasActive) {
      sessionDismissed.value = false
      dontRemindChecked.value = false
    }
    if (active && !wasActive && blankCount.value > 0 && !neverRemind.value) {
      sessionDismissed.value = false
      dontRemindChecked.value = false
    }
  }
)

onUnmounted(() => {
  unbindPositionListeners()
  stopAnchorPoll()
})

function dismissForSession(): void {
  sessionDismissed.value = true
  if (dontRemindChecked.value) {
    neverRemind.value = true
    try {
      localStorage.setItem(STORAGE_KEY, '1')
    } catch {
      /* ignore private mode */
    }
  }
}

function onNeverRemindChange(event: Event): void {
  dontRemindChecked.value = (event.target as HTMLInputElement).checked
}
</script>

<template>
  <Teleport to="body">
    <Transition name="ls-export-nudge">
      <div
        v-if="visible"
        class="ls-export-nudge"
        :style="nudgeStyle"
        role="status"
      >
        <span
          class="ls-export-nudge__arrow"
          aria-hidden="true"
        />
        <div class="ls-export-nudge__card">
          <button
            type="button"
            class="ls-export-nudge__close"
            :aria-label="t('canvas.toolbar.learningSheetExportNudgeDismiss')"
            @click="dismissForSession"
          >
            <X
              class="h-3 w-3"
              :stroke-width="2"
            />
          </button>
          <p class="ls-export-nudge__title">
            {{ t('canvas.toolbar.learningSheetExportNudgeTitle') }}
          </p>
          <p class="ls-export-nudge__desc">
            {{ t('canvas.toolbar.learningSheetExportNudgeDesc') }}
          </p>
          <div class="ls-export-nudge__footer">
            <label class="ls-export-nudge__never">
              <input
                type="checkbox"
                class="ls-export-nudge__checkbox"
                :checked="dontRemindChecked"
                @change="onNeverRemindChange"
              />
              <span>{{ t('canvas.toolbar.learningSheetExportNudgeNeverRemind') }}</span>
            </label>
            <button
              type="button"
              class="ls-export-nudge__action"
              @click="dismissForSession"
            >
              {{ t('canvas.toolbar.learningSheetExportNudgeDismiss') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.ls-export-nudge {
  position: fixed;
  z-index: 10050;
  width: max-content;
  max-width: min(13.5rem, calc(100vw - 2rem));
  pointer-events: auto;
}

.ls-export-nudge__arrow {
  position: absolute;
  top: -5px;
  left: 50%;
  width: 10px;
  height: 10px;
  margin-left: -5px;
  background: #fffbeb;
  border-left: 1px solid rgb(251 191 36 / 0.45);
  border-top: 1px solid rgb(251 191 36 / 0.45);
  transform: rotate(45deg);
}

.ls-export-nudge__card {
  position: relative;
  padding: 7px 26px 7px 9px;
  border: 1px solid rgb(251 191 36 / 0.4);
  border-radius: 8px;
  background: rgb(255 251 235 / 0.97);
  box-shadow: 0 4px 14px rgb(15 23 42 / 0.08);
}

.ls-export-nudge__close {
  position: absolute;
  top: 5px;
  right: 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
}

.ls-export-nudge__close:hover {
  background: rgb(251 191 36 / 0.12);
  color: #78716c;
}

.ls-export-nudge__title {
  margin: 0;
  color: #92400e;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
}

.ls-export-nudge__desc {
  margin: 2px 0 0;
  color: #a8a29e;
  font-size: 10px;
  line-height: 1.35;
}

.ls-export-nudge__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
}

.ls-export-nudge__never {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  color: #a8a29e;
  font-size: 10px;
  cursor: pointer;
  user-select: none;
}

.ls-export-nudge__checkbox {
  width: 11px;
  height: 11px;
  margin: 0;
  accent-color: #d97706;
  cursor: pointer;
}

.ls-export-nudge__action {
  flex-shrink: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: #b45309;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
}

.ls-export-nudge__action:hover {
  color: #92400e;
  text-decoration: underline;
}

.ls-export-nudge-enter-active,
.ls-export-nudge-leave-active {
  transition: opacity 0.18s ease;
}

.ls-export-nudge-enter-from,
.ls-export-nudge-leave-to {
  opacity: 0;
}
</style>
