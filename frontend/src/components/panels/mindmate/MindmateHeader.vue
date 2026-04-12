<script setup lang="ts">
import { computed } from 'vue'

import { ElButton, ElDropdown, ElDropdownMenu, ElIcon, ElScrollbar, ElTooltip } from 'element-plus'

import { Close, Delete, DocumentCopy, Menu, Plus } from '@element-plus/icons-vue'

import { LayoutGrid } from 'lucide-vue-next'

import IntlModuleGrid from '@/components/mindgraph/IntlModuleGrid.vue'
import { useLanguage } from '@/composables'
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import type { MindMateConversation } from '@/stores'

const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
    title?: string
    isTyping?: boolean
    isAuthenticated?: boolean
    /** For panel mode: conversations for history dropdown */
    conversations?: MindMateConversation[]
    isLoadingHistory?: boolean
    currentConversationId?: string | null
    /** Fullpage: true when app sidebar already shows conversation list (e.g. simplified UI). */
    hideHistoryToggle?: boolean
  }>(),
  {
    mode: 'panel',
    title: 'MindMate',
    isTyping: false,
    isAuthenticated: true,
    conversations: () => [],
    isLoadingHistory: false,
    currentConversationId: null,
    hideHistoryToggle: false,
  }
)

const emit = defineEmits<{
  (e: 'toggleHistory'): void
  (e: 'newConversation'): void
  (e: 'close'): void
  (e: 'loadHistory', conversationId: string): void
  (e: 'deleteHistory', conversationId: string): void
}>()

const { t, currentLanguage } = useLanguage()
const isFullpageMode = computed(() => props.mode === 'fullpage')

function formatConversationDate(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return t('common.date.today')
  }
  if (diffDays === 1) {
    return t('common.date.yesterday')
  }
  if (diffDays < 7) {
    return t('common.date.daysAgo', { n: diffDays })
  }
  const localeTag = intlLocaleForUiCode(currentLanguage.value as LocaleCode)
  return date.toLocaleDateString(localeTag, {
    month: 'short',
    day: 'numeric',
  })
}

function handleLoadHistory(convId: string) {
  emit('loadHistory', convId)
}

function handleDeleteHistory(convId: string, event: Event) {
  event.stopPropagation()
  emit('deleteHistory', convId)
}
</script>

<template>
  <div
    class="panel-header h-14 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0"
  >
    <div class="flex items-center gap-2 min-w-0 flex-1">
      <!-- History button (drawer) - fullpage mode only; hidden when sidebar lists chats -->
      <ElTooltip
        v-if="isFullpageMode && !props.hideHistoryToggle"
        :content="t('mindmate.historyTitle')"
      >
        <ElButton
          text
          circle
          size="small"
          class="shrink-0"
          @click="emit('toggleHistory')"
        >
          <ElIcon><Menu /></ElIcon>
        </ElButton>
      </ElTooltip>
      <h1
        class="text-sm font-semibold text-gray-800 dark:text-white truncate"
        :class="{ 'typing-cursor': isTyping }"
      >
        {{ title }}
      </h1>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <!-- New Conversation button - fullpage only -->
      <ElButton
        v-if="isFullpageMode"
        class="new-chat-btn"
        size="small"
        :disabled="!props.isAuthenticated"
        @click="emit('newConversation')"
      >
        <ElIcon class="mr-1"><Plus /></ElIcon>
        {{ t('mindmate.newChat') }}
      </ElButton>
      <IntlModuleGrid v-if="isFullpageMode">
        <template #reference>
          <ElButton
            size="small"
            class="other-modules-pill-btn"
            :title="t('mindmate.otherModules')"
          >
            <LayoutGrid class="other-modules-pill-btn__icon" />
            {{ t('mindmate.otherModules') }}
          </ElButton>
        </template>
      </IntlModuleGrid>
      <!-- History dropdown - panel mode only, left of close -->
      <ElDropdown
        v-if="!isFullpageMode"
        trigger="click"
        placement="bottom-end"
        :hide-on-click="false"
        teleported
        popper-class="mindmate-history-dropdown-popper"
      >
        <ElButton
          text
          circle
          size="small"
          class="shrink-0 history-dropdown-trigger"
        >
          <ElIcon><Menu /></ElIcon>
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu class="history-dropdown-menu">
            <div class="history-dropdown-content">
              <div
                v-if="isLoadingHistory"
                class="history-dropdown-loading"
              >
                <div
                  class="animate-spin w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full"
                />
                <span class="text-xs text-gray-500">{{ t('common.loading') }}</span>
              </div>
              <div
                v-else-if="!conversations?.length"
                class="history-dropdown-empty"
              >
                <ElIcon class="text-2xl text-gray-300"><DocumentCopy /></ElIcon>
                <p class="text-xs text-gray-500">{{ t('mindmate.noHistory') }}</p>
              </div>
              <ElScrollbar
                v-else
                :max-height="280"
                class="history-dropdown-list"
              >
                <div
                  v-for="conv in conversations"
                  :key="conv.id"
                  class="history-dropdown-item"
                  :class="{ 'is-active': currentConversationId === conv.id }"
                  @click="handleLoadHistory(conv.id)"
                >
                  <div class="history-item-content">
                    <p class="history-item-title">
                      {{ conv.name || t('mindmate.untitled') }}
                    </p>
                    <p class="history-item-date">
                      {{ formatConversationDate(conv.updated_at) }}
                    </p>
                  </div>
                  <ElButton
                    text
                    size="small"
                    class="history-item-delete"
                    @click="handleDeleteHistory(conv.id, $event)"
                  >
                    <ElIcon :size="14"><Delete /></ElIcon>
                  </ElButton>
                </div>
              </ElScrollbar>
            </div>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
      <!-- Close button (panel mode only) -->
      <ElButton
        v-if="!isFullpageMode"
        text
        circle
        size="small"
        @click="emit('close')"
      >
        <ElIcon><Close /></ElIcon>
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';

