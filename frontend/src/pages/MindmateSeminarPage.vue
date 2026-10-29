<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MindmateSeminarEmbed from '@/components/mindmate/MindmateSeminarEmbed.vue'
import { useNotifications } from '@/composables'
import { useMindmateSeminarNotify } from '@/composables/social/useMindmateSeminarNotify'
import { useAuthStore } from '@/stores/auth'
import {
  notifyMindmateSeminarLibraryChanged,
  saveFinishedSeminar,
  shouldAutoSaveSeminarOnOwnerEnd,
  shouldRefreshSavedSeminarLibrary,
} from '@/utils/mindmateSeminarLibrarySave'
import {
  loadLocalMindmateSeminarSessions,
  normalizeMindmateSeminarCode,
} from '@/utils/mindmateSeminarSessions'
import {
  resolveEndedMindmateSeminarSessionId,
  shouldRemoveCollabFromHistory,
  teardownMindmateSeminarClient,
} from '@/utils/mindmateSeminarTeardown'

const route = useRoute()
const router = useRouter()
const notify = useNotifications()
const authStore = useAuthStore()

useMindmateSeminarNotify()

const roomCode = computed(() => {
  const raw = route.query.code
  return typeof raw === 'string' ? raw : null
})

onMounted(() => {
  if (!roomCode.value) {
    void router.replace('/mindmate')
  }
})

function handleEnded(reason: 'expired' | 'host' | 'left' = 'left') {
  const roomKey = normalizeMindmateSeminarCode(roomCode.value || '')
  const localRow = loadLocalMindmateSeminarSessions().find(
    (row) => normalizeMindmateSeminarCode(row.code) === roomKey
  )
  const sessionId = resolveEndedMindmateSeminarSessionId(localRow?.session_id, roomCode.value) || ''
  const isOwner = localRow?.owner_user_id === Number(authStore.user?.id)
  teardownMindmateSeminarClient(roomCode.value, {
    removeFromHistory: shouldRemoveCollabFromHistory(reason),
  })
  if (shouldRefreshSavedSeminarLibrary(reason)) {
    notifyMindmateSeminarLibraryChanged()
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
  <MindmateSeminarEmbed
    v-if="roomCode"
    class="h-full min-h-0"
    :room-code="roomCode"
    :embedded="false"
    @ended="handleEnded"
  />
</template>
