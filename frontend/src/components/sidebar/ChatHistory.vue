<script setup lang="ts">
/**
 * ChatHistory - MindMate conversations grouped into archive folders
 * and an uncategorized timeline, matching saved-diagram history.
 */
import { computed, defineAsyncComponent, ref, watch } from 'vue'

import { ElIcon, ElMessageBox, ElScrollbar } from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import {
  ChevronDown,
  ChevronRight,
  Edit3,
  Folder,
  FolderPlus,
  Lock,
  MessageCircle,
  Trash2,
} from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import {
  type MindmateFolder,
  useConversations,
  useCreateMindmateFolder,
  useDeleteConversation,
  useDeleteMindmateFolder,
  useMindmateFolders,
  useMoveMindmateConversation,
  usePinConversation,
  usePinnedConversations,
  useRenameConversation,
  useRenameMindmateFolder,
} from '@/composables/queries'
import {
  MINDMATE_TIME_GROUP_KEYS,
  useMindmateArchiveHistory,
} from '@/composables/sidebar/useMindmateArchiveHistory'
import { type MindMateConversation, useMindMateStore } from '@/stores'

import ChatHistoryConversationRow from './ChatHistoryConversationRow.vue'

const MindmateCollabHistory = defineAsyncComponent(() => import('./MindmateCollabHistory.vue'))

type HistoryConversation = MindMateConversation & { folder_id: string | null }

const props = withDefaults(
  defineProps<{
    isBlurred?: boolean
    compact?: boolean
    initialVisibleLimit?: number
    showCollabSessions?: boolean
  }>(),
  {
    compact: false,
    initialVisibleLimit: 10,
    showCollabSessions: false,
  }
)

const { t } = useLanguage()
const notify = useNotifications()
const mindMateStore = useMindMateStore()

const collabHistoryVisible = ref(false)

const { data: conversationsData, isLoading: isLoadingConversations } = useConversations()
const { data: pinnedData } = usePinnedConversations()
const {
  data: folderData,
  isLoading: isLoadingFolders,
  isError: foldersLoadFailed,
} = useMindmateFolders()

const { mutate: deleteConv } = useDeleteConversation()
const { mutate: renameConv } = useRenameConversation()
const { mutate: pinConv } = usePinConversation()
const { mutateAsync: createFolder } = useCreateMindmateFolder()
const { mutateAsync: renameFolder } = useRenameMindmateFolder()
const { mutateAsync: deleteFolder } = useDeleteMindmateFolder()
const { mutateAsync: moveConversation } = useMoveMindmateConversation()

const folders = computed(() => folderData.value?.folders ?? [])

const conversations = computed((): HistoryConversation[] => {
  if (!conversationsData.value) return []
  const pinnedIds = pinnedData.value?.ids ?? new Set()
  const folderByConversation = new Map(
    (folderData.value?.assignments ?? []).map((row) => [row.conversation_id, row.folder_id])
  )
  const convs = conversationsData.value.map((conv) => ({
    ...conv,
    is_pinned: pinnedIds.has(conv.id),
    folder_id: folderByConversation.get(conv.id) ?? null,
  }))
  return convs.sort((a, b) => {
    if (a.is_pinned && !b.is_pinned) return -1
    if (!a.is_pinned && b.is_pinned) return 1
    return b.updated_at - a.updated_at
  })
})

const isLoading = computed(() => isLoadingConversations.value || isLoadingFolders.value)
const currentConversationId = computed(() => mindMateStore.currentConversationId)

watch(
  [conversationsData, pinnedData],
  ([convs, pinned]) => {
    if (convs && pinned) {
      mindMateStore.syncConversationsFromQuery(convs, pinned)
    }
  },
  { immediate: true }
)

const {
  showAllUncategorized,
  groupedUncategorized,
  hasMoreUncategorized,
  remainingUncategorizedCount,
  uncategorizedConversations,
  isFolderCollapsed,
  toggleFolderCollapsed,
  conversationsForFolder,
} = useMindmateArchiveHistory(conversations, () => props.initialVisibleLimit)

const folderCountLabel = computed(() =>
  t('sidebar.chatHistory.folderCount', { count: folders.value.length })
)

const groupLabels = computed(() => ({
  pinned: t('sidebar.history.pinned'),
  today: t('common.date.today'),
  yesterday: t('common.date.yesterday'),
  week: t('common.date.pastWeek'),
  month: t('common.date.pastMonth'),
}))

