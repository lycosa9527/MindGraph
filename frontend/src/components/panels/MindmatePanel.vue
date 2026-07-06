<script setup lang="ts">
/**
 * MindMate Panel - AI assistant chat interface (ChatGPT-style)
 * Uses useMindMate composable for SSE streaming
 * Features: Markdown rendering, code highlighting, message actions, stop generation
 */
import { computed, defineAsyncComponent, nextTick, onActivated, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { ElButton, ElIcon } from 'element-plus'

import { Plus } from '@element-plus/icons-vue'

import { PanelLeftOpen } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { useMindMate } from '@/composables/mindmate/useMindMate'
import type { FeedbackRating } from '@/composables/mindmate/useMindMate'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import { useConversations, usePinnedConversations } from '@/composables/queries'
import { useAuthStore, useMindMateStore } from '@/stores'
import { useUIStore } from '@/stores/ui'
import { resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'
import { copyMindmateAssistantMessage } from '@/utils/copyMindmateMessage'
import { authFetch } from '@/utils/api'
import { confirmMindmateCollabStop } from '@/utils/mindmateCollabConfirm'
import {
  loadLocalMindmateCollabSessions,
  normalizeMindmateCollabCode,
} from '@/utils/mindmateCollabSessions'
import {
  requestMindmateCollabStop,
  resolveMindmateCollabSessionId,
  shouldRemoveCollabFromHistory,
  teardownMindmateCollabClient,
} from '@/utils/mindmateCollabTeardown'

import ShareExportModal from './ShareExportModal.vue'
import MindmateHeader from './mindmate/MindmateHeader.vue'
import MindmateInput from './mindmate/MindmateInput.vue'
import MindmateMessages from './mindmate/MindmateMessages.vue'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import {
  embeddedCollabRoomCode,
  setEmbeddedCollabRoomCode,
} from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import type { MindMateMessage } from '@/stores/mindmateActiveThread'
import { displayMindmateUserQueryForUi } from '@/utils/mindmateExtensionPageContext'

const MindmateCollabPanel = defineAsyncComponent(
  () => import('@/components/mindmate/MindmateCollabPanel.vue'),
)
const MindmateCollabEmbed = defineAsyncComponent(
  () => import('@/components/mindmate/MindmateCollabEmbed.vue'),
)
const MindmateCollabBreadcrumb = defineAsyncComponent(
  () => import('@/components/mindmate/MindmateCollabBreadcrumb.vue'),
)

interface MindmateCollabPanelHandle {
  prefillAndAutoJoin: (rawCode: string) => void
}

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

const { promptLanguage, t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()
const uiStore = useUIStore()
const featureFlagsStore = useFeatureFlagsStore()
const { loadPhase: mindMateLoadPhase } = storeToRefs(mindMateStore)

const showMindmateCollab = computed(() => featureFlagsStore.getFeatureMindmateCollab())

const { displayName: defaultMindMateTitle } = useMindMateBranding()

// Typing effect state
const displayTitle = ref(defaultMindMateTitle.value)
const isTypingTitle = ref(false)

// Use MindMate composable for SSE streaming
const mindMate = useMindMate({
  language: promptLanguage.value,
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
const showShareModal = ref(false)
const collabPanelRef = ref<MindmateCollabPanelHandle | null>(null)
const collabRoomCode = ref<string | null>(null)
const collabRoomTitle = ref<string | null>(null)
const collabVisibility = ref<'organization' | 'network'>('organization')
const collabSessionId = ref('')
const collabOwnerId = ref<number | null>(null)
const collabSeedMessages = ref<MindmateCollabMessage[]>([])

function mapThreadToCollabSeed(msgs: MindMateMessage[]): MindmateCollabMessage[] {
  return msgs
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && m.content.trim())
    .map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.role === 'user' ? displayMindmateUserQueryForUi(m.content) : m.content,
      sender_user_id: m.role === 'user' ? Number(authStore.user?.id) || null : null,
      username: m.role === 'user' ? authStore.user?.username ?? null : null,
    }))
}

function prefillCollabJoin(rawCode: string): void {
  collabPanelRef.value?.prefillAndAutoJoin(rawCode)
}

defineExpose({ prefillCollabJoin })

// Computed for loading state
const isLoading = computed(
  () => mindMateStore.isGenerating || mindMate.isLoading.value || mindMate.isStreaming.value
)

// User avatar from auth store
const userAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))

