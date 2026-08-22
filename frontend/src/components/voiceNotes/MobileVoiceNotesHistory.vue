<script setup lang="ts">
/**
 * Left history drawer for previous Voice Notes conversations.
 */
import { computed, ref, watch } from 'vue'

import { ElDrawer } from 'element-plus'

import { X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { fetchVoiceNoteHistoryDiagrams } from '@/composables/voiceNotes/fetchVoiceNoteHistory'
import { formatVoiceNoteHistoryTitle } from '@/composables/voiceNotes/mobileVoiceNotesFinish'
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { useAuthStore } from '@/stores'
import type { SavedDiagram } from '@/stores/savedDiagrams'

const props = defineProps<{
  visible: boolean
  currentDiagramId: string | null
  removeDiagram: (diagramId: string) => Promise<boolean>
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'select', diagram: SavedDiagram): void
}>()

const { t, currentLanguage } = useLanguage()
const authStore = useAuthStore()

const showHistory = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const isLoading = ref(false)
const voiceNoteDiagrams = ref<SavedDiagram[]>([])

async function loadHistory(): Promise<void> {
  if (!authStore.isAuthenticated) {
    voiceNoteDiagrams.value = []
    return
  }
  isLoading.value = true
  try {
    const rows = await fetchVoiceNoteHistoryDiagrams(50)
    voiceNoteDiagrams.value = rows
      .slice()
      .sort((left, right) => right.updated_at.localeCompare(left.updated_at))
  } catch {
    voiceNoteDiagrams.value = []
  } finally {
    isLoading.value = false
  }
}

watch(
  () => props.visible,
  (open) => {
    if (open) {
      void loadHistory()
    }
  }
)

function formatUpdatedAt(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return t('common.date.today')
  if (diffDays === 1) return t('common.date.yesterday')
  if (diffDays < 7) return t('common.date.daysAgo', { n: diffDays })
  const localeTag = intlLocaleForUiCode(currentLanguage.value as LocaleCode)
  return date.toLocaleDateString(localeTag, { month: 'short', day: 'numeric' })
}

function handleSelect(diagram: SavedDiagram): void {
  emit('select', diagram)
}

async function handleDelete(diagramId: string, event: Event): Promise<void> {
  event.stopPropagation()
  const success = await props.removeDiagram(diagramId)
  if (success) {
    voiceNoteDiagrams.value = voiceNoteDiagrams.value.filter((row) => row.id !== diagramId)
  }
}

function handleClose(): void {
  showHistory.value = false
}
</script>

<template>
  <ElDrawer
    v-model="showHistory"
    direction="ltr"
    size="80%"
    :with-header="true"
    :show-close="false"
    :modal="true"
    :append-to-body="true"
    :z-index="2000"
    class="voice-notes-history-drawer"
  >
    <template #header>
      <div class="vn-history-head">
        <h2 class="vn-history-head__title">
          {{ t('auth.voiceNotes.historyTitle') }}
        </h2>
        <button
          type="button"
          class="vn-history-head__close"
          :aria-label="t('common.close')"
          @click="handleClose"
        >
          <X :size="18" />
        </button>
      </div>
    </template>

    <div class="vn-history-list">
      <div
        v-if="isLoading && voiceNoteDiagrams.length === 0"
        class="vn-history-state"
      >
        <div class="vn-history-spinner" />
        <span>{{ t('common.loading') }}</span>
      </div>

      <div
        v-else-if="voiceNoteDiagrams.length === 0"
        class="vn-history-state"
      >
        <p>{{ t('auth.voiceNotes.historyEmpty') }}</p>
      </div>

      <div
        v-else
        class="vn-history-items"
      >
        <div
          v-for="diagram in voiceNoteDiagrams"
          :key="diagram.id"
          class="vn-history-item"
          :class="{ 'vn-history-item--current': currentDiagramId === diagram.id }"
          @click="handleSelect(diagram)"
        >
          <div class="vn-history-item__copy">
            <p class="vn-history-item__title">
              {{ formatVoiceNoteHistoryTitle(diagram.title) }}
            </p>
            <p class="vn-history-item__meta">
              {{ formatUpdatedAt(diagram.updated_at) }}
            </p>
          </div>
          <button
            type="button"
            class="vn-history-item__delete"
            :aria-label="t('common.delete')"
            @click="handleDelete(diagram.id, $event)"
          >
            {{ t('common.delete') }}
          </button>
        </div>
      </div>
    </div>
  </ElDrawer>
</template>

<style scoped>
.vn-history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
}

.vn-history-head__title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 1rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: #1c1917;
}

.vn-history-head__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
  border: 0;
  border-radius: 0.5rem;
  background: transparent;
  color: #57534e;
}

.vn-history-head__close:active {
  background: #f5f5f4;
}

.vn-history-list {
  min-height: 8rem;
}

.vn-history-state {
  padding: 2.5rem 0.75rem;
  text-align: center;
  color: #78716c;
  font-size: 0.875rem;
}

.vn-history-spinner {
  width: 1.35rem;
  height: 1.35rem;
  margin: 0 auto 0.5rem;
  border: 2px solid #d6d3d1;
  border-top-color: #1c1917;
  border-radius: 9999px;
  animation: vn-history-spin 0.7s linear infinite;
}

.vn-history-items {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.vn-history-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.8rem 0.75rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.75rem;
  background: #fafaf9;
}

.vn-history-item--current {
  border-color: #1c1917;
  background: #ffffff;
}

.vn-history-item:active {
  background: #f5f5f4;
}

.vn-history-item__copy {
  flex: 1;
  min-width: 0;
}

.vn-history-item__title {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vn-history-item__meta {
  margin: 0.2rem 0 0;
  font-size: 0.75rem;
  color: #78716c;
}

.vn-history-item__delete {
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: #a8a29e;
  font-size: 0.75rem;
  font-weight: 600;
}

.vn-history-item__delete:active {
  color: #b91c1c;
}

@keyframes vn-history-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<style>
.el-drawer.voice-notes-history-drawer {
  width: 80vw !important;
  max-width: 320px !important;
  background: #ffffff !important;
}

.el-drawer.voice-notes-history-drawer .el-drawer__header {
  margin-bottom: 0 !important;
  padding: 1rem 1rem 0.85rem !important;
  border-bottom: 1px solid #e7e5e4 !important;
}

.el-drawer.voice-notes-history-drawer .el-drawer__body {
  padding: 0.75rem 0.85rem 1rem !important;
  background: #ffffff !important;
}
</style>
