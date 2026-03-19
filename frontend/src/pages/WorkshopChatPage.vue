<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { CirclePlus } from '@element-plus/icons-vue'
import { School, PanelRightOpen, PanelRightClose, MoreVertical } from 'lucide-vue-next'

import {
  ChannelBrowser,
  ChannelMemberList,
  ChatComposeBox,
  ChatMessageList,
  TopicCard,
  UserCardPopover,
} from '@/components/workshop-chat'
import type { UserCardUser } from '@/components/workshop-chat/UserCardPopover.vue'
import ChannelActionsPopover from '@/components/workshop-chat/ChannelActionsPopover.vue'
import WorkshopGearMenu from '@/components/workshop-chat/WorkshopGearMenu.vue'
import WorkshopPersonalMenu from '@/components/workshop-chat/WorkshopPersonalMenu.vue'
import ChannelSettingsDialog from '@/components/workshop-chat/ChannelSettingsDialog.vue'
import TopicEditDialog from '@/components/workshop-chat/TopicEditDialog.vue'
import { useLanguage } from '@/composables/useLanguage'
import { useWorkshopChatComposable } from '@/composables/useWorkshopChat'
import { useAuthStore } from '@/stores/auth'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import { apiRequest } from '@/utils/apiClient'

const { t } = useLanguage()
const store = useWorkshopChatStore()
const authStore = useAuthStore()
const ws = useWorkshopChatComposable()

const messageListRef = ref<InstanceType<typeof ChatMessageList>>()
const loadingMessages = ref(false)

const showNewTopicDialog = ref(false)
const newTopicTitle = ref('')
const newTopicDescription = ref('')
const creatingTopic = ref(false)

const isAdmin = computed(() => authStore.isAdmin)

const showRightSidebar = ref(true)
const showChannelSettings = ref(false)
const channelSettingsId = ref<number>(0)
const showTopicEdit = ref(false)
const topicEditMode = ref<'rename' | 'move'>('rename')
const topicEditId = ref(0)
const topicEditChannelId = ref(0)
const showChannelHeaderPopover = ref(false)
const contactPopoverUserId = ref<number | null>(null)

type CenterView = 'empty' | 'channel' | 'topic' | 'dm' | 'browse'

const centerView = computed<CenterView>(() => {
  if (store.showChannelBrowser) return 'browse'
  if (store.currentDMPartnerId) return 'dm'
  if (store.currentTopicId && store.currentChannelId) return 'topic'
  if (store.currentChannelId) return 'channel'
  return 'empty'
})

const currentTopicDetail = computed(() => {
  if (!store.currentTopicId) return null
  return store.topics.find(tp => tp.id === store.currentTopicId) ?? null
})

const currentDMPartner = computed(() => {
  if (!store.currentDMPartnerId) return null
  return store.dmConversations.find(c => c.partner_id === store.currentDMPartnerId) ?? null
})

const channelStatusConfig: Record<string, { labelKey: string; color: string }> = {
  open: { labelKey: 'workshop.statusOpen', color: '#22c55e' },
  in_progress: { labelKey: 'workshop.statusInProgress', color: '#eab308' },
  completed: { labelKey: 'workshop.statusCompleted', color: '#a8a29e' },
  archived: { labelKey: 'workshop.statusArchived', color: '#d6d3d1' },
}

const parentGroupName = computed(() => {
  if (!store.currentChannelId) return null
  const group = store.findParentGroup(store.currentChannelId)
  return group?.name ?? null
})

onMounted(async () => {
  store.loading = true
  await store.initializeDefaults()
  await Promise.all([
    store.fetchChannels(),
    store.fetchDMConversations(),
    store.fetchOrgMembers(),
  ])
  if (isAdmin.value) {
    store.fetchAdminOrgs()
  }
  ws.connect()
  store.loading = false
})

watch(() => store.currentChannelId, async (channelId) => {
  if (!channelId) return
  store.showChannelBrowser = false
  loadingMessages.value = true
  await Promise.all([
    store.fetchChannelMessages(channelId),
    store.fetchTopics(channelId),
    store.fetchChannelMembers(channelId),
  ])
  loadingMessages.value = false
})

watch(() => store.currentTopicId, async (topicId) => {
  if (!topicId || !store.currentChannelId) return
  loadingMessages.value = true
  await store.fetchTopicMessages(store.currentChannelId, topicId)
  loadingMessages.value = false
})

