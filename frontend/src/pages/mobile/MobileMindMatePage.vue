<script setup lang="ts">
/**
 * MobileMindMatePage — ChatGPT-style mobile chat.
 * Single top bar: home/history on left, "MindMate" center, new chat on right.
 * Reuses MindmatePanel internals but with a custom mobile header.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { Home, Menu, Plus } from 'lucide-vue-next'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import ShareExportModal from '@/components/panels/ShareExportModal.vue'
import ConversationHistory from '@/components/panels/mindmate/ConversationHistory.vue'
import MindmateInput from '@/components/panels/mindmate/MindmateInput.vue'
import MindmateMessages from '@/components/panels/mindmate/MindmateMessages.vue'
import { useLanguage, useMindMate, useNotifications } from '@/composables'
import type { FeedbackRating } from '@/composables/mindmate/useMindMate'
import { useConversations, usePinnedConversations } from '@/composables/queries'
import { useAuthStore, useMindMateStore, useVoiceStore } from '@/stores'

const router = useRouter()
const { promptLanguage, t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()
const voiceStore = useVoiceStore()

const displayTitle = ref('MindMate')
const isTypingTitle = ref(false)

const mindMate = useMindMate({
  language: promptLanguage.value,
  onError: (error: string) => {
    notify.error(error)
  },
  onTitleChanged: (title: string, oldTitle?: string) => {
    animateTitleChange(title, oldTitle)
  },
})

const inputText = ref('')
const editingMessageId = ref<string | null>(null)
const editingContent = ref('')
const hoveredMessageId = ref<string | null>(null)
const showHistoryDrawer = ref(false)
const showShareModal = ref(false)

const isLoading = computed(() => mindMate.isLoading.value || mindMate.isStreaming.value)

const userAvatar = computed(() => {
  const avatar = authStore.user?.avatar || '👤'
  return avatar.startsWith('avatar_') ? '👤' : avatar
})

const showWelcome = computed(
  () => !mindMate.hasMessages.value && !mindMate.isLoading.value && !mindMate.isStreaming.value
)

const { data: conversationsData } = useConversations()
const { data: pinnedData } = usePinnedConversations()

const historyLoading = computed(() => mindMate.isLoadingConversations.value)

watch(
  [conversationsData, pinnedData],
  ([convs, pinned]) => {
    if (convs && pinned !== undefined) {
      mindMateStore.syncConversationsFromQuery(convs, pinned)
    }
  },
  { immediate: true }
)

watch(
  () => mindMateStore.conversationTitle,
  (newTitle) => {
    if (!isTypingTitle.value && newTitle !== displayTitle.value) {
      displayTitle.value = newTitle
    }
  }
)

async function animateTitleChange(newTitle: string, oldTitle?: string) {
  if (isTypingTitle.value) return
  isTypingTitle.value = true
  const currentTitle = oldTitle ?? displayTitle.value

  for (let i = currentTitle.length; i >= 0; i--) {
    displayTitle.value = currentTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 20))
  }
  for (let i = 0; i <= newTitle.length; i++) {
    displayTitle.value = newTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 30))
  }
  isTypingTitle.value = false
}

function goHome() {
  router.push('/m')
}

function toggleHistory() {
  showHistoryDrawer.value = !showHistoryDrawer.value
}

function startNewConversation() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  mindMate.startNewConversation()
  displayTitle.value = 'MindMate'
}

async function loadConversationFromHistory(convId: string) {
  await mindMate.loadConversation(convId)
  showHistoryDrawer.value = false
}

async function deleteConversationFromHistory(convId: string) {
  const success = await mindMate.deleteConversation(convId)
  if (success) {
    notify.success(t('notification.conversationDeleted'))
  } else {
    notify.error(t('notification.deleteFailed'))
  }
}

async function sendMessage() {
  if ((!inputText.value.trim() && mindMate.pendingFiles.value.length === 0) || isLoading.value)
    return
  const message = inputText.value.trim()
  inputText.value = ''
  await mindMate.sendMessage(message)
}

function handleSuggestionSelect(suggestion: string) {
  inputText.value = suggestion
  nextTick(() => {
    sendMessage()
  })
}

async function handleFileSelect(files: FileList) {
  if (!files || files.length === 0) return
  for (const file of Array.from(files)) {
    await mindMate.uploadFile(file)
  }
}

function stopGeneration() {
  mindMate.stopGeneration()
}

async function copyMessage(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

function regenerateMessage(messageId: string) {
  mindMate.regenerateMessage(messageId)
}

async function handleFeedback(messageId: string, rating: FeedbackRating) {
  const message = mindMate.messages.value.find((m) => m.id === messageId)
  if (!message) return
  const newRating = message.feedback === rating ? null : rating
  const success = await mindMate.submitFeedback(messageId, newRating)
  if (success) {
    notify.success(
      newRating === 'like'
        ? t('notification.feedbackThanks')
        : newRating === 'dislike'
          ? t('notification.feedbackThanksDislike')
          : t('notification.feedbackCancelled')
    )
  }
}

function startEdit(message: { id: string; content: string }) {
  editingMessageId.value = message.id
  editingContent.value = message.content
}

function cancelEdit() {
  editingMessageId.value = null
  editingContent.value = ''
}

async function saveEdit(content: string) {
  if (!editingMessageId.value || !content.trim()) {
    cancelEdit()
    return
  }
  const messageId = editingMessageId.value
  editingMessageId.value = null
  editingContent.value = ''
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex !== -1) {
    mindMate.messages.value = mindMate.messages.value.slice(0, msgIndex)
  }
  await mindMate.sendMessage(content, false)
}

function hasPreviousUserMessage(messageId: string): boolean {
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex <= 0) return false
  for (let i = msgIndex - 1; i >= 0; i--) {
    if (mindMate.messages.value[i].role === 'user') return true
  }
  return false
}

function isLastAssistantMessage(messageId: string): boolean {
  const assistantMessages = mindMate.messages.value.filter((m) => m.role === 'assistant')
  if (assistantMessages.length === 0) return false
  return assistantMessages[assistantMessages.length - 1].id === messageId
}

onUnmounted(() => {
  voiceStore.reset()
})
</script>

<template>
  <div class="mobile-mindmate flex flex-col h-full overflow-hidden bg-white">
    <!-- Single top bar -->
    <header class="mobile-mm-header flex items-center h-12 px-3 border-b border-gray-200 shrink-0">
      <div class="flex items-center gap-1">
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
          @click="goHome"
        >
          <Home
            :size="18"
            class="text-gray-500"
          />
        </button>
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
          @click="toggleHistory"
        >
          <Menu
            :size="18"
            class="text-gray-600"
          />
        </button>
      </div>

      <h1
        class="flex-1 text-center text-base font-semibold text-gray-800 truncate"
        :class="{ 'typing-cursor': isTypingTitle }"
      >
        {{ displayTitle }}
      </h1>

      <button
        class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
        :disabled="!authStore.isAuthenticated"
        @click="startNewConversation"
      >
        <Plus
          :size="18"
          class="text-gray-600"
        />
      </button>
    </header>

    <!-- Conversation History Drawer -->
    <ConversationHistory
      v-model:visible="showHistoryDrawer"
      :conversations="mindMate.conversations.value"
      :is-loading="historyLoading"
      :current-conversation-id="mindMateStore.currentConversationId"
      @load="loadConversationFromHistory"
      @delete="deleteConversationFromHistory"
    />

    <!-- Welcome mode: single scrollable page (avatar + suggestions + input together) -->
    <div
      v-if="showWelcome"
      class="mobile-welcome-scroll flex-1 min-h-0 overflow-y-auto"
    >
      <!-- Welcome content — avatar + text, centered -->
      <div class="flex flex-col items-center justify-center px-6 pt-16 pb-6">
        <img
          :src="mindmateAvatarMd"
          alt="MindMate"
          class="w-16 h-16 rounded-2xl shadow-md"
        />
        <div class="text-center mt-4">
          <div class="text-lg font-medium text-gray-800">MindMate</div>
          <div class="text-sm text-gray-500 mt-1">
            {{ t('mindmate.welcome', { username: authStore.user?.username || '' }) }}
          </div>
        </div>
      </div>

      <!-- Suggestions + input -->
      <div class="px-4 pb-8">
        <MindmateInput
          v-model:input-text="inputText"
          mode="fullpage"
          :is-loading="isLoading"
          :is-streaming="mindMate.isStreaming.value"
          :is-uploading="mindMate.isUploading.value"
          :pending-files="mindMate.pendingFiles.value"
          :show-suggestions="true"
          :show-file-upload="true"
          @send="sendMessage"
          @stop="stopGeneration"
          @upload="handleFileSelect"
          @remove-file="mindMate.removeFile"
          @suggestion-select="handleSuggestionSelect"
        />
      </div>
    </div>

    <!-- Chat mode: scrolling messages + fixed input at bottom -->
    <template v-else>
      <MindmateMessages
        mode="fullpage"
        :messages="mindMate.messages.value"
        :user-avatar="userAvatar"
        :show-welcome="false"
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
        @share="showShareModal = true"
        @message-hover="hoveredMessageId = $event"
      />

      <div class="mobile-mm-input shrink-0">
        <MindmateInput
          v-model:input-text="inputText"
          mode="fullpage"
          :is-loading="isLoading"
          :is-streaming="mindMate.isStreaming.value"
          :is-uploading="mindMate.isUploading.value"
          :pending-files="mindMate.pendingFiles.value"
          :show-suggestions="false"
          :show-file-upload="true"
          @send="sendMessage"
          @stop="stopGeneration"
          @upload="handleFileSelect"
          @remove-file="mindMate.removeFile"
          @suggestion-select="handleSuggestionSelect"
        />
      </div>
    </template>

    <ShareExportModal
      v-model:visible="showShareModal"
      :messages="mindMate.messages.value"
      :conversation-title="mindMate.conversationTitle.value"
    />
  </div>
</template>

<style scoped>
.mobile-mm-header {
  -webkit-user-select: none;
  user-select: none;
  z-index: 10;
}

.typing-cursor::after {
  content: '|';
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.mobile-welcome-scroll {
  -webkit-overflow-scrolling: touch;
}

.mobile-mm-input {
  padding-bottom: 0;
}

/* Shrink avatars in conversation bubbles */
.mobile-mindmate :deep(.message .el-avatar) {
  width: 28px !important;
  height: 28px !important;
  min-width: 28px !important;
  font-size: 14px !important;
  line-height: 28px !important;
}

