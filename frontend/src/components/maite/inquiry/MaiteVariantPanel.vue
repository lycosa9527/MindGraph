<script setup lang="ts">
/**
 * MaiteVariantPanel — variant practice tasks.
 */
import { useLanguage } from '@/composables/core/useLanguage'

import MaiteMathText from '@/components/maite/shared/MaiteMathText.vue'

import type { MaiteVariantTask } from '@/types/maite'

defineProps<{
  tasks: MaiteVariantTask[]
  loading?: boolean
}>()

const emit = defineEmits<{
  generate: []
  complete: []
}>()

const { t } = useLanguage()
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
        :disabled="loading"
        @click="emit('complete')"
      >
        {{ t('maite.inquiry.complete') }}
      </button>
    </div>
    <article v-for="task in tasks" :key="task.id" class="maite-variant-panel__card">
      <header>
        <span class="maite-variant-panel__type">{{ task.variant_type }}</span>
        <span class="maite-variant-panel__status">{{ task.status }}</span>
      </header>
      <MaiteMathText :text="task.variant_text" tag="p" />
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
  background: #667eea;
  color: #fff;
  cursor: pointer;
}

.maite-variant-panel__btn--secondary {
  background: var(--el-fill-color, #fafaf9);
  color: var(--el-text-color-primary, #1c1917);
  border: 1px solid var(--el-border-color, #e7e5e4);
}

.maite-variant-panel__card {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
  background: #fff;
}

.maite-variant-panel__card header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
}

.maite-variant-panel__card p {
  margin: 0;
  font-size: 13px;
}

.maite-variant-panel__empty {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary, #78716c);
}
</style>
