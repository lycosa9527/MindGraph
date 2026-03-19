<script setup lang="ts">
/**
 * WorkshopChatHistory - Sidebar panel for Workshop Chat inside AppSidebar.
 *
 * Hierarchy (aligned with Zulip):
 *   Group header (collapsible section)
 *     └─ Lesson-study channel (ChannelSidebarItem)
 *          └─ Topic (conversation thread)
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  ChevronRight, ChevronDown, Plus, Search,
  Star, AtSign, Inbox,
} from 'lucide-vue-next'

import ChannelSidebarItem from '@/components/sidebar/ChannelSidebarItem.vue'
import { useLanguage } from '@/composables/useLanguage'
import { useWorkshopChatStore, type ChatChannel, type ChatTopic } from '@/stores/workshopChat'

defineProps<{
  isBlurred?: boolean
}>()

const { t } = useLanguage()
const router = useRouter()
const store = useWorkshopChatStore()

const sidebarFilter = ref('')
const expandedChannelId = ref<number | null>(null)
const collapsedGroupIds = ref<Set<number>>(new Set())
const channelsSectionCollapsed = ref(false)
const dmsSectionCollapsed = ref(false)
const viewsSectionCollapsed = ref(false)
const activeChannelPopover = ref<number | null>(null)
const activeTopicPopover = ref<number | null>(null)

function matchesFilter(name: string): boolean {
  const q = sidebarFilter.value.trim().toLowerCase()
  if (!q) return true
  return name.toLowerCase().includes(q)
}

const announceChannels = computed(() =>
  store.channels.filter(
    c => c.channel_type === 'announce' && matchesFilter(c.name),
  ),
)

const groupChannels = computed(() =>
  store.channels.filter(
    c => c.channel_type !== 'announce'
      && (c.parent_id === null || c.parent_id === undefined)
      && matchesFilter(c.name),
  ),
)

const filteredDMs = computed(() => {
  const q = sidebarFilter.value.trim().toLowerCase()
  if (!q) return store.dmConversations
  return store.dmConversations.filter(c =>
    c.partner_name.toLowerCase().includes(q),
  )
})

function topicsForChannel(channelId: number): ChatTopic[] {
  return store.topics.filter(tp => tp.channel_id === channelId)
}

function isGroupCollapsed(groupId: number): boolean {
  return collapsedGroupIds.value.has(groupId)
}

function toggleGroupCollapse(groupId: number): void {
  if (collapsedGroupIds.value.has(groupId)) {
    collapsedGroupIds.value.delete(groupId)
  } else {
    collapsedGroupIds.value.add(groupId)
  }
}

function toggleChannelExpand(channelId: number): void {
  if (expandedChannelId.value === channelId) {
    expandedChannelId.value = null
  } else {
    expandedChannelId.value = channelId
    store.fetchTopics(channelId)
  }
}

function navigateToChannel(channelId: number): void {
  const switchingChannel = store.currentChannelId !== channelId
  store.currentChannelId = channelId
  store.currentTopicId = null
  store.channelMessages = []
  store.topicMessages = []
  store.activeTab = 'channels'
  store.showChannelBrowser = false
  if (switchingChannel || expandedChannelId.value !== channelId) {
    expandedChannelId.value = channelId
    store.fetchTopics(channelId)
  }
  router.push('/workshop-chat')
}

function navigateToTopic(channelId: number, topicId: number): void {
  if (store.currentChannelId !== channelId) {
    store.currentChannelId = channelId
    store.channelMessages = []
  }
  store.selectTopic(topicId)
  store.activeTab = 'channels'
  store.showChannelBrowser = false
  router.push('/workshop-chat')
}

function navigateToAllTopics(channelId: number): void {
  if (store.currentChannelId !== channelId) {
    store.currentChannelId = channelId
    store.channelMessages = []
  }
  store.currentTopicId = null
  store.activeTab = 'channels'
  store.showChannelBrowser = false
  router.push('/workshop-chat')
}

function navigateToDM(partnerId: number): void {
  store.selectDMPartner(partnerId)
  store.activeTab = 'dms'
  store.showChannelBrowser = false
  router.push('/workshop-chat')
}

function browseChannels(): void {
  store.showChannelBrowser = true
  store.selectChannel(null)
  store.selectDMPartner(null)
  router.push('/workshop-chat')
}

function startNewDM(): void {
  store.showChannelBrowser = false
  router.push('/workshop-chat')
}

function handleOpenChannelSettings(channelId: number): void {
  store.dialogChannelSettingsId = channelId
  router.push('/workshop-chat')
}

function handleRenameTopic(topicId: number, channelId: number): void {
  store.dialogTopicEdit = { topicId, channelId, mode: 'rename' }
  router.push('/workshop-chat')
}

function handleMoveTopic(topicId: number, channelId: number): void {
  store.dialogTopicEdit = { topicId, channelId, mode: 'move' }
  router.push('/workshop-chat')
}

function childChannels(group: ChatChannel): ChatChannel[] {
  return (group.children ?? []).filter(c => matchesFilter(c.name))
}

onMounted(async () => {
  await store.fetchChannels()
  await store.fetchDMConversations()

  const allChildren = store.channels.flatMap(g => g.children ?? [])
  const announceList = store.channels.filter(c => c.channel_type === 'announce')

  for (const ch of [...announceList, ...allChildren]) {
    if (ch.is_joined) {
      await store.fetchTopics(ch.id)
    }
  }
})
</script>

<template>
  <div
    class="ws-sidebar-panel"
    :class="{ 'ws-sidebar-panel--blurred': isBlurred }"
  >
    <!-- Filter box -->
    <div class="sidebar-search">
      <div class="search-wrapper">
        <Search class="search-icon" :size="14" />
        <input
          v-model="sidebarFilter"
          type="text"
          class="search-input"
          :placeholder="t('workshop.filterSidebar')"
        >
      </div>
    </div>

    <!-- Views section -->
    <div class="sidebar-section">
      <button
        class="section-header"
        @click="viewsSectionCollapsed = !viewsSectionCollapsed"
      >
        <component
          :is="viewsSectionCollapsed ? ChevronRight : ChevronDown"
          :size="12"
          class="section-chevron"
        />
        <span class="section-label">{{ t('workshop.views') }}</span>
      </button>
      <ul v-if="!viewsSectionCollapsed" class="view-list">
        <li class="view-row">
          <Inbox :size="16" class="view-icon" />
          <span class="view-label">{{ t('workshop.inbox') }}</span>
        </li>
        <li class="view-row">
          <Star :size="16" class="view-icon" />
          <span class="view-label">{{ t('workshop.starred') }}</span>
        </li>
        <li class="view-row">
          <AtSign :size="16" class="view-icon" />
          <span class="view-label">{{ t('workshop.mentions') }}</span>
        </li>
      </ul>
    </div>

    <div class="sidebar-scroll-area">
      <!-- Channels section -->
      <div class="sidebar-section">
        <div class="section-header-row">
          <button
            class="section-header"
            @click="channelsSectionCollapsed = !channelsSectionCollapsed"
          >
            <component
              :is="channelsSectionCollapsed ? ChevronRight : ChevronDown"
              :size="12"
              class="section-chevron"
            />
            <span class="section-label">{{ t('workshop.channels') }}</span>
          </button>
          <button
            class="section-action"
            :title="t('workshop.browseChannels')"
            @click="browseChannels"
          >
            <Plus :size="14" />
          </button>
        </div>

        <ul v-if="!channelsSectionCollapsed" class="channel-list">
          <!-- Announce channels (standalone) -->
          <ChannelSidebarItem
            v-for="ch in announceChannels"
            :key="ch.id"
            :channel="ch"
            :topics="topicsForChannel(ch.id)"
            :is-expanded="expandedChannelId === ch.id"
            :is-active-channel="ch.id === store.currentChannelId"
            :active-topic-id="store.currentTopicId"
            :channel-popover-visible="activeChannelPopover === ch.id"
            :topic-popover-id="activeTopicPopover"
            @navigate="navigateToChannel"
            @toggle-expand="toggleChannelExpand"
            @navigate-to-topic="navigateToTopic"
            @navigate-to-all-topics="navigateToAllTopics"
            @open-settings="handleOpenChannelSettings"
            @update-channel-popover="(v) => activeChannelPopover = v ? ch.id : null"
            @update-topic-popover="(id) => activeTopicPopover = id"
            @rename-topic="handleRenameTopic"
            @move-topic="handleMoveTopic"
          />

          <!-- Groups with lesson-study children -->
          <template v-for="group in groupChannels" :key="group.id">
            <li class="group-header-item">
              <button
                class="group-header-btn"
                @click="toggleGroupCollapse(group.id)"
              >
                <component
                  :is="isGroupCollapsed(group.id) ? ChevronRight : ChevronDown"
                  :size="12"
                  class="group-chevron"
                />
                <span v-if="group.avatar" class="group-avatar">{{ group.avatar }}</span>
                <span class="group-name">{{ group.name }}</span>
              </button>
            </li>

            <template v-if="!isGroupCollapsed(group.id)">
              <ChannelSidebarItem
                v-for="child in childChannels(group)"
                :key="child.id"
                :channel="child"
                :topics="topicsForChannel(child.id)"
                :is-expanded="expandedChannelId === child.id"
                :is-active-channel="child.id === store.currentChannelId"
                :active-topic-id="store.currentTopicId"
                :channel-popover-visible="activeChannelPopover === child.id"
                :topic-popover-id="activeTopicPopover"
                :indent-level="1"
                @navigate="navigateToChannel"
                @toggle-expand="toggleChannelExpand"
                @navigate-to-topic="navigateToTopic"
                @navigate-to-all-topics="navigateToAllTopics"
                @open-settings="handleOpenChannelSettings"
                @update-channel-popover="(v) => activeChannelPopover = v ? child.id : null"
                @update-topic-popover="(id) => activeTopicPopover = id"
                @rename-topic="handleRenameTopic"
                @move-topic="handleMoveTopic"
              />
            </template>
          </template>

          <!-- Browse more channels -->
          <li class="browse-more-row" @click="browseChannels">
            <Plus :size="12" class="browse-more-icon" />
            <span class="browse-more-label">{{ t('workshop.browseChannels') }}</span>
          </li>
        </ul>
      </div>

      <!-- Direct Messages section -->
      <div class="sidebar-section">
        <div class="section-header-row">
          <button
            class="section-header"
            @click="dmsSectionCollapsed = !dmsSectionCollapsed"
          >
            <component
              :is="dmsSectionCollapsed ? ChevronRight : ChevronDown"
              :size="12"
              class="section-chevron"
            />
            <span class="section-label">{{ t('workshop.dms') }}</span>
          </button>
          <button
            class="section-action"
            :title="t('workshop.newDM')"
            @click="startNewDM"
          >
            <Plus :size="14" />
          </button>
        </div>

        <ul v-if="!dmsSectionCollapsed" class="dm-list">
          <li
            v-for="conv in filteredDMs"
            :key="conv.partner_id"
            class="dm-row"
            :class="{ 'dm-row--active': conv.partner_id === store.currentDMPartnerId }"
            @click="navigateToDM(conv.partner_id)"
          >
            <span
              class="dm-presence"
              :class="store.onlineUserIds.has(conv.partner_id) ? 'dm-presence--online' : 'dm-presence--offline'"
            />
            <span class="dm-name">{{ conv.partner_name }}</span>
            <span v-if="conv.unread_count > 0" class="unread-badge">
              {{ conv.unread_count }}
            </span>
          </li>
          <li v-if="filteredDMs.length === 0" class="dm-empty">
            {{ t('workshop.noConversationsYet') }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ws-sidebar-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  font-size: 13px;
  user-select: none;
}

.ws-sidebar-panel--blurred {
  filter: blur(4px);
  pointer-events: none;
}

/* Search */
.sidebar-search { padding: 8px; }
.search-wrapper { position: relative; }

