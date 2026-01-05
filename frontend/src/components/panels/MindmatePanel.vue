<script setup lang="ts">
/**
 * MindMate Panel - AI assistant chat interface (ChatGPT-style)
 * Uses useMindMate composable for SSE streaming
 * Features: Markdown rendering, code highlighting, message actions, stop generation
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { ElButton, ElDrawer, ElIcon, ElInput, ElScrollbar, ElTooltip } from 'element-plus'

import {
  Bottom,
  ChatDotRound,
  CircleClose,
  Close,
  CopyDocument,
  Delete,
  DocumentCopy,
  Edit,
  Menu,
  Promotion,
  RefreshRight,
  Share,
  Top,
  UploadFilled,
} from '@element-plus/icons-vue'

import DOMPurify from 'dompurify'
import { Paperclip, Send } from 'lucide-vue-next'
import MarkdownIt from 'markdown-it'

import { useLanguage, useMindMate, useNotifications } from '@/composables'
import type { FeedbackRating } from '@/composables/useMindMate'
import { useAuthStore, useMindMateStore } from '@/stores'

import ShareExportModal from './ShareExportModal.vue'

// Props for different display modes
const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
  }>(),
  {
    mode: 'panel',
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

// Computed for mode checks
const isFullpageMode = computed(() => props.mode === 'fullpage')

// AI robot image URL (for fullpage mode)
const robotImageUrl =
  'https://space-static.coze.site/coze_space/7586606221064585514/upload/%E6%96%B0%E5%AF%B9%E8%AF%9D%281%29%281%29%281%29_536x662.png?sign=1768989628-231ab7c8de-0-26441aa331e9c26987be17f74685c0f95079054464622780e9f012aa077f9606'

const { isZh } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()

// Markdown renderer
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true,
})

// Typing effect state
const displayTitle = ref('MindMate')
const isTypingTitle = ref(false)

// Use MindMate composable for SSE streaming
const mindMate = useMindMate({
  language: isZh.value ? 'zh' : 'en',
  onError: (error) => {
    notify.error(error)
  },
  onTitleChanged: (title) => {
    animateTitleChange(title)
  },
})

// Local state
const inputText = ref('')
const scrollbarRef = ref<InstanceType<typeof ElScrollbar> | null>(null)
const editingMessageId = ref<string | null>(null)
const editingContent = ref('')
const hoveredMessageId = ref<string | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const showHistorySidebar = ref(false)
const showShareModal = ref(false)

// Computed for loading state
const isLoading = computed(() => mindMate.isLoading.value || mindMate.isStreaming.value)

// User avatar from auth store
const userAvatar = computed(() => {
  const avatar = authStore.user?.avatar || '👤'
  if (avatar.startsWith('avatar_')) {
    return '👤'
  }
  return avatar
})

// Check if welcome message should be shown
const showWelcome = computed(() => {
  return !mindMate.hasMessages.value && !mindMate.isLoading.value && !mindMate.isStreaming.value
})

// Send welcome message on mount and fetch conversations
onMounted(() => {
  if (!mindMate.hasMessages.value) {
    mindMate.sendGreeting()
  }
  // Fetch conversation history
  mindMate.fetchConversations()
})

// Watch for title changes to sync display (from store)
watch(
  () => mindMateStore.conversationTitle,
  (newTitle) => {
    if (!isTypingTitle.value && newTitle !== displayTitle.value) {
      displayTitle.value = newTitle
    }
  }
)

// Watch for new messages to scroll
watch(
  () => mindMate.messages.value.length,
  async () => {
    await scrollToBottom()
  }
)

// Also scroll when streaming updates content
watch(
  () => mindMate.lastMessage.value?.content,
  async () => {
    if (mindMate.isStreaming.value) {
      await scrollToBottom()
    }
  }
)

// Render markdown with sanitization
function renderMarkdown(content: string): string {
  if (!content) return ''
  const html = md.render(content)
  return DOMPurify.sanitize(html)
}

// Trigger file input
function triggerFileUpload() {
  fileInputRef.value?.click()
}

// Handle file selection
async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  for (const file of Array.from(files)) {
    await mindMate.uploadFile(file)
  }

  // Reset input
  input.value = ''
}

// Get file icon based on type
function getFileIcon(type: string): string {
  switch (type) {
    case 'image':
      return '🖼️'
    case 'audio':
      return '🎵'
    case 'video':
      return '🎬'
    case 'document':
      return '📄'
    default:
      return '📎'
  }
}

// Format file size
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Send message using composable
async function sendMessage() {
  if ((!inputText.value.trim() && mindMate.pendingFiles.value.length === 0) || isLoading.value)
    return

  const message = inputText.value.trim()
  inputText.value = ''

  await mindMate.sendMessage(message)
}

// Handle keyboard
function handleKeydown(event: Event | KeyboardEvent) {
  if ('key' in event && event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

// Scroll to bottom of messages
async function scrollToBottom() {
  await nextTick()
  if (scrollbarRef.value) {
    const scrollContainer = scrollbarRef.value.$el.querySelector('.el-scrollbar__wrap')
    if (scrollContainer) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight
    }
  }
}

// Typing animation for title changes
async function animateTitleChange(newTitle: string) {
  if (isTypingTitle.value) return
  isTypingTitle.value = true

  // First, clear current title character by character
  const currentTitle = displayTitle.value
  for (let i = currentTitle.length; i >= 0; i--) {
    displayTitle.value = currentTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 20))
  }

  // Then type new title character by character
  for (let i = 0; i <= newTitle.length; i++) {
    displayTitle.value = newTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 30))
  }

  isTypingTitle.value = false
}

// Toggle history sidebar
function toggleHistorySidebar() {
  showHistorySidebar.value = !showHistorySidebar.value
  if (showHistorySidebar.value) {
    mindMate.fetchConversations()
  }
}

// Load a conversation from history
async function loadConversationFromHistory(convId: string) {
  await mindMate.loadConversation(convId)
  showHistorySidebar.value = false
  await scrollToBottom()
}

// Delete a conversation
async function deleteConversationFromHistory(convId: string) {
  const success = await mindMate.deleteConversation(convId)
  if (success) {
    notify.success(isZh.value ? '会话已删除' : 'Conversation deleted')
  } else {
    notify.error(isZh.value ? '删除失败' : 'Failed to delete')
  }
}

// Format conversation date
function formatConversationDate(timestamp: number): string {
  const date = new Date(timestamp * 1000) // Dify uses seconds
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return isZh.value ? '今天' : 'Today'
  } else if (diffDays === 1) {
    return isZh.value ? '昨天' : 'Yesterday'
  } else if (diffDays < 7) {
    return isZh.value ? `${diffDays}天前` : `${diffDays} days ago`
  } else {
    return date.toLocaleDateString(isZh.value ? 'zh-CN' : 'en-US', {
      month: 'short',
      day: 'numeric',
    })
  }
}

// Stop generation
function stopGeneration() {
  mindMate.stopGeneration()
}

// Copy message to clipboard
async function copyMessage(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    notify.success(isZh.value ? '已复制到剪贴板' : 'Copied to clipboard')
  } catch {
    notify.error(isZh.value ? '复制失败' : 'Failed to copy')
  }
}

// Regenerate message
function regenerateMessage(messageId: string) {
  mindMate.regenerateMessage(messageId)
}

// Handle like/dislike feedback
async function handleFeedback(messageId: string, rating: FeedbackRating) {
  const message = mindMate.messages.value.find((m) => m.id === messageId)
  if (!message) return

  // Toggle if same rating clicked again
  const newRating = message.feedback === rating ? null : rating

  const success = await mindMate.submitFeedback(messageId, newRating)
  if (success) {
    notify.success(
      isZh.value
        ? newRating === 'like'
          ? '感谢您的反馈'
          : newRating === 'dislike'
            ? '感谢您的反馈，我们会努力改进'
            : '已取消反馈'
        : newRating === 'like'
          ? 'Thanks for your feedback'
          : newRating === 'dislike'
            ? 'Thanks for your feedback, we will improve'
            : 'Feedback removed'
    )
  }
}

// Open share modal
function openShareModal() {
  showShareModal.value = true
}

// Start editing message
function startEdit(message: { id: string; content: string }) {
  editingMessageId.value = message.id
  editingContent.value = message.content
}

// Cancel editing
function cancelEdit() {
  editingMessageId.value = null
  editingContent.value = ''
}

// Save edited message
async function saveEdit() {
  if (!editingMessageId.value || !editingContent.value.trim()) {
    cancelEdit()
    return
  }

  const messageId = editingMessageId.value
  const message = editingContent.value.trim()
  editingMessageId.value = null
  editingContent.value = ''

  // Remove the edited user message and resend
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex !== -1) {
    mindMate.messages.value = mindMate.messages.value.slice(0, msgIndex)
  }

  await mindMate.sendMessage(message, false)
}

// Get previous user message for regeneration context
function getPreviousUserMessage(messageId: string): string | null {
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex <= 0) return null

  for (let i = msgIndex - 1; i >= 0; i--) {
    if (mindMate.messages.value[i].role === 'user') {
      return mindMate.messages.value[i].content
    }
  }
  return null
}

// Check if a message is the last assistant message
function isLastAssistantMessage(messageId: string): boolean {
  const assistantMessages = mindMate.messages.value.filter((m) => m.role === 'assistant')
  if (assistantMessages.length === 0) return false
  return assistantMessages[assistantMessages.length - 1].id === messageId
}
</script>

<template>
  <div
    class="mindmate-panel bg-white dark:bg-gray-800 flex flex-col h-full"
    :class="{
      'border-l border-gray-200 dark:border-gray-700 shadow-lg': !isFullpageMode,
    }"
  >
    <!-- Header -->
    <div
      class="panel-header h-14 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
    >
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <!-- History button only in panel mode -->
        <ElTooltip
          v-if="!isFullpageMode"
          :content="isZh ? '历史会话' : 'Conversation History'"
        >
          <ElButton
            text
            circle
            size="small"
            class="flex-shrink-0"
            @click="toggleHistorySidebar"
          >
            <ElIcon><Menu /></ElIcon>
          </ElButton>
        </ElTooltip>
        <!-- Gradient icon for panel mode only (no avatar in fullpage header) -->
        <div
          v-if="!isFullpageMode"
          class="w-8 h-8 bg-gradient-to-br from-primary-400 to-purple-500 rounded-lg flex items-center justify-center flex-shrink-0"
        >
          <ElIcon class="text-white text-sm"><ChatDotRound /></ElIcon>
        </div>
        <h3
          class="font-semibold text-gray-800 dark:text-white text-sm truncate"
          :class="{ 'typing-cursor': isTypingTitle }"
        >
          {{ displayTitle }}
        </h3>
      </div>
      <div class="flex items-center gap-1 flex-shrink-0">
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

    <!-- Conversation History Drawer -->
    <ElDrawer
      v-model="showHistorySidebar"
      :title="isZh ? '历史会话' : 'Conversation History'"
      direction="ltr"
      size="280px"
      :with-header="true"
      :modal="true"
      :append-to-body="true"
      class="history-drawer"
    >
      <div class="conversation-list">
        <!-- Loading State -->
        <div
          v-if="mindMate.isLoadingConversations.value"
          class="text-center py-8 text-gray-500"
        >
          <div
            class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mx-auto mb-2"
          />
          <span class="text-sm">{{ isZh ? '加载中...' : 'Loading...' }}</span>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="mindMate.conversations.value.length === 0"
          class="text-center py-8 text-gray-500"
        >
          <ElIcon class="text-4xl mb-2 text-gray-300"><DocumentCopy /></ElIcon>
          <p class="text-sm">{{ isZh ? '暂无历史会话' : 'No conversation history' }}</p>
        </div>

        <!-- Conversation List -->
        <div
          v-else
          class="space-y-1"
        >
          <div
            v-for="conv in mindMate.conversations.value"
            :key="conv.id"
            class="conversation-item p-3 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors group"
            :class="{
              'bg-primary-50 dark:bg-primary-900/30':
                mindMateStore.currentConversationId === conv.id,
            }"
            @click="loadConversationFromHistory(conv.id)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-800 dark:text-white truncate">
                  {{ conv.name || (isZh ? '未命名会话' : 'Untitled') }}
                </p>
                <p class="text-xs text-gray-500 mt-0.5">
                  {{ formatConversationDate(conv.updated_at) }}
                </p>
              </div>
              <ElButton
                text
                size="small"
                class="opacity-0 group-hover:opacity-100 transition-opacity"
                @click.stop="deleteConversationFromHistory(conv.id)"
              >
                <ElIcon class="text-gray-400 hover:text-red-500"><Delete /></ElIcon>
              </ElButton>
            </div>
          </div>
        </div>
      </div>
    </ElDrawer>

    <!-- Messages with Element Plus Scrollbar -->
    <ElScrollbar
      ref="scrollbarRef"
      class="flex-1 messages-scrollbar"
    >
      <div class="messages-wrapper p-4 space-y-6">
        <!-- Welcome Message - Fullpage Mode -->
        <div
          v-if="showWelcome && isFullpageMode"
          class="flex flex-col items-center justify-center h-full"
        >
          <img
            :src="robotImageUrl"
            alt="MindMate"
            class="w-36 h-28 object-contain"
          />
          <div class="text-center mt-6">
            <div class="text-2xl font-medium text-gray-800 mb-2">
              {{ isZh ? '你好' : 'Hello' }}
            </div>
            <div class="text-lg text-gray-600">
              {{
                isZh
                  ? '我是你的虚拟教研伙伴MindMate'
                  : "I'm MindMate, your virtual teaching partner"
              }}
            </div>
          </div>
        </div>

        <!-- Welcome Message - Panel Mode -->
        <div
          v-else-if="showWelcome"
          class="welcome-card bg-gradient-to-br from-primary-50 to-purple-50 dark:from-gray-700 dark:to-gray-600 rounded-xl p-6 text-center"
        >
          <div class="welcome-icon text-5xl mb-3">✨</div>
          <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
            {{ isZh ? 'MindMate AI 已就绪' : 'MindMate AI is Ready' }}
          </h3>
          <p class="text-sm text-gray-600 dark:text-gray-300">
            {{ isZh ? '有什么可以帮助您的吗？' : 'How can I help you today?' }}
          </p>
        </div>

        <!-- Messages -->
        <div
          v-for="message in mindMate.messages.value"
          :key="message.id"
          class="message-wrapper group"
          :class="message.role === 'user' ? 'user-message' : 'assistant-message'"
          @mouseenter="hoveredMessageId = message.id"
          @mouseleave="hoveredMessageId = null"
        >
          <div
            class="message flex gap-3"
            :class="message.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <!-- Avatar -->
            <template v-if="message.role === 'user'">
              <div
                class="avatar flex-shrink-0 w-8 h-8 rounded-lg bg-primary-500 flex items-center justify-center text-white text-sm"
              >
                <span class="text-base">{{ userAvatar }}</span>
              </div>
            </template>
            <template v-else>
              <!-- Robot avatar for fullpage, gradient icon for panel -->
              <img
                v-if="isFullpageMode"
                :src="robotImageUrl"
                alt="AI"
                class="w-8 h-8 rounded-full object-cover flex-shrink-0"
              />
              <div
                v-else
                class="avatar flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-primary-400 to-purple-500 flex items-center justify-center text-white"
              >
                <ElIcon><ChatDotRound /></ElIcon>
              </div>
            </template>

            <!-- Content -->
            <div
              class="message-content-wrapper flex-1"
              :class="
                message.role === 'user' ? 'flex flex-col items-end' : 'flex flex-col items-start'
              "
            >
              <!-- User message editing -->
              <template v-if="message.role === 'user' && editingMessageId === message.id">
                <div class="edit-input-wrapper w-full max-w-[85%]">
                  <ElInput
                    v-model="editingContent"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 6 }"
                    @keydown.enter.exact.prevent="saveEdit"
                    @keydown.esc.prevent="cancelEdit"
                  />
                  <div class="flex gap-2 mt-2 justify-end">
                    <ElButton
                      size="small"
                      @click="cancelEdit"
                    >
                      {{ isZh ? '取消' : 'Cancel' }}
                    </ElButton>
                    <ElButton
                      type="primary"
                      size="small"
                      @click="saveEdit"
                    >
                      {{ isZh ? '保存' : 'Save' }}
                    </ElButton>
                  </div>
                </div>
              </template>

              <!-- Message content -->
              <template v-else>
                <div
                  class="message-content rounded-lg px-4 py-3 max-w-[85%] relative"
                  :class="[
                    message.role === 'user'
                      ? 'bg-primary-500 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-white',
                    message.isStreaming ? 'streaming' : '',
                  ]"
                >
                  <!-- User message - plain text with files -->
                  <template v-if="message.role === 'user'">
                    <!-- Attached files -->
                    <div
                      v-if="message.files && message.files.length > 0"
                      class="message-files flex flex-wrap gap-2 mb-2"
                    >
                      <div
                        v-for="file in message.files"
                        :key="file.id"
                        class="file-attachment flex items-center gap-1.5 px-2 py-1 bg-white/20 rounded text-xs"
                      >
                        <img
                          v-if="file.preview_url"
                          :src="file.preview_url"
                          :alt="file.name"
                          class="w-6 h-6 object-cover rounded"
                        />
                        <span v-else>{{ getFileIcon(file.type) }}</span>
                        <span class="max-w-[80px] truncate">{{ file.name }}</span>
                      </div>
                    </div>
                    <p class="whitespace-pre-wrap text-sm leading-relaxed">
                      {{ message.content }}
                    </p>
                  </template>

                  <!-- Assistant message - markdown rendered -->
                  <template v-else>
                    <!-- eslint-disable vue/no-v-html -- Content is sanitized via DOMPurify -->
                    <div
                      class="markdown-content text-sm leading-relaxed"
                      v-html="renderMarkdown(message.content)"
                    />
                    <!-- eslint-enable vue/no-v-html -->
                    <!-- Streaming cursor -->
                    <span
                      v-if="message.isStreaming"
                      class="inline-block w-0.5 h-4 bg-current animate-pulse ml-1"
                    />
                  </template>
                </div>

                <!-- User message actions (on hover) -->
                <div
                  v-if="message.role === 'user'"
                  class="message-actions flex gap-1 mt-1 px-1 justify-end"
                  :style="{
                    opacity: hoveredMessageId === message.id ? 1 : 0,
                  }"
                >
                  <ElTooltip :content="isZh ? '编辑' : 'Edit'">
                    <ElButton
                      text
                      circle
                      size="small"
                      @click="startEdit(message)"
                    >
                      <ElIcon class="text-xs"><Edit /></ElIcon>
                    </ElButton>
                  </ElTooltip>
                  <ElTooltip :content="isZh ? '复制' : 'Copy'">
                    <ElButton
                      text
                      circle
                      size="small"
                      @click="copyMessage(message.content)"
                    >
                      <ElIcon class="text-xs"><CopyDocument /></ElIcon>
                    </ElButton>
                  </ElTooltip>
                </div>

                <!-- AI message action bar -->
                <div
                  v-if="message.role === 'assistant' && !message.isStreaming"
                  class="action-bar mt-3 flex flex-wrap items-center gap-1"
                  :class="{
                    'action-bar-visible': isLastAssistantMessage(message.id),
                    'action-bar-hover': !isLastAssistantMessage(message.id),
                  }"
                >
                  <!-- Copy -->
                  <ElTooltip
                    :content="isZh ? '复制' : 'Copy'"
                    placement="top"
                  >
                    <ElButton
                      text
                      class="action-btn-lg"
                      @click="copyMessage(message.content)"
                    >
                      <ElIcon :size="18"><CopyDocument /></ElIcon>
                    </ElButton>
                  </ElTooltip>

                  <!-- Regenerate -->
                  <ElTooltip
                    v-if="getPreviousUserMessage(message.id)"
                    :content="isZh ? '重新生成' : 'Regenerate'"
                    placement="top"
                  >
                    <ElButton
                      text
                      class="action-btn-lg"
                      :disabled="isLoading"
                      @click="regenerateMessage(message.id)"
                    >
                      <ElIcon :size="18"><RefreshRight /></ElIcon>
                    </ElButton>
                  </ElTooltip>

                  <!-- Like -->
                  <ElTooltip
                    :content="isZh ? '点赞' : 'Like'"
                    placement="top"
                  >
                    <ElButton
                      text
                      class="action-btn-lg"
                      :class="{ 'is-active': message.feedback === 'like' }"
                      @click="handleFeedback(message.id, 'like')"
                    >
                      <ElIcon :size="18"><Top /></ElIcon>
                    </ElButton>
                  </ElTooltip>

                  <!-- Dislike -->
                  <ElTooltip
                    :content="isZh ? '踩' : 'Dislike'"
                    placement="top"
                  >
                    <ElButton
                      text
                      class="action-btn-lg"
                      :class="{ 'is-active-dislike': message.feedback === 'dislike' }"
                      @click="handleFeedback(message.id, 'dislike')"
                    >
                      <ElIcon :size="18"><Bottom /></ElIcon>
                    </ElButton>
                  </ElTooltip>

                  <!-- Share -->
                  <ElTooltip
                    :content="isZh ? '分享' : 'Share'"
                    placement="top"
                  >
                    <ElButton
                      text
                      class="action-btn-lg"
                      @click="openShareModal"
                    >
                      <ElIcon :size="18"><Share /></ElIcon>
                    </ElButton>
                  </ElTooltip>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Loading indicator (before first response) -->
        <div
          v-if="mindMate.isLoading.value && !mindMate.isStreaming.value"
          class="message flex gap-3"
        >
          <!-- Robot avatar for fullpage, gradient icon for panel -->
          <img
            v-if="isFullpageMode"
            :src="robotImageUrl"
            alt="AI"
            class="w-8 h-8 rounded-full object-cover flex-shrink-0"
          />
          <div
            v-else
            class="avatar w-8 h-8 rounded-lg bg-gradient-to-br from-primary-400 to-purple-500 flex items-center justify-center flex-shrink-0"
          >
            <ElIcon class="text-white"><ChatDotRound /></ElIcon>
          </div>
          <div class="message-content bg-gray-100 dark:bg-gray-700 rounded-lg px-4 py-3">
            <div class="flex gap-1.5">
              <span
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 0ms"
              />
              <span
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 150ms"
              />
              <span
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 300ms"
              />
            </div>
          </div>
        </div>
      </div>
    </ElScrollbar>

    <!-- Input Area - Fullpage Mode (Swiss style with Element Plus) -->
    <div
      v-if="isFullpageMode"
      class="input-area-fullpage"
    >
      <!-- Hidden file input -->
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        accept="image/*,audio/*,video/*,.pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.xls,.ppt,.pptx"
        multiple
        @change="handleFileSelect"
      />

      <!-- Pending Files Preview -->
      <div
        v-if="mindMate.pendingFiles.value.length > 0"
        class="pending-files-fullpage"
      >
        <div
          v-for="file in mindMate.pendingFiles.value"
          :key="file.id"
          class="file-chip"
        >
          <img
            v-if="file.preview_url"
            :src="file.preview_url"
            :alt="file.name"
            class="w-5 h-5 object-cover rounded"
          />
          <span v-else>{{ getFileIcon(file.type) }}</span>
          <span class="file-name">{{ file.name }}</span>
          <ElButton
            text
            circle
            size="small"
            class="file-remove-btn"
            @click="mindMate.removeFile(file.id)"
          >
            <ElIcon :size="12"><Close /></ElIcon>
          </ElButton>
        </div>
      </div>

      <!-- Input Container -->
      <div class="input-container-fullpage">
        <!-- Text Input -->
        <div class="input-field-fullpage">
          <ElInput
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="isZh ? '输入你的问题...' : 'Type your question...'"
            :disabled="isLoading"
            class="fullpage-textarea"
            @keydown="handleKeydown"
          />
        </div>

        <!-- Action buttons (right side) -->
        <div class="input-actions-fullpage">
          <!-- Upload Button (Paperclip) -->
          <ElTooltip :content="isZh ? '上传文件' : 'Attach file'">
            <ElButton
              text
              class="attach-btn-fullpage"
              :disabled="isLoading || mindMate.isUploading.value"
              @click="triggerFileUpload"
            >
              <Paperclip
                v-if="!mindMate.isUploading.value"
                :size="20"
              />
              <span
                v-else
                class="loading-dot"
              />
            </ElButton>
          </ElTooltip>

          <!-- Send/Stop Button -->
          <ElButton
            v-if="mindMate.isStreaming.value"
            type="danger"
            class="send-btn-fullpage stop"
            @click="stopGeneration"
          >
            <ElIcon><CircleClose /></ElIcon>
          </ElButton>
          <ElButton
            v-else
            type="primary"
            class="send-btn-fullpage"
            :disabled="(!inputText.trim() && mindMate.pendingFiles.value.length === 0) || isLoading"
            @click="sendMessage"
          >
            <Send :size="18" />
          </ElButton>
        </div>
      </div>

      <!-- Footer hint -->
      <div class="input-footer-fullpage">
        <span class="hint-text">
          {{ isZh ? 'Enter 发送' : 'Enter to send' }}
        </span>
        <span class="divider">·</span>
        <span class="disclaimer">
          {{ isZh ? '内容由AI生成，请仔细甄别' : 'AI-generated content' }}
        </span>
      </div>
    </div>

    <!-- Input Area - Panel Mode (Swiss Design) -->
    <div
      v-else
      class="input-area-swiss"
    >
      <!-- Pending Files Preview -->
      <div
        v-if="mindMate.pendingFiles.value.length > 0"
        class="pending-files-swiss"
      >
        <div
          v-for="file in mindMate.pendingFiles.value"
          :key="file.id"
          class="pending-file-chip"
        >
          <img
            v-if="file.preview_url"
            :src="file.preview_url"
            :alt="file.name"
            class="w-6 h-6 object-cover"
          />
          <span
            v-else
            class="file-icon"
            >{{ getFileIcon(file.type) }}</span
          >
          <span class="file-name">{{ file.name }}</span>
          <span class="file-size">{{ formatFileSize(file.size) }}</span>
          <button
            class="file-remove"
            @click="mindMate.removeFile(file.id)"
          >
            <ElIcon><Close /></ElIcon>
          </button>
        </div>
      </div>

      <!-- Hidden file input -->
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        accept="image/*,audio/*,video/*,.pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.xls,.ppt,.pptx"
        multiple
        @change="handleFileSelect"
      />

      <!-- Input Container -->
      <div class="input-container-swiss">
        <!-- Attach Button -->
        <button
          class="attach-btn"
          :disabled="isLoading || mindMate.isUploading.value"
          :class="{ 'is-loading': mindMate.isUploading.value }"
          @click="triggerFileUpload"
        >
          <ElIcon v-if="!mindMate.isUploading.value"><UploadFilled /></ElIcon>
          <span
            v-else
            class="loading-spinner"
          />
        </button>

        <!-- Text Input -->
        <div class="input-wrapper">
          <ElInput
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 6 }"
            :placeholder="
              isZh
                ? '提问、分析图表、或请求修改...'
                : 'Ask questions, analyze diagrams, or request changes...'
            "
            :disabled="isLoading"
            class="swiss-textarea"
            @keydown="handleKeydown"
          />
          <span class="input-hint">
            {{
              isZh ? 'Enter 发送 · Shift+Enter 换行' : 'Enter to send · Shift+Enter for new line'
            }}
          </span>
        </div>

        <!-- Send/Stop Button -->
        <button
          v-if="mindMate.isStreaming.value"
          class="send-btn stop-btn"
          @click="stopGeneration"
        >
          <ElIcon><CircleClose /></ElIcon>
        </button>
        <button
          v-else
          class="send-btn"
          :disabled="(!inputText.trim() && mindMate.pendingFiles.value.length === 0) || isLoading"
          @click="sendMessage"
        >
          <ElIcon><Promotion /></ElIcon>
        </button>
      </div>
    </div>

    <!-- Share Export Modal -->
    <ShareExportModal
      v-model:visible="showShareModal"
      :messages="mindMate.messages.value"
      :conversation-title="mindMate.conversationTitle.value"
    />
  </div>
</template>

<style scoped>
.mindmate-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-scrollbar {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

/* Ensure Element Plus scrollbar wrapper fills the container */
.messages-scrollbar :deep(.el-scrollbar__wrap) {
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.messages-scrollbar :deep(.el-scrollbar__view) {
  min-height: 100%;
}

/* Typing cursor animation for title */
.typing-cursor::after {
  content: '|';
  animation: blink 0.7s infinite;
  margin-left: 1px;
  font-weight: normal;
}

@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }
  51%,
  100% {
    opacity: 0;
  }
}

