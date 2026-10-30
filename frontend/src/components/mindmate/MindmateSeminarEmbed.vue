<script setup lang="ts">
/**
 * MindMate collab layout — chat | optional doc viewer | right task pane.
 * Reading mode collapses the task drawer so only chat + document share the row.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import MindmateSeminarRoom from '@/components/mindmate/MindmateSeminarRoom.vue'
import MindmateDmDrawer from '@/components/mindmate/MindmateDmDrawer.vue'
import MindmateSeminarDocViewer from '@/components/mindmate/MindmateSeminarDocViewer.vue'
import MindmateSeminarTaskPane from '@/components/mindmate/MindmateSeminarTaskPane.vue'
import {
  closeSeminarChrome,
  seminarDocFullscreen,
  seminarDocPaneWidthPreferred,
  seminarDocPaneWidthPx,
  seminarDocViewerOpen,
  setSeminarDocPaneWidth,
} from '@/composables/mindmate/mindmateSeminarChrome'
import type { MindmateSeminarMessage } from '@/composables/mindmate/useMindmateSeminar'
import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'

const props = withDefaults(
  defineProps<{
    roomCode: string
    seedMessages?: MindmateSeminarMessage[]
    /** False on the standalone /mindmate/seminar route (room shows its own header). */
    embedded?: boolean
    members?: SeminarGroupMember[]
    isLeader?: boolean
    selfUserId?: number
    memberBusy?: boolean
    briefTopic?: string
    briefGoals?: string[]
  }>(),
  {
    seedMessages: () => [],
    embedded: true,
    members: () => [],
    isLeader: false,
    selfUserId: 0,
    memberBusy: false,
    briefTopic: '',
    briefGoals: () => [],
  }
)

const emit = defineEmits<{
  (e: 'ended', reason: 'expired' | 'host' | 'left'): void
  (
    e: 'roomMeta',
    payload: {
      title: string
      visibility: string
      sessionId: string
      code: string
      ownerId: number
    }
  ): void
  (e: 'addMembers'): void
  (e: 'changeRole', userId: number, role: SeminarBriefRole): void
  (e: 'removeMember', userId: number): void
  (e: 'goalsChange', goals: string[]): void
  (e: 'topicChange', topic: string): void
}>()

const RAIL_WIDTH = 56
const CHAT_MIN_READING = 300
const CHAT_MIN_DEFAULT = 280

const sessionId = ref('')
const shellRef = ref<HTMLElement | null>(null)
const resizing = ref(false)

const viewerStyle = computed(() => ({
  width: `${seminarDocPaneWidthPx.value}px`,
  flex: `0 0 ${seminarDocPaneWidthPx.value}px`,
}))

watch(
  () => props.roomCode,
  () => {
    sessionId.value = ''
    closeSeminarChrome()
  }
)

watch(seminarDocViewerOpen, (open, wasOpen) => {
  if (open && !wasOpen && !seminarDocPaneWidthPreferred.value) {
    fitDocWidthForReading()
  }
})

const dmPartnerId = ref<number | null>(null)
const showDm = ref(false)

function fitDocWidthForReading(): void {
  const shellWidth = shellRef.value?.clientWidth ?? window.innerWidth
  const available = Math.max(0, shellWidth - RAIL_WIDTH)
  // First open only: reading-first split. Later widths come from user preference.
  const ideal = Math.round(available * 0.58)
  const maxWidth = Math.max(320, available - CHAT_MIN_READING)
  setSeminarDocPaneWidth(Math.min(maxWidth, Math.max(ideal, 520)), true)
}

function onRoomMeta(payload: {
  title: string
  visibility: string
  sessionId: string
  code: string
  ownerId: number
}) {
  const firstEnter = !sessionId.value && Boolean(payload.sessionId)
  sessionId.value = payload.sessionId
  if (firstEnter) {
    closeSeminarChrome()
  }
  emit('roomMeta', {
    title: payload.title,
    visibility: payload.visibility,
    sessionId: payload.sessionId,
    code: payload.code,
    ownerId: payload.ownerId,
  })
}

