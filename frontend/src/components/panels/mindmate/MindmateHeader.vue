<script setup lang="ts">
import { computed } from 'vue'

import { ElButton, ElDropdown, ElDropdownMenu, ElIcon } from 'element-plus'

import { Close, Delete, DocumentCopy, Menu } from '@element-plus/icons-vue'

import { MessageCirclePlus } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateSeminarRosterBar from '@/components/mindmate/MindmateSeminarRosterBar.vue'
import MindMateDingtalkBadge from '@/components/sidebar/MindMateDingtalkBadge.vue'
import { useLanguage } from '@/composables'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import type { MindMateConversation } from '@/stores'
import { beijingCalendarDaysBetween, formatInBeijing } from '@/utils/beijingClock'

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
    showContactsToggle?: boolean
    membersOpen?: boolean
    showContinueSession?: boolean
  }>(),
  {
    mode: 'panel',
    title: '',
    isTyping: false,
    isAuthenticated: true,
    conversations: () => [],
    isLoadingHistory: false,
    currentConversationId: null,
    showContactsToggle: false,
    membersOpen: false,
    showContinueSession: false,
  }
)

const { displayName: brandedTitle } = useMindMateBranding()
const headerTitle = computed(() => props.title || brandedTitle.value)

const emit = defineEmits<{
  (e: 'newConversation'): void
  (e: 'close'): void
  (e: 'loadHistory', conversationId: string): void
  (e: 'deleteHistory', conversationId: string): void
  (e: 'toggleMembers'): void
  (e: 'addMembers'): void
  (e: 'continueSession'): void
}>()

const { t, currentLanguage } = useLanguage()
const isFullpageMode = computed(() => props.mode === 'fullpage')

function formatConversationDate(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  const diffDays = beijingCalendarDaysBetween(date, new Date())

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
  return formatInBeijing(date, localeTag, {
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

function isMindbotConversation(conv: MindMateConversation): boolean {
  if (conv.channel === 'mindbot') {
    return true
  }
  return (conv.dify_user || '').startsWith('mindbot_')
}
</script>

<template>
  <div
    class="panel-header h-14 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0"
  >
    <div class="flex-1 min-w-0 flex items-center">
      <span
        v-if="!isFullpageMode && headerTitle"
        class="panel-header-title"
      >
        {{ headerTitle }}
      </span>
    </div>
    <div class="mindmate-header-actions flex items-center gap-2 shrink-0">
      <ElButton
        v-if="showContinueSession"
        size="small"
        class="shrink-0"
        @click="emit('continueSession')"
      >
        <I18nText
          k="mindmate.collabContinueSession"
          dense
        />
      </ElButton>
      <MindmateSeminarRosterBar
        v-if="showContactsToggle"
        :members-open="membersOpen"
        @toggle-members="emit('toggleMembers')"
        @add-members="emit('addMembers')"
      />
      <!-- History dropdown - panel mode only -->
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
                <span class="text-xs text-gray-500"><I18nText k="common.loading" /></span>
              </div>
              <div
                v-else-if="!conversations?.length"
                class="history-dropdown-empty"
              >
                <ElIcon class="text-2xl text-gray-300"><DocumentCopy /></ElIcon>
                <p class="text-xs text-gray-500">
                  <I18nText k="mindmate.noHistory" />
                </p>
              </div>
              <div
                v-else
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
                      <span class="history-item-title-text">
                        <template v-if="conv.name">{{ conv.name }}</template
                        ><I18nText
                          v-else
                          k="mindmate.untitled"
                        />
                      </span>
                      <MindMateDingtalkBadge v-if="isMindbotConversation(conv)" />
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
              </div>
            </div>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
      <!-- New chat — right of history -->
      <ElButton
        v-if="!isFullpageMode"
        text
        circle
        size="small"
        class="new-chat-icon-btn shrink-0"
        :disabled="!isAuthenticated"
        :aria-label="t('mindmate.newChat')"
        :title="t('mindmate.newChat')"
        @click="emit('newConversation')"
      >
        <MessageCirclePlus
          class="new-chat-icon"
          :size="18"
          :stroke-width="2"
        />
      </ElButton>
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

.mindmate-header-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.panel-header-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--swiss-ink, #1c1917);
  line-height: 1.2;
}

:global(html.dark) .panel-header-title {
  color: var(--swiss-ink, #f5f5f4);
}

.new-chat-icon-btn {
  color: #5b21b6;
}

.new-chat-icon-btn:hover:not(:disabled) {
  color: #4c1d95;
  background: #ede9fe;
}

.new-chat-icon {
  display: block;
}

:global(html.dark) .new-chat-icon-btn {
  color: #c4b5fd;
}

:global(html.dark) .new-chat-icon-btn:hover:not(:disabled) {
  color: #e0e7ff;
  background: rgb(99 102 241 / 0.2);
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
  max-height: min(280px, 50vh);
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
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
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.history-item-title-text {
  flex: 1;
  min-width: 0;
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
/* Popper is teleported to body - needs global style for z-index / clip */
.mindmate-history-dropdown-popper {
  z-index: 9999 !important;
}

/* Override ElDropdownMenu default padding for custom content */
.mindmate-history-dropdown-popper .el-dropdown-menu {
  padding: 0 !important;
  min-width: 260px !important;
  max-height: min(320px, 60vh) !important;
  overflow: hidden !important;
}

.mindmate-history-dropdown-popper .history-dropdown-list {
  max-height: min(280px, 50vh);
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
}
</style>
