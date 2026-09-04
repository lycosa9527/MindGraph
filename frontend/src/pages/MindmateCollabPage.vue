<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MindmateCollabEmbed from '@/components/mindmate/MindmateCollabEmbed.vue'
import { useMindmateCollabNotify } from '@/composables/social/useMindmateCollabNotify'
import {
  shouldRemoveCollabFromHistory,
  teardownMindmateCollabClient,
} from '@/utils/mindmateCollabTeardown'

const route = useRoute()
const router = useRouter()

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
  teardownMindmateCollabClient(roomCode.value, {
    removeFromHistory: shouldRemoveCollabFromHistory(reason),
  })
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