.search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: hsl(0deg 0% 48%);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 6px 8px 6px 28px;
  font-size: 12px;
  border: 1px solid hsl(0deg 0% 84%);
  border-radius: 5px;
  background: hsl(0deg 0% 100%);
  outline: none;
  color: hsl(0deg 0% 15%);
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.search-input:focus {
  border-color: hsl(228deg 40% 68%);
  box-shadow: 0 0 0 2px hsl(228deg 56% 58% / 10%);
}

.search-input::placeholder { color: hsl(0deg 0% 55%); }

/* Section headers */
.sidebar-section { margin-bottom: 2px; }

.section-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: hsl(0deg 0% 40%);
  opacity: 0.7;
}

.section-header:hover { opacity: 0.9; }
.section-chevron { color: inherit; opacity: 0.6; }
.section-label { line-height: 1; }

.section-action {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: none;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  color: hsl(0deg 0% 40%);
  opacity: 0.5;
  transition: all 120ms ease;
}

.section-action:hover {
  opacity: 1;
  background: hsl(0deg 0% 0% / 8%);
}

/* Views */
.view-list { list-style: none; margin: 0; padding: 0 4px; }

.view-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  color: hsl(0deg 0% 20%);
  transition: all 120ms ease;
  line-height: 22px;
  font-size: 12px;
}

