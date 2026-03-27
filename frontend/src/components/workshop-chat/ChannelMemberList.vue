<script setup lang="ts">
/**
 * ChannelMemberList - Zulip-style buddy list with three sections:
 * "THIS CONVERSATION", "THIS CHANNEL", "OTHERS".
 * Presence states: active (green) when on workshop chat; offline (gray).
 */
import { computed, ref, watch } from 'vue'

import { ChevronRight, Search } from 'lucide-vue-next'

import UserCardPopover from '@/components/workshop-chat/UserCardPopover.vue'
import type { UserCardUser } from '@/components/workshop-chat/UserCardPopover.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { type ChannelMember, type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'

const { t } = useLanguage()
const store = useWorkshopChatStore()
const authStore = useAuthStore()

const emit = defineEmits<{
  startDm: [userId: number]
  insertMention: [name: string]
  viewProfile: [userId: number]
  manageUser: [userId: number]
}>()

const searchQuery = ref('')
/** When user searches, org members not in channel (server-filtered by name). */
const othersRemote = ref<OrgMember[] | null>(null)
let othersSearchTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (val) => {
  if (othersSearchTimer != null) {
    clearTimeout(othersSearchTimer)
  }
  const t = val.trim()
  if (!t) {
    othersRemote.value = null
    return
  }
  othersSearchTimer = setTimeout(async () => {
    othersSearchTimer = null
    othersRemote.value = await store.searchOrgMembers(t, 100)
  }, 280)
})

const collapsedSections = ref<Set<string>>(new Set())
const popoverUserId = ref<number | null>(null)

type PresenceStatus = 'active' | 'offline'

interface BuddyEntry extends ChannelMember {
  presence: PresenceStatus
  isCurrentUser: boolean
}

function getPresence(userId: number): PresenceStatus {
  if (store.onlineUserIds.has(userId)) return 'active'
  return 'offline'
}

function matchesSearch(name: string): boolean {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return true
  return name.toLowerCase().includes(q)
}

function sortEntries(entries: BuddyEntry[]): BuddyEntry[] {
  const order: Record<PresenceStatus, number> = { active: 0, offline: 1 }
  return entries.sort((a, b) => {
    if (a.isCurrentUser) return -1
    if (b.isCurrentUser) return 1
    const presenceDiff = order[a.presence] - order[b.presence]
    if (presenceDiff !== 0) return presenceDiff
    return a.name.localeCompare(b.name)
  })
}

const allBuddies = computed<BuddyEntry[]>(() =>
  store.channelMembers
    .filter((m) => matchesSearch(m.name))
    .map((m) => ({
      ...m,
      presence: getPresence(m.user_id),
      isCurrentUser: String(m.user_id) === authStore.user?.id,
    }))
)

const conversationParticipants = computed(() =>
  sortEntries(allBuddies.value.filter((m) => store.topicParticipantIds.has(m.user_id)))
)

const channelMembers = computed(() =>
  sortEntries(allBuddies.value.filter((m) => !store.topicParticipantIds.has(m.user_id)))
)

const otherUsers = computed<BuddyEntry[]>(() => {
  const channelMemberIds = new Set(store.channelMembers.map((m) => m.user_id))
  const q = searchQuery.value.trim().toLowerCase()
  const source: OrgMember[] =
    q && othersRemote.value != null ? othersRemote.value : store.orgMembers
  return sortEntries(
    source
      .filter((m) => !channelMemberIds.has(m.id) && (!q || m.name.toLowerCase().includes(q)))
      .map((m) => ({
        user_id: m.id,
        name: m.name,
        avatar: m.avatar,
        role: 'member',
        joined_at: '',
        presence: getPresence(m.id),
        isCurrentUser: String(m.id) === authStore.user?.id,
      }))
  )
})

const hasConversation = computed(() => store.topicParticipantIds.size > 0)

function toggleSection(sectionId: string): void {
  if (collapsedSections.value.has(sectionId)) {
    collapsedSections.value.delete(sectionId)
  } else {
    collapsedSections.value.add(sectionId)
  }
}

function isSectionCollapsed(sectionId: string): boolean {
  return collapsedSections.value.has(sectionId)
}

function toCardUser(member: BuddyEntry): UserCardUser {
  return {
    id: member.user_id,
    name: member.name,
    avatar: member.avatar,
    role: member.role,
  }
}

function isPopoverOpen(userId: number): boolean {
  return popoverUserId.value === userId
}

function setPopover(userId: number, open: boolean): void {
  popoverUserId.value = open ? userId : null
}

function handleStartDm(userId: number): void {
  emit('startDm', userId)
}

function handleInsertMention(name: string): void {
  emit('insertMention', name)
}

