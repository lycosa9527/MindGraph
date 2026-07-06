<script setup lang="ts">
/**
 * MindMate collab chatroom — inline seminar mode inside MindMate (/mindmate).
 * Swiss-style layout aligned with MindmateInput; generic chat vs @MindMate AI.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import { useMindmateCollab, type MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import MindmateInput from '@/components/panels/mindmate/MindmateInput.vue'
import MindmateCollabBreadcrumb from '@/components/mindmate/MindmateCollabBreadcrumb.vue'
import { authFetch } from '@/utils/api'
import { confirmMindmateCollabStop } from '@/utils/mindmateCollabConfirm'
import {
  requestMindmateCollabStop,
  teardownMindmateCollabClient,
} from '@/utils/mindmateCollabTeardown'
import {
  formatMindmateCollabCode,
  trackLocalMindmateCollabSession,
} from '@/utils/mindmateCollabSessions'

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
  },
)

const emit = defineEmits<{
  (e: 'ended', reason: 'idle' | 'host' | 'left'): void
  (e: 'room-meta', payload: {
    title: string
    visibility: string
    sessionId: string
    code: string
    ownerId: number
  }): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { displayName: mindmateAgentName, avatarUrl: mindmateAvatarUrl } = useMindMateBranding()

const normalizedCode = computed(() => formatMindmateCollabCode(props.roomCode))

const {
  messages,
  room,
  connected,
  connectionStatus,
  isStreaming,
  idleWarningSeconds,
  isHost,
  canSend,
  canRetryConnection,
  connect,
  disconnect,
  sendChat,
  seedRoom,
  resetForRoomChange,
  retryConnection,
} = useMindmateCollab(() => normalizedCode.value, {
  onSessionEnded: (reason) => {
    emit('ended', reason)
  },
  embedded: props.embedded,
  seedMessages: () => props.seedMessages ?? [],
})

let joinGeneration = 0

const inputText = ref('')
const joining = ref(false)
type CollabRecipientMode = 'mindmate' | 'all'
const recipientMode = ref<CollabRecipientMode>('all')

const inputPlaceholder = computed(() =>
  recipientMode.value === 'mindmate'
    ? t('mindmate.collabInputPlaceholderMindmate')
    : t('mindmate.collabInputPlaceholderAll'),
)

const showConnectionBanner = computed(
  () => connectionStatus.value === 'reconnecting' || connectionStatus.value === 'failed',
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
  const generation = ++joinGeneration
  joining.value = true
  try {
    const response = await authFetch(
      `/api/mindmate/collab/join?code=${encodeURIComponent(code)}`,
      { method: 'POST' },
    )
    if (generation !== joinGeneration) {
      return
    }
    if (!response.ok) {
      notify.error(await parseJoinErrorDetail(response))
      emit('ended', 'left')
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
  } catch {
    notify.error(t('mindgraphLanding.networkErrorJoin'))
    emit('ended', 'left')
  } finally {
    joining.value = false
  }
}

onUnmounted(() => {
  joinGeneration += 1
})

onMounted(() => {
  void joinRoomAndConnect()
})

watch(normalizedCode, (code, prev) => {
  if (code && code !== prev) {
    disconnect()
    resetForRoomChange()
    void joinRoomAndConnect()
  }
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
      emit('room-meta', {
        title: value.title,
        visibility: value.visibility,
        sessionId: value.sessionId,
        code: value.code,
        ownerId: value.ownerId,
      })
    }
  },
  { immediate: true },
)

async function stopRoom() {
  const sessionId = room.value?.sessionId
  if (!sessionId) {
    return
  }
  const confirmed = await confirmMindmateCollabStop(t)
  if (!confirmed) {
    return
  }
  const code = normalizedCode.value
  disconnect()
  teardownMindmateCollabClient(code, { removeFromHistory: true })
  emit('ended', 'host')
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

function handleSend() {
  const trimmed = inputText.value.trim()
  if (!trimmed || !canSend.value || joining.value) {
    return
  }
  const toMindmate = recipientMode.value === 'mindmate'
  sendChat(trimmed, { toMindmate })
  inputText.value = ''
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

defineExpose({ stopRoom, handleRetryConnection })
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
      <ElButton
        v-if="isHost"
        class="mindmate-collab-room__end-btn shrink-0"
        size="small"
        @click="stopRoom"
      >
        {{ t('mindmate.collabEndSeminar') }}
      </ElButton>
    </header>

    <div
      v-if="idleWarningSeconds != null"
      class="bg-amber-50 text-amber-800 text-xs px-4 py-2 text-center shrink-0 border-b border-amber-100"
    >
      {{ t('mindmate.collabIdleWarning', { n: idleWarningSeconds }) }}
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
        {{ t('mindmate.collabRetryConnection') }}
      </button>
    </div>

    <div class="mindmate-collab-room__messages">
      <div class="mindmate-collab-room__messages-scroll">
        <div class="mindmate-collab-room__messages-inner">
        <div
          v-if="joining && !connected"
          class="text-sm text-stone-500 text-center py-12"
        >
          {{ t('mindmate.collabJoining') }}
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="msg.id ?? msg.clientKey ?? `msg-${idx}-${msg.role}`"
          class="mindmate-collab-room__msg-row"
          :class="msg.role === 'user' ? 'mindmate-collab-room__msg-row--user' : 'mindmate-collab-room__msg-row--assistant'"
        >
          <div
            v-if="msg.role === 'assistant'"
            class="w-8 h-8 rounded-full shrink-0 overflow-hidden bg-stone-100 border border-stone-200"
          >
            <img
              :src="mindmateAvatarUrl"
              :alt="mindmateAgentName"
              class="w-full h-full object-cover"
            />
          </div>
          <div class="mindmate-collab-room__msg-body">
            <div
              v-if="msg.role === 'user' && msg.username"
              class="text-[11px] text-stone-500 mb-1 px-1"
            >
              {{ msg.username }}
            </div>
            <div
              v-else-if="msg.role === 'assistant'"
              class="text-[11px] text-stone-500 mb-1 px-1"
            >
              {{ mindmateAgentName }}
            </div>
            <div
              class="mindmate-collab-room__bubble text-sm rounded-2xl px-3.5 py-2.5 whitespace-pre-wrap leading-relaxed"
              :class="
                msg.role === 'user'
                  ? 'bg-stone-800 text-stone-50 text-left'
                  : 'bg-stone-100 text-stone-800 border border-stone-200/80'
              "
            >
              {{ msg.content }}
            </div>
          </div>
        </div>
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
            {{ t('mindmate.collabRecipientAll') }}
          </button>
        </div>
        <MindmateInput
          :input-text="inputText"
          mode="fullpage"
          :is-loading="joining || connectionStatus === 'connecting'"
          :is-streaming="isStreaming || !canSend"
          :show-file-upload="false"
          :placeholder="inputPlaceholder"
          @update:input-text="inputText = $event"
          @send="handleSend"
        />
      </div>
    </div>
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
  max-width: 48rem;
  margin: 0 auto;
  padding: 1rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mindmate-collab-room__msg-row {
  display: flex;
  gap: 0.625rem;
  width: 100%;
  min-width: 0;
}

.mindmate-collab-room__msg-row--user {
  flex-direction: row-reverse;
}

.mindmate-collab-room__msg-body {
  min-width: 0;
  max-width: min(85%, 42rem);
  display: flex;
  flex-direction: column;
}

.mindmate-collab-room__msg-row--user .mindmate-collab-room__msg-body {
  align-items: flex-end;
}

.mindmate-collab-room__msg-row--assistant .mindmate-collab-room__msg-body {
  align-items: flex-start;
}

.mindmate-collab-room__bubble {
  max-width: 100%;
  width: fit-content;
  overflow-wrap: anywhere;
  word-break: break-word;
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
  font-size: 12px;
  font-weight: 500;
  line-height: 1.25;
  padding: 0.35rem 0.75rem;
  border: none;
  border-radius: 9999px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  max-width: min(9.5rem, 42vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