.view-row:hover { background: hsl(0deg 0% 0% / 5%); }
.view-icon { opacity: 0.5; flex-shrink: 0; }

.view-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Scrollable area */
.sidebar-scroll-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: 8px;
}

.sidebar-scroll-area::-webkit-scrollbar { width: 4px; }

.sidebar-scroll-area::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 2px;
}

.sidebar-scroll-area:hover::-webkit-scrollbar-thumb {
  background: hsl(0deg 0% 0% / 18%);
}

/* Channel list */
.channel-list { list-style: none; margin: 0; padding: 0 4px; }

/* Group header (collapsible section divider) */
.group-header-item {
  list-style: none;
  margin-top: 6px;
}

.group-header-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  padding: 4px 6px;
  border: none;
  border-radius: 4px;
  background: none;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: hsl(0deg 0% 35%);
  transition: background 120ms ease;
}

.group-header-btn:hover {
  background: hsl(0deg 0% 0% / 5%);
}

.group-chevron {
  color: inherit;
  opacity: 0.5;
  flex-shrink: 0;
}

.group-avatar {
  font-size: 13px;
  line-height: 1;
  flex-shrink: 0;
}

.group-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Browse more */
.browse-more-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  margin-top: 2px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  color: hsl(0deg 0% 40%);
  opacity: 0.6;
  transition: all 120ms ease;
}

