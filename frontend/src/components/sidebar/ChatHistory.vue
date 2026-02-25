<script setup lang="ts">
/**
 * ChatHistory - Grouped list of recent chat conversations
 * Design: Clean minimalist grouped by time periods
 * Shows max 10 items initially with "Show more" option
 */
import { computed, ref, watch } from 'vue'

import {
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElMessageBox,
  ElScrollbar,
} from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { Edit3, Lock, MessageCircle, MoreHorizontal, Pin, Trash2 } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import {
  useConversations,
  useDeleteConversation,
  usePinConversation,
  usePinnedConversations,
  useRenameConversation,
} from '@/composables/queries'
import { type MindMateConversation, useAuthStore, useMindMateStore } from '@/stores'

const _props = defineProps<{
  isBlurred?: boolean
}>()

const { isZh } = useLanguage()
const _authStore = useAuthStore()
const mindMateStore = useMindMateStore()

// Show all or just 10
const showAll = ref(false)
const INITIAL_LIMIT = 10

// Vue Query queries
const { data: conversationsData, isLoading: isLoadingConversations } = useConversations()
const { data: pinnedData } = usePinnedConversations()

// Mutations
const { mutate: deleteConv } = useDeleteConversation()
const { mutate: renameConv } = useRenameConversation()
const { mutate: pinConv } = usePinConversation()

// Computed - sync conversations from query data
const conversations = computed(() => {
  if (!conversationsData.value) return []
  const pinnedIds = pinnedData.value || new Set()

  // Mark conversations as pinned and sort
  const convs = conversationsData.value.map((conv) => ({
    ...conv,
    is_pinned: pinnedIds.has(conv.id),
  }))

  // Sort: pinned first, then by updated_at descending
  return convs.sort((a, b) => {
    if (a.is_pinned && !b.is_pinned) return -1
    if (!a.is_pinned && b.is_pinned) return 1
    return b.updated_at - a.updated_at
  })
})

const isLoading = computed(() => isLoadingConversations.value)
const currentConversationId = computed(() => mindMateStore.currentConversationId)

// Sync conversations to store for backward compatibility
watch(
  [conversationsData, pinnedData],
  ([convs, pinned]) => {
    if (convs && pinned) {
      mindMateStore.syncConversationsFromQuery(convs, pinned)
    }
  },
  { immediate: true }
)

// Group conversations by time period
interface GroupedConversations {
  pinned: MindMateConversation[]
  today: MindMateConversation[]
  yesterday: MindMateConversation[]
  week: MindMateConversation[]
  month: MindMateConversation[]
}

