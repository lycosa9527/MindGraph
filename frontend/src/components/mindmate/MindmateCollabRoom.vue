<script setup lang="ts">
/**
 * MindMate collab chatroom — inline seminar mode inside MindMate (/mindmate).
 * Swiss-style layout aligned with MindmateInput; generic chat vs @MindMate AI.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import I18nText from '@/components/common/I18nText.vue'
import MindmateCollabBreadcrumb from '@/components/mindmate/MindmateCollabBreadcrumb.vue'
import MindmateCollabMessageRow from '@/components/mindmate/MindmateCollabMessageRow.vue'
import MindmateSeminarFaces from '@/components/mindmate/MindmateSeminarFaces.vue'
import ShareExportModal from '@/components/panels/ShareExportModal.vue'
import MindmateInput from '@/components/panels/mindmate/MindmateInput.vue'
import { useLanguage, useNotifications } from '@/composables'
import { ensureMarkdownRenderer } from '@/composables/core/lazyMarkdown'
import { rememberJoinedCollabRoom } from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import {
  dropLiveCollabRoom,
  mindmateCollabLiveCovers,
  useLiveMindmateCollab,
} from '@/composables/mindmate/mindmateCollabLiveSession'
import type { MindMateMessage } from '@/composables/mindmate/useMindMate'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { createMindmateCollabOrgBackend } from '@/composables/social/createMindmateCollabOrgBackend'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'
import { confirmMindmateCollabStop } from '@/utils/mindmateCollabConfirm'
import {
  type CollabFeedbackRating,
  collabMessageRowKey,
  collabMessagesForShareExport,
  lastFinishedAssistantIndex,
  nextCollabFeedback,
  previousCollabUserPrompt,
} from '@/utils/mindmateCollabDisplay'
import {
  formatMindmateCollabCode,
  markMindmateCollabCodeEnded,
  trackLocalMindmateCollabSession,
  wasMindmateCollabCodeRecentlyEnded,
} from '@/utils/mindmateCollabSessions'
import {
  requestMindmateCollabStop,
  teardownMindmateCollabClient,
} from '@/utils/mindmateCollabTeardown'
import { type MindmateMentionCandidate, contentMentionsMindmate } from '@/utils/mindmateMention'

const props = withDefaults(
  defineProps<{
    roomCode: string
    /** True when embedded in MindmatePanel (seminar mode). */
    embedded?: boolean
    /** Prior 1:1 MindMate thread messages shown above collab room chat. */
    seedMessages?: MindmateCollabMessage[]
  }>(),
  {
    embedded: true,
    seedMessages: () => [],
  }
)

