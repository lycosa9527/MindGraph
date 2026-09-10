<script setup lang="ts">
/**
 * DiagramSlotFullModal - Modal shown when diagram slots are full
 * Allows user to delete an existing diagram to make space for saving
 *
 * Design: Swiss Design style matching other modals in the app
 */
import { computed, ref, watch } from 'vue'

import { ElRadio, ElRadioGroup } from 'element-plus'

import { FolderOpen, Loader2, Trash2 } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useNotifications } from '@/composables'
import { useLanguage } from '@/composables'
import { getDiagramTypeDisplayName } from '@/composables/editor/useDiagramLabels'
import { intlLocaleForUiCode } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import { useUIStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

const notify = useNotifications()

const props = defineProps<{
  visible: boolean
  /** Title of the diagram to save */
  pendingTitle: string
  /** Type of the diagram to save */
  pendingDiagramType: string
  /** Spec of the diagram to save */
  pendingSpec: Record<string, unknown>
  /** Language of the diagram */
  pendingLanguage?: string
  /** Thumbnail of the diagram */
  pendingThumbnail?: string | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success', diagramId: string): void
  (e: 'cancel'): void
}>()

const savedDiagramsStore = useSavedDiagramsStore()
const uiStore = useUIStore()
const { t } = useLanguage()

// State - use empty string instead of null for ElRadioGroup compatibility
const selectedDiagramId = ref<string>('')
const isDeleting = ref(false)

// Computed
const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const diagrams = computed(() => savedDiagramsStore.diagrams)
const maxDiagrams = computed(() => savedDiagramsStore.maxDiagrams)

// Watch for visibility changes to reset state
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      selectedDiagramId.value = ''
      isDeleting.value = false
      // Fetch latest diagrams
      savedDiagramsStore.fetchDiagrams(1, 50, { force: true })
    }
  }
)

function getDiagramTypeName(type: string): string {
  return getDiagramTypeDisplayName(type, uiStore.language as LocaleCode)
}

// Format date
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return t('common.date.today')
  }
  if (diffDays === 1) {
    return t('common.date.yesterday')
  }
  if (diffDays < 7) {
    return t('common.date.daysAgo', { n: diffDays })
  }
  return date.toLocaleDateString(intlLocaleForUiCode(uiStore.language as LocaleCode), {
    month: 'short',
    day: 'numeric',
  })
}

// Close modal
function closeModal(): void {
  isVisible.value = false
  emit('cancel')
}

// Handle delete and save
async function handleDeleteAndSave(): Promise<void> {
  if (!selectedDiagramId.value) {
    notify.warning(t('library.slotFull.selectDiagram'))
    return
  }

  isDeleting.value = true

  try {
    const result = await savedDiagramsStore.deleteAndSave(
      selectedDiagramId.value,
      props.pendingTitle,
      props.pendingDiagramType,
      props.pendingSpec,
      props.pendingLanguage || 'zh',
      props.pendingThumbnail || null
    )

    if (result.success && result.diagramId) {
      notify.success(t('library.slotFull.saveSuccess'))
      isVisible.value = false
      emit('success', result.diagramId)
    } else {
      notify.error(result.error || t('library.slotFull.saveFailed'))
    }
  } catch (error) {
    console.error('Delete and save error:', error)
    notify.error(t('library.slotFull.networkError'))
  } finally {
    isDeleting.value = false
  }
}
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('canvas.hero.slotFull.ribbon')"
    :title="t('canvas.hero.slotFull.title')"
    :line1="t('library.slotFull.body', { max: maxDiagrams })"
    :icon="FolderOpen"
    card-class="swiss-glass-card--wide"
    @close="closeModal"
  >
    <div class="diagram-list">
      <ElRadioGroup
        v-model="selectedDiagramId"
        class="w-full"
      >
        <div
          v-for="diagram in diagrams"
          :key="diagram.id"
          class="diagram-item"
          :class="{ 'is-selected': selectedDiagramId === diagram.id }"
          @click="selectedDiagramId = diagram.id"
        >
          <ElRadio
            :value="diagram.id"
            class="diagram-radio"
          >
            <div class="diagram-content">
              <!-- Thumbnail -->
              <div class="diagram-thumbnail">
                <img
                  v-if="diagram.thumbnail"
                  :src="diagram.thumbnail"
                  :alt="diagram.title"
                  class="thumbnail-image"
                />
                <div
                  v-else
                  class="thumbnail-placeholder"
                >
                  <span class="text-stone-400 text-xs">
                    {{ getDiagramTypeName(diagram.diagram_type).charAt(0) }}
                  </span>
                </div>
              </div>

              <!-- Info -->
              <div class="diagram-info">
                <div class="diagram-title">{{ diagram.title }}</div>
                <div class="diagram-meta">
                  <span class="diagram-type">{{ getDiagramTypeName(diagram.diagram_type) }}</span>
                  <span class="meta-dot" />
                  <span class="diagram-date">{{ formatDate(diagram.updated_at) }}</span>
                </div>
              </div>
            </div>
          </ElRadio>
        </div>
      </ElRadioGroup>
    </div>

    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="closeModal"
        >
          {{ t('library.slotFull.cancel') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--danger min-w-22"
          :disabled="!selectedDiagramId || isDeleting"
          @click="handleDeleteAndSave"
        >
          <Loader2
            v-if="isDeleting"
            class="w-4 h-4 animate-spin"
          />
          <Trash2
            v-else
            class="w-4 h-4"
          />
          {{ t('library.slotFull.deleteAndSave') }}
        </button>
      </div>
    </template>
  </SwissGlassCard>
</template>

<style scoped>
.diagram-list {
  overflow-y: auto;
  max-height: 400px;
}

.diagram-item {
  padding: 12px;
  border: 2px solid transparent;
  border-radius: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fafaf9;
}

.diagram-item:hover {
  background: #f5f5f4;
  border-color: #d6d3d1;
}

.diagram-item.is-selected {
  background: #fef2f2;
  border-color: #ef4444;
}

.diagram-radio {
  width: 100%;
  display: flex;
  align-items: center;
}

.diagram-radio :deep(.el-radio__label) {
  flex: 1;
  padding-left: 12px;
}

.diagram-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.diagram-thumbnail {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: #e7e5e4;
}

.thumbnail-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  color: #a8a29e;
}

.diagram-info {
  flex: 1;
  min-width: 0;
}

.diagram-title {
  font-size: 14px;
  font-weight: 500;
  color: #1c1917;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.diagram-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #78716c;
}

.meta-dot {
  width: 3px;
  height: 3px;
  background: #a8a29e;
  border-radius: 50%;
}

.diagram-type {
  color: #57534e;
}

.diagram-date {
  color: #a8a29e;
}
</style>
