<script setup lang="ts">
import { computed, ref } from 'vue'

import { LogOut, ScrollText, User } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits<{
  (e: 'navigate', page: string): void
  (e: 'signOut'): void
}>()

const authStore = useAuthStore()
const { t } = useLanguage()

const visible = ref(false)

const displayName = computed(() => authStore.user?.username || authStore.user?.phone || 'User')
const displayAvatar = computed(() => authStore.user?.avatar || '👤')

function go(page: string): void {
  visible.value = false
  emit('navigate', page)
}

function handleSignOut(): void {
  visible.value = false
  emit('signOut')
}
</script>

<template>
  <el-popover
    v-model:visible="visible"
    placement="bottom-end"
    :width="200"
    trigger="click"
  >
    <template #reference>
      <el-button
        size="small"
        class="workshop-navbar-action workshop-navbar-action--me"
        :title="t('workshop.personalMenu')"
      >
        <span class="workshop-navbar-action__content">
          <User
            class="workshop-navbar-action__icon"
            :size="14"
          />
          <span class="workshop-navbar-action__label">{{ t('workshop.navbarMe') }}</span>
        </span>
      </el-button>
    </template>

    <div class="ws-popover-menu">
      <div class="ws-popover-user-info">
        <div class="ws-popover-user-avatar">{{ displayAvatar }}</div>
        <div class="ws-popover-user-meta">
          <div class="ws-popover-user-name">{{ displayName }}</div>
          <div class="ws-popover-user-phone">{{ authStore.user?.phone }}</div>
        </div>
      </div>

      <button
        type="button"
        class="ws-popover-item"
        @click="go('profile')"
      >
        <User class="ws-popover-icon" />
        {{ t('workshop.profile') }}
      </button>

      <button
        type="button"
        class="ws-popover-item"
        @click="go('update-log')"
      >
        <ScrollText class="ws-popover-icon" />
        {{ t('auth.updateLog') }}
      </button>

      <div class="ws-popover-divider" />

      <button
        type="button"
        class="ws-popover-item ws-popover-item--danger"
        @click="handleSignOut"
      >
        <LogOut class="ws-popover-icon" />
        {{ t('workshop.signOut') }}
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

.ws-popover-user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid hsl(0deg 0% 0% / 6%);
  margin-bottom: 2px;
}

.ws-popover-user-avatar {
  font-size: 22px;
  line-height: 1;
  flex-shrink: 0;
}

.ws-popover-user-meta {
  min-width: 0;
  flex: 1;
}

.ws-popover-user-name {
  font-size: 14px;
  font-weight: 600;
  color: hsl(0deg 0% 18%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-popover-user-phone {
  font-size: 11px;
  color: hsl(0deg 0% 52%);
  margin-top: 1px;
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
