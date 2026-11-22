<script setup lang="ts">
/**
 * Product roadmap from the shared COS object, opened from the account menu.
 */
import { computed, ref, useTemplateRef, watch } from 'vue'

import { ElScrollbar } from 'element-plus'

import { Route } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { apiGet, apiPut } from '@/utils/apiClient'

import ProductRoadmapEditor from './ProductRoadmapEditor.vue'
import { ROADMAP_COLUMNS, blankRoadmapItem, ownerHue, ownerMark } from './productRoadmap'
import type { RoadmapItem } from './productRoadmap'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t } = useLanguage()
const authStore = useAuthStore()
const editorRef = useTemplateRef<InstanceType<typeof ProductRoadmapEditor>>('editor')

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const COLUMNS = ROADMAP_COLUMNS

const loading = ref(false)
const loadError = ref(false)
const updatedAt = ref('')
const items = ref<RoadmapItem[]>([])
const editing = ref(false)
const saving = ref(false)
const saveError = ref(false)

const canEdit = computed(() => authStore.isSuperAdmin)

const columns = computed(() =>
  COLUMNS.map((column) => ({
    column,
    labelKey: `auth.productRoadmap.${column}`,
    items: items.value.filter((item) => item.column === column),
  }))
)

const showBoard = computed(() => !loading.value && !loadError.value && items.value.length > 0)
const showFooter = computed(
  () => editing.value || (canEdit.value && !loading.value && !loadError.value)
)
const heroLine = computed(() =>
  updatedAt.value
    ? t('auth.productRoadmapUpdated', { date: updatedAt.value })
    : t('auth.productRoadmap.line1')
)

async function fetchRoadmap(): Promise<void> {
  loading.value = true
  loadError.value = false
  try {
    const res = await apiGet('/api/roadmap')
    if (!res.ok) {
      loadError.value = true
      items.value = []
      updatedAt.value = ''
      return
    }
    const data = (await res.json()) as { updated_at?: string; items?: RoadmapItem[] }
    updatedAt.value = typeof data.updated_at === 'string' ? data.updated_at : ''
    items.value = Array.isArray(data.items)
      ? data.items.map((item) => ({ ...blankRoadmapItem(), ...item }))
      : []
  } catch {
    loadError.value = true
    items.value = []
    updatedAt.value = ''
  } finally {
    loading.value = false
  }
}

function startEdit(): void {
  saveError.value = false
  editing.value = true
}

function cancelEdit(): void {
  saveError.value = false
  editing.value = false
}

async function saveRoadmap(next: RoadmapItem[]): Promise<void> {
  saving.value = true
  saveError.value = false
  try {
    const res = await apiPut('/api/roadmap', { items: next })
    if (!res.ok) {
      saveError.value = true
      return
    }
    const data = (await res.json()) as { updated_at?: string; items?: RoadmapItem[] }
    updatedAt.value = typeof data.updated_at === 'string' ? data.updated_at : ''
    items.value = Array.isArray(data.items)
      ? data.items.map((item) => ({ ...blankRoadmapItem(), ...item }))
      : []
    editing.value = false
  } catch {
    saveError.value = true
  } finally {
    saving.value = false
  }
}

watch(
  () => props.visible,
  (open) => {
    if (open) {
      editing.value = false
      saveError.value = false
      void fetchRoadmap()
    }
  },
  { immediate: true }
)
</script>

