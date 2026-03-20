<script setup lang="ts">
import { computed, ref } from 'vue'

import { ElMessage } from 'element-plus'
import {
  Settings,
  BellOff,
  Bell,
  Pin,
  PinOff,
  LogOut,
  Link2,
  CheckCheck,
  RefreshCw,
  CircleDot,
  CalendarClock,
} from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import { workshopChatHrefFromState } from '@/utils/workshopChatRoute'

const props = defineProps<{
  channelId: number
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'openSettings'): void
}>()

const store = useWorkshopChatStore()
const authStore = useAuthStore()
const { t } = useLanguage()

const channel = computed(() =>
  store.channels.find(c => c.id === props.channelId),
)

const isManager = computed(() => authStore.isAdmin || authStore.isManager)

const isLessonStudy = computed(() => Boolean(channel.value?.parent_id))

const deadlineDialogVisible = ref(false)
const deadlineDraft = ref<Date | null>(null)

function handleCopyChannelLink(): void {
  const href = workshopChatHrefFromState({
    currentChannelId: props.channelId,
    currentTopicId: null,
    currentDMPartnerId: null,
    showChannelBrowser: false,
    workshopHomeViewActive: false,
    mainChannelFeedActive: false,
  })
  const url = `${window.location.origin}${href}`
  void navigator.clipboard.writeText(url).then(() => {
    ElMessage.success(t('workshop.linkCopied'))
  })
  emit('update:visible', false)
}

async function handleMarkAllRead(): Promise<void> {
  await store.markChannelReadAll(props.channelId)
  ElMessage.success(t('workshop.markAsRead'))
  emit('update:visible', false)
}

async function handleToggleResolved(): Promise<void> {
  const ch = channel.value
  if (!ch) return
  await store.updateChannelLessonStudy(props.channelId, {
    is_resolved: !ch.is_resolved,
  })
  emit('update:visible', false)
}

async function handleCycleStudyStatus(): Promise<void> {
  const ch = channel.value
  if (!ch) return
  const order = ['open', 'in_progress', 'completed', 'archived']
  const cur = ch.status || 'open'
  const idx = order.indexOf(cur)
  const next = order[(idx + 1) % order.length]
  await store.updateChannelLessonStudy(props.channelId, { status: next })
  emit('update:visible', false)
}

async function handleClearDeadline(): Promise<void> {
  await store.updateChannelLessonStudy(props.channelId, { deadline: null })
  emit('update:visible', false)
}

function openDeadlineDialog(): void {
  const ch = channel.value
  deadlineDraft.value = ch?.deadline ? new Date(ch.deadline) : new Date()
  deadlineDialogVisible.value = true
  emit('update:visible', false)
}

async function handleSaveDeadline(): Promise<void> {
  const d = deadlineDraft.value
  if (!d) {
    return
  }
  const ok = await store.updateChannelLessonStudy(props.channelId, {
    deadline: d.toISOString(),
  })
  if (ok) {
    ElMessage.success(t('common.success'))
    deadlineDialogVisible.value = false
  }
}

async function handleToggleMute(): Promise<void> {
  await store.toggleChannelMute(props.channelId)
  emit('update:visible', false)
}

async function handleTogglePin(): Promise<void> {
  await store.toggleChannelPin(props.channelId)
  emit('update:visible', false)
}

function handleOpenSettings(): void {
  emit('openSettings')
  emit('update:visible', false)
}

async function handleLeave(): Promise<void> {
  await store.leaveChannel(props.channelId)
  store.selectChannel(null)
  emit('update:visible', false)
}
</script>

<script lang="ts">
export default { name: 'ChannelActionsPopover' }
</script>

