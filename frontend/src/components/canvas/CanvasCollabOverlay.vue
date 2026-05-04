<script setup lang="ts">
/**
 * CanvasCollabOverlay — renders the three collab UI surfaces for an active workshop session:
 *   1. CollabUserRail (left avatar strip)
 *   2. OnlineCollabModal (host start/stop sessions)
 *   3. Session-active banner (network: shows share code; org: label only)
 *
 * Exposes ``openCollab(mode)`` so CanvasPage can proxy ZoomControls events.
 */
import { type ComputedRef, computed, ref } from 'vue'

import { OnlineCollabModal } from '@/components/workshop'
import { useLanguage } from '@/composables'
import type { ConnectionStatus, ParticipantInfo } from '@/composables/workshop/useWorkshop'

import CollabUserRail from './CollabUserRail.vue'

const collabModalRef = ref<InstanceType<typeof OnlineCollabModal> | null>(null)

const props = defineProps<{
  workshopCode: string | null
  /** From server: organization = 校内（no share code banner）; network = 对公共享 */
  workshopVisibility: 'organization' | 'network' | null
  participants: ParticipantInfo[]
  diagramId: string | null
  /**
   * Authoritative session diagram ID from the WebSocket layer. Passed straight
   * through to OnlineCollabModal so stop calls always target the right session.
   */
  sessionDiagramId?: string | null
  /** Persisted diagram title from server (joined WS payload). */
  sessionDiagramTitle?: string | null
  /** Resolved username of the diagram owner (host). Shown in the session banner. */
  ownerUsername?: string | null
  /** From useWorkshop: seconds until server closes collab after room-idle grace (during warning). */
  roomIdleRemainingSeconds?: number | ComputedRef<number | null | undefined> | null
  /** From useWorkshop: connection state for reconnecting/failed banner. */
  connectionStatus?: ConnectionStatus
  /** True when the current user is a guest (not the diagram owner). */
  isCollabGuest?: boolean
}>()

const emit = defineEmits<{
  collabSession: [payload: { code: string | null; visibility: 'organization' | 'network' | null }]
  retryConnection: []
}>()

const { t } = useLanguage()

const showCollabModal = ref(false)
const userSelectedMode = ref<'organization' | 'network' | null>(null)

/**
 * Source-of-truth collab mode, computed to prevent drift from
 * props.workshopVisibility. Rules:
 *   1. If a session is active (props.workshopCode + visibility), mirror the
 *      server-reported visibility so the modal and banner never disagree.
 *   2. Otherwise, honour the user's last explicit openCollab(mode) selection.
 *   3. Fall back to 'organization' when neither source is available.
 */
const collabMode = computed<'organization' | 'network'>(() => {
  if (props.workshopCode && props.workshopVisibility) {
    return props.workshopVisibility
  }
  return userSelectedMode.value ?? 'organization'
})

/** Banner: omit meeting code for 校内 (`organization`). */
const showShareCodeRow = computed(() => props.workshopVisibility !== 'organization')

const isReconnecting = computed(() => props.connectionStatus === 'reconnecting')
const isConnectionFailed = computed(() => props.connectionStatus === 'failed')
const isConnected = computed(() => props.connectionStatus === 'connected')

/** Support raw number or Vue computed refs from callers. */
const idleSecondsShown = computed(() => {
  const raw = props.roomIdleRemainingSeconds
  if (raw === null || raw === undefined) {
    return null
  }
  if (typeof raw === 'number') {
    return raw
  }
  const v = raw.value
  if (typeof v !== 'number' || v <= 0) {
    return null
  }
  return v
})

/**
 * Status chip: shows connected / reconnecting / failed pill plus an idle
 * countdown when the server has sent a room_idle warning. Computed once so
 * all state stays in sync with props.
 */
const statusChip = computed<{
  label: string
  tone: 'ok' | 'warn' | 'err'
  countdown: number | null
}>(() => {
  const countdown = idleSecondsShown.value
  if (isConnectionFailed.value) {
    return { label: t('canvasPage.collabConnectionFailed'), tone: 'err', countdown }
  }
  if (isReconnecting.value) {
    return { label: t('canvasPage.collabReconnecting'), tone: 'warn', countdown }
  }
  if (isConnected.value) {
    return {
      label: t('canvasPage.collabConnected'),
      tone: 'ok',
      countdown,
    }
  }
  return { label: '', tone: 'ok', countdown }
})

const diagramTitleDisplay = computed(() => {
  const trimmed = props.sessionDiagramTitle?.trim()
  return trimmed && trimmed.length > 0 ? trimmed : ''
})

const ownerCollaborationBannerText = computed(() => {
  const owner = props.ownerUsername?.trim() ?? ''
  if (!owner) {
    return null
  }
  const dt = diagramTitleDisplay.value
  if (dt) {
    return t('canvasPage.collaborationFooterOwnerDiagram', {
      username: owner,
      diagramTitle: dt,
    })
  }
  return t('canvasPage.collaborationFooterOwner', { username: owner })
})

