<script setup lang="ts">
/**
 * Read-only transcript of a finished seminar in this person's history.
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateCollabMessageRow from '@/components/mindmate/MindmateCollabMessageRow.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'
import { collabMessageRowKey } from '@/utils/mindmateCollabDisplay'
import {
  MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT,
  type MindmateCollabLibraryChangeDetail,
} from '@/utils/mindmateCollabLibrarySave'
import { sameCollabMessageMinute } from '@/utils/mindmateCollabRead'

const props = defineProps<{
  sessionId: string
}>()

const emit = defineEmits<{
  (e: 'ownership', owned: boolean): void
  (
    e: 'live',
    payload: { code: string; visibility?: string; title?: string; ownerUserId?: number }
  ): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { displayName: agentName, avatarUrl: agentAvatarUrl } = useMindMateBranding()

const loading = ref(true)
const title = ref('')
const truncated = ref(false)
const messages = ref<MindmateCollabMessage[]>([])

function isOwnMessage(message: MindmateCollabMessage): boolean {
  const userId = Number(authStore.user?.id)
  return message.role === 'user' && userId > 0 && message.sender_user_id === userId
}

function showMessageTime(index: number): boolean {
  const createdAt = messages.value[index]?.created_at
  let previousCreatedAt: string | undefined
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const earlier = messages.value[cursor]?.created_at
    if (earlier && !Number.isNaN(Date.parse(earlier))) {
      previousCreatedAt = earlier
      break
    }
  }
  return !sameCollabMessageMinute(createdAt, previousCreatedAt)
}

async function loadTranscript(sessionId: string): Promise<void> {
  loading.value = true
  messages.value = []
  title.value = ''
  truncated.value = false
  emit('ownership', false)
  try {
    const response = await authFetch(
      `/api/mindmate/collab/my/library/${encodeURIComponent(sessionId)}`
    )
    if (!response.ok) {
      notify.errorKey('mindmate.collabSavedOpenFailed')
      return
    }
    const data = (await response.json()) as {
      session?: { title?: string; owned?: boolean; visibility?: string }
      messages?: MindmateCollabMessage[]
      truncated?: boolean
      live?: boolean
      code?: string
      owner_user_id?: number
    }
    title.value = data.session?.title?.trim() || t('mindmate.collabSavedLibraryTitle')
    messages.value = Array.isArray(data.messages) ? data.messages : []
    truncated.value = Boolean(data.truncated)
    emit('ownership', data.session?.owned === true)
    if (data.live && data.code) {
      emit('live', {
        code: data.code,
        visibility: data.session?.visibility,
        title: title.value,
        ownerUserId: data.owner_user_id,
      })
    }
  } catch {
    notify.errorKey('mindmate.collabSavedOpenFailed')
  } finally {
    loading.value = false
  }
}

function onLibraryChanged(event: Event): void {
  const detail = (event as CustomEvent<MindmateCollabLibraryChangeDetail | undefined>).detail
  if (!detail || detail.sessionId !== props.sessionId || !detail.title) {
    return
  }
  title.value = detail.title
}

onMounted(() => {
  void loadTranscript(props.sessionId)
  window.addEventListener(MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT, onLibraryChanged)
})

onUnmounted(() => {
  window.removeEventListener(MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT, onLibraryChanged)
})

watch(
  () => props.sessionId,
  (sessionId) => {
    void loadTranscript(sessionId)
  }
)
</script>

<template>
  <div class="mindmate-saved-seminar">
    <div class="mindmate-saved-seminar__scroll">
      <div class="mindmate-saved-seminar__column">
        <div class="mindmate-saved-seminar__banner">
          <h2 class="text-sm font-semibold text-stone-800 truncate">
            <template v-if="title">{{ title }}</template
            ><I18nText
              v-else
              k="mindmate.collabSavedLibraryTitle"
            />
          </h2>
          <p class="mt-1 text-xs text-stone-500">
            <I18nText k="mindmate.collabSavedReadOnly" />
          </p>
          <p
            v-if="truncated"
            class="mt-1 text-xs text-stone-500"
          >
            <I18nText k="mindmate.collabSavedTruncated" />
          </p>
        </div>
        <div
          v-if="loading"
          class="mindmate-saved-seminar__loading"
          role="status"
        />
        <template v-else>
          <MindmateCollabMessageRow
            v-for="(message, index) in messages"
            :key="collabMessageRowKey(message, index)"
            :message="message"
            :is-own="isOwnMessage(message)"
            :agent-name="agentName"
            :agent-avatar-url="agentAvatarUrl"
            :session-id="sessionId"
            :live="false"
            :show-time="showMessageTime(index)"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mindmate-saved-seminar {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.mindmate-saved-seminar__scroll {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.mindmate-saved-seminar__column {
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

.mindmate-saved-seminar__banner {
  min-width: 0;
}

.mindmate-saved-seminar__loading {
  width: 1.25rem;
  height: 1.25rem;
  margin: 2.5rem auto;
  border: 2px solid #e7e5e4;
  border-top-color: #78716c;
  border-radius: 9999px;
  animation: mindmate-saved-seminar-spin 0.8s linear infinite;
}

@keyframes mindmate-saved-seminar-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