<template>
  <el-popover
    :visible="visible"
    placement="bottom-start"
    :width="240"
    trigger="click"
    @update:visible="emit('update:visible', $event)"
  >
    <template #reference>
      <slot />
    </template>

    <div class="ws-popover-menu">
      <button
        v-if="channel"
        class="ws-popover-item"
        @click="handleCopyChannelLink"
      >
        <Link2 class="ws-popover-icon" />
        {{ t('workshop.copyLink') }}
      </button>

      <button
        v-if="channel?.is_joined"
        class="ws-popover-item"
        @click="handleMarkAllRead"
      >
        <CheckCheck class="ws-popover-icon" />
        {{ t('workshop.markAllReadChannel') }}
      </button>

      <template v-if="isLessonStudy && isManager && channel">
        <div class="ws-popover-divider" />
        <button
          class="ws-popover-item"
          @click="handleCycleStudyStatus"
        >
          <RefreshCw class="ws-popover-icon" />
          {{ t('workshop.cycleStudyStatus') }}
        </button>
        <button
          class="ws-popover-item"
          @click="handleToggleResolved"
        >
          <CircleDot class="ws-popover-icon" />
          {{
            channel.is_resolved
              ? t('workshop.reopenStudy')
              : t('workshop.markStudyResolved')
          }}
        </button>
        <button
          class="ws-popover-item"
          @click="openDeadlineDialog"
        >
          <CalendarClock class="ws-popover-icon" />
          {{ t('workshop.setDeadline') }}
        </button>
        <button
          v-if="channel.deadline"
          class="ws-popover-item"
          @click="handleClearDeadline"
        >
          <span class="ws-popover-icon ws-popover-icon--text">∅</span>
          {{ t('workshop.clearDeadline') }}
        </button>
      </template>

      <div class="ws-popover-divider" />

      <button
        v-if="channel?.is_joined"
        class="ws-popover-item"
        @click="handleToggleMute"
      >
        <component :is="channel?.is_muted ? Bell : BellOff" class="ws-popover-icon" />
        {{ channel?.is_muted ? t('workshop.unmuteChannel') : t('workshop.muteChannel') }}
      </button>

      <button
        v-if="channel?.is_joined"
        class="ws-popover-item"
        @click="handleTogglePin"
      >
        <component :is="channel?.pin_to_top ? PinOff : Pin" class="ws-popover-icon" />
        {{ channel?.pin_to_top ? t('workshop.unpinChannel') : t('workshop.pinChannel') }}
      </button>

      <button class="ws-popover-item" @click="handleOpenSettings">
        <Settings class="ws-popover-icon" />
        {{ t('workshop.channelSettings') }}
      </button>

      <div class="ws-popover-divider" />

      <button
        v-if="channel?.is_joined && channel?.channel_type !== 'announce'"
        class="ws-popover-item ws-popover-item--danger"
        @click="handleLeave"
      >
        <LogOut class="ws-popover-icon" />
        {{ t('workshop.leave') }}
      </button>
    </div>
  </el-popover>

  <el-dialog
    v-model="deadlineDialogVisible"
    :title="t('workshop.deadlineDialogTitle')"
    width="400px"
    destroy-on-close
    append-to-body
  >
    <el-date-picker
      v-model="deadlineDraft"
      type="datetime"
      style="width: 100%"
      :teleported="true"
    />
    <template #footer>
      <el-button @click="deadlineDialogVisible = false">
        {{ t('common.cancel') }}
      </el-button>
      <el-button type="primary" :disabled="!deadlineDraft" @click="handleSaveDeadline">
        {{ t('common.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.ws-popover-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: -4px;
}

.ws-popover-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  font-size: 13px;
  color: hsl(0deg 0% 30%);
  background: none;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background 120ms ease;
}

.ws-popover-item:hover {
  background: hsl(0deg 0% 0% / 5%);
}

.ws-popover-item--danger {
  color: hsl(0deg 60% 48%);
}

.ws-popover-item--danger:hover {
  background: hsl(0deg 70% 97%);
}

.ws-popover-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  opacity: 0.7;
}

.ws-popover-icon--text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  opacity: 0.55;
}

.ws-popover-divider {
  height: 1px;
  background: hsl(0deg 0% 0% / 8%);
  margin: 2px 0;
}
</style>