const networkCollaborationBannerText = computed(() => {
  if (props.ownerUsername?.trim()) {
    return null
  }
  if (!showShareCodeRow.value) {
    return null
  }
  const dt = diagramTitleDisplay.value
  if (dt) {
    return t('canvasPage.collaborationFooterNetworkDiagramTitle', { diagramTitle: dt })
  }
  return t('canvasPage.collaborationFooter')
})

const schoolCollaborationBannerText = computed(() => {
  if (props.ownerUsername?.trim() || showShareCodeRow.value) {
    return null
  }
  const dt = diagramTitleDisplay.value
  if (dt) {
    return t('canvasPage.collaborationFooterSchoolDiagram', { diagramTitle: dt })
  }
  return t('canvasPage.collaborationFooterSchool')
})

function openCollab(mode: 'organization' | 'network') {
  userSelectedMode.value = mode
  if (props.workshopCode) {
    showCollabModal.value = true
  } else {
    collabModalRef.value?.startNow()
  }
}

/** Stop the active session immediately — no confirmation modal. */
async function stopNow() {
  await collabModalRef.value?.stopNow()
}

defineExpose({ openCollab, stopNow })
</script>

<template>
  <CollabUserRail
    :workshop-code="props.workshopCode"
    :participants="props.participants"
  />

  <OnlineCollabModal
    ref="collabModalRef"
    :visible="showCollabModal"
    :diagram-id="props.diagramId"
    :session-diagram-id="props.sessionDiagramId"
    :mode="collabMode"
    @update:visible="showCollabModal = $event"
    @collabSession="emit('collabSession', $event)"
  />

  <!-- Session banner: 校内 omit meeting code -->
  <div
    v-if="props.workshopCode"
    class="w-full shrink-0 flex flex-col border-b border-slate-600/60 pointer-events-none select-none"
    role="status"
  >
    <div
      class="flex items-center justify-center gap-2 px-3 py-1.5 text-xs text-white bg-slate-700/95"
    >
      <template v-if="ownerCollaborationBannerText">
        <span>{{ ownerCollaborationBannerText }}</span>
        <template v-if="showShareCodeRow">
          <span class="opacity-40">·</span>
          <span class="font-mono tracking-wide opacity-80">{{ props.workshopCode }}</span>
        </template>
      </template>
      <template v-else-if="networkCollaborationBannerText">
        <span>{{ networkCollaborationBannerText }}</span>
        <span class="opacity-40">·</span>
        <span class="font-mono tracking-wide opacity-80">{{ props.workshopCode }}</span>
      </template>
      <template v-else>
        <span>{{ schoolCollaborationBannerText }}</span>
      </template>

      <!-- Inline connection status (host + guests; matches session banner) -->
      <template v-if="statusChip.label">
        <span class="opacity-40">·</span>
        <span class="inline-flex items-center gap-1 font-medium">
          <span
            class="w-1.5 h-1.5 rounded-full shrink-0"
            :class="{
              'bg-emerald-400': statusChip.tone === 'ok',
              'bg-amber-400 animate-pulse': statusChip.tone === 'warn',
              'bg-red-400': statusChip.tone === 'err',
            }"
          />
          <span :class="{ 'text-amber-200': statusChip.tone === 'warn', 'text-red-300': statusChip.tone === 'err' }">
            {{ statusChip.label }}
          </span>
          <span
            v-if="statusChip.countdown !== null"
            class="opacity-70 tabular-nums"
          >
            · {{ statusChip.countdown }}s
          </span>
        </span>
      </template>
    </div>
    <div
      v-if="idleSecondsShown !== null"
      class="px-3 py-1 text-center text-xs font-medium text-amber-100 bg-amber-950/90"
    >
      {{ t('canvasPage.collabRoomIdleEnding', { seconds: idleSecondsShown }) }}
    </div>
  </div>

  <!-- Connection status banners -->
  <div
    v-if="isReconnecting"
    class="w-full shrink-0 flex items-center justify-center gap-2 px-3 py-1 text-xs text-amber-100 bg-amber-800/90 pointer-events-none"
    role="status"
  >
    <span>{{ t('canvasPage.collabReconnecting') }}</span>
  </div>
  <div
    v-else-if="isConnectionFailed"
    class="w-full shrink-0 flex items-center justify-center gap-2 px-3 py-1 text-xs text-red-100 bg-red-900/90"
    role="alert"
  >
    <span>{{ t('canvasPage.collabConnectionFailed') }}</span>
    <button
      class="pointer-events-auto underline ml-1"
      @click="emit('retryConnection')"
    >
      {{ t('canvasPage.collabRetryConnection') }}
    </button>
  </div>
</template>
