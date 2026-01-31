<script setup lang="ts">
/**
 * MindMate Panel - AI assistant chat interface (ChatGPT-style)
 * Uses useMindMate composable for SSE streaming
 * Features: Markdown rendering, code highlighting, message actions, stop generation
 */
import { computed, nextTick, ref, watch } from 'vue'

import { useLanguage, useMindMate, useNotifications } from '@/composables'
import type { FeedbackRating } from '@/composables/useMindMate'
import { useAuthStore, useMindMateStore } from '@/stores'

import ShareExportModal from './ShareExportModal.vue'
import ConversationHistory from './mindmate/ConversationHistory.vue'
import MindmateHeader from './mindmate/MindmateHeader.vue'
import MindmateInput from './mindmate/MindmateInput.vue'
import MindmateMessages from './mindmate/MindmateMessages.vue'

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

const { isZh } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()

// Typing effect state
const displayTitle = ref('MindMate')
const isTypingTitle = ref(false)

// Use MindMate composable for SSE streaming
const mindMate = useMindMate({
  language: isZh.value ? 'zh' : 'en',
  onError: (error) => {
    notify.error(error)
  },
  onTitleChanged: (title, oldTitle) => {
    animateTitleChange(title, oldTitle)
  },
})

// Local state
const inputText = ref('')
const editingMessageId = ref<string | null>(null)
const editingContent = ref('')
const hoveredMessageId = ref<string | null>(null)
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

// No need to fetch - Vue Query handles it automatically

// Watch for title changes to sync display (from store)
watch(
  () => mindMateStore.conversationTitle,
  (newTitle) => {
    if (!isTypingTitle.value && newTitle !== displayTitle.value) {
      displayTitle.value = newTitle
    }
  }
)

// Typing animation for title changes
async function animateTitleChange(newTitle: string, oldTitle?: string) {
  if (isTypingTitle.value) return
  isTypingTitle.value = true

  // Use provided oldTitle or current displayTitle
  const currentTitle = oldTitle ?? displayTitle.value

  // Clear old title character by character
  for (let i = currentTitle.length; i >= 0; i--) {
    displayTitle.value = currentTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 20))
  }

  // Type new title character by character
  for (let i = 0; i <= newTitle.length; i++) {
    displayTitle.value = newTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 30))
  }

  isTypingTitle.value = false
}

// Toggle history sidebar
function toggleHistorySidebar() {
  showHistorySidebar.value = !showHistorySidebar.value
  // No need to fetch - Vue Query handles it automatically
}

// Start a new conversation
function startNewConversation() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  mindMate.startNewConversation()
  displayTitle.value = 'MindMate'
}

// Load a conversation from history
async function loadConversationFromHistory(convId: string) {
  await mindMate.loadConversation(convId)
  showHistorySidebar.value = false
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

// Send message using composable
async function sendMessage() {
  if ((!inputText.value.trim() && mindMate.pendingFiles.value.length === 0) || isLoading.value)
    return

  const message = inputText.value.trim()
  inputText.value = ''

  await mindMate.sendMessage(message)
}

// Handle suggestion bubble click
function handleSuggestionSelect(suggestion: string) {
  inputText.value = suggestion
  // Focus the input and optionally send immediately
  nextTick(() => {
    sendMessage()
  })
}

// Handle file selection
async function handleFileSelect(files: FileList) {
  if (!files || files.length === 0) return

  for (const file of Array.from(files)) {
    await mindMate.uploadFile(file)
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
async function saveEdit(content: string) {
  if (!editingMessageId.value || !content.trim()) {
    cancelEdit()
    return
  }

  const messageId = editingMessageId.value
  editingMessageId.value = null
  editingContent.value = ''

  // Remove the edited user message and resend
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex !== -1) {
    mindMate.messages.value = mindMate.messages.value.slice(0, msgIndex)
  }

  await mindMate.sendMessage(content, false)
}

// Get previous user message for regeneration context
function hasPreviousUserMessage(messageId: string): boolean {
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex <= 0) return false

  for (let i = msgIndex - 1; i >= 0; i--) {
    if (mindMate.messages.value[i].role === 'user') {
      return true
    }
  }
  return false
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
    class="mindmate-panel bg-white dark:bg-gray-800 flex flex-col h-full overflow-hidden"
    :class="{
      'border-l border-gray-200 dark:border-gray-700 shadow-lg': !isFullpageMode,
      'welcome-mode': showWelcome,
    }"
  >
    <!-- Header -->
    <MindmateHeader
      :mode="mode"
      :title="displayTitle"
      :is-typing="isTypingTitle"
      :is-authenticated="authStore.isAuthenticated"
      @toggle-history="toggleHistorySidebar"
      @new-conversation="startNewConversation"
      @close="emit('close')"
    />

    <!-- Conversation History Drawer -->
    <ConversationHistory
      v-model:visible="showHistorySidebar"
      :conversations="mindMate.conversations.value"
      :is-loading="mindMate.isLoadingConversations.value"
      :current-conversation-id="mindMateStore.currentConversationId"
      @load="loadConversationFromHistory"
      @delete="deleteConversationFromHistory"
    />

    <!-- Messages -->
    <MindmateMessages
      :mode="mode"
      :messages="mindMate.messages.value"
      :user-avatar="userAvatar"
      :show-welcome="showWelcome"
      :is-loading="mindMate.isLoading.value"
      :is-streaming="mindMate.isStreaming.value"
      :is-loading-history="mindMate.isLoadingHistory.value"
      :editing-message-id="editingMessageId"
      :editing-content="editingContent"
      :hovered-message-id="hoveredMessageId"
      :is-last-assistant-message="isLastAssistantMessage"
      :has-previous-user-message="hasPreviousUserMessage"
      @edit="startEdit"
      @cancel-edit="cancelEdit"
      @save-edit="saveEdit"
      @copy="copyMessage"
      @regenerate="regenerateMessage"
      @feedback="handleFeedback"
      @share="openShareModal"
      @message-hover="hoveredMessageId = $event"
    />

    <!-- Input Area -->
    <MindmateInput
      v-model:input-text="inputText"
      :mode="mode"
      :is-loading="isLoading"
      :is-streaming="mindMate.isStreaming.value"
      :is-uploading="mindMate.isUploading.value"
      :pending-files="mindMate.pendingFiles.value"
      :show-suggestions="showWelcome"
      @send="sendMessage"
      @stop="stopGeneration"
      @upload="handleFileSelect"
      @remove-file="mindMate.removeFile"
      @suggestion-select="handleSuggestionSelect"
    />

    <!-- Share Export Modal -->
    <ShareExportModal
      v-model:visible="showShareModal"
      :messages="mindMate.messages.value"
      :conversation-title="mindMate.conversationTitle.value"
    />
  </div>
</template>

<style scoped>
@import './mindmate/mindmate.css';
</style>