<template>
  <SwissGlassDialog
    v-model="isVisible"
    :ribbon="t('auth.productRoadmap.ribbon')"
    ribbon-key="auth.productRoadmap.ribbon"
    :title="t('auth.productRoadmapModalTitle')"
    title-key="auth.productRoadmapModalTitle"
    :line1="heroLine"
    :line1-key="updatedAt ? '' : 'auth.productRoadmap.line1'"
    :icon="Route"
    width="min(1100px, 96vw)"
    top="6vh"
  >
    <div class="roadmap-body">
      <ProductRoadmapEditor
        v-if="editing"
        ref="editor"
        :items="items"
        :saving="saving"
        :save-error="saveError"
        @save="saveRoadmap"
      />
      <p
        v-else-if="loading"
        class="roadmap-status"
      >
        <I18nText k="common.loading" />
      </p>
      <p
        v-else-if="loadError"
        class="roadmap-status"
      >
        <I18nText k="auth.productRoadmapLoadError" />
      </p>
      <p
        v-else-if="!showBoard"
        class="roadmap-status"
      >
        <I18nText k="auth.productRoadmapEmpty" />
      </p>
      <ElScrollbar
        v-else
        max-height="min(68vh, 560px)"
      >
        <div class="roadmap-columns">
          <section
            v-for="column in columns"
            :key="column.column"
            class="roadmap-column"
          >
            <h3 class="roadmap-column__title">
              <span class="roadmap-column__label">
                <span
                  class="roadmap-column__dot"
                  :class="`roadmap-column__dot--${column.column}`"
                />
                <I18nText :k="column.labelKey" />
              </span>
              <span class="roadmap-column__count">{{ column.items.length }}</span>
            </h3>
            <p
              v-if="column.items.length === 0"
              class="roadmap-column__empty"
            >
              —
            </p>
            <article
              v-for="(item, index) in column.items"
              :key="`${column.column}-${index}`"
              class="roadmap-card"
            >
              <div
                v-if="item.area || item.target"
                class="roadmap-card__top"
              >
                <span
                  v-if="item.area"
                  class="roadmap-card__area"
                >
                  {{ item.area }}
                </span>
                <span
                  v-if="item.target"
                  class="roadmap-card__target"
                >
                  {{ item.target }}
                </span>
              </div>
              <h4 class="roadmap-card__title">{{ item.title }}</h4>
              <p
                v-if="item.summary"
                class="roadmap-card__summary"
              >
                {{ item.summary }}
              </p>
              <footer
                v-if="item.owner"
                class="roadmap-card__meta"
              >
                <span class="roadmap-card__owner">
                  <span
                    class="roadmap-card__avatar"
                    :style="{
                      background: `hsl(${ownerHue(item.owner)} 62% 90%)`,
                      color: `hsl(${ownerHue(item.owner)} 42% 32%)`,
                    }"
                  >
                    {{ ownerMark(item.owner) }}
                  </span>
                  {{ item.owner }}
                </span>
              </footer>
            </article>
          </section>
        </div>
      </ElScrollbar>
    </div>
    <template
      v-if="showFooter"
      #footer
    >
      <div class="swiss-glass-footer roadmap-footer">
        <template v-if="editing">
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary roadmap-footer__add"
            @click="editorRef?.addItem()"
          >
            <I18nText k="auth.productRoadmap.add" />
          </button>
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
            @click="cancelEdit"
          >
            <I18nText k="auth.productRoadmap.cancel" />
          </button>
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
            :disabled="!editorRef?.saveReady()"
            @click="editorRef?.submit()"
          >
            <I18nText k="auth.productRoadmap.save" />
          </button>
        </template>
        <button
          v-else
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
          @click="startEdit"
        >
          <I18nText k="auth.productRoadmap.edit" />
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.roadmap-body {
  min-height: 160px;
}

.roadmap-status {
  margin: 28px 4px;
  font-size: 14px;
  color: hsl(30deg 6% 42%);
}

.roadmap-columns {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 2px 2px 8px;
}

.roadmap-column {
  min-width: 0;
  min-height: 180px;
  padding: 10px;
  border-radius: 14px;
  background: hsl(36deg 24% 96%);
}

.roadmap-column__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 650;
  color: hsl(30deg 8% 22%);
}

.roadmap-column__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.roadmap-column__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.roadmap-column__dot--now {
  background: hsl(24deg 86% 52%);
}

.roadmap-column__dot--next {
  background: hsl(211deg 78% 52%);
}

.roadmap-column__dot--later {
  background: hsl(262deg 42% 58%);
}

.roadmap-column__dot--shipped {
  background: hsl(152deg 46% 40%);
}

.roadmap-column__count {
  min-width: 18px;
  padding: 1px 6px;
  border-radius: 999px;
  background: hsl(0deg 0% 100% / 80%);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
  color: hsl(30deg 6% 38%);
}

.roadmap-column__empty {
  margin: 18px 0;
  text-align: center;
  color: hsl(30deg 8% 74%);
}

.roadmap-card + .roadmap-card {
  margin-top: 8px;
}

.roadmap-card {
  padding: 10px 11px 9px;
  border: 1px solid hsl(30deg 12% 90%);
  border-radius: 10px;
  background: hsl(0deg 0% 100%);
  box-shadow: 0 1px 2px hsl(30deg 20% 20% / 6%);
}

.roadmap-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.roadmap-card__area {
  max-width: 70%;
  overflow: hidden;
  padding: 1px 6px;
  border-radius: 999px;
  background: hsl(36deg 40% 94%);
  font-size: 11px;
  font-weight: 600;
  line-height: 16px;
  color: hsl(24deg 45% 34%);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.roadmap-card__target {
  font-size: 11px;
  color: hsl(30deg 6% 46%);
  white-space: nowrap;
}

.roadmap-card__title {
  margin: 0;
  font-size: 13.5px;
  font-weight: 650;
  line-height: 1.35;
  color: hsl(30deg 10% 14%);
}

.roadmap-card__summary {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: hsl(30deg 5% 40%);
}

.roadmap-card__meta {
  display: flex;
  margin-top: 10px;
}

.roadmap-card__owner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 12px;
  color: hsl(30deg 8% 28%);
}

.roadmap-card__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.roadmap-footer {
  justify-content: flex-end;
}

.roadmap-footer__add {
  margin-right: auto;
}

@media (max-width: 900px) {
  .roadmap-columns {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .roadmap-columns {
    grid-template-columns: 1fr;
  }
}
</style>