function handleViewProfile(userId: number): void {
  emit('viewProfile', userId)
}

function handleManageUser(userId: number): void {
  emit('manageUser', userId)
}
</script>

<template>
  <div class="buddy-list">
    <!-- Header + search -->
    <div class="buddy-list__header">
      <div class="buddy-list__search-wrapper">
        <Search
          :size="13"
          class="buddy-list__search-icon"
        />
        <input
          v-model="searchQuery"
          type="text"
          class="buddy-list__search"
          :placeholder="t('workshop.filterUsers')"
        />
      </div>
    </div>

    <!-- Scrollable list -->
    <div class="buddy-list__scroll">
      <!-- THIS CONVERSATION -->
      <div
        v-if="hasConversation && conversationParticipants.length > 0"
        class="buddy-section"
      >
        <button
          class="buddy-section__header"
          @click="toggleSection('conversation')"
        >
          <ChevronRight
            :size="12"
            class="buddy-section__toggle"
            :class="{ 'buddy-section__toggle--open': !isSectionCollapsed('conversation') }"
          />
          <span class="buddy-section__heading">
            {{ t('workshop.thisConversation') }}
          </span>
          <span class="buddy-section__count"> ({{ conversationParticipants.length }}) </span>
        </button>
        <ul
          v-if="!isSectionCollapsed('conversation')"
          class="buddy-section__list"
        >
          <li
            v-for="member in conversationParticipants"
            :key="member.user_id"
          >
            <UserCardPopover
              :user="toCardUser(member)"
              :visible="isPopoverOpen(member.user_id)"
              :channel-context="true"
              @update:visible="setPopover(member.user_id, $event)"
              @start-dm="handleStartDm"
              @insert-mention="handleInsertMention"
              @view-profile="handleViewProfile"
              @manage-user="handleManageUser"
            >
              <div class="buddy-row">
                <span
                  class="buddy-circle"
                  :class="`buddy-circle--${member.presence}`"
                />
                <span class="buddy-name">
                  {{ member.name }}
                  <span
                    v-if="member.isCurrentUser"
                    class="buddy-you"
                  >
                    {{ t('workshop.you') }}
                  </span>
                </span>
              </div>
            </UserCardPopover>
          </li>
        </ul>
      </div>

      <!-- THIS CHANNEL -->
      <div
        v-if="channelMembers.length > 0"
        class="buddy-section"
      >
        <button
          class="buddy-section__header"
          @click="toggleSection('channel')"
        >
          <ChevronRight
            :size="12"
            class="buddy-section__toggle"
            :class="{ 'buddy-section__toggle--open': !isSectionCollapsed('channel') }"
          />
          <span class="buddy-section__heading">
            {{ hasConversation ? t('workshop.thisChannel') : t('workshop.members') }}
          </span>
          <span class="buddy-section__count"> ({{ channelMembers.length }}) </span>
        </button>
        <ul
          v-if="!isSectionCollapsed('channel')"
          class="buddy-section__list"
        >
          <li
            v-for="member in channelMembers"
            :key="member.user_id"
          >
            <UserCardPopover
              :user="toCardUser(member)"
              :visible="isPopoverOpen(member.user_id)"
              :channel-context="true"
              @update:visible="setPopover(member.user_id, $event)"
              @start-dm="handleStartDm"
              @insert-mention="handleInsertMention"
              @view-profile="handleViewProfile"
              @manage-user="handleManageUser"
            >
              <div class="buddy-row">
                <span
                  class="buddy-circle"
                  :class="`buddy-circle--${member.presence}`"
                />
                <span class="buddy-name">
                  {{ member.name }}
                  <span
                    v-if="member.isCurrentUser"
                    class="buddy-you"
                  >
                    {{ t('workshop.you') }}
                  </span>
                </span>
              </div>
            </UserCardPopover>
          </li>
        </ul>
      </div>

      <!-- OTHERS -->
      <div
        v-if="otherUsers.length > 0"
        class="buddy-section"
      >
        <button
          class="buddy-section__header"
          @click="toggleSection('others')"
        >
          <ChevronRight
            :size="12"
            class="buddy-section__toggle"
            :class="{ 'buddy-section__toggle--open': !isSectionCollapsed('others') }"
          />
          <span class="buddy-section__heading">
            {{ t('workshop.others') }}
          </span>
          <span class="buddy-section__count"> ({{ otherUsers.length }}) </span>
        </button>
        <ul
          v-if="!isSectionCollapsed('others')"
          class="buddy-section__list"
        >
          <li
            v-for="member in otherUsers"
            :key="member.user_id"
          >
            <UserCardPopover
              :user="toCardUser(member)"
              :visible="isPopoverOpen(member.user_id)"
              :channel-context="false"
              @update:visible="setPopover(member.user_id, $event)"
              @start-dm="handleStartDm"
              @insert-mention="handleInsertMention"
              @view-profile="handleViewProfile"
              @manage-user="handleManageUser"
            >
              <div class="buddy-row">
                <span
                  class="buddy-circle"
                  :class="`buddy-circle--${member.presence}`"
                />
                <span class="buddy-name">
                  {{ member.name }}
                  <span
                    v-if="member.isCurrentUser"
                    class="buddy-you"
                  >
                    {{ t('workshop.you') }}
                  </span>
                </span>
              </div>
            </UserCardPopover>
          </li>
        </ul>
      </div>

      <!-- Empty -->
      <div
        v-if="allBuddies.length === 0 && otherUsers.length === 0"
        class="buddy-empty"
      >
        {{ searchQuery ? t('workshop.noMembersFound') : t('workshop.noMembers') }}
      </div>

      <!-- View all members -->
      <div
        v-if="store.channelMembers.length > 0"
        class="buddy-view-all"
      >
        <a class="buddy-view-all__link">
          {{ t('workshop.viewAllMembers') }}
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.buddy-list {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Header */
.buddy-list__header {
  padding: 8px;
  border-bottom: 1px solid hsl(0deg 0% 0% / 6%);
}

.buddy-list__search-wrapper {
  position: relative;
}

.buddy-list__search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: hsl(0deg 0% 48%);
  pointer-events: none;
}

