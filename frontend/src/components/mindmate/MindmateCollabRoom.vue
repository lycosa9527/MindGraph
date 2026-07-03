<script setup lang="ts">
/**
 * MindMate collab chatroom — inline seminar mode inside MindMate (/mindmate).
 * Swiss-style layout aligned with MindmateInput; generic chat vs @MindMate AI.
 */
import { computed, onMounted, ref, watch } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { MoreHorizontal, Power } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { useMindmateCollab, type MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import MindmateInput from '@/components/panels/mindmate/MindmateInput.vue'
import { authFetch } from '@/utils/api'
import {
  collabMessageMentionsMindmate,
  insertMindmateMention,
} from '@/utils/mindmateCollabMention'
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
  (e: 'room-meta', payload: { title: string; visibility: string; sessionId: string; code: string }): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { displayName: mindmateAgentName, avatarUrl: mindmateAvatarUrl } = useMindMateBranding()

const normalizedCode = computed(() => formatMindmateCollabCode(props.roomCode))

const {
  messages,
  room,
  connected,
  isStreaming,
  idleWarningSeconds,
  isHost,
  connect,
  disconnect,
  sendChat,
  seedRoom,
} = useMindmateCollab(() => normalizedCode.value, {
  onSessionEnded: (reason) => {
    emit('ended', reason)
  },
  embedded: props.embedded,
  seedMessages: () => props.seedMessages ?? [],
})

const inputText = ref('')
const joining = ref(false)

const visibilityLabel = computed(() => {
  const vis = room.value?.visibility || 'organization'
  return vis === 'network'
    ? t('mindmate.collabSeminarPublic')
    : t('mindmate.collabSeminarOrg')
})

const roomTitle = computed(() => room.value?.title || t('mindmate.collabPill'))

const headerSubtitle = computed(() => {
  if (props.embedded) {
    return roomTitle.value
  }
  return `${normalizedCode.value} · ${room.value?.visibility || ''}`
})

async function joinRoomAndConnect(): Promise<void> {
  const code = normalizedCode.value
  if (!code) {
    return
  }
  joining.value = true
  try {
    const response = await authFetch(
      `/api/mindmate/collab/join?code=${encodeURIComponent(code)}`,
      { method: 'POST' },
    )
    if (!response.ok) {
      notify.error(t('mindmate.collabJoinFailed'))
      emit('ended', 'left')
      return
    }
    const data = (await response.json()) as Record<string, unknown>
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
  } finally {
    joining.value = false
  }
}

onMounted(() => {
  void joinRoomAndConnect()
})

watch(normalizedCode, (code, prev) => {
  if (code && code !== prev) {
    disconnect()
    void joinRoomAndConnect()
  }
})

watch(
  room,
  (value) => {
    if (value) {
      emit('room-meta', {
        title: value.title,
        visibility: value.visibility,
        sessionId: value.sessionId,
        code: value.code,
      })
    }
  },
  { immediate: true },
)

async function stopRoom() {
  if (!room.value?.sessionId) {
    return
  }
  const response = await authFetch('/api/mindmate/collab/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: room.value.sessionId }),
  })
  if (response.ok) {
    notify.success(t('mindmate.collabStopped'))
    disconnect()
    emit('ended', 'host')
  } else {
    notify.error(t('collab.endFailed'))
  }
}

function handleSend() {
  const trimmed = inputText.value.trim()
  if (!trimmed || isStreaming.value || joining.value) {
    return
  }
  const toMindmate = collabMessageMentionsMindmate(trimmed, mindmateAgentName.value)
  sendChat(trimmed, { toMindmate })
  inputText.value = ''
}

function mentionMindmate() {
  inputText.value = insertMindmateMention(inputText.value, mindmateAgentName.value)
}

defineExpose({ stopRoom })
</script>