// Check if welcome message should be shown
const showWelcome = computed(() => {
  return !mindMate.hasMessages.value && !mindMate.isLoading.value && !mindMate.isStreaming.value
})

const inConversation = computed(
  () =>
    Boolean(mindMateStore.currentConversationId) ||
    mindMate.hasMessages.value ||
    mindMate.isLoading.value ||
    mindMate.isStreaming.value,
)

const isCollabChatroomMode = computed(() => Boolean(collabRoomCode.value))

const collabSessionTitle = computed(
  () =>
    collabRoomTitle.value ||
    mindMateStore.conversationTitle ||
    t('mindmate.collabPill'),
)

const canStopCollabSession = computed(() => {
  const userId = Number(authStore.user?.id)
  if (!userId || collabOwnerId.value == null) {
    return false
  }
  return collabOwnerId.value === userId
})

function handleCollabSessionStarted(payload: {
  code: string
  visibility?: 'organization' | 'network'
  ownerUserId?: number
}) {
  collabSeedMessages.value = mapThreadToCollabSeed(mindMate.messages.value)
  collabRoomCode.value = payload.code
  if (payload.visibility === 'network' || payload.visibility === 'organization') {
    collabVisibility.value = payload.visibility
  }
  if (payload.ownerUserId != null && payload.ownerUserId > 0) {
    collabOwnerId.value = payload.ownerUserId
  } else {
    collabOwnerId.value = null
  }
  collabRoomTitle.value = mindMateStore.conversationTitle || null
  setEmbeddedCollabRoomCode(payload.code)
}

function exitCollabChatroomMode(options: { removeFromHistory?: boolean } = {}) {
  const code = collabRoomCode.value
  collabRoomCode.value = null
  collabRoomTitle.value = null
  collabVisibility.value = 'organization'
  collabSessionId.value = ''
  collabOwnerId.value = null
  collabSeedMessages.value = []
  teardownMindmateCollabClient(code, options)
}

function handleCollabEnded(reason: 'idle' | 'host' | 'left' = 'left') {
  exitCollabChatroomMode({ removeFromHistory: shouldRemoveCollabFromHistory(reason) })
}

function handleCollabRoomMeta(payload: {
  title: string
  visibility: string
  sessionId?: string
  ownerId?: number
}) {
  collabRoomTitle.value = payload.title
  if (payload.visibility === 'network' || payload.visibility === 'organization') {
    collabVisibility.value = payload.visibility
  }
  if (payload.sessionId) {
    collabSessionId.value = payload.sessionId
  }
  if (payload.ownerId != null) {
    collabOwnerId.value = payload.ownerId
  }
}

async function endCollabSession(): Promise<void> {
  if (!isCollabChatroomMode.value) {
    return
  }
  const confirmed = await confirmMindmateCollabStop(t)
  if (!confirmed) {
    return
  }
  const sessionId = resolveMindmateCollabSessionId(
    collabSessionId.value,
    collabRoomCode.value,
  )
  exitCollabChatroomMode({ removeFromHistory: true })
  if (!sessionId) {
    notify.success(t('mindmate.collabStopped'))
    return
  }
  void requestMindmateCollabStop(sessionId).then((ok) => {
    if (ok) {
      notify.success(t('mindmate.collabStopped'))
    } else {
      notify.error(t('collab.endFailed'))
    }
  }).catch(() => {
    notify.error(t('collab.endFailed'))
  })
}

function syncHeaderTitleFromBranding() {
  if (isTypingTitle.value) {
    return
  }
  if (showWelcome.value) {
    displayTitle.value = defaultMindMateTitle.value
  }
}

watch(defaultMindMateTitle, () => {
  syncHeaderTitleFromBranding()
})

watch(showWelcome, (welcome) => {
  if (welcome) {
    syncHeaderTitleFromBranding()
  }
})

watch(
  embeddedCollabRoomCode,
  (code) => {
    if (!isFullpageMode.value) {
      return
    }
    if (code && code !== collabRoomCode.value) {
      if (collabSeedMessages.value.length === 0) {
        collabSeedMessages.value = mapThreadToCollabSeed(mindMate.messages.value)
      }
      collabRoomCode.value = code
      const localRow = loadLocalMindmateCollabSessions().find(
        (row) => normalizeMindmateCollabCode(row.code) === normalizeMindmateCollabCode(code),
      )
      if (localRow?.visibility === 'network' || localRow?.visibility === 'organization') {
        collabVisibility.value = localRow.visibility
      }
      if (localRow?.title) {
        collabRoomTitle.value = localRow.title
      }
    }
    if (!code && collabRoomCode.value) {
      exitCollabChatroomMode()
    }
  },
)