const groupedConversations = computed((): GroupedConversations => {
  const groups: GroupedConversations = {
    pinned: [],
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
    // Pinned items go to pinned group regardless of time
    if (conv.is_pinned) {
      groups.pinned.push(conv)
      return
    }

    const convTime = conv.updated_at * 1000

    if (convTime >= todayStart) {
      groups.today.push(conv)
    } else if (convTime >= yesterdayStart) {
      groups.yesterday.push(conv)
    } else if (convTime >= weekStart) {
      groups.week.push(conv)
    } else {
      // Everything older goes to Past Month
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
  pinned: isZh.value ? '置顶' : 'Pinned',
  today: isZh.value ? '今天' : 'Today',
  yesterday: isZh.value ? '昨天' : 'Yesterday',
  week: isZh.value ? '上周' : 'Past Week',
  month: isZh.value ? '上月' : 'Past Month',
}))

// No need to fetch - Vue Query handles it automatically via enabled flag

// Handle conversation click
function handleConversationClick(convId: string, name: string): void {
  mindMateStore.setCurrentConversation(convId, name)
}

// Handle rename conversation
async function handleRenameConversation(convId: string): Promise<void> {
  const conv = conversations.value.find((c) => c.id === convId)
  const currentName = conv?.name || ''

  try {
    const result = await ElMessageBox.prompt(
      isZh.value ? '请输入新的对话名称' : 'Enter a new name for this conversation',
      isZh.value ? '重命名对话' : 'Rename Conversation',
      {
        confirmButtonText: isZh.value ? '确定' : 'OK',
        cancelButtonText: isZh.value ? '取消' : 'Cancel',
        inputValue: currentName,
        inputPattern: /\S+/,
        inputErrorMessage: isZh.value ? '名称不能为空' : 'Name cannot be empty',
      }
    )

    const value =
      typeof result === 'object' && result !== null && 'value' in result
        ? (result as { value: string }).value
        : undefined
    if (value && value.trim() !== currentName) {
      // Update store optimistically
      mindMateStore.renameConversation(convId, value.trim())
      // Call mutation to update server and invalidate cache
      renameConv({ convId, name: value.trim() })
    }
  } catch {
    // User cancelled
  }
}

// Handle delete conversation
async function handleDeleteConversation(convId: string): Promise<void> {
  try {
    await ElMessageBox.confirm(
      isZh.value
        ? '确定要删除这个对话吗？此操作不可撤销。'
        : 'Are you sure you want to delete this conversation? This cannot be undone.',
      isZh.value ? '删除对话' : 'Delete Conversation',
      {
        confirmButtonText: isZh.value ? '删除' : 'Delete',
        cancelButtonText: isZh.value ? '取消' : 'Cancel',
        type: 'warning',
      }
    )

    // Update store optimistically
    mindMateStore.deleteConversation(convId)
    // Call mutation to update server and invalidate cache
    deleteConv(convId)
  } catch {
    // User cancelled
  }
}

// Handle pin/unpin conversation
async function handlePinConversation(convId: string): Promise<void> {
  // Call mutation to update server and invalidate cache
  pinConv(convId)
}

// Toggle show all
function toggleShowAll(): void {
  showAll.value = !showAll.value
}
</script>

<template>
  <div class="chat-history flex flex-col border-t border-stone-200 relative overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ isZh ? '历史对话' : 'History' }}
      </div>
    </div>

    <!-- Scrollable conversation list -->
    <ElScrollbar class="flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <!-- Loading State -->
        <div
          v-if="isLoading"
          class="flex items-center justify-center py-8"
        >
          <ElIcon class="animate-spin text-stone-400">
            <Loading />
          </ElIcon>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="conversations.length === 0"
          class="text-center py-8"
        >
          <MessageCircle class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ isZh ? '暂无对话记录' : 'No conversations yet' }}
          </p>
        </div>

        <!-- Grouped Conversation List -->
        <template v-else>
          <!-- Pinned -->
          <div
            v-if="groupedConversations.pinned.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.pinned }}</div>
            <div
              v-for="conv in groupedConversations.pinned"
              :key="conv.id"
              class="conversation-item"
              :class="{ active: currentConversationId === conv.id }"
              @click="handleConversationClick(conv.id, conv.name)"
            >
              <span class="conv-name">
                <Pin class="w-3 h-3 inline-block mr-1 text-amber-500" />
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
                    <ElDropdownItem @click="handlePinConversation(conv.id)">
                      <Pin class="w-4 h-4 mr-2 text-amber-500 rotate-45" />
                      {{ isZh ? '取消置顶' : 'Unpin' }}
                    </ElDropdownItem>
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
              @click="handleConversationClick(conv.id, conv.name)"
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
                    <ElDropdownItem @click="handlePinConversation(conv.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
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
              @click="handleConversationClick(conv.id, conv.name)"
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
                    <ElDropdownItem @click="handlePinConversation(conv.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
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
              @click="handleConversationClick(conv.id, conv.name)"
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
                    <ElDropdownItem @click="handlePinConversation(conv.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
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
              @click="handleConversationClick(conv.id, conv.name)"
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
                    <ElDropdownItem @click="handlePinConversation(conv.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
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
.chat-history {
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