/* New Chat — neutral stone (primary action) */
.new-chat-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-hover-text-color: #1c1917;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

.dark .new-chat-btn {
  --el-button-bg-color: #4b5563;
  --el-button-border-color: #6b7280;
  --el-button-hover-bg-color: #6b7280;
  --el-button-hover-border-color: #9ca3af;
  --el-button-hover-text-color: #f9fafb;
  --el-button-active-bg-color: #52525b;
  --el-button-active-border-color: #a1a1aa;
  --el-button-text-color: #f9fafb;
}

/* Other modules — soft indigo (navigation / switch context) */
.other-modules-pill-btn {
  --el-button-bg-color: #eef2ff;
  --el-button-border-color: #c7d2fe;
  --el-button-hover-bg-color: #e0e7ff;
  --el-button-hover-border-color: #a5b4fc;
  --el-button-hover-text-color: #312e81;
  --el-button-active-bg-color: #c7d2fe;
  --el-button-active-border-color: #818cf8;
  --el-button-text-color: #4338ca;
  font-weight: 500;
  border-radius: 9999px;
  gap: 4px;
}

.dark .other-modules-pill-btn {
  --el-button-bg-color: #312e81;
  --el-button-border-color: #4f46e5;
  --el-button-hover-bg-color: #4338ca;
  --el-button-hover-border-color: #6366f1;
  --el-button-hover-text-color: #eef2ff;
  --el-button-active-bg-color: #4f46e5;
  --el-button-active-border-color: #818cf8;
  --el-button-text-color: #e0e7ff;
}

.other-modules-pill-btn__icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  margin-right: 2px;
  color: currentColor;
}

/* History dropdown - panel mode */
.history-dropdown-menu {
  padding: 0;
  min-width: 260px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 1px solid #e5e7eb;
}

.dark .history-dropdown-menu {
  background: #374151;
  border-color: #4b5563;
}

.history-dropdown-content {
  padding: 8px;
}

.history-dropdown-loading,
.history-dropdown-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 16px;
}

.history-dropdown-list {
  max-height: 280px;
}

.history-dropdown-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.history-dropdown-item:hover {
  background-color: #f3f4f6;
}

.dark .history-dropdown-item:hover {
  background-color: #374151;
}

.history-dropdown-item.is-active {
  background-color: #dbeafe;
}

.dark .history-dropdown-item.is-active {
  background-color: #1e3a5f;
}

.history-item-content {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 13px;
  font-weight: 500;
  color: #1f2937;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dark .history-item-title {
  color: #f3f4f6;
}

.history-item-date {
  font-size: 11px;
  color: #6b7280;
  margin: 2px 0 0 0;
}

.history-item-delete {
  opacity: 0.6;
  flex-shrink: 0;
}

.history-dropdown-item:hover .history-item-delete {
  opacity: 1;
}

.history-item-delete:hover {
  color: #dc2626 !important;
}

.history-dropdown-trigger {
  display: inline-flex;
  cursor: pointer;
}
</style>

<style>
/* Popper is teleported to body - needs global style for z-index */
.mindmate-history-dropdown-popper {
  z-index: 9999 !important;
}

/* Override ElDropdownMenu default padding for custom content */
.mindmate-history-dropdown-popper .el-dropdown-menu {
  padding: 0 !important;
  min-width: 260px !important;
  max-height: 320px !important;
}
</style>