.browse-more-row:hover {
  opacity: 1;
  background: hsl(0deg 0% 0% / 5%);
}

.browse-more-icon { flex-shrink: 0; }
.browse-more-label { font-weight: 500; }

/* DMs */
.dm-list { list-style: none; margin: 0; padding: 0 4px; }

.dm-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  color: hsl(0deg 0% 20%);
  transition: background 120ms ease, box-shadow 120ms ease;
  line-height: 22px;
  font-size: 12px;
}

.dm-row:hover {
  background: hsl(0deg 0% 0% / 5%);
  box-shadow: inset 0 0 0 1px hsl(0deg 0% 0% / 8%);
}

.dm-row--active {
  background: hsl(228deg 56% 58% / 10%);
  box-shadow: inset 0 0 0 1px hsl(228deg 56% 58% / 18%);
}

.dm-presence {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dm-presence--online { background: hsl(143deg 55% 43%); }
.dm-presence--offline { background: hsl(0deg 0% 75%); }

.dm-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.unread-badge {
  flex-shrink: 0;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
  border-radius: 8px;
  background: hsl(217deg 64% 59%);
  color: white;
  font-variant-numeric: tabular-nums;
}

.dm-empty {
  padding: 12px 8px;
  font-size: 11px;
  color: hsl(0deg 0% 52%);
  text-align: center;
}
</style>
