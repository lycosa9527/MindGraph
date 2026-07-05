<script setup lang="ts">
/**
 * MindMate collab layout — chat (left) + school members (right column).
 */
import { ref, watch } from 'vue'

import MindmateCollabMembersPanel from '@/components/mindmate/MindmateCollabMembersPanel.vue'
import MindmateDmDrawer from '@/components/mindmate/MindmateDmDrawer.vue'
import MindmateCollabRoom from '@/components/mindmate/MindmateCollabRoom.vue'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { useLanguage } from '@/composables'

const props = defineProps<{
  roomCode: string
  seedMessages?: MindmateCollabMessage[]
}>()

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

const sessionId = ref('')
const roomTitle = ref('')
const roomVisibility = ref('organization')

watch(
  () => props.roomCode,
  () => {
    sessionId.value = ''
    roomTitle.value = ''
    roomVisibility.value = 'organization'
  },
)

const dmPartnerId = ref<number | null>(null)
const showDm = ref(false)

function openDm(partnerId: number) {
  dmPartnerId.value = partnerId
  showDm.value = true
}

function onRoomMeta(payload: {
  title: string
  visibility: string
  sessionId: string
  code: string
  ownerId: number
}) {
  sessionId.value = payload.sessionId
  roomTitle.value = payload.title
  roomVisibility.value = payload.visibility
  emit('room-meta', {
    title: payload.title,
    visibility: payload.visibility,
    sessionId: payload.sessionId,
    code: payload.code,
    ownerId: payload.ownerId,
  })
}
</script>

<template>
  <div class="mindmate-collab-embed flex flex-row flex-1 min-h-0 min-w-0 w-full overflow-hidden">
    <main class="mindmate-collab-embed__main flex flex-col flex-1 min-w-0 min-h-0">
      <MindmateCollabRoom
        embedded
        :room-code="roomCode"
        :seed-messages="seedMessages"
        @ended="emit('ended', $event)"
        @room-meta="onRoomMeta"
      />
    </main>

    <aside
      class="mindmate-collab-embed__aside shrink-0 w-[17.5rem] max-w-[38vw] border-l border-stone-200 flex flex-col min-h-0 bg-stone-50"
      :aria-label="t('mindmate.collabMembersTitle')"
    >
      <MindmateCollabMembersPanel
        v-if="sessionId"
        :session-id="sessionId"
        :room-code="roomCode"
        :room-title="roomTitle"
        :visibility="roomVisibility"
        @message="openDm"
      />
    </aside>

    <MindmateDmDrawer
      v-model:visible="showDm"
      :partner-id="dmPartnerId"
    />
  </div>
</template>

<style scoped>
@media (max-width: 720px) {
  .mindmate-collab-embed__aside {
    width: 13.5rem;
  }
}
</style>