// In panel mode (canvas mini-mindmate): fetch conversations from Dify and sync to store
// ChatHistory sidebar is not mounted on canvas, so we must fetch here
const { data: conversationsData, isLoading: isLoadingConversationsQuery } = useConversations()
const { data: pinnedData } = usePinnedConversations()

const historyLoading = computed(() =>
  props.mode === 'panel' ? isLoadingConversationsQuery.value : mindMate.isLoadingConversations.value
)

watch(
  [conversationsData, pinnedData],
  ([convs, pinned]) => {
    if (convs && pinned !== undefined) {
      mindMateStore.syncConversationsFromQuery(convs, pinned)
    }
  },
  { immediate: true }
)

function refreshBrandingFromServer() {
  void authStore.checkAuth(true)
}

/** Branding refresh on mount; thread restore is handled in useMindMate init. */
onMounted(() => {
  refreshBrandingFromServer()
})

onActivated(() => {
  refreshBrandingFromServer()
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

// Start a new conversation
async function startNewConversation() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  if (isCollabChatroomMode.value && canStopCollabSession.value) {
    const confirmed = await confirmMindmateCollabStop(t)
    if (!confirmed) {
      return
    }
    const sessionId = resolveMindmateCollabSessionId(
      collabSessionId.value,
      collabRoomCode.value,
    )
    exitCollabChatroomMode({ removeFromHistory: true })
    if (sessionId) {
      void requestMindmateCollabStop(sessionId)
    }
  } else if (isCollabChatroomMode.value) {
    exitCollabChatroomMode()
  }
  mindMate.startNewConversation()
  displayTitle.value = defaultMindMateTitle.value
}

// Load a conversation from history
async function loadConversationFromHistory(convId: string) {
  await mindMate.loadConversation(convId)
}

// Delete a conversation
async function deleteConversationFromHistory(convId: string) {
  const success = await mindMate.deleteConversation(convId)
  if (success) {
    notify.success(t('notification.conversationDeleted'))
  } else {
    notify.error(t('notification.deleteFailed'))
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

// Copy message to clipboard (diagram answers copy the PNG)
async function copyMessage(content: string) {
  try {
    await copyMindmateAssistantMessage(
      content,
      typeof window !== 'undefined' ? window.location.host : undefined
    )
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
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
      newRating === 'like'
        ? t('notification.feedbackThanks')
        : newRating === 'dislike'
          ? t('notification.feedbackThanksDislike')
          : t('notification.feedbackCancelled')
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
    class="mindmate-panel bg-white dark:bg-gray-800 flex flex-col h-full min-w-0 overflow-hidden"
    :class="{
      'border-l border-gray-200 dark:border-gray-700 shadow-lg': !isFullpageMode,
      'panel-mode': !isFullpageMode,
      'welcome-mode': showWelcome,
    }"
  >
    <!-- Full page: expand when sidebar hidden + left-aligned title + new chat -->
    <div
      v-if="isFullpageMode"
      class="mindmate-fullpage-toolbar flex items-center h-14 px-4 gap-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0"
    >
      <el-button
        v-if="uiStore.sidebarCollapsed"
        text
        circle
        size="small"
        class="mindmate-sidebar-toggle shrink-0"
        :title="t('sidebar.expandSidebar')"
        :aria-label="t('sidebar.expandSidebar')"
        @click="uiStore.toggleSidebar()"
      >
        <PanelLeftOpen class="w-[18px] h-[18px]" />
      </el-button>
      <MindmateCollabBreadcrumb
        v-if="isCollabChatroomMode"
        class="flex-1 min-w-0 text-left"
        tone="toolbar"
        :visibility="collabVisibility"
        :session-title="collabSessionTitle"
        :invite-code="collabRoomCode || ''"
      />
      <h1
        v-else
        class="flex-1 min-w-0 text-sm font-semibold text-gray-800 dark:text-white truncate text-left"
        :class="{ 'typing-cursor': isTypingTitle }"
      >
        {{ displayTitle }}
      </h1>
      <MindmateCollabPanel
        v-if="showMindmateCollab && !isCollabChatroomMode"
        ref="collabPanelRef"
        :in-conversation="inConversation"
        :conversation-title="mindMateStore.conversationTitle || displayTitle"
        :get-seed-messages="() => mapThreadToCollabSeed(mindMate.messages.value)"
        embed-in-panel
        @session-started="handleCollabSessionStarted"
      />
      <div class="mindmate-toolbar-actions flex items-center gap-1.5 shrink-0">
        <el-button
          v-if="isCollabChatroomMode && canStopCollabSession"
          class="end-seminar-btn shrink-0"
          size="small"
          @click="endCollabSession"
        >
          {{ t('mindmate.collabEndSeminar') }}
        </el-button>
        <el-button
          class="new-chat-btn shrink-0"
          size="small"
          :disabled="!authStore.isAuthenticated"
          @click="startNewConversation"
        >
          <ElIcon class="mr-1"><Plus /></ElIcon>
          {{ t('mindmate.newChat') }}
        </el-button>
      </div>
    </div>
    <MindmateHeader
      v-else
      :mode="mode"
      :title="displayTitle"
      :is-typing="isTypingTitle"
      :is-authenticated="authStore.isAuthenticated"
      :conversations="mindMate.conversations.value"
      :is-loading-history="historyLoading"
      :current-conversation-id="mindMateStore.currentConversationId"
      @new-conversation="startNewConversation"
      @close="emit('close')"
      @load-history="loadConversationFromHistory"
      @delete-history="deleteConversationFromHistory"
    />

    <!-- Collab chatroom mode (chat + right member column) -->
    <MindmateCollabEmbed
      v-if="isCollabChatroomMode && collabRoomCode"
      class="flex-1 min-h-0 min-w-0"
      :room-code="collabRoomCode"
      :seed-messages="collabSeedMessages"
      @ended="handleCollabEnded"
      @room-meta="handleCollabRoomMeta"
    />

    <template v-else>
      <!-- Messages -->
      <MindmateMessages
      :mode="mode"
      :messages="mindMate.messages.value"
      :user-avatar="userAvatar"
      :show-welcome="showWelcome"
      :is-loading="mindMate.isLoading.value"
      :is-streaming="mindMate.isStreaming.value"
      :load-phase="mindMateLoadPhase"
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

    <!-- Input Area - wrapper pins to bottom in panel mode -->
    <div class="mindmate-input-section">
      <MindmateInput
        v-model:input-text="inputText"
        :mode="mode"
        :is-loading="isLoading"
        :is-streaming="mindMate.isStreaming.value"
        :is-uploading="mindMate.isUploading.value"
        :pending-files="mindMate.pendingFiles.value"
        :show-suggestions="showWelcome"
        :show-file-upload="isFullpageMode"
        @send="sendMessage"
        @stop="stopGeneration"
        @upload="handleFileSelect"
        @remove-file="mindMate.removeFile"
        @suggestion-select="handleSuggestionSelect"
      />
    </div>

    <!-- Share Export Modal -->
    <ShareExportModal
      v-model:visible="showShareModal"
      :messages="mindMate.messages.value"
      :conversation-title="mindMate.conversationTitle.value"
    />
    </template>
  </div>
</template>

<style scoped>
@import './mindmate/mindmate.css';

.mindmate-sidebar-toggle {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
  font-weight: 500;
}

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

.end-seminar-btn {
  --el-button-bg-color: #fef3c7;
  --el-button-border-color: #fcd34d;
  --el-button-hover-bg-color: #fde68a;
  --el-button-hover-border-color: #fbbf24;
  --el-button-hover-text-color: #78350f;
  --el-button-active-bg-color: #fcd34d;
  --el-button-active-border-color: #f59e0b;
  --el-button-text-color: #92400e;
  font-weight: 500;
  border-radius: 9999px;
}

.dark .end-seminar-btn {
  --el-button-bg-color: #78350f;
  --el-button-border-color: #b45309;
  --el-button-hover-bg-color: #92400e;
  --el-button-hover-border-color: #d97706;
  --el-button-hover-text-color: #fef3c7;
  --el-button-active-bg-color: #b45309;
  --el-button-active-border-color: #f59e0b;
  --el-button-text-color: #fde68a;
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
</style>
