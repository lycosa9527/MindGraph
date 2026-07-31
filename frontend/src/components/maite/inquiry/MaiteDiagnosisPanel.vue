<script setup lang="ts">
/**
 * MaiteDiagnosisPanel — auto diagnosis stage UI.
 */
import { useLanguage } from '@/composables/core/useLanguage'

defineProps<{
  loading?: boolean
  result: Record<string, unknown> | null
}>()

const emit = defineEmits<{
  runAuto: []
}>()

const studentThinking = defineModel<string>('studentThinking', { default: '' })

const { t } = useLanguage()
</script>

<template>
  <div class="maite-diagnosis-panel">
    <textarea
      v-model="studentThinking"
      class="maite-diagnosis-panel__input"
      :placeholder="t('maite.diagnosis.thinkingPlaceholder')"
      rows="4"
    />
    <button type="button" class="maite-diagnosis-panel__btn" :disabled="loading" @click="emit('runAuto')">
      {{ loading ? t('maite.diagnosis.running') : t('maite.diagnosis.runAuto') }}
    </button>
    <pre v-if="result" class="maite-diagnosis-panel__result">{{ JSON.stringify(result, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.maite-diagnosis-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.maite-diagnosis-panel__input {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 8px;
  font-family: inherit;
  font-size: 14px;
}

.maite-diagnosis-panel__btn {
  align-self: flex-start;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: #667eea;
  color: #fff;
  cursor: pointer;
}

.maite-diagnosis-panel__result {
  max-height: 240px;
  overflow: auto;
  padding: 10px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter, #fafaf9);
  font-size: 12px;
}
</style>