/* History drawer styling */
.history-drawer :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.history-drawer :deep(.el-drawer__body) {
  padding: 12px;
}

.conversation-list {
  height: 100%;
  overflow-y: auto;
}

.message-wrapper {
  transition: opacity 0.2s;
}

.message-actions {
  transition: opacity 0.2s;
}

/* Action bar for AI messages */
.action-bar {
  padding: 4px 0;
  transition: opacity 0.2s ease;
}

/* Always visible for the latest message */
.action-bar.action-bar-visible {
  opacity: 1;
}

/* Hidden by default, show on hover for older messages */
.action-bar.action-bar-hover {
  opacity: 0;
}

.message-wrapper:hover .action-bar.action-bar-hover {
  opacity: 1;
}

/* Large action buttons */
.action-btn-lg {
  padding: 8px;
  border-radius: 8px;
  color: #6b7280;
  transition:
    color 0.15s,
    background-color 0.15s;
}

.dark .action-btn-lg {
  color: #9ca3af;
}

.action-btn-lg:hover {
  color: #374151;
  background-color: #f3f4f6;
}

.dark .action-btn-lg:hover {
  color: #e5e7eb;
  background-color: #4b5563;
}

.action-btn-lg.is-active {
  color: #3b82f6;
}

.action-btn-lg.is-active:hover {
  color: #2563eb;
  background-color: #dbeafe;
}

