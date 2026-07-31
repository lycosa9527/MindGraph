<script setup lang="ts">
/**
 * MaiteTablesEditor — editable three-table decompose submission.
 */
import { useLanguage } from '@/composables/core/useLanguage'

import type { MaiteTableRow } from '@/types/maite'

const props = defineProps<{
  conditionTable: MaiteTableRow[]
  stepTable: MaiteTableRow[]
  modelTable: MaiteTableRow[]
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:conditionTable': [rows: MaiteTableRow[]]
  'update:stepTable': [rows: MaiteTableRow[]]
  'update:modelTable': [rows: MaiteTableRow[]]
}>()

const { t } = useLanguage()

function updateRow(table: 'condition' | 'step' | 'model', index: number, value: string): void {
  if (table === 'condition') {
    const next = props.conditionTable.map((row, rowIndex) =>
      rowIndex === index ? { ...row, content: value } : row
    )
    emit('update:conditionTable', next)
    return
  }
  if (table === 'step') {
    const next = props.stepTable.map((row, rowIndex) =>
      rowIndex === index ? { ...row, content: value } : row
    )
    emit('update:stepTable', next)
    return
  }
  const next = props.modelTable.map((row, rowIndex) =>
    rowIndex === index ? { ...row, content: value } : row
  )
  emit('update:modelTable', next)
}

function addRow(table: 'condition' | 'step' | 'model'): void {
  if (table === 'condition') {
    emit('update:conditionTable', [...props.conditionTable, { content: '' }])
    return
  }
  if (table === 'step') {
    emit('update:stepTable', [...props.stepTable, { content: '' }])
    return
  }
  emit('update:modelTable', [...props.modelTable, { content: '' }])
}
</script>

<template>
  <div class="maite-tables-editor">
    <section class="maite-tables-editor__section">
      <h4>{{ t('maite.tables.condition') }}</h4>
      <div v-for="(row, index) in conditionTable" :key="`c-${index}`" class="maite-tables-editor__row">
        <input
          :value="String(row.content ?? '')"
          :readonly="readonly"
          @input="updateRow('condition', index, ($event.target as HTMLInputElement).value)"
        />
      </div>
      <button v-if="!readonly" type="button" @click="addRow('condition')">{{ t('maite.tables.addRow') }}</button>
    </section>

    <section class="maite-tables-editor__section">
      <h4>{{ t('maite.tables.step') }}</h4>
      <div v-for="(row, index) in stepTable" :key="`s-${index}`" class="maite-tables-editor__row">
        <input
          :value="String(row.content ?? '')"
          :readonly="readonly"
          @input="updateRow('step', index, ($event.target as HTMLInputElement).value)"
        />
      </div>
      <button v-if="!readonly" type="button" @click="addRow('step')">{{ t('maite.tables.addRow') }}</button>
    </section>

    <section class="maite-tables-editor__section">
      <h4>{{ t('maite.tables.model') }}</h4>
      <div v-for="(row, index) in modelTable" :key="`m-${index}`" class="maite-tables-editor__row">
        <input
          :value="String(row.content ?? '')"
          :readonly="readonly"
          @input="updateRow('model', index, ($event.target as HTMLInputElement).value)"
        />
      </div>
      <button v-if="!readonly" type="button" @click="addRow('model')">{{ t('maite.tables.addRow') }}</button>
    </section>
  </div>
</template>

<style scoped>
.maite-tables-editor {
  display: grid;
  gap: 12px;
}

.maite-tables-editor__section {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
}

.maite-tables-editor__section h4 {
  margin: 0 0 8px;
  font-size: 13px;
}

.maite-tables-editor__row input {
  width: 100%;
  margin-bottom: 6px;
  padding: 8px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 6px;
  font-size: 13px;
}

.maite-tables-editor__section button {
  margin-top: 4px;
  border: none;
  background: transparent;
  color: #667eea;
  cursor: pointer;
  font-size: 12px;
}
</style>
