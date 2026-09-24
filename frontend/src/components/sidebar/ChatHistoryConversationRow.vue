<script setup lang="ts">
import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import {
  Edit3,
  FolderInput,
  FolderMinus,
  FolderPlus,
  MoreHorizontal,
  Pin,
  Trash2,
} from '@lucide/vue'

import { useLanguage } from '@/composables'
import type { MindmateFolder } from '@/composables/queries/useMindmateFolderQueries'
import type { MindMateConversation } from '@/stores'

import ChatHistoryConversationTitle from './ChatHistoryConversationTitle.vue'

defineProps<{
  conv: MindMateConversation & { folder_id?: string | null }
  folders: MindmateFolder[]
  isActive: boolean
  pinned?: boolean
}>()

const emit = defineEmits<{
  (e: 'select'): void
  (e: 'pin'): void
  (e: 'rename'): void
  (e: 'delete'): void
  (e: 'move', folderId: string | null): void
  (e: 'createFolder'): void
}>()

const { t } = useLanguage()
</script>

<template>
  <div
    class="conversation-item"
    :class="{ active: isActive }"
    @click="emit('select')"
  >
    <ChatHistoryConversationTitle
      :conv="conv"
      :pinned="pinned"
    />
    <ElDropdown
      trigger="click"
      placement="bottom-end"
      popper-class="chat-history-folder-popper"
      class="folder-dropdown"
      @click.stop
    >
      <button
        class="folder-btn"
        :title="t('sidebar.actions.moveToFolder')"
        @click.stop
      >
        <FolderInput class="w-4 h-4" />
      </button>
      <template #dropdown>
        <ElDropdownMenu>
          <ElDropdownItem
            v-if="conv.folder_id"
            @click.stop="emit('move', null)"
          >
            <span class="chat-history-menu-row">
              <FolderMinus class="w-4 h-4 shrink-0" />
              {{ t('sidebar.actions.removeFromFolder') }}
            </span>
          </ElDropdownItem>
          <ElDropdownItem
            v-for="folder in folders"
            :key="folder.id"
            :disabled="conv.folder_id === folder.id"
            @click.stop="emit('move', folder.id)"
          >
            {{ folder.name }}
          </ElDropdownItem>
          <ElDropdownItem
            divided
            @click.stop="emit('createFolder')"
          >
            <span class="chat-history-menu-row">
              <FolderPlus class="w-4 h-4 shrink-0" />
              {{ t('sidebar.chatHistory.createFolderAndMove') }}
            </span>
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
    <ElDropdown
      trigger="click"
      class="more-dropdown"
      @click.stop
    >
      <button
        class="more-btn"
        @click.stop
      >
        <MoreHorizontal class="w-4 h-4" />
      </button>
      <template #dropdown>
        <ElDropdownMenu>
          <ElDropdownItem @click="emit('pin')">
            <Pin
              class="w-4 h-4 mr-2"
              :class="pinned ? 'text-amber-500 rotate-45' : ''"
            />
            {{ pinned ? t('sidebar.actions.unpin') : t('sidebar.actions.pinToTop') }}
          </ElDropdownItem>
          <ElDropdownItem @click="emit('rename')">
            <Edit3 class="w-4 h-4 mr-2" />
            {{ t('sidebar.actions.rename') }}
          </ElDropdownItem>
          <ElDropdownItem
            divided
            @click="emit('delete')"
          >
            <span class="delete-option">
              <Trash2 class="w-4 h-4 mr-2" />
              {{ t('sidebar.actions.delete') }}
            </span>
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
  </div>
</template>

<style scoped>
.conversation-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  transition: background-color 0.15s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.conversation-item:hover {
  background-color: #f5f5f4;
}

.conversation-item.active {
  background-color: #e7e5e4;
  color: #1c1917;
}

.folder-btn,
.more-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0;
  color: #78716c;
  transition: all 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
}

.folder-dropdown {
  flex-shrink: 0;
}

.conversation-item:hover .folder-btn,
.conversation-item:hover .more-btn {
  opacity: 1;
}

.folder-btn:hover {
  background-color: #fef3c7;
  color: #b45309;
}

.more-btn:hover {
  background-color: #e7e5e4;
  color: #1c1917;
}

.more-dropdown :deep(.el-dropdown-menu) {
  padding: 4px;
  border-radius: 8px;
  min-width: 140px;
}

.more-dropdown :deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  font-size: 13px;
  border-radius: 4px;
  color: #57534e;
}

.more-dropdown :deep(.el-dropdown-menu__item:hover) {
  background-color: #f5f5f4;
  color: #1c1917;
}

.more-dropdown :deep(.el-dropdown-menu__item.is-divided) {
  margin-top: 4px;
  border-top: 1px solid #e7e5e4;
  padding-top: 8px;
}

.delete-option {
  display: flex;
  align-items: center;
  color: #dc2626;
}
</style>

<style>
.chat-history-folder-popper.el-popper {
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 8px !important;
  min-width: 140px !important;
  max-width: min(calc(100vw - 24px), 220px) !important;
}

.chat-history-folder-popper .el-dropdown-menu__item {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-history-folder-popper .chat-history-menu-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