.action-btn-lg.is-active-dislike {
  color: #ef4444;
}

.action-btn-lg.is-active-dislike:hover {
  color: #dc2626;
  background-color: #fee2e2;
}

.action-btn-lg:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Legacy small action buttons (for backward compatibility) */
.action-bar .action-btn {
  color: #6b7280;
  transition:
    color 0.15s,
    background-color 0.15s;
}

.dark .action-bar .action-btn {
  color: #9ca3af;
}

.action-bar .action-btn:hover {
  color: #374151;
  background-color: #f3f4f6;
}

.dark .action-bar .action-btn:hover {
  color: #e5e7eb;
  background-color: #4b5563;
}

.action-bar .action-btn.is-active {
  color: #3b82f6;
}

.action-bar .action-btn.is-active:hover {
  color: #2563eb;
  background-color: #dbeafe;
}

.action-bar .action-btn.is-active-dislike {
  color: #ef4444;
}

.action-bar .action-btn.is-active-dislike:hover {
  color: #dc2626;
  background-color: #fee2e2;
}

.message-content.streaming {
  animation: streaming-pulse 1.5s ease-in-out infinite;
}

@keyframes streaming-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

/* Markdown styling */
:deep(.markdown-content) {
  word-wrap: break-word;
  overflow-wrap: break-word;
}