function handleConversationClick(convId: string, name: string): void {
  mindMateStore.setCurrentConversation(convId, name)
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

async function handleCreateFolder(): Promise<MindmateFolder | null> {
  const name = await promptFolderName(
    'sidebar.chatHistory.folderCreateTitle',
    'sidebar.chatHistory.folderCreatePrompt'
  )
  if (!name) return null
  try {
    const created = await createFolder(name)
    notify.success(t('sidebar.chatHistory.folderCreated'))
    return created
  } catch {
    notify.error(t('sidebar.chatHistory.folderCreateFailed'))
    return null
  }
}

async function handleRenameFolder(folderId: string, currentName: string): Promise<void> {
  const name = await promptFolderName(
    'sidebar.chatHistory.folderRenameTitle',
    'sidebar.chatHistory.folderRenamePrompt',
    currentName
  )
  if (!name || name === currentName) return
  try {
    await renameFolder({ folderId, name })
    notify.success(t('sidebar.chatHistory.folderRenamed'))
  } catch {
    notify.error(t('sidebar.chatHistory.folderRenameFailed'))
  }
}

async function handleDeleteFolder(folderId: string): Promise<void> {
  try {
    await swissGlassConfirm(
      t('sidebar.chatHistory.folderDeleteConfirm'),
      t('sidebar.chatHistory.folderDeleteTitle'),
      {
        confirmButtonText: t('common.ok'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  try {
    await deleteFolder(folderId)
    notify.success(t('sidebar.chatHistory.folderDeleted'))
  } catch {
    notify.error(t('sidebar.chatHistory.folderDeleteFailed'))
  }
}

async function handleMoveConversation(convId: string, folderId: string | null): Promise<void> {
  try {
    await moveConversation({ conversationId: convId, folderId })
    notify.success(
      folderId ? t('sidebar.chatHistory.movedToFolder') : t('sidebar.chatHistory.removedFromFolder')
    )
  } catch {
    notify.error(t('sidebar.chatHistory.moveFailed'))
  }
}

async function handleCreateFolderAndMove(convId: string): Promise<void> {
  const created = await handleCreateFolder()
  if (created) {
    await handleMoveConversation(convId, created.id)
  }
}

async function handleRenameConversation(convId: string): Promise<void> {
  const conv = conversations.value.find((item) => item.id === convId)
  const currentName = conv?.name || ''
  try {
    const result = await ElMessageBox.prompt(
      t('sidebar.chatHistory.renamePrompt'),
      t('sidebar.chatHistory.renameTitle'),
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
      mindMateStore.renameConversation(convId, value.trim())
      renameConv({
        convId,
        name: value.trim(),
        difyUser: conv?.dify_user,
        server: conv?.server,
        mindbotConfigId: conv?.mindbot_config_id,
      })
    }
  } catch {
    // cancelled
  }
}

async function handleDeleteConversation(convId: string): Promise<void> {
  try {
    await swissGlassConfirm(
      t('sidebar.chatHistory.deleteConfirm'),
      t('sidebar.chatHistory.deleteTitle'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
    mindMateStore.deleteConversation(convId)
    const conv = conversations.value.find((item) => item.id === convId)
    deleteConv({
      convId,
      difyUser: conv?.dify_user,
      server: conv?.server,
      mindbotConfigId: conv?.mindbot_config_id,
    })
  } catch {
    // cancelled
  }
}

function handlePinConversation(convId: string): void {
  pinConv({ convId, ...mindMateStore.getConversationRoute(convId) })
}
</script>

<template>
  <div
    class="chat-history flex flex-1 min-h-0 flex-col border-t border-stone-200 relative overflow-hidden"
    :class="{ 'chat-history--compact': props.compact }"
  >
    <div
      class="history-header"
      :class="props.compact ? 'px-3 py-2.5' : 'px-4 py-3'"
    >
      <div class="min-w-0">
        <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
          {{ t('sidebar.chatHistory.title') }}
        </div>
        <div
          v-if="!isBlurred && folders.length > 0"
          class="text-[11px] text-stone-400 mt-0.5 truncate"
        >
          {{ folderCountLabel }}
        </div>
      </div>
      <button
        v-if="!isBlurred"
        class="new-folder-btn"
        type="button"
        :title="t('sidebar.chatHistory.folderCreateTitle')"
        @click="handleCreateFolder"
      >
        <FolderPlus class="w-3.5 h-3.5 shrink-0" />
        <span
          v-if="!props.compact"
          class="new-folder-btn__label"
        >
          {{ t('sidebar.chatHistory.folderCreateTitle') }}
        </span>
      </button>
    </div>

    <ElScrollbar
      :class="['flex-1 min-h-0', props.compact ? 'chat-history-scroll--compact' : 'px-4 pb-4']"
    >
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <MindmateCollabHistory
          v-if="props.showCollabSessions"
          inline
          @visible-change="collabHistoryVisible = $event"
        />

        <div
          v-if="foldersLoadFailed"
          class="archive-warning"
        >
          {{ t('sidebar.chatHistory.foldersLoadFailed') }}
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
          v-else-if="conversations.length === 0 && folders.length === 0 && !collabHistoryVisible"
          class="text-center py-8"
        >
          <MessageCircle class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ t('sidebar.chatHistory.empty') }}
          </p>
        </div>

        <template v-else-if="!isLoading">
          <section
            v-if="folders.length > 0"
            class="archive-section"
          >
            <div class="section-heading">
              {{ t('sidebar.chatHistory.foldersSection') }}
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
                <span class="folder-count">{{ conversationsForFolder(folder.id).length }}</span>
                <div
                  class="folder-actions"
                  @click.stop
                >
                  <button
                    class="folder-action-btn"
                    type="button"
                    :title="t('sidebar.actions.rename')"
                    @click="handleRenameFolder(folder.id, folder.name)"
                  >
                    <Edit3 class="w-3.5 h-3.5" />
                  </button>
                  <button
                    class="folder-action-btn folder-action-btn--danger"
                    type="button"
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
                <ChatHistoryConversationRow
                  v-for="conv in conversationsForFolder(folder.id)"
                  :key="conv.id"
                  :conv="conv"
                  :folders="folders"
                  :is-active="currentConversationId === conv.id"
                  :pinned="!!conv.is_pinned"
                  @select="handleConversationClick(conv.id, conv.name)"
                  @pin="handlePinConversation(conv.id)"
                  @rename="handleRenameConversation(conv.id)"
                  @delete="handleDeleteConversation(conv.id)"
                  @move="handleMoveConversation(conv.id, $event)"
                  @create-folder="handleCreateFolderAndMove(conv.id)"
                />
                <p
                  v-if="conversationsForFolder(folder.id).length === 0"
                  class="folder-empty"
                >
                  {{ t('sidebar.chatHistory.folderEmpty') }}
                </p>
              </div>
            </div>
          </section>

          <section
            v-if="uncategorizedConversations.length > 0 || folders.length > 0"
            class="archive-section"
          >
            <div class="section-heading">
              {{ t('sidebar.chatHistory.uncategorizedSection') }}
            </div>

            <template
              v-for="groupKey in MINDMATE_TIME_GROUP_KEYS"
              :key="groupKey"
            >
              <div
                v-if="groupedUncategorized[groupKey].length > 0"
                class="group-section"
              >
                <div class="group-label">{{ groupLabels[groupKey] }}</div>
                <ChatHistoryConversationRow
                  v-for="conv in groupedUncategorized[groupKey]"
                  :key="conv.id"
                  :conv="conv"
                  :folders="folders"
                  :is-active="currentConversationId === conv.id"
                  :pinned="!!conv.is_pinned"
                  @select="handleConversationClick(conv.id, conv.name)"
                  @pin="handlePinConversation(conv.id)"
                  @rename="handleRenameConversation(conv.id)"
                  @delete="handleDeleteConversation(conv.id)"
                  @move="handleMoveConversation(conv.id, $event)"
                  @create-folder="handleCreateFolderAndMove(conv.id)"
                />
              </div>
            </template>

            <p
              v-if="uncategorizedConversations.length === 0"
              class="uncategorized-empty"
            >
              {{ t('sidebar.chatHistory.uncategorizedEmpty') }}
            </p>

            <button
              v-if="hasMoreUncategorized"
              class="show-more-btn"
              type="button"
              @click="showAllUncategorized = true"
            >
              {{ t('sidebar.actions.showMore', { n: remainingUncategorizedCount }) }}
            </button>
            <button
              v-if="showAllUncategorized && uncategorizedConversations.length > initialVisibleLimit"
              class="show-more-btn"
              type="button"
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
          {{ t('sidebar.chatHistory.loginPrompt') }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-history {
  min-height: 120px;
}

.chat-history--compact {
  min-height: 0;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chat-history-scroll--compact :deep(.el-scrollbar__view) {
  box-sizing: border-box;
  padding-left: 12px;
  padding-right: 2px;
  padding-bottom: 12px;
}

.chat-history-scroll--compact :deep(.el-scrollbar__bar.is-vertical) {
  right: 0;
  width: 5px;
}

.chat-history-scroll--compact :deep(.el-scrollbar__thumb) {
  background-color: rgb(214 211 209 / 0.9);
}

.chat-history--compact :deep(.conversation-item) {
  padding: 6px 4px 6px 6px;
}

.chat-history--compact .group-label {
  padding-left: 0;
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

.archive-warning {
  font-size: 11px;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 10px;
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
}

.folder-header:hover .folder-actions {
  opacity: 1;
  pointer-events: auto;
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

.folder-action-btn:hover {
  background: #e7e5e4;
  color: #1c1917;
}

.folder-action-btn--danger:hover {
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
}

.show-more-btn:hover {
  background-color: #fafaf9;
  border-color: #a8a29e;
  color: #57534e;
}
</style>
