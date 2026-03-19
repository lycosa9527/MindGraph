<script setup lang="ts">
import {
  Settings, BellOff, Bell, Pin, PinOff, LogOut,
  Shield, Trash2, Palette,
} from 'lucide-vue-next'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  channelId: number
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'openSettings'): void
}>()

const store = useWorkshopChatStore()
const { t } = useLanguage()

const channel = computed(() =>
  store.channels.find(c => c.id === props.channelId),
)

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
import { computed } from 'vue'

export default { name: 'ChannelActionsPopover' }
</script>

<template>
  <el-popover
    :visible="visible"
    placement="bottom-start"
    :width="220"
    trigger="click"
    @update:visible="emit('update:visible', $event)"
  >
    <template #reference>
      <slot />
    </template>

    <div class="ws-popover-menu">
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

.ws-popover-divider {
  height: 1px;
  background: hsl(0deg 0% 0% / 8%);
  margin: 2px 0;
}
</style>