const emit = defineEmits<{
  (e: 'ended', reason: 'idle' | 'host' | 'left'): void
  (
    e: 'roomMeta',
    payload: {
      title: string
      visibility: string
      sessionId: string
      code: string
      ownerId: number
    }
  ): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { displayName: mindmateAgentName, avatarUrl: mindmateAvatarUrl } = useMindMateBranding()

const normalizedCode = computed(() => formatMindmateCollabCode(props.roomCode))

const {
  messages,
  hasOlder,
  room,
  connected,
  connectionStatus,
  isStreaming,
  idleWarningSeconds,
  isHost,
  canSend,
  canRetryConnection,
  connect,
  sendChat,
  seedRoom,
  loadOlderMessages,
  retryConnection,
  readCursors,
} = useLiveMindmateCollab(normalizedCode.value, {
  onSessionEnded: (reason) => {
    roomEndNotified = true
    emit('ended', reason)
  },
  seedMessages: () => props.seedMessages ?? [],
})

const mentionRoster = createMindmateCollabOrgBackend(
  () => room.value?.code || normalizedCode.value,
  () => room.value?.visibility || 'organization'
)

const mentionCandidates = computed((): MindmateMentionCandidate[] => {
  const agentName = mindmateAgentName.value.trim() || 'MindMate'
  const agent: MindmateMentionCandidate = {
    id: 'agent-mindmate',
    name: agentName,
    avatar: '✨',
    kind: 'agent',
  }
  const people = mentionRoster.members.value.map((member) => ({
    id: `user-${member.id}`,
    name: member.name,
    avatar: member.avatar,
    kind: 'user' as const,
  }))
  return [agent, ...people]
})

let joinGeneration = 0
let roomEndNotified = false
const stoppingRoom = ref(false)

const inputText = ref('')
const joining = ref(false)
const followTranscript = ref(true)
type CollabRecipientMode = 'mindmate' | 'all'
const recipientMode = ref<CollabRecipientMode>('all')
const showShareModal = ref(false)
const feedbackByKey = ref<Record<string, CollabFeedbackRating>>({})

const inputPlaceholder = computed(() =>
  recipientMode.value === 'mindmate'
    ? t('mindmate.collabInputPlaceholderMindmate')
    : t('mindmate.collabInputPlaceholderAll')
)

const showConnectionBanner = computed(
  () => connectionStatus.value === 'reconnecting' || connectionStatus.value === 'failed'
)

const connectionBannerText = computed(() => {
  if (connectionStatus.value === 'reconnecting') {
    return t('mindmate.collabReconnecting')
  }
  return t('mindmate.collabConnectionLost')
})

const roomTitle = computed(() => room.value?.title || t('mindmate.collabPill'))

async function parseJoinErrorDetail(response: Response): Promise<string> {
  try {
    const err = (await response.json()) as { detail?: string }
    return err.detail?.trim() || t('mindmate.collabJoinFailed')
  } catch {
    return t('mindmate.collabJoinFailed')
  }
}

let viewActive = true

const headerSubtitle = computed(() => {
  if (room.value?.visibility === 'network') {
    return ''
  }
  return `${normalizedCode.value} · ${room.value?.visibility || ''}`
})

async function joinRoomAndConnect(): Promise<void> {
  const code = normalizedCode.value
  if (!code) {
    return
  }
  if (wasMindmateCollabCodeRecentlyEnded(code)) {
    dropLiveCollabRoom(code)
    if (viewActive) {
      emit('ended', 'host')
    }
    return
  }
  if (mindmateCollabLiveCovers(code)) {
    rememberJoinedCollabRoom(code)
    return
  }
  const generation = ++joinGeneration
  if (viewActive) {
    joining.value = true
  }
  try {
    const response = await authFetch(`/api/mindmate/collab/join?code=${encodeURIComponent(code)}`, {
      method: 'POST',
    })
    if (generation !== joinGeneration) {
      return
    }
    if (!response.ok) {
      const hostJustEnded = wasMindmateCollabCodeRecentlyEnded(code)
      if (response.status === 404 || hostJustEnded) {
        markMindmateCollabCodeEnded(code)
        dropLiveCollabRoom(code)
        teardownMindmateCollabClient(code, { removeFromHistory: true })
        if (viewActive) {
          emit('ended', 'host')
          if (!hostJustEnded) {
            notify.error(await parseJoinErrorDetail(response))
          }
        }
        return
      }
      dropLiveCollabRoom(code)
      if (viewActive) {
        notify.error(await parseJoinErrorDetail(response))
        emit('ended', 'left')
      }
      return
    }
    const data = (await response.json()) as Record<string, unknown>
    if (generation !== joinGeneration) {
      return
    }
    trackLocalMindmateCollabSession({
      session_id: String(data.session_id || ''),
      code: String(data.code || code),
      title: String(data.title || t('mindmate.collabPill')),
      owner_user_id: Number(data.owner_user_id || 0),
      participant_count: Number(data.participant_count || 0),
      visibility: String(data.visibility || 'organization'),
      expires_at: (data.expires_at as string | null) ?? null,
    })
    seedRoom({
      sessionId: String(data.session_id || ''),
      code: String(data.code || code),
      title: String(data.title || t('mindmate.collabPill')),
      visibility: String(data.visibility || 'organization'),
      ownerId: Number(data.owner_user_id || 0),
    })
    connect()
    rememberJoinedCollabRoom(code)
  } catch {
    dropLiveCollabRoom(code)
    if (viewActive) {
      notify.errorKey('mindgraphLanding.networkErrorJoin')
      emit('ended', 'left')
    }
  } finally {
    if (viewActive) {
      joining.value = false
    }
  }
}

onUnmounted(() => {
  viewActive = false
})

onMounted(() => {
  void ensureMarkdownRenderer()
  followTranscript.value = true
  void joinRoomAndConnect()
  void scrollTranscriptToBottom()
})

watch(
  room,
  (value) => {
    if (value) {
      trackLocalMindmateCollabSession({
        session_id: value.sessionId,
        code: value.code,
        title: value.title,
        owner_user_id: value.ownerId,
        visibility: value.visibility,
      })
      emit('roomMeta', {
        title: value.title,
        visibility: value.visibility,
        sessionId: value.sessionId,
        code: value.code,
        ownerId: value.ownerId,
      })
    }
  },
  { immediate: true }
)

watch(
  () => room.value?.sessionId,
  (sessionId) => {
    if (!sessionId) {
      return
    }
    void mentionRoster.fetchMembers({ limit: 200 })
  }
)

async function stopRoom() {
  const sessionId = room.value?.sessionId
  if (!sessionId || stoppingRoom.value) {
    return
  }
  const confirmed = await confirmMindmateCollabStop(t)
  if (!confirmed) {
    return
  }
  stoppingRoom.value = true
  const code = normalizedCode.value
  try {
    const ok = await requestMindmateCollabStop(sessionId)
    if (!ok) {
      notify.errorKey('collab.endFailed')
      return
    }
    dropLiveCollabRoom(code)
    if (roomEndNotified) {
      return
    }
    emit('ended', 'host')
    notify.successKey('mindmate.collabStopped')
  } catch {
    notify.errorKey('collab.endFailed')
  } finally {
    stoppingRoom.value = false
  }
}

function handleSend() {
  const trimmed = inputText.value.trim()
  if (!trimmed || !canSend.value || joining.value) {
    return
  }
  followTranscript.value = true
  const toMindmate =
    recipientMode.value === 'mindmate' ||
    contentMentionsMindmate(trimmed, [mindmateAgentName.value])
  sendChat(trimmed, { toMindmate })
  inputText.value = ''
}

function handleRegenerate(prompt: string | undefined): void {
  const text = prompt?.trim()
  if (!text || !canSend.value || joining.value) {
    return
  }
  sendChat(text, { toMindmate: true })
}

function handleFeedback(key: string, clicked: 'like' | 'dislike'): void {
  const next = nextCollabFeedback(feedbackByKey.value[key], clicked)
  feedbackByKey.value = { ...feedbackByKey.value, [key]: next }
  const thanksKey =
    next === 'like'
      ? 'notification.feedbackThanks'
      : next === 'dislike'
        ? 'notification.feedbackThanksDislike'
        : 'notification.feedbackCancelled'
  notify.successKey(thanksKey)
}

function handleRetryConnection(): void {
  if (joining.value) {
    return
  }
  if (room.value?.sessionId) {
    retryConnection()
    return
  }
  void joinRoomAndConnect()
}

function isOwnMessage(msg: MindmateCollabMessage): boolean {
  if (msg.role !== 'user') {
    return false
  }
  const selfId = Number(authStore.user?.id)
  const senderId = Number(msg.sender_user_id)
  return selfId > 0 && senderId === selfId
}

const lastAssistantIdx = computed(() => lastFinishedAssistantIndex(messages.value))

const shareExportMessages = computed(
  () => collabMessagesForShareExport(messages.value) as MindMateMessage[]
)

const transcript = computed(() =>
  messages.value.map((msg, idx) => ({
    key: collabMessageRowKey(msg, idx),
    msg,
    isOwn: isOwnMessage(msg),
    isLastAssistant: idx === lastAssistantIdx.value,
    userPrompt:
      msg.role === 'assistant' ? previousCollabUserPrompt(messages.value, idx) : undefined,
  }))
)

const messagesScrollEl = ref<HTMLElement | null>(null)
let programmaticScroll = false

function isMessagesNearBottom(): boolean {
  const el = messagesScrollEl.value
  if (!el) {
    return true
  }
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

function scrollMessagesToBottom(): void {
  const el = messagesScrollEl.value
  if (!el) {
    return
  }
  programmaticScroll = true
  el.scrollTop = el.scrollHeight
}

function releaseProgrammaticScroll(): void {
  requestAnimationFrame(() => {
    programmaticScroll = false
  })
}

async function scrollTranscriptToBottom(): Promise<void> {
  await nextTick()
  scrollMessagesToBottom()
  requestAnimationFrame(() => {
    scrollMessagesToBottom()
    releaseProgrammaticScroll()
  })
}

function onMessagesScroll(): void {
  if (programmaticScroll) {
    return
  }
  followTranscript.value = isMessagesNearBottom()
  const el = messagesScrollEl.value
  if (!el || el.scrollTop >= 80 || el.scrollHeight <= el.clientHeight) {
    return
  }
  if (!hasOlder.value) {
    return
  }
  void loadOlderKeepingPlace()
}

async function loadOlderKeepingPlace(): Promise<void> {
  const el = messagesScrollEl.value
  if (!el) {
    return
  }
  const beforeHeight = el.scrollHeight
  const beforeTop = el.scrollTop
  followTranscript.value = false
  await loadOlderMessages()
  await nextTick()
  const grown = el.scrollHeight - beforeHeight
  if (grown <= 0) {
    return
  }
  programmaticScroll = true
  el.scrollTop = beforeTop + grown
  releaseProgrammaticScroll()
}

watch(messages, () => {
  if (!followTranscript.value) {
    return
  }
  void scrollTranscriptToBottom()
})
</script>

<template>
  <div
    class="mindmate-collab-room flex flex-col flex-1 min-h-0 min-w-0 w-full overflow-hidden bg-white"
    :class="{ 'mindmate-collab-room--embedded': embedded }"
  >
    <header
      v-if="!embedded"
      class="mindmate-collab-room__header shrink-0 px-4 py-3 border-b border-stone-200 bg-white flex items-center justify-between gap-3"
    >
      <div class="min-w-0 flex-1">
        <MindmateCollabBreadcrumb
          :visibility="room?.visibility || 'organization'"
          :session-title="roomTitle"
          :invite-code="normalizedCode"
        />
        <p
          v-if="headerSubtitle"
          class="text-[11px] text-stone-400 truncate mt-0.5"
        >
          {{ headerSubtitle }}
        </p>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <MindmateSeminarFaces />
        <ElButton
          v-if="isHost"
          class="mindmate-collab-room__end-btn shrink-0"
          size="small"
          :disabled="stoppingRoom"
          @click="stopRoom"
        >
          <I18nText
            k="mindmate.collabEndSeminar"
            dense
          />
        </ElButton>
      </div>
    </header>

    <div
      v-if="idleWarningSeconds != null"
      class="bg-amber-50 text-amber-800 text-xs px-4 py-2 text-center shrink-0 border-b border-amber-100"
    >
      <I18nText
        k="mindmate.collabIdleWarning"
        :params="{ n: idleWarningSeconds }"
      />
    </div>

    <div
      v-else-if="showConnectionBanner"
      class="text-xs px-4 py-2 text-center shrink-0 border-b flex items-center justify-center gap-3"
      :class="
        connectionStatus === 'reconnecting'
          ? 'bg-sky-50 text-sky-800 border-sky-100'
          : 'bg-rose-50 text-rose-800 border-rose-100'
      "
    >
      <span>{{ connectionBannerText }}</span>
      <button
        v-if="canRetryConnection"
        type="button"
        class="underline font-medium hover:opacity-80"
        @click="handleRetryConnection"
      >
        <I18nText k="mindmate.collabRetryConnection" />
      </button>
    </div>

    <div class="mindmate-collab-room__messages">
      <div
        ref="messagesScrollEl"
        class="mindmate-collab-room__messages-scroll"
        @scroll="onMessagesScroll"
      >
        <div class="mindmate-collab-room__messages-inner">
          <div
            v-if="joining && !connected"
            class="text-sm text-stone-500 text-center py-12"
          >
            <I18nText k="mindmate.collabJoining" />
          </div>

          <MindmateCollabMessageRow
            v-for="row in transcript"
            :key="row.key"
            :message="row.msg"
            :is-own="row.isOwn"
            :user-prompt="row.userPrompt"
            :agent-name="mindmateAgentName"
            :agent-avatar-url="mindmateAvatarUrl"
            :is-last-assistant="row.isLastAssistant"
            :regenerate-disabled="!canSend || joining || isStreaming"
            :feedback="feedbackByKey[row.key]"
            :session-id="room?.sessionId || ''"
            :read-cursors="readCursors"
            @regenerate="handleRegenerate(row.userPrompt)"
            @share="showShareModal = true"
            @feedback="handleFeedback(row.key, $event)"
          />
        </div>
      </div>
    </div>

    <div class="mindmate-collab-room__input shrink-0 bg-white mt-auto min-w-0 w-full">
      <div class="mindmate-collab-room__input-inner">
        <div
          class="mindmate-collab-room__recipient-tabs"
          role="tablist"
          :aria-label="t('mindmate.collabRecipientTabsLabel')"
        >
          <button
            type="button"
            role="tab"
            class="mindmate-collab-room__recipient-tab"
            :class="{ 'mindmate-collab-room__recipient-tab--active': recipientMode === 'mindmate' }"
            :aria-selected="recipientMode === 'mindmate'"
            :title="mindmateAgentName"
            @click="recipientMode = 'mindmate'"
          >
            {{ mindmateAgentName }}
          </button>
          <button
            type="button"
            role="tab"
            class="mindmate-collab-room__recipient-tab"
            :class="{ 'mindmate-collab-room__recipient-tab--active': recipientMode === 'all' }"
            :aria-selected="recipientMode === 'all'"
            @click="recipientMode = 'all'"
          >
            <I18nText
              k="mindmate.collabRecipientAll"
              dense
            />
          </button>
        </div>
        <MindmateInput
          :input-text="inputText"
          mode="fullpage"
          :is-loading="joining || connectionStatus === 'connecting'"
          :is-streaming="isStreaming || !canSend"
          :show-file-upload="false"
          :placeholder="inputPlaceholder"
          enable-mentions
          :mention-candidates="mentionCandidates"
          @update:input-text="inputText = $event"
          @send="handleSend"
        />
      </div>
    </div>

    <ShareExportModal
      v-model:visible="showShareModal"
      :messages="shareExportMessages"
      :conversation-title="roomTitle"
    />
  </div>
</template>

<style scoped>
.mindmate-collab-room__messages {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.mindmate-collab-room__messages-scroll {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.mindmate-collab-room__messages-inner {
  width: 100%;
  min-width: 0;
  max-width: min(680px, 100%);
  margin: 0 auto;
  padding: 1rem 1.25rem 1.5rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mindmate-collab-room__end-btn {
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
  height: auto;
  min-height: 32px;
  padding-top: 4px;
  padding-bottom: 4px;
  line-height: 1.15;
}

.mindmate-collab-room__input-inner {
  max-width: min(680px, 100%);
  width: 100%;
  min-width: 0;
  margin: 0 auto;
  padding: 0.5rem 20px 1.25rem;
  padding-bottom: max(1.25rem, env(safe-area-inset-bottom, 0px));
  box-sizing: border-box;
}

.mindmate-collab-room:not(.mindmate-collab-room--embedded) .mindmate-collab-room__input-inner {
  padding-bottom: max(1.5rem, env(safe-area-inset-bottom, 0px));
}

.mindmate-collab-room__input :deep(.input-area-fullpage) {
  padding-top: 0;
  padding-left: 0;
  padding-right: 0;
  padding-bottom: 0;
  max-width: none;
  margin: 0;
  width: 100%;
}

.mindmate-collab-room__recipient-tabs {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  max-width: 100%;
  padding: 3px;
  margin-bottom: 0.625rem;
  background: #f5f5f4;
  border: 1px solid #e7e5e4;
  border-radius: 9999px;
}

.mindmate-collab-room__recipient-tab {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.15;
  height: auto;
  min-height: 28px;
  padding: 0.3rem 0.85rem;
  border: none;
  border-radius: 9999px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  max-width: min(18rem, 70vw);
  overflow: hidden;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.mindmate-collab-room__recipient-tab:hover:not(.mindmate-collab-room__recipient-tab--active) {
  color: #44403c;
  background: rgba(255, 255, 255, 0.45);
}

.mindmate-collab-room__recipient-tab--active {
  background: #ffffff;
  color: #1c1917;
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.06);
}

.mindmate-collab-room__recipient-tab:focus-visible {
  outline: 2px solid #a8a29e;
  outline-offset: 1px;
}
</style>
