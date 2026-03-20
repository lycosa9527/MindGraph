<script setup lang="ts">
/**
 * Workshop options: 教研组 management opens the consolidated modal; optional
 * channel settings when a concrete channel is selected; notifications / preferences.
 */
import { computed, ref } from 'vue'

import { Bell, ListTree, Settings, SlidersHorizontal } from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'

defineProps<{
  /** Lesson / stream / announce channel — show settings (not 教研组 landing-only). */
  showChannelSettings: boolean
}>()

const emit = defineEmits<{
  (e: 'navigate', page: string): void
  (e: 'openChannelSettings'): void
  (e: 'manageTeachingGroups'): void
}>()

const { t } = useLanguage()
const authStore = useAuthStore()

const visible = ref(false)

const canManageChannels = computed(() => authStore.isAdminOrManager)

function go(page: string): void {
  visible.value = false
  emit('navigate', page)
}

function openChannelSettings(): void {
  visible.value = false
  emit('openChannelSettings')
}

function manageTeachingGroups(): void {
  visible.value = false
  emit('manageTeachingGroups')
}
</script>

<template>
  <el-popover
    v-model:visible="visible"
    placement="bottom-end"
    :width="260"
    trigger="click"
  >
    <template #reference>
      <el-button
        size="small"
        class="workshop-navbar-action workshop-navbar-action--options"
        :title="t('workshop.gearMenu')"
      >
        <span class="workshop-navbar-action__content">
          <Settings
            class="workshop-navbar-action__icon"
            :size="14"
          />
          <span class="workshop-navbar-action__label">{{ t('workshop.navbarOptions') }}</span>
        </span>
      </el-button>
    </template>

    <div class="ws-popover-menu">
      <template v-if="canManageChannels">
        <button
          type="button"
          class="ws-popover-item ws-popover-item--emphasis"
          @click="manageTeachingGroups"
        >
          <ListTree
            class="ws-popover-item-icon"
            :size="16"
          />
          {{ t('workshop.manageTeachingGroups') }}
        </button>
        <div
          v-if="showChannelSettings"
          class="ws-popover-divider"
        />
      </template>

      <button
        v-if="showChannelSettings"
        type="button"
        class="ws-popover-item"
        @click="openChannelSettings"
      >
        <Settings
          class="ws-popover-item-icon"
          :size="16"
        />
        {{ t('workshop.channelSettings') }}
      </button>

      <div
        v-if="canManageChannels || showChannelSettings"
        class="ws-popover-divider"
      />

      <button
        type="button"
        class="ws-popover-item"
        @click="go('notifications')"
      >
        <Bell
          class="ws-popover-item-icon"
          :size="16"
        />
        {{ t('workshop.notifications') }}
      </button>
      <button
        type="button"
        class="ws-popover-item"
        @click="go('preferences')"
      >
        <SlidersHorizontal
          class="ws-popover-item-icon"
          :size="16"
        />
        {{ t('workshop.preferences') }}
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

.ws-popover-divider {
  height: 1px;
  margin: 6px 4px;
  background: hsl(0deg 0% 0% / 8%);
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

.ws-popover-item:hover:not(:disabled) {
  background: hsl(0deg 0% 0% / 5%);
}

.ws-popover-item:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.ws-popover-item--emphasis {
  font-weight: 600;
  color: hsl(228deg 45% 32%);
}

.ws-popover-item-icon {
  flex-shrink: 0;
  opacity: 0.7;
}
</style>