<template>
  <div
    class="mindmate-collab-room flex flex-col flex-1 min-h-0 min-w-0 bg-white"
    :class="{ 'mindmate-collab-room--embedded': embedded }"
  >
    <header
      class="mindmate-collab-room__header shrink-0 px-4 py-3 border-b border-stone-200 bg-white flex items-start justify-between gap-3"
    >
      <div class="min-w-0">
        <p class="text-[11px] font-medium uppercase tracking-wide text-stone-500">
          {{ visibilityLabel }}
        </p>
        <h2 class="text-sm font-semibold text-stone-900 truncate leading-snug">
          {{ roomTitle }}
        </h2>
        <p
          v-if="!embedded"
          class="text-[11px] text-stone-400 truncate mt-0.5"
        >
          {{ headerSubtitle }}
        </p>
      </div>
      <ElDropdown
        v-if="isHost"
        trigger="click"
        placement="bottom-end"
        popper-class="user-dropdown-popper"
        teleported
        class="shrink-0"
      >
        <button
          type="button"
          class="mindmate-collab-room__more-btn"
          :aria-label="t('mindmate.collabEnd')"
        >
          <MoreHorizontal class="w-4 h-4" />
        </button>
        <template #dropdown>
          <ElDropdownMenu class="user-dropdown-menu">
            <ElDropdownItem
              class="user-dropdown-item--logout"
              @click="stopRoom"
            >
              <Power class="w-4 h-4 mr-2" />
              {{ t('sidebar.actions.turnOffOnlineCollab') }}
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </header>

    <div
      v-if="idleWarningSeconds != null"
      class="bg-amber-50 text-amber-800 text-xs px-4 py-2 text-center shrink-0 border-b border-amber-100"
    >
      {{ t('mindmate.collabIdleWarning', { n: idleWarningSeconds }) }}
    </div>

    <div class="flex-1 overflow-y-auto min-h-0">
      <div class="max-w-3xl mx-auto px-4 py-4 space-y-4">
        <div
          v-if="joining && !connected"
          class="text-sm text-stone-500 text-center py-12"
        >
          {{ t('mindmate.collabJoining') }}
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="flex gap-2.5"
          :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'"
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
          <div
            class="min-w-0 max-w-[min(85%,42rem)]"
            :class="msg.role === 'user' ? 'text-right' : 'text-left'"
          >
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
              class="text-sm rounded-2xl px-3.5 py-2.5 whitespace-pre-wrap leading-relaxed"
              :class="
                msg.role === 'user'
                  ? 'bg-stone-800 text-stone-50 inline-block text-left'
                  : 'bg-stone-100 text-stone-800 border border-stone-200/80'
              "
            >
              {{ msg.content }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mindmate-collab-room__input shrink-0 border-t border-stone-200 bg-white">
      <div class="max-w-3xl mx-auto px-4 pt-2">
        <div class="flex items-center gap-2 pb-1">
          <button
            type="button"
            class="mindmate-collab-room__mention-btn"
            @click="mentionMindmate"
          >
            @{{ mindmateAgentName }}
          </button>
          <span class="text-[11px] text-stone-400">
            {{ t('mindmate.collabInputHint') }}
          </span>
        </div>
      </div>
      <MindmateInput
        :input-text="inputText"
        mode="fullpage"
        :is-loading="joining"
        :is-streaming="isStreaming"
        :show-file-upload="false"
        :placeholder="t('mindmate.collabInputPlaceholder')"
        @update:input-text="inputText = $event"
        @send="handleSend"
      />
    </div>
  </div>
</template>

<style scoped>
.mindmate-collab-room__more-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.mindmate-collab-room__more-btn:hover {
  background: #f5f5f4;
  color: #1c1917;
}

.mindmate-collab-room__mention-btn {
  font-size: 12px;
  font-weight: 500;
  color: #44403c;
  background: #f5f5f4;
  border: 1px solid #e7e5e4;
  border-radius: 9999px;
  padding: 4px 10px;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.mindmate-collab-room__mention-btn:hover {
  background: #e7e5e4;
  border-color: #d6d3d1;
}

.mindmate-collab-room__input :deep(.input-area-fullpage) {
  padding-top: 0;
}
</style>
