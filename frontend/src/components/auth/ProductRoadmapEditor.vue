<script setup lang="ts">
/**
 * Super-admin form for the shared product roadmap.
 */
import { computed, ref } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'

import {
  ROADMAP_COLUMNS,
  blankRoadmapItem,
  cloneRoadmapItems,
  roadmapTargetOptions,
} from './productRoadmap'
import type { RoadmapItem } from './productRoadmap'

const props = defineProps<{
  items: RoadmapItem[]
  saving: boolean
  saveError: boolean
}>()

const emit = defineEmits<{
  save: [items: RoadmapItem[]]
}>()

const { t } = useLanguage()
const draft = ref<RoadmapItem[]>(cloneRoadmapItems(props.items))
const columnChoices = computed(() =>
  ROADMAP_COLUMNS.map((value) => ({
    value,
    text: t(`auth.productRoadmap.${value}`),
  }))
)
const targetNoneLabel = computed(() => t('auth.productRoadmap.targetNone'))

const canSave = computed(
  () => !props.saving && draft.value.every((item) => item.title.trim() !== '')
)

function addItem(): void {
  draft.value.push(blankRoadmapItem())
}

function removeItem(index: number): void {
  draft.value.splice(index, 1)
}

function submit(): void {
  if (!canSave.value) return
  emit(
    'save',
    draft.value.map((item) => ({
      column: item.column,
      title: item.title.trim(),
      summary: item.summary.trim(),
      owner: item.owner.trim(),
      area: item.area.trim(),
      target: item.target,
    }))
  )
}

function saveReady(): boolean {
  return canSave.value
}

defineExpose({ addItem, submit, saveReady })
</script>

<template>
  <form
    class="roadmap-editor"
    @submit.prevent="submit"
  >
    <p
      v-if="draft.length === 0"
      class="roadmap-editor__empty"
    >
      <I18nText k="auth.productRoadmapEmpty" />
    </p>
    <article
      v-for="(item, index) in draft"
      :key="index"
      class="roadmap-editor__card"
    >
      <label class="roadmap-editor__field">
        <span><I18nText k="auth.productRoadmap.column" /></span>
        <select v-model="item.column">
          <option
            v-for="column in columnChoices"
            :key="column.value"
            :value="column.value"
          >
            {{ column.text }}
          </option>
        </select>
      </label>
      <label class="roadmap-editor__field">
        <span><I18nText k="auth.productRoadmap.fieldTitle" /></span>
        <input
          v-model="item.title"
          type="text"
          maxlength="400"
        />
      </label>
      <label class="roadmap-editor__field">
        <span><I18nText k="auth.productRoadmap.fieldSummary" /></span>
        <textarea
          v-model="item.summary"
          rows="2"
          maxlength="400"
        />
      </label>
      <div class="roadmap-editor__pair">
        <label class="roadmap-editor__field">
          <span><I18nText k="auth.productRoadmap.fieldOwner" /></span>
          <input
            v-model="item.owner"
            type="text"
            maxlength="80"
          />
        </label>
        <label class="roadmap-editor__field">
          <span><I18nText k="auth.productRoadmap.fieldTarget" /></span>
          <select v-model="item.target">
            <option value="">{{ targetNoneLabel }}</option>
            <option
              v-for="month in roadmapTargetOptions(item.target)"
              :key="month"
              :value="month"
            >
              {{ month }}
            </option>
          </select>
        </label>
      </div>
      <label class="roadmap-editor__field">
        <span><I18nText k="auth.productRoadmap.fieldArea" /></span>
        <input
          v-model="item.area"
          type="text"
          maxlength="80"
        />
      </label>
      <button
        type="button"
        class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost roadmap-editor__remove"
        @click="removeItem(index)"
      >
        <I18nText k="auth.productRoadmap.remove" />
      </button>
    </article>
    <p
      v-if="saveError"
      class="roadmap-editor__error"
    >
      <I18nText k="auth.productRoadmap.saveError" />
    </p>
  </form>
</template>

<style scoped>
.roadmap-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.roadmap-editor__empty,
.roadmap-editor__error {
  margin: 0;
  font-size: 13px;
  color: hsl(0deg 0% 38%);
}

.roadmap-editor__error {
  color: hsl(0deg 62% 42%);
}

.roadmap-editor__card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border-radius: 10px;
  background: hsl(40deg 20% 97%);
}

.roadmap-editor__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: hsl(0deg 0% 32%);
}

.roadmap-editor__pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.roadmap-editor__field input,
.roadmap-editor__field textarea,
.roadmap-editor__field select {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid var(--swiss-border-strong, #d6d3d1);
  border-radius: 10px;
  font: inherit;
  font-size: 13px;
  color: var(--swiss-ink, #1c1917);
  background: var(--swiss-surface, #fff);
}

.roadmap-editor__field input:focus,
.roadmap-editor__field textarea:focus,
.roadmap-editor__field select:focus {
  outline: 2px solid var(--swiss-ink, #1c1917);
  outline-offset: 1px;
}

.roadmap-editor__remove {
  align-self: flex-start;
}
</style>