.mobile-mindmate :deep(.message .el-avatar img) {
  width: 28px !important;
  height: 28px !important;
}

/* Widen message bubbles to use more screen */
.mobile-mindmate :deep(.message-content) {
  max-width: 88% !important;
}

.mobile-mindmate :deep(.edit-input-wrapper) {
  max-width: 88% !important;
}

/* Tighten gap between avatar and bubble */
.mobile-mindmate :deep(.message) {
  gap: 8px !important;
}

/* History drawer: make delete button visible on mobile (no hover) */
.mobile-mindmate :deep(.conversation-item .el-button) {
  opacity: 0.6 !important;
}

/* Remove bottom padding on input so it touches screen edge */
.mobile-mindmate :deep(.input-area-fullpage) {
  padding-bottom: 8px !important;
  padding-left: 12px !important;
  padding-right: 12px !important;
  max-width: 100% !important;
}

.mobile-mindmate :deep(.suggestions-above-input) {
  padding-left: 12px !important;
  padding-right: 12px !important;
  max-width: 100% !important;
}
</style>

<style>
/* Global styles for ElDrawer (teleported to body, can't use scoped) */
@media (max-width: 640px) {
  .el-drawer.history-drawer {
    width: 80vw !important;
    max-width: 320px !important;
    background: #ffffff !important;
  }

  .el-drawer.history-drawer .el-drawer__header {
    padding: 16px !important;
    margin-bottom: 0 !important;
    border-bottom: 1px solid #e5e7eb !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
  }

  .el-drawer.history-drawer .el-drawer__header span {
    font-size: 16px !important;
    font-weight: 600 !important;
    color: #1f2937 !important;
  }

  .el-drawer.history-drawer .el-drawer__header .el-drawer__close-btn {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    order: 1 !important;
    width: 32px !important;
    height: 32px !important;
    padding: 0 !important;
    border-radius: 8px !important;
    margin: 0 !important;
  }

  .el-drawer.history-drawer .el-drawer__body {
    padding: 8px 12px !important;
    background: #ffffff !important;
  }

  .el-overlay {
    background-color: rgba(0, 0, 0, 0.4) !important;
  }
}
</style>
