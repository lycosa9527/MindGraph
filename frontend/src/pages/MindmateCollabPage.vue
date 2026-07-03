<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MindmateCollabRoom from '@/components/mindmate/MindmateCollabRoom.vue'
import MindmateCollabMembersPanel from '@/components/mindmate/MindmateCollabMembersPanel.vue'
import MindmateDmDrawer from '@/components/mindmate/MindmateDmDrawer.vue'
import { useMindmateCollabNotify } from '@/composables/social/useMindmateCollabNotify'

const route = useRoute()
const router = useRouter()

useMindmateCollabNotify()

const roomCode = computed(() => {
  const raw = route.query.code
  return typeof raw === 'string' ? raw : null
})

const sessionId = ref('')
const roomTitle = ref('')

const dmPartnerId = ref<number | null>(null)
const showDm = ref(false)

onMounted(() => {
  if (!roomCode.value) {
    void router.replace('/mindmate')
  }
})

function openDm(partnerId: number) {
  dmPartnerId.value = partnerId
  showDm.value = true
}

function handleEnded() {
  void router.push('/mindmate')
}

function onRoomMeta(payload: {
  title: string
  visibility: string
  sessionId: string
  code: string
}) {
  sessionId.value = payload.sessionId
  roomTitle.value = payload.title
}
</script>

<template>
  <div
    v-if="roomCode"
    class="mindmate-collab-page flex flex-row h-full min-h-0 w-full overflow-hidden bg-white"
  >
    <main class="flex flex-col flex-1 min-w-0 min-h-0">
      <MindmateCollabRoom
        :embedded="false"
        :room-code="roomCode"
        @ended="handleEnded"
        @room-meta="onRoomMeta"
      />
    </main>

    <aside
      class="shrink-0 w-[17.5rem] max-w-[38vw] border-l border-stone-200 flex flex-col min-h-0 bg-stone-50"
    >
      <MindmateCollabMembersPanel
        :session-id="sessionId"
        :room-code="roomCode"
        :room-title="roomTitle"
        @message="openDm"
      />
    </aside>

    <MindmateDmDrawer
      v-model:visible="showDm"
      :partner-id="dmPartnerId"
    />
  </div>
</template>
