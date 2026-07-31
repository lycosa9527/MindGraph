<script setup lang="ts">
/**
 * MaiteRemedyPanel — remedy task list and generate action.
 */
import { useLanguage } from '@/composables/core/useLanguage'

import type { MaiteRemedyTask } from '@/types/maite'

defineProps<{
  tasks: MaiteRemedyTask[]
  loading?: boolean
}>()

const emit = defineEmits<{
  generate: []
}>()

const { t } = useLanguage()
</script>

<template>
  <div class="maite-remedy-panel">
    <button type="button" class="maite-remedy-panel__btn" :disabled="loading" @click="emit('generate')">
      {{ loading ? t('maite.remedy.generating') : t('maite.remedy.generate') }}
    </button>
    <ul v-if="tasks.length > 0" class="maite-remedy-panel__list">
      <li v-for="task in tasks" :key="task.id">
        <strong>{{ task.block_name }}</strong>
        <span class="maite-remedy-panel__status">{{ task.status }}</span>
      </li>
    </ul>
    <p v-else class="maite-remedy-panel__empty">{{ t('maite.remedy.empty') }}</p>
  </div>
</template>

<style scoped>
.maite-remedy-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.maite-remedy-panel__btn {
  align-self: flex-start;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: #667eea;
  color: #fff;
  cursor: pointer;
}

.maite-remedy-panel__list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
}

.maite-remedy-panel__status {
  margin-left: 8px;
  color: var(--el-text-color-secondary, #78716c);
  font-size: 12px;
}

.maite-remedy-panel__empty {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary, #78716c);
}
</style>
