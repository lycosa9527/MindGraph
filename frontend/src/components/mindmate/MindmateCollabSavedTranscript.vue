<script setup lang="ts">
/**
 * Read-only transcript of a seminar the owner saved to their MindMate library.
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'

import { ElIcon } from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

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
import { type CollabReadCursor, applyCollabReadCursorList } from '@/utils/mindmateCollabRead'

const props = defineProps<{
  sessionId: string
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { displayName: agentName, avatarUrl: agentAvatarUrl } = useMindMateBranding()

const loading = ref(true)
const title = ref('')
const truncated = ref(false)
const messages = ref<MindmateCollabMessage[]>([])
const readCursors = ref<CollabReadCursor[]>([])

function isOwnMessage(message: MindmateCollabMessage): boolean {
  const userId = Number(authStore.user?.id)
  return message.role === 'user' && userId > 0 && message.sender_user_id === userId
}

async function loadTranscript(sessionId: string): Promise<void> {
  loading.value = true
  messages.value = []
  readCursors.value = []
  title.value = ''
  truncated.value = false
  try {
    const response = await authFetch(
      `/api/mindmate/collab/my/library/${encodeURIComponent(sessionId)}`
    )
    if (!response.ok) {
      notify.errorKey('mindmate.collabSavedOpenFailed')
      return
    }
    const data = (await response.json()) as {
      session?: { title?: string }
      messages?: MindmateCollabMessage[]
      read_cursors?: unknown
      truncated?: boolean
    }
    title.value = data.session?.title?.trim() || t('mindmate.collabSavedLibraryTitle')
    messages.value = Array.isArray(data.messages) ? data.messages : []
    readCursors.value = applyCollabReadCursorList([], data.read_cursors)
    truncated.value = Boolean(data.truncated)
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
  <div class="mindmate-saved-seminar flex flex-col flex-1 min-h-0 min-w-0 bg-white">
    <div class="px-5 pt-4 pb-2 shrink-0">
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
    <div class="flex-1 min-h-0 overflow-y-auto px-5 pb-6">
      <div
        v-if="loading"
        class="flex items-center justify-center py-10"
      >
        <ElIcon class="animate-spin text-stone-400">
          <Loading />
        </ElIcon>
      </div>
      <div
        v-else
        class="flex flex-col gap-4"
      >
        <MindmateCollabMessageRow
          v-for="(message, index) in messages"
          :key="collabMessageRowKey(message, index)"
          :message="message"
          :is-own="isOwnMessage(message)"
          :agent-name="agentName"
          :agent-avatar-url="agentAvatarUrl"
          :session-id="sessionId"
          :read-cursors="readCursors"
        />
      </div>
    </div>
  </div>
</template>