.buddy-list__search {
  width: 100%;
  padding: 6px 8px 6px 28px;
  font-size: 12px;
  border: 1px solid hsl(0deg 0% 84%);
  border-radius: 5px;
  background: hsl(0deg 0% 100%);
  outline: none;
  color: hsl(0deg 0% 15%);
  transition:
    border-color 150ms ease,
    box-shadow 150ms ease;
}

.buddy-list__search:focus {
  border-color: hsl(228deg 40% 68%);
  box-shadow: 0 0 0 2px hsl(228deg 56% 58% / 10%);
}

.buddy-list__search::placeholder {
  color: hsl(0deg 0% 55%);
}

/* Scroll area */
.buddy-list__scroll {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 8px;
}

.buddy-list__scroll::-webkit-scrollbar {
  width: 4px;
}

.buddy-list__scroll::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}

.buddy-list__scroll:hover::-webkit-scrollbar-thumb {
  background: hsl(0deg 0% 0% / 14%);
}

/* Section */
.buddy-section {
  padding: 2px 0;
}

.buddy-section__header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px 4px;
  width: 100%;
  background: none;
  border: none;
  cursor: pointer;
  user-select: none;
}

.buddy-section__header:hover {
  background: hsl(0deg 0% 0% / 3%);
}

.buddy-section__toggle {
  flex-shrink: 0;
  color: hsl(0deg 0% 50%);
  transition: transform 150ms ease;
  transform: rotate(0deg);
}

.buddy-section__toggle--open {
  transform: rotate(90deg);
}

.buddy-section__heading {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: hsl(0deg 0% 38%);
}

.buddy-section__count {
  font-size: 10px;
  font-weight: 600;
  color: hsl(0deg 0% 50%);
}

.buddy-section__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* Buddy row — Zulip-style: circle + name */
.buddy-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 12px 3px 20px;
  cursor: pointer;
  transition: background 100ms ease;
  border-radius: 4px;
  margin: 0 4px;
}

.buddy-row:hover {
  background: hsl(0deg 0% 0% / 5%);
  box-shadow: inset 0 0 0 1px hsl(0deg 0% 0% / 6%);
}

/* Presence circle — Zulip-style icon */
.buddy-circle {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.buddy-circle--active {
  background: hsl(143deg 55% 43%);
}

.buddy-circle--offline {
  background: hsl(225deg 10% 75%);
}

/* Name */
.buddy-name {
  font-size: 13px;
  color: hsl(0deg 0% 20%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 22px;
}

.buddy-you {
  font-size: 11px;
  color: hsl(0deg 0% 50%);
  font-weight: 400;
  margin-left: 2px;
}

/* Empty */
.buddy-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 12px;
  color: hsl(0deg 0% 52%);
}

/* View all link */
.buddy-view-all {
  padding: 8px 20px;
}

.buddy-view-all__link {
  font-size: 11px;
  font-weight: 600;
  color: hsl(228deg 40% 48%);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  cursor: pointer;
}

.buddy-view-all__link:hover {
  color: hsl(228deg 50% 38%);
  text-decoration: underline;
}
</style>
