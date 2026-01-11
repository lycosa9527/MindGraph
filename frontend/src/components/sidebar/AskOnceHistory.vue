<script setup lang="ts">
/**
 * AskOnceHistory - Grouped list of recent AskOnce conversations
 * Design: Clean minimalist grouped by time periods (localStorage-based)
 * Shows max 10 items initially with "Show more" option
 */
import { computed, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu, ElScrollbar } from 'element-plus'

import { Edit3, Lock, MessageCircle, MoreHorizontal, Trash2 } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { type AskOnceConversation, useAskOnceStore } from '@/stores/askonce'

defineProps<{
  isBlurred?: boolean
}>()

const { isZh } = useLanguage()
const askOnceStore = useAskOnceStore()

// Show all or just 10
const showAll = ref(false)
const INITIAL_LIMIT = 10

// Computed - get conversations from store
const conversations = computed(() => askOnceStore.sortedConversations)

const currentConversationId = computed(() => askOnceStore.currentConversationId)

// Group conversations by time period
interface GroupedConversations {
  today: AskOnceConversation[]
  yesterday: AskOnceConversation[]
  week: AskOnceConversation[]
  month: AskOnceConversation[]
}

const groupedConversations = computed((): GroupedConversations => {
  const groups: GroupedConversations = {
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  // Limit to 10 unless showAll
  const items = showAll.value ? conversations.value : conversations.value.slice(0, INITIAL_LIMIT)

  items.forEach((conv) => {
    const convTime = conv.updatedAt

    if (convTime >= todayStart) {
      groups.today.push(conv)
    } else if (convTime >= yesterdayStart) {
      groups.yesterday.push(conv)
    } else if (convTime >= weekStart) {
      groups.week.push(conv)
    } else {
      groups.month.push(conv)
    }
  })

  return groups
})

// Check if there are more conversations to show
const hasMore = computed(() => conversations.value.length > INITIAL_LIMIT && !showAll.value)
const remainingCount = computed(() => conversations.value.length - INITIAL_LIMIT)

// Group labels
const groupLabels = computed(() => ({
  today: isZh.value ? '今天' : 'Today',
  yesterday: isZh.value ? '昨天' : 'Yesterday',
  week: isZh.value ? '上周' : 'Past Week',
  month: isZh.value ? '上月' : 'Past Month',
}))

// Handle conversation click
function handleConversationClick(convId: string): void {
  askOnceStore.setCurrentConversation(convId)
}

// Handle rename conversation
function handleRenameConversation(convId: string): void {
  const conv = conversations.value.find((c) => c.id === convId)
  const currentName = conv?.name || ''

  const newName = window.prompt(
    isZh.value ? '请输入新的对话名称' : 'Enter a new name for this conversation',
    currentName
  )

  if (newName !== null && newName.trim() !== currentName) {
    askOnceStore.renameConversation(convId, newName.trim())
  }
}

// Handle delete conversation
function handleDeleteConversation(convId: string): void {
  const confirmed = window.confirm(
    isZh.value
      ? '确定要删除这个对话吗？此操作不可撤销。'
      : 'Are you sure you want to delete this conversation? This cannot be undone.'
  )

  if (confirmed) {
    askOnceStore.deleteConversation(convId)
  }
}

// Toggle show all
function toggleShowAll(): void {
  showAll.value = !showAll.value
}
</script>

<template>
  <div class="askonce-history flex flex-col border-t border-stone-200 relative overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ isZh ? '历史对话' : 'History' }}
      </div>
    </div>

    <!-- Scrollable conversation list -->
    <ElScrollbar class="flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <!-- Empty State -->
        <div
          v-if="conversations.length === 0"
          class="text-center py-8"
        >
          <MessageCircle class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ isZh ? '暂无对话记录' : 'No conversations yet' }}
          </p>
        </div>

        <!-- Grouped Conversation List -->
        <template v-else>
          <!-- Today -->
          <div
            v-if="groupedConversations.today.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.today }}</div>
            <div
              v-for="conv in groupedConversations.today"
              :key="conv.id"
              class="conversation-item"
              :class="{ active: currentConversationId === conv.id }"
              @click="handleConversationClick(conv.id)"
            >
              <span class="conv-name">
                {{ conv.name || (isZh ? '未命名' : 'Untitled') }}
              </span>
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
                    <ElDropdownItem @click="handleRenameConversation(conv.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteConversation(conv.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Yesterday -->
          <div
            v-if="groupedConversations.yesterday.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.yesterday }}</div>
            <div
              v-for="conv in groupedConversations.yesterday"
              :key="conv.id"
              class="conversation-item"
              :class="{ active: currentConversationId === conv.id }"
              @click="handleConversationClick(conv.id)"
            >
              <span class="conv-name">
                {{ conv.name || (isZh ? '未命名' : 'Untitled') }}
              </span>
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
                    <ElDropdownItem @click="handleRenameConversation(conv.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteConversation(conv.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Past Week -->
          <div
            v-if="groupedConversations.week.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.week }}</div>
            <div
              v-for="conv in groupedConversations.week"
              :key="conv.id"
              class="conversation-item"
              :class="{ active: currentConversationId === conv.id }"
              @click="handleConversationClick(conv.id)"
            >
              <span class="conv-name">
                {{ conv.name || (isZh ? '未命名' : 'Untitled') }}
              </span>
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
                    <ElDropdownItem @click="handleRenameConversation(conv.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteConversation(conv.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Past Month -->
          <div
            v-if="groupedConversations.month.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.month }}</div>
            <div
              v-for="conv in groupedConversations.month"
              :key="conv.id"
              class="conversation-item"
              :class="{ active: currentConversationId === conv.id }"
              @click="handleConversationClick(conv.id)"
            >
              <span class="conv-name">
                {{ conv.name || (isZh ? '未命名' : 'Untitled') }}
              </span>
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
                    <ElDropdownItem @click="handleRenameConversation(conv.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteConversation(conv.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Show More button -->
          <button
            v-if="hasMore"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ isZh ? `显示更多 (${remainingCount})` : `Show more (${remainingCount})` }}
          </button>

          <!-- Show Less button -->
          <button
            v-if="showAll && conversations.length > INITIAL_LIMIT"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ isZh ? '收起' : 'Show less' }}
          </button>
        </template>
      </div>
    </ElScrollbar>

    <!-- Login overlay when blurred -->
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
          {{ isZh ? '登录后查看历史对话' : 'Login to view history' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.askonce-history {
  min-height: 120px;
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

.conv-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

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

.conversation-item:hover .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background-color: #e7e5e4;
  color: #1c1917;
}

/* Dropdown menu styling */
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
