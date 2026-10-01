<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MindmateCollabEmbed from '@/components/mindmate/MindmateCollabEmbed.vue'
import { useNotifications } from '@/composables'
import { useMindmateCollabNotify } from '@/composables/social/useMindmateCollabNotify'
import { useAuthStore } from '@/stores/auth'
import {
  notifyMindmateCollabLibraryChanged,
  saveFinishedSeminar,
  shouldAutoSaveSeminarOnOwnerEnd,
} from '@/utils/mindmateCollabLibrarySave'
import {
  loadLocalMindmateCollabSessions,
  normalizeMindmateCollabCode,
} from '@/utils/mindmateCollabSessions'
import {
  shouldRemoveCollabFromHistory,
  teardownMindmateCollabClient,
} from '@/utils/mindmateCollabTeardown'

const route = useRoute()
const router = useRouter()
const notify = useNotifications()
const authStore = useAuthStore()

useMindmateCollabNotify()

const roomCode = computed(() => {
  const raw = route.query.code
  return typeof raw === 'string' ? raw : null
})

onMounted(() => {
  if (!roomCode.value) {
    void router.replace('/mindmate')
  }
})

function handleEnded(reason: 'idle' | 'host' | 'left' = 'left') {
  const roomKey = normalizeMindmateCollabCode(roomCode.value || '')
  const localRow = loadLocalMindmateCollabSessions().find(
    (row) => normalizeMindmateCollabCode(row.code) === roomKey
  )
  const sessionId = localRow?.session_id || ''
  const isOwner = localRow?.owner_user_id === Number(authStore.user?.id)
  teardownMindmateCollabClient(roomCode.value, {
    removeFromHistory: shouldRemoveCollabFromHistory(reason),
  })
  if (reason === 'idle' && isOwner) {
    notifyMindmateCollabLibraryChanged()
  }
  if (sessionId && shouldAutoSaveSeminarOnOwnerEnd(reason, isOwner)) {
    void saveFinishedSeminar(sessionId).then((outcome) => {
      if (outcome === 'failed') {
        notify.errorKey('mindmate.collabSaveLibraryFailed')
        void router.push('/mindmate')
        return
      }
      if (outcome === 'saved') {
        notify.successKey('mindmate.collabSaveLibraryDone')
      }
    })
    return
  }
  if (reason === 'host' && !sessionId) {
    return
  }
  void router.push('/mindmate')
}
</script>

<template>
  <MindmateCollabEmbed
    v-if="roomCode"
    class="h-full min-h-0"
    :room-code="roomCode"
    :embedded="false"
    @ended="handleEnded"
  />
</template>
