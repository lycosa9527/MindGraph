<script setup lang="ts">
/**
 * DiagramHistory - Saved diagrams with archive folders and uncategorized timeline
 */
import { computed, onMounted, watch } from 'vue'

import { ElIcon, ElMessageBox, ElScrollbar } from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import {
  ChevronDown,
  ChevronRight,
  Edit3,
  FileImage,
  Folder,
  FolderPlus,
  Lock,
  Trash2,
} from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { useDiagramArchiveHistory } from '@/composables/sidebar/useDiagramArchiveHistory'
import { useAuthStore } from '@/stores'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { formatDiagramCountLabel } from '@/utils/diagramLimit'

import DiagramHistoryRow from './DiagramHistoryRow.vue'

const props = defineProps<{
  isBlurred?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', diagram: SavedDiagram): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()

const INITIAL_LIMIT = 10

const diagrams = computed(() => savedDiagramsStore.diagrams)
const folders = computed(() => savedDiagramsStore.folders)
const isLoading = computed(() => savedDiagramsStore.isLoading)
const currentDiagramId = computed(() => savedDiagramsStore.currentDiagramId)
const maxDiagrams = computed(() => savedDiagramsStore.maxDiagrams)
const hasSaveLimit = computed(() => savedDiagramsStore.hasSaveLimit)
const foldersLoadFailed = computed(() => savedDiagramsStore.foldersLoadFailed)
const fetchError = computed(() => savedDiagramsStore.error)

const diagramCountLabel = computed(() =>
  formatDiagramCountLabel(savedDiagramsStore.total || diagrams.value.length, maxDiagrams.value)
)

const folderCountLabel = computed(() =>
  t('sidebar.diagramHistory.folderCount', {
    count: folders.value.length,
  })
)

const {
  showAllUncategorized,
  groupedUncategorized,
  hasMoreUncategorized,
  remainingUncategorizedCount,
  uncategorizedDiagrams,
  isFolderCollapsed,
  toggleFolderCollapsed,
  diagramsForFolder,
} = useDiagramArchiveHistory(diagrams, folders, INITIAL_LIMIT)

const groupLabels = computed(() => ({
  pinned: t('sidebar.history.pinned'),
  today: t('common.date.today'),
  yesterday: t('common.date.yesterday'),
  week: t('common.date.pastWeek'),
  month: t('common.date.pastMonth'),
}))

onMounted(() => {
  if (authStore.isAuthenticated && !props.isBlurred) {
    savedDiagramsStore.fetchDiagrams()
  }
})

watch(
  () => authStore.isAuthenticated,
  (isAuth) => {
    if (isAuth) {
      savedDiagramsStore.fetchDiagrams()
    } else {
      savedDiagramsStore.reset()
    }
  }
)

function handleDiagramClick(diagram: SavedDiagram): void {
  savedDiagramsStore.setCurrentDiagram(diagram.id)
  emit('select', diagram)
}

async function promptFolderName(
  titleKey: string,
  promptKey: string,
  initialValue = ''
): Promise<string | null> {
  try {
    const result = await ElMessageBox.prompt(t(promptKey), t(titleKey), {
      confirmButtonText: t('common.ok'),
      cancelButtonText: t('common.cancel'),
      inputValue: initialValue,
      inputPattern: /\S+/,
      inputErrorMessage: t('sidebar.diagramHistory.nameRequired'),
    })
    const value =
      typeof result === 'object' && result !== null && 'value' in result
        ? (result as { value: string }).value
        : undefined
    return value?.trim() || null
  } catch {
    return null
  }
}

async function handleCreateFolder(): Promise<void> {
  const name = await promptFolderName(
    'sidebar.diagramHistory.folderCreateTitle',
    'sidebar.diagramHistory.folderCreatePrompt'
  )
  if (!name) return
  const created = await savedDiagramsStore.createFolder(name)
  if (created) {
    notify.success(t('sidebar.diagramHistory.folderCreated'))
  } else {
    notify.error(t('sidebar.diagramHistory.folderCreateFailed'))
  }
}

async function handleRenameFolder(folderId: string, currentName: string): Promise<void> {
  const name = await promptFolderName(
    'sidebar.diagramHistory.folderRenameTitle',
    'sidebar.diagramHistory.folderRenamePrompt',
    currentName
  )
  if (!name || name === currentName) return
  const ok = await savedDiagramsStore.renameFolder(folderId, name)
  if (ok) {
    notify.success(t('sidebar.diagramHistory.folderRenamed'))
  } else {
    notify.error(t('sidebar.diagramHistory.folderRenameFailed'))
  }
}

async function handleDeleteFolder(folderId: string): Promise<void> {
  try {
    await swissGlassConfirm(
      t('sidebar.diagramHistory.folderDeleteConfirm'),
      t('sidebar.diagramHistory.folderDeleteTitle'),
      {
        confirmButtonText: t('common.ok'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
    const ok = await savedDiagramsStore.deleteFolder(folderId)
    if (ok) {
      notify.success(t('sidebar.diagramHistory.folderDeleted'))
    } else {
      notify.error(savedDiagramsStore.error || t('sidebar.diagramHistory.folderDeleteFailed'))
    }
  } catch {
    // cancelled
  }
}

async function handleCreateFolderFromRow(): Promise<string | null> {
  const name = await promptFolderName(
    'sidebar.diagramHistory.folderCreateTitle',
    'sidebar.diagramHistory.folderCreatePrompt'
  )
  if (!name) return null
  const created = await savedDiagramsStore.createFolder(name)
  if (!created) {
    notify.error(t('sidebar.diagramHistory.folderCreateFailed'))
    return null
  }
  notify.success(t('sidebar.diagramHistory.folderCreated'))
  return created.id
}
</script>

<template>
  <div
    class="diagram-history flex flex-1 min-h-0 flex-col border-t border-stone-200 relative overflow-hidden"
  >
    <div class="px-4 py-3 flex items-center justify-between gap-2">
      <div class="min-w-0">
        <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
          {{ t('sidebar.diagramHistory.title') }}
        </div>
        <div
          v-if="!isBlurred && (diagrams.length > 0 || folders.length > 0)"
          class="text-[11px] text-stone-400 mt-0.5 truncate"
        >
          {{ diagramCountLabel }}
          <span v-if="folders.length > 0"> · {{ folderCountLabel }}</span>
        </div>
      </div>
      <button
        v-if="!isBlurred"
        class="new-folder-btn"
        type="button"
        @click="handleCreateFolder"
      >
        <FolderPlus class="w-3.5 h-3.5 shrink-0" />
        <span class="new-folder-btn__label">
          {{ t('sidebar.diagramHistory.folderCreateTitle') }}
        </span>
      </button>
    </div>

    <ElScrollbar class="flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <div
          v-if="fetchError"
          class="archive-error"
        >
          {{ t('sidebar.diagramHistory.loadFailed') }}
        </div>
        <div
          v-if="foldersLoadFailed"
          class="archive-warning"
        >
          {{ t('sidebar.diagramHistory.foldersLoadFailed') }}
        </div>

        <div
          v-if="isLoading"
          class="flex items-center justify-center py-8"
        >
          <ElIcon class="animate-spin text-stone-400">
            <Loading />
          </ElIcon>
        </div>

        <div
          v-else-if="diagrams.length === 0 && folders.length === 0"
          class="text-center py-8"
        >
          <FileImage class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ t('sidebar.diagramHistory.empty') }}
          </p>
          <p
            v-if="hasSaveLimit"
            class="text-xs text-stone-300 mt-1"
          >
            {{ t('sidebar.diagramHistory.capacity', { n: maxDiagrams }) }}
          </p>
        </div>

        <template v-else>
          <section
            v-if="folders.length > 0"
            class="archive-section"
          >
            <div class="section-heading">
              {{ t('sidebar.diagramHistory.foldersSection') }}
            </div>
            <div
              v-for="folder in folders"
              :key="folder.id"
              class="group-section folder-section"
            >
              <div
                class="folder-header"
                @click="toggleFolderCollapsed(folder.id)"
              >
                <component
                  :is="isFolderCollapsed(folder.id) ? ChevronRight : ChevronDown"
                  class="w-3.5 h-3.5 shrink-0 text-stone-400"
                />
                <Folder class="w-3.5 h-3.5 shrink-0 text-amber-600" />
                <span class="folder-name">{{ folder.name }}</span>
                <span class="folder-count">{{ diagramsForFolder(folder.id).length }}</span>
                <div
                  class="folder-actions"
                  @click.stop
                >
                  <button
                    class="folder-action-btn"
                    :title="t('sidebar.actions.rename')"
                    @click="handleRenameFolder(folder.id, folder.name)"
                  >
                    <Edit3 class="w-3.5 h-3.5" />
                  </button>
                  <button
                    class="folder-action-btn folder-action-btn--danger"
                    :title="t('sidebar.actions.delete')"
                    @click="handleDeleteFolder(folder.id)"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div
                v-if="!isFolderCollapsed(folder.id)"
                class="folder-items"
              >
                <DiagramHistoryRow
                  v-for="diagram in diagramsForFolder(folder.id)"
                  :key="diagram.id"
                  :diagram="diagram"
                  :folders="folders"
                  :is-active="currentDiagramId === diagram.id"
                  show-pinned-icon
                  :create-folder="handleCreateFolderFromRow"
                  @select="handleDiagramClick"
                />
                <p
                  v-if="diagramsForFolder(folder.id).length === 0"
                  class="folder-empty"
                >
                  {{ t('sidebar.diagramHistory.folderEmpty') }}
                </p>
              </div>
            </div>
          </section>

          <section
            v-if="uncategorizedDiagrams.length > 0 || folders.length > 0"
            class="archive-section"
          >
            <div class="section-heading">
              {{ t('sidebar.diagramHistory.uncategorizedSection') }}
            </div>

            <div
              v-if="groupedUncategorized.pinned.length > 0"
              class="group-section"
            >
              <div class="group-label">{{ groupLabels.pinned }}</div>
              <DiagramHistoryRow
                v-for="diagram in groupedUncategorized.pinned"
                :key="diagram.id"
                :diagram="diagram"
                :folders="folders"
                :is-active="currentDiagramId === diagram.id"
                show-pinned-icon
                :create-folder="handleCreateFolderFromRow"
                @select="handleDiagramClick"
              />
            </div>

            <div
              v-if="groupedUncategorized.today.length > 0"
              class="group-section"
            >
              <div class="group-label">{{ groupLabels.today }}</div>
              <DiagramHistoryRow
                v-for="diagram in groupedUncategorized.today"
                :key="diagram.id"
                :diagram="diagram"
                :folders="folders"
                :is-active="currentDiagramId === diagram.id"
                :create-folder="handleCreateFolderFromRow"
                @select="handleDiagramClick"
              />
            </div>

            <div
              v-if="groupedUncategorized.yesterday.length > 0"
              class="group-section"
            >
              <div class="group-label">{{ groupLabels.yesterday }}</div>
              <DiagramHistoryRow
                v-for="diagram in groupedUncategorized.yesterday"
                :key="diagram.id"
                :diagram="diagram"
                :folders="folders"
                :is-active="currentDiagramId === diagram.id"
                :create-folder="handleCreateFolderFromRow"
                @select="handleDiagramClick"
              />
            </div>

            <div
              v-if="groupedUncategorized.week.length > 0"
              class="group-section"
            >
              <div class="group-label">{{ groupLabels.week }}</div>
              <DiagramHistoryRow
                v-for="diagram in groupedUncategorized.week"
                :key="diagram.id"
                :diagram="diagram"
                :folders="folders"
                :is-active="currentDiagramId === diagram.id"
                :create-folder="handleCreateFolderFromRow"
                @select="handleDiagramClick"
              />
            </div>

            <div
              v-if="groupedUncategorized.month.length > 0"
              class="group-section"
            >
              <div class="group-label">{{ groupLabels.month }}</div>
              <DiagramHistoryRow
                v-for="diagram in groupedUncategorized.month"
                :key="diagram.id"
                :diagram="diagram"
                :folders="folders"
                :is-active="currentDiagramId === diagram.id"
                :create-folder="handleCreateFolderFromRow"
                @select="handleDiagramClick"
              />
            </div>

            <p
              v-if="uncategorizedDiagrams.length === 0"
              class="uncategorized-empty"
            >
              {{ t('sidebar.diagramHistory.uncategorizedEmpty') }}
            </p>

            <button
              v-if="hasMoreUncategorized"
              class="show-more-btn"
              @click="showAllUncategorized = true"
            >
              {{ t('sidebar.actions.showMore', { n: remainingUncategorizedCount }) }}
            </button>

            <button
              v-if="showAllUncategorized && uncategorizedDiagrams.length > INITIAL_LIMIT"
              class="show-more-btn"
              @click="showAllUncategorized = false"
            >
              {{ t('sidebar.actions.showLess') }}
            </button>
          </section>
        </template>
      </div>
    </ElScrollbar>

    <div
      v-if="isBlurred"
      class="absolute inset-0 flex items-center justify-center bg-stone-50/60 backdrop-blur-[2px]"
    >
      <div class="text-center px-4">
        <div
          class="w-10 h-10 rounded-full bg-stone-100 flex items-center justify-center mx-auto mb-2"
        >
          <Lock class="w-5 h-5 text-stone-400" />
        </div>
        <p class="text-xs text-stone-500">
          {{ t('sidebar.diagramHistory.loginPrompt') }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagram-history {
  min-height: 120px;
}

.archive-section + .archive-section {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #e7e5e4;
}

.section-heading {
  font-size: 11px;
  font-weight: 600;
  color: #78716c;
  letter-spacing: 0.03em;
  margin-bottom: 8px;
}

.archive-error,
.archive-warning {
  font-size: 11px;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 10px;
}

.archive-error {
  color: #b91c1c;
  background: #fef2f2;
}

.archive-warning {
  color: #92400e;
  background: #fffbeb;
}

.group-section {
  margin-bottom: 12px;
}

.group-section:last-child {
  margin-bottom: 0;
}

.group-label {
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  margin-bottom: 4px;
  padding-left: 2px;
}

.folder-header {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  padding-right: 28px;
  border-radius: 6px;
  cursor: pointer;
  color: #44403c;
  font-size: 13px;
  font-weight: 500;
  transition: background-color 0.15s ease;
}

.folder-header:hover {
  background-color: #f5f5f4;
}

.folder-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-count {
  flex-shrink: 0;
  font-size: 11px;
  color: #a8a29e;
  min-width: 1rem;
  text-align: right;
}

.folder-actions {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 2px;
  opacity: 0;
  pointer-events: none;
  padding-left: 6px;
  background: linear-gradient(to right, transparent, #fafaf9 28%);
  border-radius: 4px;
  transition: opacity 0.15s ease;
}

.folder-header:hover .folder-actions {
  opacity: 1;
  pointer-events: auto;
  background: linear-gradient(to right, transparent, #f5f5f4 28%);
}

.folder-header:hover .folder-count {
  visibility: hidden;
}

.folder-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
}

.folder-action-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.folder-action-btn:hover:not(:disabled) {
  background: #e7e5e4;
  color: #1c1917;
}

.folder-action-btn--danger:hover:not(:disabled) {
  background: #fee2e2;
  color: #dc2626;
}

.folder-items {
  margin-left: 12px;
  padding-left: 8px;
  border-left: 1px solid #e7e5e4;
}

.folder-empty,
.uncategorized-empty {
  font-size: 11px;
  color: #a8a29e;
  padding: 4px 8px 8px;
}

.new-folder-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 8px;
  border: 1px solid #e7e5e4;
  border-radius: 6px;
  background: #fafaf9;
  color: #78716c;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
  white-space: nowrap;
}

.new-folder-btn__label {
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
}

.new-folder-btn:hover {
  border-color: #d6d3d1;
  color: #44403c;
  background: #f5f5f4;
}

.show-more-btn {
  display: block;
  width: 100%;
  padding: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: #78716c;
  text-align: center;
  background: transparent;
  border: 1px dashed #d6d3d1;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.show-more-btn:hover {
  background-color: #fafaf9;
  border-color: #a8a29e;
  color: #57534e;
}
</style>

<style>
.diagram-history-more-popper.el-popper {
  min-width: 0 !important;
  box-sizing: border-box !important;
  padding: 3px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

.diagram-history-more-popper.diagram-history-more-popper--narrow.el-popper {
  width: max-content !important;
  max-width: min(calc(100vw - 24px), 260px) !important;
}

.diagram-history-more-popper.diagram-history-more-popper--narrow .diagram-history-more__row {
  white-space: nowrap;
  word-break: normal;
  align-items: center;
}

.diagram-history-more-popper.diagram-history-more-popper--wide.el-popper {
  width: max-content !important;
  max-width: min(calc(100vw - 24px), 172px) !important;
}

.diagram-history-more-popper.diagram-history-more-popper--wide .diagram-history-more__row {
  align-items: flex-start;
}

.diagram-history-more-popper .diagram-history-more__menu.el-dropdown-menu {
  min-width: 0 !important;
  width: max-content !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  scrollbar-gutter: auto;
}

.diagram-history-more-popper .el-dropdown-menu__item {
  display: flex !important;
  min-width: 0 !important;
  box-sizing: border-box;
  width: auto !important;
  max-width: 100%;
  padding: 0 !important;
  margin: 0 !important;
  border-radius: 6px;
  justify-content: flex-start !important;
  transition:
    background 0.12s,
    color 0.12s;
}

.diagram-history-more-popper .el-dropdown-menu__item:hover,
.diagram-history-more-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917;
}

.diagram-history-more-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

.diagram-history-more-popper .el-dropdown-menu__item.is-divided {
  margin-top: 4px !important;
  border-top: 1px solid #e7e5e4 !important;
  padding-top: 0 !important;
}

.diagram-history-more-popper .diagram-history-more__row {
  display: inline-flex;
  align-items: flex-start;
  gap: 6px;
  box-sizing: border-box;
  width: auto;
  max-width: 100%;
  min-width: 0;
  padding: 6px 5px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  color: #44403c;
  letter-spacing: 0.01em;
  white-space: normal;
  word-break: break-word;
}

.diagram-history-more-popper.diagram-history-more-popper--wide .diagram-history-more__row svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.diagram-history-more-popper .el-dropdown-menu__item:hover .diagram-history-more__row,
.diagram-history-more-popper .el-dropdown-menu__item:focus .diagram-history-more__row {
  color: #1c1917;
}

.diagram-history-more-popper .diagram-history-more__row--danger,
.diagram-history-more-popper .el-dropdown-menu__item:hover .diagram-history-more__row--danger,
.diagram-history-more-popper .el-dropdown-menu__item:focus .diagram-history-more__row--danger {
  color: #dc2626;
}

.diagram-history-folder-submenu.el-popper {
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 8px !important;
  min-width: 140px !important;
  max-width: min(calc(100vw - 24px), 220px) !important;
}

.diagram-history-folder-popper .el-dropdown-menu__item {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