function onSplitPointerDown(event: PointerEvent): void {
  if (event.button !== 0) {
    return
  }
  event.preventDefault()
  const handle = event.currentTarget as HTMLElement
  handle.setPointerCapture(event.pointerId)
  resizing.value = true
  const startX = event.clientX
  const startWidth = seminarDocPaneWidthPx.value
  const shellWidth = shellRef.value?.clientWidth ?? window.innerWidth
  const chatMin = seminarDocViewerOpen.value ? CHAT_MIN_READING : CHAT_MIN_DEFAULT

  const onMove = (ev: PointerEvent): void => {
    const delta = startX - ev.clientX
    const maxWidth = Math.max(320, shellWidth - chatMin - RAIL_WIDTH)
    setSeminarDocPaneWidth(Math.min(maxWidth, startWidth + delta))
  }

  const onUp = (ev: PointerEvent): void => {
    resizing.value = false
    handle.releasePointerCapture(ev.pointerId)
    handle.removeEventListener('pointermove', onMove)
    handle.removeEventListener('pointerup', onUp)
    handle.removeEventListener('pointercancel', onUp)
  }

  handle.addEventListener('pointermove', onMove)
  handle.addEventListener('pointerup', onUp)
  handle.addEventListener('pointercancel', onUp)
}

onBeforeUnmount(() => {
  resizing.value = false
})
</script>

<template>
  <div
    ref="shellRef"
    class="mindmate-seminar-embed flex flex-row flex-1 min-h-0 min-w-0 w-full overflow-hidden relative"
    :class="{
      'is-resizing': resizing,
      'is-reading': seminarDocViewerOpen,
      'is-doc-fullscreen': seminarDocFullscreen,
    }"
  >
    <main class="mindmate-seminar-embed__main flex flex-col flex-1 min-w-0 min-h-0">
      <MindmateSeminarRoom
        :key="roomCode"
        :embedded="embedded"
        :room-code="roomCode"
        :seed-messages="seedMessages"
        :brief-topic="briefTopic"
        :brief-goals="briefGoals"
        :members="members"
        @ended="emit('ended', $event)"
        @room-meta="onRoomMeta"
        @goals-change="emit('goalsChange', $event)"
        @topic-change="emit('topicChange', $event)"
      />
    </main>

    <template v-if="sessionId && seminarDocViewerOpen">
      <div
        class="mm-split-handle"
        role="separator"
        aria-orientation="vertical"
        :aria-valuenow="seminarDocPaneWidthPx"
        tabindex="0"
        @pointerdown="onSplitPointerDown"
      >
        <span
          class="mm-split-handle__pill"
          aria-hidden="true"
        />
      </div>
      <aside
        class="mindmate-seminar-embed__doc min-h-0 min-w-0"
        :style="viewerStyle"
      >
        <MindmateSeminarDocViewer :session-id="sessionId" />
      </aside>
    </template>

    <MindmateSeminarTaskPane
      v-if="sessionId"
      :session-id="sessionId"
      :members="members"
      :is-leader="isLeader"
      :self-user-id="selfUserId"
      :busy="memberBusy"
      @add-members="emit('addMembers')"
      @change-role="(userId, role) => emit('changeRole', userId, role)"
      @remove-member="(userId) => emit('removeMember', userId)"
    />

    <MindmateDmDrawer
      v-model:visible="showDm"
      :partner-id="dmPartnerId"
    />
  </div>
</template>

<style scoped>
.mindmate-seminar-embed.is-resizing {
  cursor: col-resize;
  user-select: none;
}

.mindmate-seminar-embed.is-resizing * {
  cursor: col-resize !important;
}

.mindmate-seminar-embed.is-reading .mindmate-seminar-embed__main {
  min-width: 280px;
}

.mindmate-seminar-embed.is-doc-fullscreen .mindmate-seminar-embed__main,
.mindmate-seminar-embed.is-doc-fullscreen .mm-split-handle,
.mindmate-seminar-embed.is-doc-fullscreen :deep(.mm-task-pane) {
  display: none;
}

.mindmate-seminar-embed.is-doc-fullscreen .mindmate-seminar-embed__doc {
  position: absolute;
  inset: 0;
  z-index: 40;
  width: 100% !important;
  flex: 1 1 auto !important;
  max-width: none;
  min-width: 0;
  background: #fff;
}

.mm-split-handle {
  position: relative;
  z-index: 3;
  flex: 0 0 12px;
  width: 12px;
  margin: 0 -6px;
  cursor: col-resize;
  touch-action: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mm-split-handle::before {
  content: '';
  position: absolute;
  inset: 0 5px;
  background: #e8e4df;
}

.mm-split-handle:hover::before,
.mm-split-handle:focus-visible::before,
.mindmate-seminar-embed.is-resizing .mm-split-handle::before {
  background: #a8a29e;
}

.mm-split-handle__pill {
  position: relative;
  z-index: 1;
  width: 5px;
  height: 44px;
  border-radius: 999px;
  background: #d6d3d1;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.85);
}

.mm-split-handle:hover .mm-split-handle__pill,
.mm-split-handle:focus-visible .mm-split-handle__pill,
.mindmate-seminar-embed.is-resizing .mm-split-handle__pill {
  background: #8b5cf6;
}

.mindmate-seminar-embed__doc {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 320px;
}
</style>