watch(() => store.currentDMPartnerId, async (partnerId) => {
  if (!partnerId) return
  store.showChannelBrowser = false
  loadingMessages.value = true
  await store.fetchDMMessages(partnerId)
  loadingMessages.value = false
})

watch(() => store.dialogChannelSettingsId, (id) => {
  if (id) {
    channelSettingsId.value = id
    showChannelSettings.value = true
    store.dialogChannelSettingsId = null
  }
})

watch(() => store.dialogTopicEdit, (editState) => {
  if (editState) {
    topicEditId.value = editState.topicId
    topicEditChannelId.value = editState.channelId
    topicEditMode.value = editState.mode
    showTopicEdit.value = true
    store.dialogTopicEdit = null
  }
})

async function handleSendChannelMessage(content: string): Promise<void> {
  if (!store.currentChannelId) return
  await apiRequest(`/api/chat/channels/${store.currentChannelId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  await store.fetchChannelMessages(store.currentChannelId)
  messageListRef.value?.scrollToBottom()
}

async function handleSendTopicMessage(content: string): Promise<void> {
  if (!store.currentChannelId || !store.currentTopicId) return
  await apiRequest(
    `/api/chat/channels/${store.currentChannelId}/topics/${store.currentTopicId}/messages`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    },
  )
  await store.fetchTopicMessages(store.currentChannelId, store.currentTopicId)
  messageListRef.value?.scrollToBottom()
}

async function handleSendDM(content: string): Promise<void> {
  if (!store.currentDMPartnerId) return
  await apiRequest(`/api/chat/dm/${store.currentDMPartnerId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  await store.fetchDMMessages(store.currentDMPartnerId)
  messageListRef.value?.scrollToBottom()
}

function handleSelectChannel(channelId: number): void {
  store.selectChannel(channelId)
  store.selectDMPartner(null)
  store.showChannelBrowser = false
}

function handleSelectTopic(channelId: number, topicId: number): void {
  store.selectChannel(channelId)
  store.selectTopic(topicId)
  store.selectDMPartner(null)
}

function handleSelectDM(partnerId: number): void {
  store.selectDMPartner(partnerId)
  store.selectChannel(null)
}

function handleBrowseChannels(): void {
  store.showChannelBrowser = true
  store.selectChannel(null)
  store.selectDMPartner(null)
}

function handleJoinChannel(channelId: number): void {
  store.joinChannel(channelId)
}

function handleLeaveChannel(channelId: number): void {
  store.leaveChannel(channelId)
  if (store.currentChannelId === channelId) {
    store.selectChannel(null)
  }
}

function handleStartDMPicker(): void {
  store.activeTab = 'dms'
  showRightSidebar.value = true
}

function handleStartDM(memberId: number): void {
  store.selectDMPartner(memberId)
  store.selectChannel(null)
  store.showChannelBrowser = false
  const existing = store.dmConversations.find(c => c.partner_id === memberId)
  if (!existing) {
    const member = store.orgMembers.find(m => m.id === memberId)
    if (member) {
      store.dmConversations.unshift({
        partner_id: member.id,
        partner_name: member.name,
        partner_avatar: member.avatar,
        last_message: { content: null, created_at: null, is_mine: false },
        unread_count: 0,
      })
    }
  }
}

async function handleCreateTopic(): Promise<void> {
  if (!store.currentChannelId || !newTopicTitle.value.trim()) return
  creatingTopic.value = true
  const body = {
    title: newTopicTitle.value.trim(),
    description: newTopicDescription.value.trim() || null,
  }

  await apiRequest(`/api/chat/channels/${store.currentChannelId}/topics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  await store.fetchTopics(store.currentChannelId)
  showNewTopicDialog.value = false
  newTopicTitle.value = ''
  newTopicDescription.value = ''
  creatingTopic.value = false
}

function handleTypingChannel(): void {
  if (store.currentChannelId) ws.sendTypingChannel(store.currentChannelId)
}

function handleTypingTopic(): void {
  if (store.currentChannelId && store.currentTopicId)
    ws.sendTypingTopic(store.currentChannelId, store.currentTopicId)
}

function handleTypingDM(): void {
  if (store.currentDMPartnerId) ws.sendTypingDM(store.currentDMPartnerId)
}

async function handleLoadMoreChannelMessages(): Promise<void> {
  if (!store.currentChannelId || store.channelMessages.length === 0) return
  const oldestId = store.channelMessages[0]?.id
  if (oldestId) {
    loadingMessages.value = true
    await store.fetchChannelMessages(store.currentChannelId, oldestId)
    loadingMessages.value = false
  }
}

async function handleLoadMoreTopicMessages(): Promise<void> {
  if (!store.currentChannelId || !store.currentTopicId || store.topicMessages.length === 0) return
  const oldestId = store.topicMessages[0]?.id
  if (oldestId) {
    loadingMessages.value = true
    await store.fetchTopicMessages(store.currentChannelId, store.currentTopicId, oldestId)
    loadingMessages.value = false
  }
}

async function handleSwitchSchool(orgId: number | null): Promise<void> {
  store.setAdminOrgId(orgId)
  store.selectChannel(null)
  store.loading = true
  await Promise.all([
    store.fetchChannels(),
    store.fetchOrgMembers(),
  ])
  store.loading = false
}

function handleSignOut(): void {
  authStore.logout()
}

function handleOpenChannelSettings(channelId: number): void {
  channelSettingsId.value = channelId
  showChannelSettings.value = true
}

function handleTopicRename(topicId: number): void {
  const topic = store.topics.find(tp => tp.id === topicId)
  topicEditId.value = topicId
  topicEditChannelId.value = topic?.channel_id ?? store.currentChannelId ?? 0
  topicEditMode.value = 'rename'
  showTopicEdit.value = true
}

function handleTopicMove(topicId: number): void {
  const topic = store.topics.find(tp => tp.id === topicId)
  topicEditId.value = topicId
  topicEditChannelId.value = topic?.channel_id ?? store.currentChannelId ?? 0
  topicEditMode.value = 'move'
  showTopicEdit.value = true
}
</script>

<template>
  <div class="ws-app">
    <!-- Top navbar -->
    <div class="ws-navbar">
      <div class="ws-navbar__left">
        <span class="ws-navbar__title">{{ t('workshop.title') }}</span>
      </div>

      <div class="ws-navbar__center">
        <input
          type="text"
          class="ws-navbar__search"
          :placeholder="t('workshop.searchMessages')"
        >
      </div>

      <div class="ws-navbar__right">
        <!-- Admin school switcher -->
        <el-select
          v-if="isAdmin && store.adminOrgs.length > 0"
          :model-value="store.adminOrgId"
          :placeholder="t('workshop.mySchool')"
          size="small"
          clearable
          class="ws-navbar__school-select"
          @change="handleSwitchSchool"
        >
          <template #prefix>
            <School class="w-3.5 h-3.5" style="color: hsl(0deg 0% 55%);" />
          </template>
          <el-option
            v-for="org in store.adminOrgs"
            :key="org.id"
            :label="org.name"
            :value="org.id"
          >
            <div class="flex items-center justify-between w-full">
              <span class="truncate">{{ org.name }}</span>
              <span class="text-xs ml-2 shrink-0" style="color: hsl(0deg 0% 55%);">{{ org.user_count }}</span>
            </div>
          </el-option>
        </el-select>

        <!-- Admin viewing indicator -->
        <span
          v-if="isAdmin && store.adminOrgId"
          class="ws-navbar__admin-badge"
        >
          {{ t('workshop.viewingSchool').replace('{0}', store.adminOrgs.find(o => o.id === store.adminOrgId)?.name || '') }}
        </span>

        <button
          class="ws-navbar__icon-btn"
          :class="{ 'ws-navbar__icon-btn--active': showRightSidebar }"
          @click="showRightSidebar = !showRightSidebar"
        >
          <component :is="showRightSidebar ? PanelRightClose : PanelRightOpen" :size="18" />
        </button>

        <WorkshopGearMenu />
        <WorkshopPersonalMenu @sign-out="handleSignOut" />
      </div>
    </div>

    <!-- Three-column main area -->
    <div class="ws-main">
      <!-- Center column -->
      <div class="ws-column-middle">
        <div class="ws-column-middle__inner">
          <!-- Empty state: nothing selected -->
          <template v-if="centerView === 'empty'">
            <div class="ws-empty-state">
              <div class="ws-empty-state__icon">💬</div>
              <p class="ws-empty-state__title">{{ t('workshop.title') }}</p>
              <p class="ws-empty-state__hint">{{ t('workshop.selectConversation') }}</p>
            </div>
          </template>

          <!-- Channel browser overlay -->
          <template v-else-if="centerView === 'browse'">
            <div class="ws-center-header">
              <h2 class="ws-center-header__title">{{ t('workshop.browseChannels') }}</h2>
            </div>
            <ChannelBrowser
              class="flex-1 overflow-y-auto"
              :channels="store.channels"
              :loading="store.loading"
              @select="handleSelectChannel"
              @join="handleJoinChannel"
              @leave="handleLeaveChannel"
            />
          </template>

          <!-- Channel view (lesson-study or announce) -->
          <template v-else-if="centerView === 'channel'">
            <div class="ws-center-header">
              <div class="ws-center-header__info">
                <span class="ws-center-header__channel-icon" :style="{ color: store.currentChannel?.color || undefined }">
                  #
                </span>
                <h2 class="ws-center-header__title">{{ store.currentChannel?.name }}</h2>
                <span v-if="parentGroupName" class="ws-center-header__group-tag">
                  {{ parentGroupName }}
                </span>
                <span
                  v-if="store.currentChannel?.status"
                  class="ws-status-badge"
                  :style="{
                    backgroundColor: (channelStatusConfig[store.currentChannel.status]?.color || '#a8a29e') + '20',
                    color: channelStatusConfig[store.currentChannel.status]?.color || '#a8a29e',
                  }"
                >
                  {{ t(channelStatusConfig[store.currentChannel.status]?.labelKey || 'workshop.statusOpen') }}
                </span>
                <span class="ws-center-header__meta">
                  {{ store.channelMembers.length }} {{ t('workshop.members') }}
                  · {{ store.topics.length }} {{ t('workshop.conversations') }}
                </span>
                <ChannelActionsPopover
                  v-if="store.currentChannelId"
                  :channel-id="store.currentChannelId"
                  :visible="showChannelHeaderPopover"
                  @update:visible="showChannelHeaderPopover = $event"
                  @open-settings="handleOpenChannelSettings(store.currentChannelId!)"
                >
                  <button class="ws-center-header__kebab">
                    <MoreVertical :size="16" />
                  </button>
                </ChannelActionsPopover>
              </div>
            </div>

            <!-- Topic list (conversations) — default channel view -->
            <div class="ws-topic-grid">
              <div class="ws-topic-grid__actions">
                <el-button
                  type="primary"
                  size="small"
                  @click="showNewTopicDialog = true"
                >
                  <el-icon class="mr-1"><CirclePlus /></el-icon>
                  {{ t('workshop.newConversation') }}
                </el-button>
              </div>
              <div v-if="store.topics.length > 0" class="ws-topic-grid__list">
                <TopicCard
                  v-for="topic in store.topics"
                  :key="topic.id"
                  :topic="topic"
                  @click="(topicId: number) => handleSelectTopic(store.currentChannelId!, topicId)"
                  @rename="handleTopicRename"
                  @move="handleTopicMove"
                />
              </div>
              <div v-else class="ws-topic-grid__empty">
                <p>{{ t('workshop.noConversationsYet') }}</p>
                <p class="ws-topic-grid__empty-hint">{{ t('workshop.startConversationHint') }}</p>
              </div>
            </div>
          </template>

          <!-- Topic (conversation) detail view -->
          <template v-else-if="centerView === 'topic' && currentTopicDetail">
            <div class="ws-center-header">
              <div class="ws-center-header__breadcrumb">
                <button
                  class="ws-breadcrumb-link"
                  @click="store.selectTopic(null)"
                >
                  <span :style="{ color: store.currentChannel?.color || undefined }">#</span>
                  {{ store.currentChannel?.name }}
                </button>
                <span class="ws-breadcrumb-sep">›</span>
                <span class="ws-breadcrumb-current">{{ currentTopicDetail.title }}</span>
              </div>
            </div>
            <ChatMessageList
              ref="messageListRef"
              :messages="store.topicMessages"
              :loading="loadingMessages"
              :channel-name="store.currentChannel?.name"
              :channel-type="store.currentChannel?.channel_type"
              :channel-color="store.currentChannel?.color"
              :topic-name="currentTopicDetail.title"
              @load-more="handleLoadMoreTopicMessages"
            />
            <ChatComposeBox
              mode="topic"
              :channel-name="store.currentChannel?.name"
              :channel-color="store.currentChannel?.color"
              :topic-name="currentTopicDetail.title"
              @send="handleSendTopicMessage"
              @typing="handleTypingTopic"
              @new-conversation="showNewTopicDialog = true"
              @new-d-m="handleStartDMPicker"
            />
          </template>

          <!-- DM view -->
          <template v-else-if="centerView === 'dm' && currentDMPartner">
            <div class="ws-center-header">
              <div class="ws-center-header__info">
                <span class="ws-center-header__dm-icon">
                  {{ currentDMPartner.partner_avatar || '👤' }}
                </span>
                <h2 class="ws-center-header__title">{{ currentDMPartner.partner_name }}</h2>
              </div>
            </div>
            <ChatMessageList
              ref="messageListRef"
              :messages="store.dmMessages as any"
              :loading="loadingMessages"
              :dm-partner-name="currentDMPartner.partner_name"
            />
            <ChatComposeBox
              mode="dm"
              :dm-partner-name="currentDMPartner.partner_name"
              @send="handleSendDM"
              @typing="handleTypingDM"
              @new-d-m="handleStartDMPicker"
            />
          </template>
        </div>
      </div>

      <!-- Right sidebar -->
      <div v-if="showRightSidebar" class="ws-column-right">
        <ChannelMemberList
          v-if="store.currentChannelId"
          @start-dm="handleStartDM"
        />
        <div v-else class="ws-right-contacts">
          <div class="ws-right-contacts__header">
            <span class="ws-right-contacts__label">{{ t('workshop.contacts') }}</span>
            <span class="ws-right-contacts__count">
              {{ store.orgMembers.filter(m => store.onlineUserIds.has(m.id) || store.idleUserIds.has(m.id)).length }} {{ t('workshop.online') }}
            </span>
          </div>
          <div class="ws-right-contacts__list">
            <div
              v-for="member in store.orgMembers"
              :key="member.id"
            >
              <UserCardPopover
                :user="{ id: member.id, name: member.name, avatar: member.avatar }"
                :visible="contactPopoverUserId === member.id"
                :channel-context="false"
                @update:visible="contactPopoverUserId = $event ? member.id : null"
                @start-dm="handleStartDM"
                @view-profile="() => {}"
              >
                <div class="ws-right-contacts__row">
                  <span
                    class="ws-right-contacts__presence"
                    :class="{
                      'ws-right-contacts__presence--online': store.onlineUserIds.has(member.id),
                      'ws-right-contacts__presence--idle': store.idleUserIds.has(member.id),
                      'ws-right-contacts__presence--offline': !store.onlineUserIds.has(member.id) && !store.idleUserIds.has(member.id),
                    }"
                  />
                  <span
                    class="ws-right-contacts__name"
                    :class="{ 'ws-right-contacts__name--online': store.onlineUserIds.has(member.id) || store.idleUserIds.has(member.id) }"
                  >
                    {{ member.name }}
                  </span>
                </div>
              </UserCardPopover>
            </div>
            <div v-if="store.orgMembers.length === 0" class="ws-right-contacts__empty">
              {{ t('workshop.noMembersFound') }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- New Conversation Dialog -->
    <el-dialog
      v-model="showNewTopicDialog"
      :title="t('workshop.newConversation')"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top" class="space-y-4">
        <el-form-item :label="t('workshop.conversationTitle')">
          <el-input v-model="newTopicTitle" :placeholder="t('workshop.conversationTitlePlaceholder')" maxlength="200" />
        </el-form-item>
        <el-form-item :label="t('workshop.topicDescription')">
          <el-input v-model="newTopicDescription" type="textarea" :rows="3" :placeholder="t('workshop.topicDescriptionPlaceholder')" maxlength="1000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewTopicDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creatingTopic" :disabled="!newTopicTitle.trim()" @click="handleCreateTopic">
          {{ t('workshop.create') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Channel Settings Dialog -->
    <ChannelSettingsDialog
      v-if="channelSettingsId"
      :channel-id="channelSettingsId"
      :visible="showChannelSettings"
      @update:visible="showChannelSettings = $event"
    />

    <!-- Topic Edit Dialog -->
    <TopicEditDialog
      v-if="topicEditId && topicEditChannelId"
      :visible="showTopicEdit"
      :mode="topicEditMode"
      :topic-id="topicEditId"
      :channel-id="topicEditChannelId"
      @update:visible="showTopicEdit = $event"
    />
  </div>
</template>

<style src="./workshop-chat-page.css" scoped></style>
