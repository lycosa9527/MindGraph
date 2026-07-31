<script setup lang="ts">
/**
 * MaiteVariantPanel — variant practice tasks with real answer submission.
 */
import { reactive, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'

import MaiteMathText from '@/components/maite/shared/MaiteMathText.vue'

import type { MaiteVariantTask } from '@/types/maite'

const props = defineProps<{
  tasks: MaiteVariantTask[]
  loading?: boolean
  canComplete?: boolean
}>()

const emit = defineEmits<{
  generate: []
  complete: []
  submit: [taskId: number, answer: string, strategy: string]
}>()

const { t } = useLanguage()

const drafts = reactive<Record<number, { answer: string; strategy: string }>>({})

watch(
  () => props.tasks,
  (tasks) => {
    for (const task of tasks) {
      if (!drafts[task.id]) {
        drafts[task.id] = {
          answer: task.student_answer ?? '',
          strategy: task.student_strategy ?? '',
        }
      }
    }
  },
  { immediate: true, deep: true }
)

function onSubmit(task: MaiteVariantTask): void {
  const draft = drafts[task.id]
  if (!draft) {
    return
  }
  emit('submit', task.id, draft.answer, draft.strategy)
}
</script>

<template>
  <div class="maite-variant-panel">
    <div class="maite-variant-panel__actions">
      <button type="button" class="maite-variant-panel__btn" :disabled="loading" @click="emit('generate')">
        {{ t('maite.variant.generate') }}
      </button>
      <button
        type="button"
        class="maite-variant-panel__btn maite-variant-panel__btn--secondary"
        :disabled="loading || !canComplete"
        @click="emit('complete')"
      >
        {{ t('maite.inquiry.complete') }}
      </button>
    </div>
    <p v-if="tasks.length > 0 && !canComplete" class="maite-variant-panel__hint">
      {{ t('maite.variant.completeHint') }}
    </p>
    <article v-for="task in tasks" :key="task.id" class="maite-variant-panel__card">
      <header>
        <span class="maite-variant-panel__type">{{ task.variant_type }}</span>
        <span class="maite-variant-panel__status">{{ task.status }}</span>
      </header>
      <MaiteMathText :text="task.variant_text" tag="p" />
      <template v-if="task.status !== 'submitted' && drafts[task.id]">
        <label class="maite-variant-panel__label">
          {{ t('maite.variant.answer') }}
          <textarea
            v-model="drafts[task.id].answer"
            rows="3"
            :disabled="loading"
            :placeholder="t('maite.variant.answerPlaceholder')"
          />
        </label>
        <label class="maite-variant-panel__label">
          {{ t('maite.variant.strategy') }}
          <textarea
            v-model="drafts[task.id].strategy"
            rows="2"
            :disabled="loading"
            :placeholder="t('maite.variant.strategyPlaceholder')"
          />
        </label>
        <button
          type="button"
          class="maite-variant-panel__btn"
          :disabled="loading"
          @click="onSubmit(task)"
        >
          {{ t('maite.variant.submit') }}
        </button>
      </template>
      <template v-else>
        <p class="maite-variant-panel__submitted">
          <strong>{{ t('maite.variant.answer') }}:</strong> {{ task.student_answer }}
        </p>
        <p class="maite-variant-panel__submitted">
          <strong>{{ t('maite.variant.strategy') }}:</strong> {{ task.student_strategy }}
        </p>
      </template>
    </article>
    <p v-if="tasks.length === 0" class="maite-variant-panel__empty">{{ t('maite.variant.empty') }}</p>
  </div>
</template>

<style scoped>
.maite-variant-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.maite-variant-panel__actions {
  display: flex;
  gap: 8px;
}

.maite-variant-panel__btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: #334155;
  color: #fff;
  cursor: pointer;
}

.maite-variant-panel__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.maite-variant-panel__btn--secondary {
  background: var(--el-fill-color, #fafaf9);
  color: var(--el-text-color-primary, #1c1917);
  border: 1px solid var(--el-border-color, #e7e5e4);
}

.maite-variant-panel__hint {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary, #78716c);
}

.maite-variant-panel__card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
  background: #fff;
}

.maite-variant-panel__card header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.maite-variant-panel__card p {
  margin: 0;
  font-size: 13px;
}

.maite-variant-panel__label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #78716c);
}

.maite-variant-panel__label textarea {
  resize: vertical;
  padding: 8px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 8px;
  font: inherit;
}

.maite-variant-panel__submitted {
  font-size: 12px;
  color: var(--el-text-color-regular, #44403c);
}

.maite-variant-panel__empty {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary, #78716c);
}
</style>
