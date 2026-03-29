<script setup lang="ts">
/**
 * IntlDiagramDropdown — Saved-diagram library dropdown for the international landing.
 * Shown beneath the prompt bar on focus. Scrollable list with rename / delete,
 * a slot counter footer, and click-to-open behaviour.
 */
import { computed, onMounted, watch } from 'vue'

import { ElIcon, ElMessageBox } from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { Edit3, FileImage, Pin, Trash2 } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

const emit = defineEmits<{
  (e: 'select', diagram: SavedDiagram): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const store = useSavedDiagramsStore()

const diagrams = computed(() => store.diagrams)
const isLoading = computed(() => store.isLoading)
const maxDiagrams = computed(() => store.maxDiagrams)

onMounted(() => {
  if (authStore.isAuthenticated) {
    store.fetchDiagrams()
  }
})

watch(
  () => authStore.isAuthenticated,
  (auth) => {
    if (auth) store.fetchDiagrams()
    else store.reset()
  }
)

function typeLabel(type: string): string {
  const key = `sidebar.diagramType.${type}`
  const val = t(key)
  return val !== key ? val : type
}

function handleClick(diagram: SavedDiagram) {
  emit('select', diagram)
}

async function handleRename(diagramId: string) {
  const diagram = diagrams.value.find((d) => d.id === diagramId)
  const currentName = diagram?.title || ''
  try {
    const result = await ElMessageBox.prompt(
      t('sidebar.diagramHistory.renamePrompt'),
      t('sidebar.diagramHistory.renameTitle'),
      {
        confirmButtonText: t('common.ok'),
        cancelButtonText: t('common.cancel'),
        inputValue: currentName,
        inputPattern: /\S+/,
        inputErrorMessage: t('sidebar.diagramHistory.nameRequired'),
      }
    )
    const value =
      typeof result === 'object' && result !== null && 'value' in result
        ? (result as { value: string }).value
        : undefined
    if (value && value.trim() !== currentName) {
      await store.updateDiagram(diagramId, { title: value.trim() })
    }
  } catch {
    /* cancelled */
  }
}

async function handleDelete(diagramId: string) {
  try {
    const success = await store.deleteDiagram(diagramId)
    if (success) notify.success(t('sidebar.diagramHistory.deleted'))
    else notify.error(t('sidebar.diagramHistory.deleteFailed'))
  } catch {
    notify.error(t('sidebar.diagramHistory.deleteFailed'))
  }
}
</script>

<template>
  <div class="dd">
    <!-- Scrollable body -->
    <div class="dd-body">
      <!-- Loading -->
      <div
        v-if="isLoading"
        class="dd-empty"
      >
        <ElIcon class="animate-spin text-gray-400">
          <Loading />
        </ElIcon>
      </div>

      <!-- Empty -->
      <div
        v-else-if="diagrams.length === 0"
        class="dd-empty"
      >
        <FileImage class="dd-empty-icon" />
        <span class="dd-empty-text">{{ t('sidebar.diagramHistory.empty') }}</span>
      </div>

      <!-- List -->
      <template v-else>
        <div
          v-for="diagram in diagrams"
          :key="diagram.id"
          class="dd-item"
          @click="handleClick(diagram)"
        >
          <div class="dd-item-info">
            <span class="dd-item-name">
              <Pin
                v-if="diagram.is_pinned"
                class="dd-pin-icon"
              />
              {{ diagram.title || t('sidebar.history.untitled') }}
            </span>
            <span class="dd-item-type">{{ typeLabel(diagram.diagram_type) }}</span>
          </div>

          <div class="dd-item-actions">
            <button
              class="dd-action"
              :title="t('sidebar.actions.rename')"
              @click.stop="handleRename(diagram.id)"
            >
              <Edit3 class="w-3.5 h-3.5" />
            </button>
            <button
              class="dd-action dd-action--danger"
              :title="t('sidebar.actions.delete')"
              @click.stop="handleDelete(diagram.id)"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- Footer — slot counter -->
    <div class="dd-footer">
      <span class="dd-footer-count">{{ diagrams.length }}/{{ maxDiagrams }}</span>
      <span class="dd-footer-label">{{ t('sidebar.diagramHistory.title') }}</span>
    </div>
  </div>
</template>

<style scoped>
.dd {
  background: #fff;
  border-radius: 16px;
  box-shadow:
    0 12px 48px rgba(0, 0, 0, 0.12),
    0 2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

/* ── Scrollable body ── */

.dd-body {
  max-height: 320px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 6px;
}

.dd-body::-webkit-scrollbar {
  width: 5px;
}

.dd-body::-webkit-scrollbar-track {
  background: transparent;
}

.dd-body::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 99px;
}

.dd-body::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}

/* ── Empty / loading state ── */

.dd-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  gap: 6px;
}

.dd-empty-icon {
  width: 28px;
  height: 28px;
  color: #d6d3d1;
}

.dd-empty-text {
  font-size: 13px;
  color: #a8a29e;
}

/* ── List items ── */

.dd-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.dd-item:hover {
  background-color: #f5f5f4;
}

.dd-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dd-item-name {
  font-size: 14px;
  font-weight: 500;
  color: #1c1917;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 4px;
}

.dd-pin-icon {
  width: 12px;
  height: 12px;
  color: #d97706;
  flex-shrink: 0;
}

.dd-item-type {
  font-size: 12px;
  color: #a8a29e;
  line-height: 1.3;
}

/* ── Action buttons ── */

.dd-item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
  flex-shrink: 0;
}

.dd-item:hover .dd-item-actions {
  opacity: 1;
}

.dd-action {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  border-radius: 6px;
  color: #78716c;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dd-action:hover {
  background-color: #e7e5e4;
  color: #1c1917;
}

.dd-action--danger:hover {
  background-color: #fee2e2;
  color: #dc2626;
}

/* ── Footer ── */

.dd-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border-top: 1px solid #f5f5f4;
  background: #fafaf9;
}

.dd-footer-count {
  font-size: 13px;
  font-weight: 600;
  color: #57534e;
}

.dd-footer-label {
  font-size: 13px;
  color: #a8a29e;
}

/* ── Dark mode ── */

.dark .dd {
  background: #1c1917;
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow:
    0 12px 48px rgba(0, 0, 0, 0.4),
    0 2px 8px rgba(0, 0, 0, 0.2);
}

.dark .dd-body::-webkit-scrollbar-thumb {
  background: #44403c;
}

.dark .dd-item:hover {
  background-color: #292524;
}

.dark .dd-item-name {
  color: #fafaf9;
}

.dark .dd-action:hover {
  background-color: #44403c;
  color: #fafaf9;
}

.dark .dd-action--danger:hover {
  background-color: #450a0a;
  color: #fca5a5;
}

.dark .dd-footer {
  background: #171412;
  border-color: #292524;
}

.dark .dd-footer-count {
  color: #d6d3d1;
}
</style>
