<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Users } from '@lucide/vue'

import MindmateCollabRoom from '@/components/mindmate/MindmateCollabRoom.vue'
import MindmateCollabMembersPanel from '@/components/mindmate/MindmateCollabMembersPanel.vue'
import MindmateDmDrawer from '@/components/mindmate/MindmateDmDrawer.vue'
import { useMindmateCollabNotify } from '@/composables/social/useMindmateCollabNotify'
import { useLanguage } from '@/composables'
import { teardownMindmateCollabClient, shouldRemoveCollabFromHistory } from '@/utils/mindmateCollabTeardown'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()

useMindmateCollabNotify()

const roomCode = computed(() => {
  const raw = route.query.code
  return typeof raw === 'string' ? raw : null
})

const sessionId = ref('')
const roomTitle = ref('')
const roomVisibility = ref('organization')
const showMembers = ref(false)

watch(roomCode, () => {
  sessionId.value = ''
  roomTitle.value = ''
  roomVisibility.value = 'organization'
  showMembers.value = false
})

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

function handleEnded(reason: 'idle' | 'host' | 'left' = 'left') {
  teardownMindmateCollabClient(roomCode.value, {
    removeFromHistory: shouldRemoveCollabFromHistory(reason),
  })
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
  roomVisibility.value = payload.visibility
}

function toggleMembers(): void {
  showMembers.value = !showMembers.value
}
</script>

<template>
  <div
    v-if="roomCode"
    class="mindmate-collab-page flex flex-row h-full min-h-0 min-w-0 w-full overflow-hidden bg-white relative"
  >
    <main class="flex flex-col flex-1 min-w-0 min-h-0">
      <div class="mindmate-collab-page__toolbar shrink-0 flex justify-end px-3 py-2 border-b border-stone-100 md:hidden">
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
        :embedded="false"
        :room-code="roomCode"
        @ended="handleEnded"
        @room-meta="onRoomMeta"
      />
    </main>

    <aside
      class="mindmate-collab-page__aside shrink-0 w-[17.5rem] max-w-[38vw] min-w-0 border-l border-stone-200 flex flex-col min-h-0 bg-stone-50"
      :class="{ 'mindmate-collab-page__aside--open': showMembers }"
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
  .mindmate-collab-page__aside {
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

  .mindmate-collab-page__aside--open {
    display: flex;
  }
}
</style>
