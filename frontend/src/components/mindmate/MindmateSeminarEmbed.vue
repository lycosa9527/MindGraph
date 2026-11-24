<script setup lang="ts">
/**
 * MindMate collab layout — chat | optional doc viewer | right task pane.
 * Reading mode collapses the task drawer so only chat + document share the row.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import MindmateDmDrawer from '@/components/mindmate/MindmateDmDrawer.vue'
import MindmateSeminarDocViewer from '@/components/mindmate/MindmateSeminarDocViewer.vue'
import MindmateSeminarRoom from '@/components/mindmate/MindmateSeminarRoom.vue'
import MindmateSeminarTaskPane from '@/components/mindmate/MindmateSeminarTaskPane.vue'
import {
  SEMINAR_TASK_RAIL_PX,
  closeSeminarChrome,
  seminarDocFullscreen,
  seminarDocPaneBudget,
  seminarDocPaneWidthPreferred,
  seminarDocPaneWidthPx,
  seminarDocViewerOpen,
  seminarTaskPaneOpen,
  setSeminarDocPaneWidth,
} from '@/composables/mindmate/mindmateSeminarChrome'
import {
  loadSeminarGroupRoster,
  seminarGroupMembers,
} from '@/composables/mindmate/seminarGroupRoster'
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

const sessionId = ref('')
const shellRef = ref<HTMLElement | null>(null)
const shellWidth = ref(0)
const resizing = ref(false)
let shellObserver: ResizeObserver | null = null

const reading = computed(() => seminarDocViewerOpen.value)

const docPaneMaxPx = computed(() =>
  seminarDocPaneBudget(shellWidth.value || 0, {
    drawerOpen: seminarTaskPaneOpen.value,
    reading: reading.value,
  })
)

const docPaneWidthPx = computed(() => Math.min(seminarDocPaneWidthPx.value, docPaneMaxPx.value))

const viewerStyle = computed(() => {
  const width = docPaneWidthPx.value
  return {
    width: `${width}px`,
    maxWidth: `${width}px`,
    flex: `0 1 ${width}px`,
  }
})

watch(
  () => props.roomCode,
  () => {
    sessionId.value = ''
    closeSeminarChrome()
  }
)

const displayMembers = computed(() =>
  seminarGroupMembers.value.length > 0 ? seminarGroupMembers.value : props.members
)

watch(
  () => sessionId.value,
  (id) => {
    if (!id) {
      return
    }
    void loadSeminarGroupRoster(id)
  }
)

function measureShell(): void {
  const width = shellRef.value?.clientWidth ?? 0
  if (width > 0) {
    shellWidth.value = width
  }
}

watch(seminarDocViewerOpen, (open, wasOpen) => {
  measureShell()
  if (open && !wasOpen && !seminarDocPaneWidthPreferred.value) {
    fitDocWidthForReading()
  }
})

watch(seminarTaskPaneOpen, () => {
  measureShell()
})

const dmPartnerId = ref<number | null>(null)
const showDm = ref(false)

function fitDocWidthForReading(): void {
  measureShell()
  const available = Math.max(0, (shellWidth.value || window.innerWidth) - SEMINAR_TASK_RAIL_PX)
  // First open only: reading-first split. Later widths come from user preference.
  const ideal = Math.round(available * 0.58)
  const maxWidth = seminarDocPaneBudget(shellWidth.value || window.innerWidth, {
    drawerOpen: seminarTaskPaneOpen.value,
    reading: true,
  })
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
  measureShell()

  const onMove = (ev: PointerEvent): void => {
    const delta = startX - ev.clientX
    const maxWidth = seminarDocPaneBudget(shellWidth.value || window.innerWidth, {
      drawerOpen: seminarTaskPaneOpen.value,
      reading: reading.value,
    })
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

onMounted(() => {
  measureShell()
  if (typeof ResizeObserver === 'undefined' || !shellRef.value) {
    return
  }
  shellObserver = new ResizeObserver(() => {
    measureShell()
  })
  shellObserver.observe(shellRef.value)
})

onBeforeUnmount(() => {
  resizing.value = false
  shellObserver?.disconnect()
  shellObserver = null
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
        :members="displayMembers"
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
      :members="displayMembers"
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

.mindmate-seminar-embed :deep(.mm-task-pane) {
  z-index: 4;
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
  background: #c4b5fd;
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
  min-width: 0;
  flex-shrink: 1;
}
</style>
