<script setup lang="ts">
/**
 * MaiteDecomposeTables — display three reverse-decompose tables.
 */
import { computed } from 'vue'

import MaiteMathText from '@/components/maite/shared/MaiteMathText.vue'
import { useLanguage } from '@/composables/core/useLanguage'

import type { MaiteDecomposeTables } from '@/types/maite'

const props = defineProps<{
  tables: MaiteDecomposeTables | null
}>()

const { t } = useLanguage()

const sections = computed(() => {
  if (!props.tables) {
    return []
  }
  return [
    { key: 'condition', title: t('maite.tables.condition'), rows: props.tables.condition_table },
    { key: 'step', title: t('maite.tables.step'), rows: props.tables.step_table },
    { key: 'model', title: t('maite.tables.model'), rows: props.tables.model_table },
  ]
})

function rowText(row: Record<string, string>): string {
  const values = Object.values(row).filter(Boolean)
  return values.join(' · ') || '—'
}
</script>

<template>
  <div v-if="tables" class="maite-decompose-tables">
    <section v-for="section in sections" :key="section.key" class="maite-decompose-tables__section">
      <h4 class="maite-decompose-tables__title">{{ section.title }}</h4>
      <ul class="maite-decompose-tables__list">
        <li v-for="(row, index) in section.rows" :key="`${section.key}-${index}`">
          <MaiteMathText :text="rowText(row as Record<string, string>)" />
        </li>
      </ul>
    </section>
    <p v-if="tables.next_question" class="maite-decompose-tables__question">
      <strong>{{ t('maite.demo.nextQuestion') }}:</strong>
      <MaiteMathText :text="tables.next_question" />
    </p>
  </div>
</template>

<style scoped>
.maite-decompose-tables {
  display: grid;
  gap: 12px;
}

.maite-decompose-tables__section {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
  background: #fff;
}

.maite-decompose-tables__title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
}

.maite-decompose-tables__list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.6;
}

.maite-decompose-tables__question {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light, #f5f5f4);
  font-size: 13px;
}
</style>
