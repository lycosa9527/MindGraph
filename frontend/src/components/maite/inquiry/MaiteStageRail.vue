<script setup lang="ts">
/**
 * MaiteStageRail — inquiry stage navigation (past + current only).
 */
import { useLanguage } from '@/composables/core/useLanguage'

import type { MaiteInquiryStage } from '@/types/maite'

const props = defineProps<{
  activeStage: MaiteInquiryStage
  readOnlyPhases: string[]
}>()

const emit = defineEmits<{
  select: [stage: MaiteInquiryStage]
}>()

const { t } = useLanguage()

const stages: MaiteInquiryStage[] = ['decompose', 'diagnosis', 'remedy', 'variant', 'completed']

function isReadOnly(stage: MaiteInquiryStage): boolean {
  return props.readOnlyPhases.includes(stage)
}

function isLocked(stage: MaiteInquiryStage): boolean {
  const order = stages.indexOf(stage)
  const current = stages.indexOf(props.activeStage)
  return order > current
}

function onSelect(stage: MaiteInquiryStage): void {
  if (isLocked(stage)) {
    return
  }
  emit('select', stage)
}
</script>

<template>
  <nav class="maite-stage-rail">
    <button
      v-for="stage in stages"
      :key="stage"
      type="button"
      class="maite-stage-rail__item"
      :class="{
        'maite-stage-rail__item--active': activeStage === stage,
        'maite-stage-rail__item--readonly': isReadOnly(stage),
        'maite-stage-rail__item--locked': isLocked(stage),
      }"
      :disabled="isLocked(stage)"
      @click="onSelect(stage)"
    >
      <span class="maite-stage-rail__label">{{ t(`maite.stage.${stage}`) }}</span>
    </button>
  </nav>
</template>

<style scoped>
.maite-stage-rail {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.maite-stage-rail__item {
  padding: 6px 12px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
}

.maite-stage-rail__item--active {
  border-color: #334155;
  background: #334155;
  color: #fff;
}

.maite-stage-rail__item--readonly:not(.maite-stage-rail__item--active) {
  opacity: 0.7;
}

.maite-stage-rail__item--locked {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
