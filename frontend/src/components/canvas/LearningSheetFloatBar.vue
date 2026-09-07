<script setup lang="ts">
/**
 * Learning-sheet session bar — custom pick / random blank, below the ribbon.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { Hammer, Shuffle, X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useLearningSheetCustomMode } from '@/composables/mindMap/useLearningSheetCustomMode'

const { t } = useLanguage()
const diagramStore = useDiagramSession()
const {
  isPickActive,
  blankCount,
  isFloatBarOpen,
  isLearningSheetActive,
  dismissFloatBar,
  exitLearningSheet,
} = useLearningSheetCustomMode()

const showBar = computed(() => isFloatBarOpen.value && diagramStore.isLearningSheet)

const showReferenceAnswers = computed(() => diagramStore.learningSheetShowAnswers)

const barTop = ref('96px')

function updateBarTop(): void {
  const chrome =
    document.querySelector('.canvas-top-bar--mindmap') ?? document.querySelector('.canvas-top-bar')
  const bottom = chrome instanceof HTMLElement ? chrome.getBoundingClientRect().bottom : 96
  barTop.value = `${bottom + 12}px`
}

function onHideAnswersChange(event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  diagramStore.setLearningSheetShowAnswers(!checked)
}

function onDone(): void {
  dismissFloatBar()
}

function onClose(): void {
  if (isLearningSheetActive.value) {
    dismissFloatBar()
    return
  }
  exitLearningSheet()
}

onMounted(() => {
  updateBarTop()
  window.addEventListener('resize', updateBarTop)
})

watch(showBar, (open) => {
  if (open) {
    requestAnimationFrame(updateBarTop)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', updateBarTop)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="ls-session-bar">
      <div
        v-if="showBar"
        class="ls-session-bar"
        :style="{ top: barTop }"
        role="status"
      >
        <span
          class="ls-session-bar__icon"
          :class="isPickActive ? 'ls-session-bar__icon--pick' : 'ls-session-bar__icon--random'"
          aria-hidden="true"
        >
          <Hammer
            v-if="isPickActive"
            class="h-3.5 w-3.5 rotate-[-38deg]"
            :stroke-width="2"
          />
          <Shuffle
            v-else
            class="h-3.5 w-3.5"
            :stroke-width="2"
          />
        </span>

        <div class="ls-session-bar__copy">
          <p class="ls-session-bar__title">
            {{
              isPickActive
                ? t('canvas.mindMapSideToolbar.learningSheetPickTitle')
                : t('canvas.mindMapSideToolbar.learningSheetRandomTitle')
            }}
          </p>
          <p class="ls-session-bar__hint">
            {{
              isPickActive
                ? t('canvas.mindMapSideToolbar.learningSheetPickHint', { count: blankCount })
                : t('canvas.mindMapSideToolbar.learningSheetRandomActiveHint', {
                    count: blankCount,
                  })
            }}
          </p>
        </div>

        <label
          v-if="blankCount > 0"
          class="ls-session-bar__answers"
        >
          <input
            type="checkbox"
            class="ls-session-bar__checkbox"
            :checked="!showReferenceAnswers"
            @change="onHideAnswersChange"
          />
          <span>{{ t('canvas.mindMapSideToolbar.learningSheetHideAnswers') }}</span>
        </label>

        <button
          type="button"
          class="ls-session-bar__done"
          @click="onDone"
        >
          {{ t('canvas.mindMapSideToolbar.learningSheetPickDone') }}
        </button>

        <button
          type="button"
          class="ls-session-bar__close"
          :aria-label="t('common.close')"
          @click="onClose"
        >
          <X
            class="h-3.5 w-3.5"
            :stroke-width="2"
          />
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.ls-session-bar {
  position: fixed;
  left: 50%;
  z-index: 10060;
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: min(94vw, 720px);
  padding: 8px 10px 8px 12px;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  background: #fff;
  box-shadow:
    0 10px 15px -3px rgb(15 23 42 / 0.12),
    0 4px 6px -4px rgb(15 23 42 / 0.08);
  transform: translateX(-50%);
  pointer-events: auto;
}

.ls-session-bar__icon {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  color: #fff;
}

.ls-session-bar__icon--pick {
  background: #2563eb;
}

.ls-session-bar__icon--random {
  background: #f59e0b;
}

.ls-session-bar__copy {
  min-width: 0;
  flex: 1;
}

.ls-session-bar__title {
  margin: 0;
  color: #111827;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.3;
}

.ls-session-bar__hint {
  margin: 2px 0 0;
  color: #6b7280;
  font-size: 11px;
  line-height: 1.35;
}

.ls-session-bar__answers {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #4b5563;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}

.ls-session-bar__checkbox {
  width: 13px;
  height: 13px;
  margin: 0;
  accent-color: #2563eb;
  cursor: pointer;
}

.ls-session-bar__done {
  flex-shrink: 0;
  height: 28px;
  padding: 0 14px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.ls-session-bar__done:hover {
  background: #1d4ed8;
}

.ls-session-bar__close {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #9ca3af;
  cursor: pointer;
}

.ls-session-bar__close:hover {
  background: #f9fafb;
  color: #6b7280;
}

.ls-session-bar-enter-active,
.ls-session-bar-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.ls-session-bar-enter-from,
.ls-session-bar-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-6px);
}
</style>