:deep(.markdown-content p) {
  margin: 0 0 8px 0;
}

:deep(.markdown-content p:last-child) {
  margin-bottom: 0;
}

:deep(.markdown-content code) {
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.dark :deep(.markdown-content code) {
  background: rgba(255, 255, 255, 0.15);
}

:deep(.markdown-content pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  position: relative;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
  line-height: 1.5;
}

.dark :deep(.markdown-content pre) {
  background: #2d2d2d;
}

:deep(.markdown-content pre code) {
  background: none;
  padding: 0;
  color: inherit;
}

:deep(.markdown-content ul),
:deep(.markdown-content ol) {
  margin: 8px 0;
  padding-left: 24px;
}

:deep(.markdown-content li) {
  margin: 4px 0;
}

:deep(.markdown-content blockquote) {
  border-left: 3px solid #667eea;
  padding-left: 12px;
  margin: 8px 0;
  color: #666;
  font-style: italic;
}

.dark :deep(.markdown-content blockquote) {
  border-left-color: #818cf8;
  color: #999;
}

:deep(.markdown-content table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 0.9em;
}

:deep(.markdown-content th),
:deep(.markdown-content td) {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: left;
}

.dark :deep(.markdown-content th),
.dark :deep(.markdown-content td) {
  border-color: #555;
}

:deep(.markdown-content th) {
  background-color: #f5f5f5;
  font-weight: 600;
}

.dark :deep(.markdown-content th) {
  background-color: #3a3a3a;
}

:deep(.markdown-content a) {
  color: #667eea;
  text-decoration: underline;
}

.dark :deep(.markdown-content a) {
  color: #818cf8;
}

:deep(.markdown-content a:hover) {
  opacity: 0.8;
}

:deep(.markdown-content img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 8px 0;
}

:deep(.markdown-content h1),
:deep(.markdown-content h2),
:deep(.markdown-content h3),
:deep(.markdown-content h4),
:deep(.markdown-content h5),
:deep(.markdown-content h6) {
  margin: 12px 0 8px 0;
  font-weight: 600;
}

:deep(.markdown-content h1) {
  font-size: 1.5em;
}

:deep(.markdown-content h2) {
  font-size: 1.3em;
}

:deep(.markdown-content h3) {
  font-size: 1.1em;
}

/* Code block copy button enhancement */
:deep(.markdown-content pre) {
  position: relative;
}

/* Scrollbar styling */
:deep(.el-scrollbar__bar) {
  right: 2px;
  bottom: 2px;
}

:deep(.el-scrollbar__thumb) {
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.dark :deep(.el-scrollbar__thumb) {
  background-color: rgba(255, 255, 255, 0.2);
}

:deep(.el-scrollbar__thumb:hover) {
  background-color: rgba(0, 0, 0, 0.3);
}

.dark :deep(.el-scrollbar__thumb:hover) {
  background-color: rgba(255, 255, 255, 0.3);
}

/* ============================================
   Swiss Design Input Area
   Clean geometry, bold typography, precise spacing
   ============================================ */

.input-area-swiss {
  padding: 16px 20px 20px;
  background: #fafafa;
  border-top: 2px solid #000;
}

.dark .input-area-swiss {
  background: #1a1a1a;
  border-top-color: #fff;
}

/* Pending Files - Geometric chips */
.pending-files-swiss {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.pending-file-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid #000;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.dark .pending-file-chip {
  background: #2a2a2a;
  border-color: #fff;
  color: #fff;
}

.pending-file-chip .file-icon {
  font-size: 14px;
}

.pending-file-chip .file-name {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #000;
}

.dark .pending-file-chip .file-name {
  color: #fff;
}

.pending-file-chip .file-size {
  color: #666;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.dark .pending-file-chip .file-size {
  color: #999;
}

.pending-file-chip .file-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  padding: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #666;
  transition: color 0.15s;
}

.pending-file-chip .file-remove:hover {
  color: #e53935;
}

/* Input Container */
.input-container-swiss {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

/* Action Buttons - Bold geometric */
.attach-btn,
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 2px solid #000;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.dark .attach-btn,
.dark .send-btn {
  border-color: #fff;
  background: #2a2a2a;
  color: #fff;
}

.attach-btn:hover:not(:disabled),
.send-btn:hover:not(:disabled) {
  background: #000;
  color: #fff;
}

.dark .attach-btn:hover:not(:disabled),
.dark .send-btn:hover:not(:disabled) {
  background: #fff;
  color: #000;
}

.attach-btn:disabled,
.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.attach-btn.is-loading {
  pointer-events: none;
}

.attach-btn .loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Send Button - Primary action */
.send-btn {
  background: #000;
  color: #fff;
}

.dark .send-btn {
  background: #fff;
  color: #000;
}

.send-btn:hover:not(:disabled) {
  background: #333;
}

.dark .send-btn:hover:not(:disabled) {
  background: #e0e0e0;
  color: #000;
}

.send-btn.stop-btn {
  background: #e53935;
  border-color: #e53935;
  color: #fff;
}

.send-btn.stop-btn:hover {
  background: #c62828;
  border-color: #c62828;
}

/* Input Wrapper */
.input-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Swiss Textarea Styling */
.swiss-textarea {
  width: 100%;
}

.swiss-textarea :deep(.el-textarea__inner) {
  padding: 12px 14px;
  border: 2px solid #000;
  border-radius: 0;
  background: #fff;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5;
  letter-spacing: 0.01em;
  resize: none;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.dark .swiss-textarea :deep(.el-textarea__inner) {
  border-color: #fff;
  background: #2a2a2a;
  color: #fff;
}

.swiss-textarea :deep(.el-textarea__inner):focus {
  border-color: #000;
  box-shadow: 4px 4px 0 rgba(0, 0, 0, 0.1);
  outline: none;
}

.dark .swiss-textarea :deep(.el-textarea__inner):focus {
  border-color: #fff;
  box-shadow: 4px 4px 0 rgba(255, 255, 255, 0.1);
}

.swiss-textarea :deep(.el-textarea__inner)::placeholder {
  color: #999;
  font-weight: 400;
  letter-spacing: 0.01em;
}

.dark .swiss-textarea :deep(.el-textarea__inner)::placeholder {
  color: #666;
}

.swiss-textarea :deep(.el-textarea__inner):disabled {
  background: #f5f5f5;
  color: #999;
  cursor: not-allowed;
}

.dark .swiss-textarea :deep(.el-textarea__inner):disabled {
  background: #1a1a1a;
  color: #555;
}

/* Input Hint */
.input-hint {
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #999;
  padding-left: 2px;
}

.dark .input-hint {
  color: #666;
}

/* ============================================
   Fullpage Mode Input Area - Swiss Design
   ============================================ */

.input-area-fullpage {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.pending-files-fullpage {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.pending-files-fullpage .file-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f3f4f6;
  border-radius: 20px;
  font-size: 13px;
}

.pending-files-fullpage .file-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #374151;
}

.pending-files-fullpage .file-remove-btn {
  margin-left: 2px;
  color: #9ca3af;
}

.pending-files-fullpage .file-remove-btn:hover {
  color: #ef4444;
}

.input-container-fullpage {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 16px;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.input-container-fullpage:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.input-actions-fullpage {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.attach-btn-fullpage {
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 8px;
  color: #6b7280;
  transition: all 0.15s;
}

.attach-btn-fullpage:hover:not(:disabled) {
  color: #374151;
  background: #f3f4f6;
}

.attach-btn-fullpage:disabled {
  opacity: 0.5;
}

.attach-btn-fullpage .loading-dot {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.input-field-fullpage {
  flex: 1;
  min-width: 0;
}

.fullpage-textarea {
  width: 100%;
}

.fullpage-textarea :deep(.el-textarea__inner) {
  padding: 8px 0;
  border: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  box-shadow: none;
}

.fullpage-textarea :deep(.el-textarea__inner):focus {
  box-shadow: none;
}

.fullpage-textarea :deep(.el-textarea__inner)::placeholder {
  color: #9ca3af;
}

.send-btn-fullpage {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 10px;
  font-size: 18px;
}

.send-btn-fullpage:not(.stop):disabled {
  background: #e5e7eb;
  color: #9ca3af;
}

.send-btn-fullpage.stop {
  background: #ef4444;
}

.send-btn-fullpage.stop:hover {
  background: #dc2626;
}

.input-footer-fullpage {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 12px;
  color: #9ca3af;
}

.input-footer-fullpage .divider {
  color: #d1d5db;
}

.input-footer-fullpage .hint-text {
  font-weight: 500;
}

.input-footer-fullpage .disclaimer {
  font-style: italic;
}
</style>
