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
import { Users } from '@lucide/vue'

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
const showMembers = ref(false)

watch(
  () => props.roomCode,
  () => {
    sessionId.value = ''
    roomTitle.value = ''
    roomVisibility.value = 'organization'
    showMembers.value = false
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

function toggleMembers(): void {
  showMembers.value = !showMembers.value
}
</script>

<template>
  <div class="mindmate-collab-embed flex flex-row flex-1 min-h-0 min-w-0 w-full overflow-hidden relative">
    <main class="mindmate-collab-embed__main flex flex-col flex-1 min-w-0 min-h-0">
      <div class="mindmate-collab-embed__toolbar shrink-0 flex justify-end px-3 py-2 border-b border-stone-100 md:hidden">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 text-xs font-medium text-stone-600 px-2.5 py-1.5 rounded-lg border border-stone-200 bg-white"
          :aria-expanded="showMembers"
          @click="toggleMembers"
        >
          <Users
            class="w-4 h-4"
            aria-hidden="true"
          />
          {{ t('mindmate.collabMembersTitle') }}
        </button>
      </div>
      <MindmateCollabRoom
        embedded
        :room-code="roomCode"
        :seed-messages="seedMessages"
        @ended="emit('ended', $event)"
        @room-meta="onRoomMeta"
      />
    </main>

    <aside
      class="mindmate-collab-embed__aside shrink-0 w-[17.5rem] max-w-[38vw] min-w-0 border-l border-stone-200 flex flex-col min-h-0 bg-stone-50"
      :class="{ 'mindmate-collab-embed__aside--open': showMembers }"
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
@media (max-width: 768px) {
  .mindmate-collab-embed__aside {
    display: none;
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    width: min(17.5rem, 88vw);
    max-width: 88vw;
    box-shadow: -8px 0 24px rgba(15, 23, 42, 0.12);
  }

  .mindmate-collab-embed__aside--open {
    display: flex;
  }
}

@media (max-width: 720px) {
  .mindmate-collab-embed__aside {
    width: min(13.5rem, 88vw);
  }
}
</style>
