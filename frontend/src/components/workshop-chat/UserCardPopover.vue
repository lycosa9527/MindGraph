<script setup lang="ts">
/**
 * UserCardPopover — Zulip-style user card shown when clicking a contact or
 * buddy-list row. Offers profile view, DM, mention, mute, and admin actions.
 */
import { computed } from 'vue'

import {
  User, MessageSquare, AtSign, Copy,
  VolumeX, Volume2, ShieldCheck,
} from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { useWorkshopChatStore } from '@/stores/workshopChat'

export interface UserCardUser {
  id: number
  name: string
  avatar?: string | null
  role?: string
}

const props = defineProps<{
  user: UserCardUser
  visible: boolean
  channelContext?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'startDm', userId: number): void
  (e: 'insertMention', name: string): void
  (e: 'viewProfile', userId: number): void
}>()

const { t } = useLanguage()
const authStore = useAuthStore()
const store = useWorkshopChatStore()

const isSelf = computed(
  () => String(props.user.id) === authStore.user?.id,
)
const isAdmin = computed(
  () => authStore.isAdmin || authStore.isManager,
)

type PresenceStatus = 'active' | 'idle' | 'offline'

const presence = computed<PresenceStatus>(() => {
  if (store.onlineUserIds.has(props.user.id)) return 'active'
  if (store.idleUserIds.has(props.user.id)) return 'idle'
  return 'offline'
})

const presenceLabel = computed(() => {
  const labels: Record<PresenceStatus, string> = {
    active: t('workshop.presenceActive'),
    idle: t('workshop.presenceIdle'),
    offline: t('workshop.presenceOffline'),
  }
  return labels[presence.value]
})

const roleBadge = computed(() => {
  const role = props.user.role ?? 'member'
  const map: Record<string, string> = {
    admin: t('workshop.roleAdmin'),
    superadmin: t('workshop.roleAdmin'),
    manager: t('workshop.roleManager'),
    owner: t('workshop.roleOwner'),
  }
  return map[role] ?? null
})

const userInitial = computed(() =>
  (props.user.name || '?')[0].toUpperCase(),
)

function close(): void {
  emit('update:visible', false)
}

function handleViewProfile(): void {
  emit('viewProfile', props.user.id)
  close()
}

function handleStartDm(): void {
  emit('startDm', props.user.id)
  close()
}

function handleInsertMention(): void {
  emit('insertMention', props.user.name)
  close()
}

function handleCopyMention(): void {
  navigator.clipboard.writeText(`@**${props.user.name}**`)
  close()
}

function handleManageUser(): void {
  close()
}
</script>

<script lang="ts">
export default { name: 'UserCardPopover' }
</script>

<template>
  <el-popover
    :visible="visible"
    placement="left-start"
    :width="260"
    trigger="click"
    @update:visible="emit('update:visible', $event)"
  >
    <template #reference>
      <slot />
    </template>

    <div class="user-card">
      <!-- Header: avatar + name + presence -->
      <div class="user-card__header">
        <div class="user-card__avatar-wrapper">
          <img
            v-if="user.avatar"
            :src="user.avatar"
            :alt="user.name"
            class="user-card__avatar"
          >
          <span v-else class="user-card__avatar user-card__avatar--initials">
            {{ userInitial }}
          </span>
          <span
            class="user-card__presence-dot"
            :class="`user-card__presence-dot--${presence}`"
          />
        </div>
        <div class="user-card__info">
          <span class="user-card__name">{{ user.name }}</span>
          <span class="user-card__presence-label">{{ presenceLabel }}</span>
        </div>
        <span v-if="roleBadge" class="user-card__role-badge">
          {{ roleBadge }}
        </span>
      </div>

      <div class="ws-popover-divider" />

      <!-- Actions -->
      <div class="ws-popover-menu">
        <button class="ws-popover-item" @click="handleViewProfile">
          <User class="ws-popover-icon" />
          {{ t('workshop.viewProfile') }}
        </button>

        <button v-if="!isSelf" class="ws-popover-item" @click="handleStartDm">
          <MessageSquare class="ws-popover-icon" />
          {{ t('workshop.sendDirectMessage') }}
        </button>

        <button
          v-if="!isSelf && channelContext"
          class="ws-popover-item"
          @click="handleInsertMention"
        >
          <AtSign class="ws-popover-icon" />
          {{ t('workshop.replyMentioning') }}
        </button>

        <button v-if="!isSelf" class="ws-popover-item" @click="handleCopyMention">
          <Copy class="ws-popover-icon" />
          {{ t('workshop.copyMentionSyntax') }}
        </button>
      </div>

      <!-- Admin section -->
      <template v-if="isAdmin && !isSelf">
        <div class="ws-popover-divider" />
        <div class="ws-popover-menu">
          <button class="ws-popover-item" @click="handleManageUser">
            <ShieldCheck class="ws-popover-icon" />
            {{ t('workshop.manageUser') }}
          </button>
        </div>
      </template>
    </div>
  </el-popover>
</template>

<style scoped>
.user-card {
  margin: -4px;
}

.user-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 4px 8px;
}

.user-card__avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.user-card__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.user-card__avatar--initials {
  display: flex;
  align-items: center;
  justify-content: center;
  background: hsl(228deg 44% 60%);
  color: #fff;
  font-weight: 700;
  font-size: 16px;
}

.user-card__presence-dot {
  position: absolute;
  bottom: 1px;
  right: 1px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #fff;
}

.user-card__presence-dot--active {
  background: hsl(143deg 55% 43%);
}

.user-card__presence-dot--idle {
  background: hsl(38deg 85% 55%);
}

.user-card__presence-dot--offline {
  background: hsl(225deg 10% 75%);
}

.user-card__info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.user-card__name {
  font-size: 14px;
  font-weight: 600;
  color: hsl(0deg 0% 15%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-card__presence-label {
  font-size: 12px;
  color: hsl(0deg 0% 50%);
}

.user-card__role-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px 6px;
  border-radius: 3px;
  background: hsl(228deg 44% 94%);
  color: hsl(228deg 44% 45%);
}

.ws-popover-menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
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

.ws-popover-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  opacity: 0.7;
}

.ws-popover-divider {
  height: 1px;
  background: hsl(0deg 0% 0% / 8%);
  margin: 4px 0;
}
</style>
