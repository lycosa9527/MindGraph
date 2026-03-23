<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useTimestamp } from '@vueuse/core'

import { ElMessage } from 'element-plus'

import { CirclePlus } from '@element-plus/icons-vue'

import { MoreVertical, School, Users } from 'lucide-vue-next'

import {
  ChannelBrowser,
  ChannelMemberList,
  ChatComposeBox,
  ChatMessageList,
  TopicCard,
  UserCardPopover,
} from '@/components/workshop-chat'
import ChannelActionsPopover from '@/components/workshop-chat/ChannelActionsPopover.vue'
import TeachingGroupLanding from '@/components/workshop-chat/TeachingGroupLanding.vue'
import WorkshopGearMenu from '@/components/workshop-chat/WorkshopGearMenu.vue'
import WorkshopInboxWelcome from '@/components/workshop-chat/WorkshopInboxWelcome.vue'
import WorkshopPersonalMenu from '@/components/workshop-chat/WorkshopPersonalMenu.vue'
import { useLanguage } from '@/composables/useLanguage'
import { useWorkshopChatComposable } from '@/composables/useWorkshopChat'
import { intlLocaleForUiCode } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import { useAuthStore } from '@/stores/auth'
import {
  type ChatMessage,
  type DirectMessageItem,
  type OrgMember,
  useWorkshopChatStore,
} from '@/stores/workshopChat'
import { apiRequest } from '@/utils/apiClient'
import { formatContactLastOnlineLabel } from '@/utils/formatContactLastOnline'
import { formatDeadlineRelative, lessonStudyDeadlineBadge } from '@/utils/lessonStudyDeadline'
import {
  normalizeWorkshopNarrowQuery,
  normalizeWorkshopRouteQuery,
  parseWorkshopChatRouteQuery,
  parseWorkshopMessageFocus,
  workshopChatHrefFromState,
  workshopQueryFromState,
  workshopRouteQueriesEqual,
} from '@/utils/workshopChatRoute'
import { LAST_SEEN_ONLINE_MAX_AGE_MS } from '@/utils/workshopContactLastSeenStorage'

const AccountInfoModal = defineAsyncComponent(
  () => import('@/components/auth/AccountInfoModal.vue')
)
const ChannelSettingsDialog = defineAsyncComponent(
  () => import('@/components/workshop-chat/ChannelSettingsDialog.vue')
)
const CreateChannelDialog = defineAsyncComponent(
  () => import('@/components/workshop-chat/CreateChannelDialog.vue')
)
const TeachingGroupsManageDialog = defineAsyncComponent(
  () => import('@/components/workshop-chat/TeachingGroupsManageDialog.vue')
)
const TopicEditDialog = defineAsyncComponent(
  () => import('@/components/workshop-chat/TopicEditDialog.vue')
)

const { t, currentLanguage } = useLanguage()

const intlLocale = computed(() => intlLocaleForUiCode(currentLanguage.value as LocaleCode))
const route = useRoute()
const router = useRouter()
const store = useWorkshopChatStore()
const authStore = useAuthStore()
const ws = useWorkshopChatComposable()

/** Ticks every minute so "online … ago" labels stay current. */
const nowMs = useTimestamp({ interval: 60_000 })

const applyingWorkshopRoute = ref(false)

const messageListRef = ref<InstanceType<typeof ChatMessageList>>()
const loadingMessages = ref(false)

const showNewTopicDialog = ref(false)
const newTopicTitle = ref('')
const newTopicDescription = ref('')
const creatingTopic = ref(false)

const isAdmin = computed(() => authStore.isAdmin)
const isManager = computed(() => authStore.isManager)

const showRightSidebar = ref(true)
const showChannelSettings = ref(false)
const channelSettingsId = ref<number>(0)
const showTopicEdit = ref(false)
const topicEditMode = ref<'rename' | 'move'>('rename')
const topicEditId = ref(0)
const topicEditChannelId = ref(0)
const showChannelHeaderPopover = ref(false)
const contactPopoverUserId = ref<number | null>(null)
const contactsSearchInput = ref('')
let contactsSearchDebounce: ReturnType<typeof setTimeout> | null = null
const loadingMoreContacts = ref(false)
const showAccountModal = ref(false)
const showTeachingGroupsManage = ref(false)

const messageSearchQuery = ref('')
const topicSearchServerResults = ref<ChatMessage[] | null>(null)
const dmSearchServerResults = ref<DirectMessageItem[] | null>(null)
const channelSearchServerResults = ref<ChatMessage[] | null>(null)
/** When opening a topic from channel search, load history around this message id. */
const pendingTopicFocusMessageId = ref<number | null>(null)
/** When opening main channel stream from search, anchor load around this message id. */
const pendingMainChannelFocusMessageId = ref<number | null>(null)
const pendingDmFocusMessageId = ref<number | null>(null)
/** When set, strip `message` query + hash after scroll (URL deep link only). */
const messageIdToStripFromUrlAfterFocus = ref<number | null>(null)
const TOPIC_FOCUS_NUM_BEFORE = 45
const TOPIC_FOCUS_NUM_AFTER = 25
const messageSearchLoading = ref(false)
let messageSearchDebounce: ReturnType<typeof setTimeout> | null = null

function clearMessageSearchDebounce(): void {
  if (messageSearchDebounce != null) {
    clearTimeout(messageSearchDebounce)
    messageSearchDebounce = null
  }
}
const workshopSettingsPanel = ref<null | 'notifications' | 'preferences'>(null)
const showShortcutsHelp = ref(false)
const contactProfileUserId = ref<number | null>(null)

const composeDraftKey = computed(() => {
  if (store.currentDMPartnerId != null) {
    return `dm:${store.currentDMPartnerId}`
  }
  if (store.currentChannelId != null && store.currentTopicId != null) {
    return `topic:${store.currentChannelId}:${store.currentTopicId}`
  }
  if (store.currentChannelId != null && store.mainChannelFeedActive) {
    return `channel-stream:${store.currentChannelId}`
  }
  return undefined
})

const settingsPanelTitle = computed(() => {
  if (workshopSettingsPanel.value === 'notifications') {
    return t('workshop.notifications')
  }
  if (workshopSettingsPanel.value === 'preferences') {
    return t('workshop.preferences')
  }
  return ''
})

const workshopSettingsDialogVisible = computed({
  get: () => workshopSettingsPanel.value !== null,
  set: (v: boolean) => {
    if (!v) workshopSettingsPanel.value = null
  },
})

const contactProfileMember = computed(() => {
  const id = contactProfileUserId.value
  if (id == null) return null
  return store.orgMembers.find((m) => m.id === id) ?? null
})

const contactProfileDialogVisible = computed({
  get: () => contactProfileUserId.value !== null,
  set: (v: boolean) => {
    if (!v) contactProfileUserId.value = null
  },
})

function filterMessagesBySearch<T extends { content: string }>(msgs: T[]): T[] {
  const q = messageSearchQuery.value.trim().toLowerCase()
  if (!q) return msgs
  return msgs.filter((m) => m.content.toLowerCase().includes(q))
}

const displayTopicMessages = computed((): ChatMessage[] => {
  const server = topicSearchServerResults.value
  if (server !== null) {
    return server
  }
  return filterMessagesBySearch(store.topicMessages)
})

const displayDmMessages = computed((): DirectMessageItem[] => {
  const server = dmSearchServerResults.value
  if (server !== null) {
    return server
  }
  return filterMessagesBySearch(store.dmMessages)
})

const displayChannelStreamMessages = computed((): ChatMessage[] =>
  filterMessagesBySearch(store.channelMessages)
)

const messageListLoading = computed(() => loadingMessages.value || messageSearchLoading.value)

const lessonStudyMetaChannel = computed(() => {
  const ch = store.currentChannel
  if (!ch?.parent_id) {
    return null
  }
  return ch
})

function copyAbsoluteWorkshopHref(state: Parameters<typeof workshopChatHrefFromState>[0]): void {
  const href = workshopChatHrefFromState(state)
  const url = `${window.location.origin}${href}`
  void navigator.clipboard.writeText(url).then(() => {
    ElMessage.success(t('workshop.linkCopied'))
  })
}

function onGearNavigate(page: string): void {
  if (page === 'notifications' || page === 'preferences') {
    workshopSettingsPanel.value = page
  }
}

/** Gear: 课例/频道设置 when a concrete channel is selected (not 教研组 landing-only). */
const showGearChannelSettings = computed(
  () =>
    authStore.isAdminOrManager &&
    store.activeTab === 'channels' &&
    store.currentDMPartnerId == null &&
    store.currentChannelId != null
)

function openChannelSettingsFromGear(): void {
  const id = store.currentChannelId ?? store.teachingGroupLandingId
  if (id == null) {
    ElMessage.info(t('workshop.selectChannelForSettings'))
    return
  }
  handleOpenChannelSettings(id)
}

function handleManageUserFromDirectory(_userId: number): void {
  void router.push({ name: 'Admin', query: { tab: 'users' } })
}

function onGlobalKeydown(ev: KeyboardEvent): void {
  if (ev.ctrlKey || ev.metaKey || ev.altKey) return
  const el = ev.target as HTMLElement | null
  if (!el) return
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
  if (el.isContentEditable) return
  if (ev.key === '?' || (ev.shiftKey && ev.key === '/')) {
    showShortcutsHelp.value = true
    ev.preventDefault()
  }
}

type CenterView =
  | 'empty'
  | 'inbox'
  | 'teaching-group'
  | 'channel'
  | 'channel-stream'
  | 'topic'
  | 'dm'
  | 'browse'

const centerView = computed<CenterView>(() => {
  if (store.workshopHomeViewActive) return 'inbox'
  if (store.showChannelBrowser) return 'browse'
  if (store.currentDMPartnerId) return 'dm'
  if (store.currentTopicId && store.currentChannelId) return 'topic'
  if (store.currentChannelId && store.mainChannelFeedActive && store.currentTopicId == null) {
    return 'channel-stream'
  }
  if (store.currentChannelId) return 'channel'
  if (store.teachingGroupLandingId != null) return 'teaching-group'
  return 'empty'
})

const lessonStudyChannelHeaderLine = computed(() => {
  const ch = lessonStudyMetaChannel.value
  if (!ch || (centerView.value !== 'channel' && centerView.value !== 'channel-stream')) {
    return null
  }
  const badge = lessonStudyDeadlineBadge(ch)
  if (badge.kind === 'done') {
    return t('workshop.deadlineBadgeDone')
  }
  if (!ch.deadline) {
    return t('workshop.lessonStudyNoDeadline')
  }
  const rel = formatDeadlineRelative(ch.deadline, intlLocale.value)
  if (badge.kind === 'overdue') {
    return `${t('workshop.lessonStudyDue')}: ${rel} (${t('workshop.deadlineBadgeOverdue')})`
  }
  if (badge.kind === 'soon') {
    return `${t('workshop.lessonStudyDue')}: ${rel}`
  }
  return `${t('workshop.lessonStudyDue')}: ${rel}`
})

const lessonStudyTopicBannerLine = computed(() => {
  const ch = lessonStudyMetaChannel.value
  if (!ch || centerView.value !== 'topic') {
    return null
  }
  const badge = lessonStudyDeadlineBadge(ch)
  if (badge.kind === 'done') {
    return t('workshop.deadlineBadgeDone')
  }
  if (!ch.deadline) {
    return t('workshop.lessonStudyNoDeadline')
  }
  const rel = formatDeadlineRelative(ch.deadline, intlLocale.value)
  if (badge.kind === 'overdue') {
    return `${t('workshop.lessonStudyDue')}: ${rel} · ${t('workshop.deadlineBadgeOverdue')}`
  }
  return `${t('workshop.lessonStudyDue')}: ${rel}`
})

watch(
  () => [store.currentChannelId, store.currentTopicId, store.currentDMPartnerId] as const,
  () => {
    clearMessageSearchDebounce()
    topicSearchServerResults.value = null
    dmSearchServerResults.value = null
    channelSearchServerResults.value = null
    messageSearchLoading.value = false
  }
)

watch(
  [
    messageSearchQuery,
    centerView,
    () => store.currentChannelId,
    () => store.currentTopicId,
    () => store.currentDMPartnerId,
  ],
  () => {
    clearMessageSearchDebounce()
    const view = centerView.value
    const q = messageSearchQuery.value.trim()

    if (view !== 'topic' && view !== 'dm' && view !== 'channel') {
      topicSearchServerResults.value = null
      dmSearchServerResults.value = null
      channelSearchServerResults.value = null
      messageSearchLoading.value = false
      return
    }

    if (q.length < 2) {
      topicSearchServerResults.value = null
      dmSearchServerResults.value = null
      channelSearchServerResults.value = null
      messageSearchLoading.value = false
      return
    }

    const ch = store.currentChannelId
    const tp = store.currentTopicId
    const dmPid = store.currentDMPartnerId

    messageSearchDebounce = setTimeout(() => {
      messageSearchDebounce = null
      void (async () => {
        messageSearchLoading.value = true
        try {
          if (view === 'topic' && ch != null && tp != null) {
            const rows = await store.searchTopicMessages(ch, tp, q)
            if (
              messageSearchQuery.value.trim() === q &&
              centerView.value === 'topic' &&
              store.currentChannelId === ch &&
              store.currentTopicId === tp
            ) {
              topicSearchServerResults.value = rows
              dmSearchServerResults.value = null
              channelSearchServerResults.value = null
            }
          } else if (view === 'dm' && dmPid != null) {
            const rows = await store.searchDMMessages(dmPid, q)
            if (
              messageSearchQuery.value.trim() === q &&
              centerView.value === 'dm' &&
              store.currentDMPartnerId === dmPid
            ) {
              dmSearchServerResults.value = rows
              topicSearchServerResults.value = null
              channelSearchServerResults.value = null
            }
          } else if (view === 'channel' && ch != null) {
            const rows = await store.searchChannelMessages(ch, q)
            if (
              messageSearchQuery.value.trim() === q &&
              centerView.value === 'channel' &&
              store.currentChannelId === ch
            ) {
              channelSearchServerResults.value = rows
              topicSearchServerResults.value = null
              dmSearchServerResults.value = null
            }
          }
        } finally {
          messageSearchLoading.value = false
        }
      })()
    }, 300)
  }
)

const currentTopicDetail = computed(() => {
  if (!store.currentTopicId) return null
  return store.topics.find((tp) => tp.id === store.currentTopicId) ?? null
})

const currentDMPartner = computed(() => {
  if (!store.currentDMPartnerId) return null
  return store.dmConversations.find((c) => c.partner_id === store.currentDMPartnerId) ?? null
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

const selfContactUserId = computed(() => Number(authStore.user?.id) || 0)

/** Max of server `last_seen_at` and client-observed disconnect time. */
function effectiveContactLastSeenMs(memberId: number): number | undefined {
  const member = store.orgMembers.find((m) => m.id === memberId)
  let serverMs: number | undefined
  if (member?.last_seen_at) {
    const parsed = Date.parse(member.last_seen_at)
    if (!Number.isNaN(parsed)) {
      serverMs = parsed
    }
  }
  const localMs = store.lastSeenOnlineAtByUserId[memberId]
  if (serverMs === undefined && localMs === undefined) {
    return undefined
  }
  if (serverMs === undefined) {
    return localMs
  }
  if (localMs === undefined) {
    return serverMs
  }
  return Math.max(serverMs, localMs)
}

function contactPresenceRank(memberId: number): number {
  void nowMs.value
  if (store.onlineUserIds.has(memberId)) {
    return 0
  }
  const ts = effectiveContactLastSeenMs(memberId)
  if (
    ts !== undefined &&
    nowMs.value - ts >= 0 &&
    nowMs.value - ts <= LAST_SEEN_ONLINE_MAX_AGE_MS
  ) {
    return 1
  }
  return 2
}

function sortContactsWithSelfFirst(members: OrgMember[]): OrgMember[] {
  const sid = selfContactUserId.value
  const copy = [...members]
  copy.sort((a, b) => {
    const d = contactPresenceRank(a.id) - contactPresenceRank(b.id)
    if (d !== 0) return d
    if (sid) {
      if (a.id === sid) return -1
      if (b.id === sid) return 1
    }
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })
  return copy
}

/** Recently online: most recently seen first (after self). */
function sortRecentlyContactsWithSelfFirst(members: OrgMember[]): OrgMember[] {
  const sid = selfContactUserId.value
  const copy = [...members]
  copy.sort((a, b) => {
    if (sid) {
      if (a.id === sid) return -1
      if (b.id === sid) return 1
    }
    const ta = effectiveContactLastSeenMs(a.id) ?? 0
    const tb = effectiveContactLastSeenMs(b.id) ?? 0
    return tb - ta
  })
  return copy
}

const contactsOnline = computed(() => {
  void nowMs.value
  const list = store.orgMembers.filter((m) => contactPresenceRank(m.id) === 0)
  return sortContactsWithSelfFirst(list)
})

const contactsRecentlyOnline = computed(() => {
  void nowMs.value
  const list = store.orgMembers.filter((m) => contactPresenceRank(m.id) === 1)
  return sortRecentlyContactsWithSelfFirst(list)
})

const contactsOffline = computed(() => {
  void nowMs.value
  const list = store.orgMembers.filter((m) => contactPresenceRank(m.id) === 2)
  return sortContactsWithSelfFirst(list)
})

const contactsOnlineCount = computed(
  () => store.orgMembers.filter((m) => store.onlineUserIds.has(m.id)).length
)

function isContactSelf(memberId: number): boolean {
  const sid = selfContactUserId.value
  return sid !== 0 && memberId === sid
}

function contactLastOnlineSubtitle(memberId: number): string {
  void nowMs.value
  const ts = effectiveContactLastSeenMs(memberId)
  if (ts === undefined) {
    return ''
  }
  return formatContactLastOnlineLabel(ts, nowMs.value, t)
}

interface ContactSection {
  key: string
  labelKey: string | null
  members: OrgMember[]
}

const contactSections = computed((): ContactSection[] => {
  void nowMs.value
  const on = contactsOnline.value
  const recent = contactsRecentlyOnline.value
  const off = contactsOffline.value
  const sections: ContactSection[] = []
  if (on.length > 0) {
    sections.push({
      key: 'online',
      labelKey: 'workshop.contactsOnlineNow',
      members: on,
    })
  }
  if (recent.length > 0) {
    sections.push({
      key: 'recently_online',
      labelKey: 'workshop.contactsRecentlyOnline',
      members: recent,
    })
  }
  if (off.length > 0) {
    sections.push({
      key: 'offline',
      labelKey: 'workshop.contactsOffline',
      members: off,
    })
  }
  return sections
})

watch(contactsSearchInput, (val) => {
  if (contactsSearchDebounce != null) {
    clearTimeout(contactsSearchDebounce)
  }
  contactsSearchDebounce = setTimeout(async () => {
    contactsSearchDebounce = null
    const q = val.trim()
    await store.fetchOrgMembers({ q, offset: 0, limit: 200 })
  }, 350)
})

async function loadMoreContacts(): Promise<void> {
  if (!store.orgMembersHasMore || loadingMoreContacts.value) {
    return
  }
  loadingMoreContacts.value = true
  try {
    await store.fetchOrgMembers({
      q: store.orgMembersListQuery,
      offset: store.orgMembers.length,
      append: true,
      limit: 200,
    })
  } finally {
    loadingMoreContacts.value = false
  }
}

function applyOrgScopeFromProfile(): void {
  const raw = authStore.user?.schoolId
  if (!raw) return
  const id = parseInt(raw, 10)
  if (!Number.isNaN(id)) {
    store.setAdminOrgId(id)
  }
}

function resolveAdminOrgSelection(): void {
  if (!isAdmin.value || store.adminOrgs.length === 0) return
  const valid = new Set(store.adminOrgs.map((o) => o.id))
  if (store.adminOrgId != null && valid.has(store.adminOrgId)) return
  const raw = authStore.user?.schoolId
  const sid = raw ? parseInt(raw, 10) : NaN
  const byProfile = !Number.isNaN(sid) ? store.adminOrgs.find((o) => o.id === sid) : undefined
  store.setAdminOrgId((byProfile ?? store.adminOrgs[0]).id)
}

function syncWorkshopUrlFromStore(): void {
  if (applyingWorkshopRoute.value) return
  const next = workshopQueryFromState({
    currentChannelId: store.currentChannelId,
    currentTopicId: store.currentTopicId,
    currentDMPartnerId: store.currentDMPartnerId,
    showChannelBrowser: store.showChannelBrowser,
    workshopHomeViewActive: store.workshopHomeViewActive,
    mainChannelFeedActive: store.mainChannelFeedActive,
    teachingGroupLandingId: store.teachingGroupLandingId,
  })
  const cur = normalizeWorkshopNarrowQuery(route.query)
  if (workshopRouteQueriesEqual(cur, next)) return
  router.replace({ name: 'WorkshopChat', query: next })
}

function stripWorkshopMessageFromUserUrl(): void {
  const next = normalizeWorkshopRouteQuery(route.query)
  delete next.message
  void router.replace({ name: 'WorkshopChat', query: next, hash: '' })
}

function maybeStripMessageFromUrlAfterFocus(expectedId: number): void {
  if (messageIdToStripFromUrlAfterFocus.value === expectedId) {
    messageIdToStripFromUrlAfterFocus.value = null
    stripWorkshopMessageFromUserUrl()
  }
}

async function applyWorkshopRouteFromQuery(): Promise<void> {
  applyingWorkshopRoute.value = true
  try {
    const parsed = parseWorkshopChatRouteQuery(route.query)
    const msgFocus = parseWorkshopMessageFocus(route)
    messageIdToStripFromUrlAfterFocus.value = null
    switch (parsed.kind) {
      case 'home':
        store.openWorkshopInboxHome()
        break
      case 'browse':
        store.leaveWorkshopHomeView()
        store.showChannelBrowser = true
        store.selectChannel(null)
        store.selectDMPartner(null)
        break
      case 'teachingGroup': {
        const g = store.findChannelById(parsed.groupId)
        if (!g || g.parent_id != null || g.channel_type === 'announce') {
          store.openWorkshopInboxHome()
          void router.replace({ name: 'WorkshopChat', query: {} })
          break
        }
        store.showChannelBrowser = false
        await store.openTeachingGroupLanding(parsed.groupId)
        store.activeTab = 'channels'
        break
      }
      case 'dm': {
        store.showChannelBrowser = false
        if (msgFocus != null) {
          pendingDmFocusMessageId.value = msgFocus
          messageIdToStripFromUrlAfterFocus.value = msgFocus
        }
        store.selectDMPartner(parsed.partnerId)
        store.selectChannel(null)
        store.activeTab = 'dms'
        break
      }
      case 'channel': {
        const ch = store.findChannelById(parsed.channelId)
        if (!ch) {
          store.openWorkshopInboxHome()
          void router.replace({ name: 'WorkshopChat', query: {} })
          break
        }
        store.showChannelBrowser = false
        store.selectChannel(parsed.channelId)
        if (parsed.topicId != null) {
          if (msgFocus != null) {
            pendingTopicFocusMessageId.value = msgFocus
            messageIdToStripFromUrlAfterFocus.value = msgFocus
          }
          store.selectTopic(parsed.topicId)
        } else if (parsed.mainStream) {
          if (msgFocus != null) {
            pendingMainChannelFocusMessageId.value = msgFocus
            messageIdToStripFromUrlAfterFocus.value = msgFocus
          }
          store.openMainChannelFeed()
        }
        break
      }
    }
  } finally {
    applyingWorkshopRoute.value = false
  }
}

onMounted(async () => {
  store.loading = true
  applyOrgScopeFromProfile()
  if (isAdmin.value) {
    await store.fetchAdminOrgs()
    resolveAdminOrgSelection()
  }
  await store.initializeDefaults()
  await Promise.all([store.fetchChannels(), store.fetchDMConversations(), store.fetchOrgMembers()])
  await applyWorkshopRouteFromQuery()
  store.hydrateLastSeenOnlineFromStorage()
  ws.connect()
  store.loading = false
  window.addEventListener('keydown', onGlobalKeydown)
})

onUnmounted(() => {
  clearMessageSearchDebounce()
  window.removeEventListener('keydown', onGlobalKeydown)
})

watch(
  () => ({
    currentChannelId: store.currentChannelId,
    currentTopicId: store.currentTopicId,
    currentDMPartnerId: store.currentDMPartnerId,
    showChannelBrowser: store.showChannelBrowser,
    workshopHomeViewActive: store.workshopHomeViewActive,
    mainChannelFeedActive: store.mainChannelFeedActive,
    teachingGroupLandingId: store.teachingGroupLandingId,
  }),
  () => {
    if (store.loading) return
    syncWorkshopUrlFromStore()
  },
  { deep: true }
)

watch(
  () => route.query,
  (q) => {
    if (store.loading || applyingWorkshopRoute.value) return
    const newQ = normalizeWorkshopNarrowQuery(q)
    const fromStore = workshopQueryFromState({
      currentChannelId: store.currentChannelId,
      currentTopicId: store.currentTopicId,
      currentDMPartnerId: store.currentDMPartnerId,
      showChannelBrowser: store.showChannelBrowser,
      workshopHomeViewActive: store.workshopHomeViewActive,
      mainChannelFeedActive: store.mainChannelFeedActive,
      teachingGroupLandingId: store.teachingGroupLandingId,
    })
    if (workshopRouteQueriesEqual(newQ, fromStore)) return
    void applyWorkshopRouteFromQuery()
  },
  { deep: true }
)

watch(
  () => store.currentChannelId,
  async (channelId, prevChannelId) => {
    if (prevChannelId != null && channelId !== prevChannelId) {
      pendingTopicFocusMessageId.value = null
      pendingMainChannelFocusMessageId.value = null
      pendingDmFocusMessageId.value = null
      messageIdToStripFromUrlAfterFocus.value = null
    }
    if (!channelId) {
      pendingTopicFocusMessageId.value = null
      pendingMainChannelFocusMessageId.value = null
      if (store.currentDMPartnerId == null) {
        pendingDmFocusMessageId.value = null
        messageIdToStripFromUrlAfterFocus.value = null
      }
      return
    }
    pendingDmFocusMessageId.value = null
    store.showChannelBrowser = false
    loadingMessages.value = true
    await Promise.all([
      store.fetchChannelMessages(channelId),
      store.fetchTopics(channelId),
      store.fetchChannelMembers(channelId),
    ])
    loadingMessages.value = false
  }
)

watch(
  () => store.currentTopicId,
  async (topicId) => {
    if (!topicId || !store.currentChannelId) return
    const focusId = pendingTopicFocusMessageId.value
    pendingTopicFocusMessageId.value = null
    loadingMessages.value = true
    try {
      if (focusId != null) {
        await store.fetchTopicMessages(
          store.currentChannelId,
          topicId,
          focusId,
          TOPIC_FOCUS_NUM_BEFORE,
          TOPIC_FOCUS_NUM_AFTER
        )
      } else {
        await store.fetchTopicMessages(store.currentChannelId, topicId)
      }
      await store.markTopicRead(store.currentChannelId, topicId)
    } finally {
      loadingMessages.value = false
    }
    if (focusId != null) {
      await nextTick()
      messageListRef.value?.scrollToMessageId(focusId)
      maybeStripMessageFromUrlAfterFocus(focusId)
    }
  }
)

watch(
  () => store.currentDMPartnerId,
  async (partnerId) => {
    if (partnerId != null) {
      pendingTopicFocusMessageId.value = null
      pendingMainChannelFocusMessageId.value = null
    }
    if (!partnerId) return
    const focusDm = pendingDmFocusMessageId.value
    pendingDmFocusMessageId.value = null
    store.showChannelBrowser = false
    loadingMessages.value = true
    try {
      if (focusDm != null) {
        await store.fetchDMMessages(
          partnerId,
          focusDm,
          TOPIC_FOCUS_NUM_BEFORE,
          TOPIC_FOCUS_NUM_AFTER
        )
      } else {
        await store.fetchDMMessages(partnerId)
      }
    } finally {
      loadingMessages.value = false
    }
    if (focusDm != null) {
      await nextTick()
      messageListRef.value?.scrollToMessageId(focusDm)
      maybeStripMessageFromUrlAfterFocus(focusDm)
    }
  }
)

watch(
  () => store.dialogChannelSettingsId,
  (id) => {
    if (id) {
      channelSettingsId.value = id
      showChannelSettings.value = true
      store.dialogChannelSettingsId = null
    }
  }
)

watch(
  () => store.dialogTopicEdit,
  (editState) => {
    if (editState) {
      topicEditId.value = editState.topicId
      topicEditChannelId.value = editState.channelId
      topicEditMode.value = editState.mode
      showTopicEdit.value = true
      store.dialogTopicEdit = null
    }
  }
)

watch(
  () => store.newTopicDialogRequestChannelId,
  (channelId) => {
    if (channelId == null) {
      return
    }
    store.selectChannel(channelId)
    store.selectTopic(null)
    newTopicTitle.value = ''
    newTopicDescription.value = ''
    showNewTopicDialog.value = true
    store.clearNewTopicDialogRequest()
  }
)

watch(
  () => [store.mainChannelFeedActive, store.currentChannelId] as const,
  async ([feed, ch]) => {
    if (!feed || !ch) return
    const focusId = pendingMainChannelFocusMessageId.value
    if (focusId == null) return
    pendingMainChannelFocusMessageId.value = null
    loadingMessages.value = true
    try {
      await store.fetchChannelMessages(ch, focusId, TOPIC_FOCUS_NUM_BEFORE, TOPIC_FOCUS_NUM_AFTER)
    } finally {
      loadingMessages.value = false
    }
    await nextTick()
    messageListRef.value?.scrollToMessageId(focusId)
    maybeStripMessageFromUrlAfterFocus(focusId)
  }
)

async function showSendMentionError(res: Response): Promise<boolean> {
  try {
    const data = (await res.json()) as {
      detail?: { code?: string; unknown?: string[]; ambiguous?: string[] }
    }
    const d = data.detail
    if (d?.code === 'invalid_mentions') {
      const parts: string[] = []
      if (d.unknown?.length) {
        parts.push(t('workshop.mentionUnknown').replace('{0}', d.unknown.join(', ')))
      }
      if (d.ambiguous?.length) {
        parts.push(t('workshop.mentionAmbiguous').replace('{0}', d.ambiguous.join(', ')))
      }
      ElMessage.warning(parts.join(' · ') || t('workshop.messageSendFailed'))
      return true
    }
  } catch {
    /* ignore parse errors */
  }
  return false
}

async function handleSendChannelMessage(content: string): Promise<void> {
  if (!store.currentChannelId) return
  const res = await apiRequest(`/api/chat/channels/${store.currentChannelId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) {
    if (!(await showSendMentionError(res))) {
      ElMessage.error(t('workshop.messageSendFailed'))
    }
    return
  }
  await store.fetchChannelMessages(store.currentChannelId)
  messageListRef.value?.scrollToBottom()
}

async function handleSendTopicMessage(content: string): Promise<void> {
  if (!store.currentChannelId || !store.currentTopicId) return
  if (store.currentChannel?.channel_type === 'announce' && !isAdmin.value) return
  const res = await apiRequest(
    `/api/chat/channels/${store.currentChannelId}/topics/${store.currentTopicId}/messages`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    }
  )
  if (!res.ok) {
    if (!(await showSendMentionError(res))) {
      ElMessage.error(t('workshop.messageSendFailed'))
    }
    return
  }
  await store.fetchTopicMessages(store.currentChannelId, store.currentTopicId)
  messageListRef.value?.scrollToBottom()
}

async function handleSendDM(content: string): Promise<void> {
  if (!store.currentDMPartnerId) return
  const res = await apiRequest(`/api/chat/dm/${store.currentDMPartnerId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) {
    if (!(await showSendMentionError(res))) {
      ElMessage.error(t('workshop.messageSendFailed'))
    }
    return
  }
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

const CHANNEL_SEARCH_SNIPPET_LEN = 140

function workshopMessageSnippet(content: string): string {
  const one = content.replace(/\s+/g, ' ').trim()
  if (one.length <= CHANNEL_SEARCH_SNIPPET_LEN) {
    return one
  }
  return `${one.slice(0, CHANNEL_SEARCH_SNIPPET_LEN)}…`
}

function topicTitleForChannelSearchHit(msg: ChatMessage): string {
  if (msg.topic_id == null) {
    return t('workshop.mainChannelStream')
  }
  const tp = store.topics.find((x) => x.id === msg.topic_id)
  return tp?.title ?? t('workshop.selectTopic')
}

function formatSearchHitTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function handleChannelSearchHitClick(msg: ChatMessage): void {
  const cid = store.currentChannelId
  if (cid == null) {
    return
  }
  if (msg.topic_id == null) {
    if (store.currentChannelId === cid && store.mainChannelFeedActive) {
      void (async () => {
        loadingMessages.value = true
        try {
          await store.fetchChannelMessages(
            cid,
            msg.id,
            TOPIC_FOCUS_NUM_BEFORE,
            TOPIC_FOCUS_NUM_AFTER
          )
        } finally {
          loadingMessages.value = false
        }
        await nextTick()
        messageListRef.value?.scrollToMessageId(msg.id)
      })()
      return
    }
    pendingMainChannelFocusMessageId.value = msg.id
    store.openMainChannelFeed()
    return
  }
  const focusTopicId = msg.topic_id
  if (
    store.currentChannelId === cid &&
    store.currentTopicId === focusTopicId &&
    focusTopicId != null
  ) {
    void (async () => {
      loadingMessages.value = true
      try {
        await store.fetchTopicMessages(
          cid,
          focusTopicId,
          msg.id,
          TOPIC_FOCUS_NUM_BEFORE,
          TOPIC_FOCUS_NUM_AFTER
        )
        await store.markTopicRead(cid, focusTopicId)
      } finally {
        loadingMessages.value = false
      }
      await nextTick()
      messageListRef.value?.scrollToMessageId(msg.id)
    })()
    return
  }
  pendingTopicFocusMessageId.value = msg.id
  handleSelectTopic(cid, msg.topic_id)
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
  if (selfContactUserId.value && memberId === selfContactUserId.value) return
  store.selectDMPartner(memberId)
  store.selectChannel(null)
  store.showChannelBrowser = false
  const existing = store.dmConversations.find((c) => c.partner_id === memberId)
  if (!existing) {
    const member = store.orgMembers.find((m) => m.id === memberId)
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
  await store.fetchTopics(store.currentChannelId, { force: true })
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
  if (topicSearchServerResults.value !== null) return
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
  await Promise.all([store.fetchChannels(), store.fetchOrgMembers()])
  store.loading = false
  store.openWorkshopInboxHome()
}

function handleSignOut(): void {
  authStore.logout()
}

function handlePersonalNavigate(page: string): void {
  if (page === 'profile') {
    showAccountModal.value = true
  }
}

function handleContactViewProfile(userId: number): void {
  if (String(userId) === authStore.user?.id) {
    showAccountModal.value = true
    return
  }
  contactProfileUserId.value = userId
}

function handleOpenChannelSettings(channelId: number): void {
  channelSettingsId.value = channelId
  showChannelSettings.value = true
}

function handleTopicRename(topicId: number): void {
  const topic = store.topics.find((tp) => tp.id === topicId)
  topicEditId.value = topicId
  topicEditChannelId.value = topic?.channel_id ?? store.currentChannelId ?? 0
  topicEditMode.value = 'rename'
  showTopicEdit.value = true
}

function handleTopicMove(topicId: number): void {
  const topic = store.topics.find((tp) => tp.id === topicId)
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
          v-model="messageSearchQuery"
          type="search"
          class="ws-navbar__search"
          :placeholder="t('workshop.searchMessages')"
          autocomplete="off"
        />
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
            <School
              class="w-3.5 h-3.5"
              style="color: hsl(0deg 0% 55%)"
            />
          </template>
          <el-option
            v-for="org in store.adminOrgs"
            :key="org.id"
            :label="org.name"
            :value="org.id"
          >
            <div class="flex items-center justify-between w-full">
              <span class="truncate">{{ org.name }}</span>
              <span
                class="text-xs ml-2 shrink-0"
                style="color: hsl(0deg 0% 55%)"
                >{{ org.user_count }}</span
              >
            </div>
          </el-option>
        </el-select>

        <span
          v-if="isManager && authStore.user?.schoolName && !isAdmin"
          class="ws-navbar__admin-badge"
        >
          {{ authStore.user.schoolName }}
        </span>

        <div class="ws-navbar__action-group">
          <el-button
            size="small"
            class="workshop-navbar-action workshop-navbar-action--contacts"
            :class="{ 'workshop-navbar-action--active': showRightSidebar }"
            :title="t('workshop.toggleContacts')"
            @click="showRightSidebar = !showRightSidebar"
          >
            <span class="workshop-navbar-action__content">
              <Users
                class="workshop-navbar-action__icon"
                :size="14"
              />
              <span class="workshop-navbar-action__label">{{ t('workshop.navbarContacts') }}</span>
            </span>
          </el-button>

          <WorkshopGearMenu
            :show-channel-settings="showGearChannelSettings"
            @navigate="onGearNavigate"
            @openChannelSettings="openChannelSettingsFromGear"
            @manageTeachingGroups="showTeachingGroupsManage = true"
          />
          <WorkshopPersonalMenu
            @navigate="handlePersonalNavigate"
            @sign-out="handleSignOut"
          />
        </div>
      </div>
    </div>

    <!-- Three-column main area -->
    <div class="ws-main">
      <!-- Center column -->
      <div class="ws-column-middle">
        <div class="ws-column-middle__inner">
          <!-- Inbox + welcome (default landing) -->
          <template v-if="centerView === 'inbox'">
            <WorkshopInboxWelcome />
          </template>

          <!-- Teaching group (教研组): overview of lesson studies + conversations (Zulip stream narrow) -->
          <template v-else-if="centerView === 'teaching-group'">
            <TeachingGroupLanding />
          </template>

          <!-- Empty state: nothing selected -->
          <template v-else-if="centerView === 'empty'">
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

          <!-- Main channel stream (messages without a topic) -->
          <template v-else-if="centerView === 'channel-stream' && store.currentChannel">
            <div class="ws-center-header">
              <div class="ws-center-header__info ws-center-header__info--with-back">
                <button
                  type="button"
                  class="ws-back-to-conversations"
                  @click="store.leaveMainChannelFeed()"
                >
                  {{ t('workshop.backToConversations') }}
                </button>
                <span
                  class="ws-center-header__channel-icon"
                  :style="{ color: store.currentChannel.color || undefined }"
                >
                  #
                </span>
                <h2 class="ws-center-header__title">{{ store.currentChannel.name }}</h2>
                <span
                  v-if="parentGroupName"
                  class="ws-center-header__group-tag"
                >
                  {{ parentGroupName }}
                </span>
                <span
                  v-if="store.currentChannel.status"
                  class="ws-status-badge"
                  :style="{
                    backgroundColor:
                      (channelStatusConfig[store.currentChannel.status]?.color || '#a8a29e') + '20',
                    color: channelStatusConfig[store.currentChannel.status]?.color || '#a8a29e',
                  }"
                >
                  {{
                    t(
                      channelStatusConfig[store.currentChannel.status]?.labelKey ||
                        'workshop.statusOpen'
                    )
                  }}
                </span>
                <span class="ws-center-header__meta">
                  {{ store.channelMembers.length }} {{ t('workshop.members') }} ·
                  {{ t('workshop.mainChannelStream') }}
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
              <p
                v-if="lessonStudyChannelHeaderLine"
                class="ws-center-header__lesson-line"
              >
                {{ lessonStudyChannelHeaderLine }}
              </p>
            </div>
            <ChatMessageList
              ref="messageListRef"
              :messages="displayChannelStreamMessages"
              :loading="loadingMessages"
              :channel-name="store.currentChannel.name"
              :channel-type="store.currentChannel.channel_type"
              :channel-color="store.currentChannel.color"
              :topic-name="t('workshop.mainChannelStream')"
              @load-more="handleLoadMoreChannelMessages"
              @back-to-topic-list="store.leaveMainChannelFeed()"
            >
              <template #recipientActions>
                <el-dropdown
                  trigger="click"
                  @click.stop
                >
                  <button
                    type="button"
                    class="recipient-bar__menu-btn"
                    :title="t('workshop.more')"
                  >
                    <MoreVertical :size="16" />
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        @click="
                          copyAbsoluteWorkshopHref({
                            currentChannelId: store.currentChannelId,
                            currentTopicId: null,
                            currentDMPartnerId: null,
                            showChannelBrowser: false,
                            workshopHomeViewActive: false,
                            mainChannelFeedActive: true,
                          })
                        "
                      >
                        {{ t('workshop.copyLink') }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        @click="void store.markChannelReadAll(store.currentChannelId!)"
                      >
                        {{ t('workshop.markAsRead') }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </ChatMessageList>
            <ChatComposeBox
              mode="channel"
              :draft-key="composeDraftKey"
              :channel-name="store.currentChannel.name"
              :channel-color="store.currentChannel.color"
              :allow-send="store.currentChannel.channel_type !== 'announce' || isAdmin"
              @send="handleSendChannelMessage"
              @typing="handleTypingChannel"
              @new-conversation="showNewTopicDialog = true"
              @new-d-m="handleStartDMPicker"
            />
          </template>

          <!-- Channel view (lesson-study or announce) -->
          <template v-else-if="centerView === 'channel'">
            <div class="ws-center-header">
              <div class="ws-center-header__info">
                <span
                  class="ws-center-header__channel-icon"
                  :style="{ color: store.currentChannel?.color || undefined }"
                >
                  #
                </span>
                <h2 class="ws-center-header__title">{{ store.currentChannel?.name }}</h2>
                <span
                  v-if="parentGroupName"
                  class="ws-center-header__group-tag"
                >
                  {{ parentGroupName }}
                </span>
                <span
                  v-if="store.currentChannel?.status"
                  class="ws-status-badge"
                  :style="{
                    backgroundColor:
                      (channelStatusConfig[store.currentChannel.status]?.color || '#a8a29e') + '20',
                    color: channelStatusConfig[store.currentChannel.status]?.color || '#a8a29e',
                  }"
                >
                  {{
                    t(
                      channelStatusConfig[store.currentChannel.status]?.labelKey ||
                        'workshop.statusOpen'
                    )
                  }}
                </span>
                <span class="ws-center-header__meta">
                  {{ store.channelMembers.length }} {{ t('workshop.members') }} ·
                  {{ store.topics.length }} {{ t('workshop.conversations') }}
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
              <p
                v-if="lessonStudyChannelHeaderLine"
                class="ws-center-header__lesson-line"
              >
                {{ lessonStudyChannelHeaderLine }}
              </p>
            </div>

            <section
              v-if="messageSearchQuery.trim().length >= 2"
              class="ws-channel-search"
              :aria-label="t('workshop.channelSearchResultsTitle')"
            >
              <div class="ws-channel-search__head">
                <span class="ws-channel-search__title">
                  {{ t('workshop.channelSearchResultsTitle') }}
                </span>
                <span
                  v-if="messageSearchLoading"
                  class="ws-channel-search__loading"
                  >{{ t('common.loading') }}</span
                >
              </div>
              <template v-if="!messageSearchLoading && channelSearchServerResults != null">
                <p
                  v-if="channelSearchServerResults.length === 0"
                  class="ws-channel-search__empty"
                >
                  {{ t('workshop.channelSearchNoMatches') }}
                </p>
                <ul
                  v-else
                  class="ws-channel-search__list"
                >
                  <li
                    v-for="msg in channelSearchServerResults"
                    :key="msg.id"
                    class="ws-channel-search__hit ws-channel-search__hit--clickable"
                    @click="handleChannelSearchHitClick(msg)"
                  >
                    <div class="ws-channel-search__hit-meta">
                      <span class="ws-channel-search__hit-topic">{{
                        topicTitleForChannelSearchHit(msg)
                      }}</span>
                      <span class="ws-channel-search__hit-sender">{{ msg.sender_name }}</span>
                      <time
                        class="ws-channel-search__hit-time"
                        :datetime="msg.created_at"
                        >{{ formatSearchHitTime(msg.created_at) }}</time
                      >
                    </div>
                    <p class="ws-channel-search__hit-snippet">
                      {{ workshopMessageSnippet(msg.content) }}
                    </p>
                  </li>
                </ul>
              </template>
            </section>

            <!-- Topic list (conversations) — default channel view -->
            <div class="ws-topic-grid">
              <div class="ws-topic-grid__actions">
                <el-button
                  text
                  size="small"
                  class="ws-topic-grid__main-stream"
                  @click="store.openMainChannelFeed()"
                >
                  {{ t('workshop.openMainChannelStream') }}
                </el-button>
                <el-button
                  v-if="store.currentChannel?.channel_type !== 'announce' || isAdmin"
                  type="primary"
                  size="small"
                  @click="showNewTopicDialog = true"
                >
                  <el-icon class="mr-1"><CirclePlus /></el-icon>
                  {{ t('workshop.newConversation') }}
                </el-button>
              </div>
              <div
                v-if="store.topics.length > 0"
                class="ws-topic-grid__list"
              >
                <TopicCard
                  v-for="topic in store.topics"
                  :key="topic.id"
                  :topic="topic"
                  @click="(topicId: number) => handleSelectTopic(store.currentChannelId!, topicId)"
                  @rename="handleTopicRename"
                  @move="handleTopicMove"
                />
              </div>
              <div
                v-else
                class="ws-topic-grid__empty"
              >
                <p>{{ t('workshop.noConversationsYet') }}</p>
                <p class="ws-topic-grid__empty-hint">{{ t('workshop.startConversationHint') }}</p>
              </div>
            </div>
          </template>

          <!-- Topic (conversation) detail view — context lives in ChatMessageList RecipientBar + date rows -->
          <template v-else-if="centerView === 'topic' && currentTopicDetail">
            <p
              v-if="lessonStudyTopicBannerLine"
              class="ws-topic-lesson-banner"
            >
              {{ lessonStudyTopicBannerLine }}
            </p>
            <ChatMessageList
              ref="messageListRef"
              :messages="displayTopicMessages"
              :loading="messageListLoading"
              :channel-name="store.currentChannel?.name"
              :channel-type="store.currentChannel?.channel_type"
              :channel-color="store.currentChannel?.color"
              :topic-name="currentTopicDetail.title"
              @load-more="handleLoadMoreTopicMessages"
              @back-to-topic-list="store.selectTopic(null)"
            >
              <template #recipientActions>
                <el-dropdown
                  trigger="click"
                  @click.stop
                >
                  <button
                    type="button"
                    class="recipient-bar__menu-btn"
                    :title="t('workshop.more')"
                  >
                    <MoreVertical :size="16" />
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        @click="
                          copyAbsoluteWorkshopHref({
                            currentChannelId: store.currentChannelId,
                            currentTopicId: store.currentTopicId,
                            currentDMPartnerId: null,
                            showChannelBrowser: false,
                            workshopHomeViewActive: false,
                            mainChannelFeedActive: false,
                          })
                        "
                      >
                        {{ t('workshop.copyLink') }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        @click="
                          void store.markTopicRead(store.currentChannelId!, currentTopicDetail.id)
                        "
                      >
                        {{ t('workshop.markAsRead') }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </ChatMessageList>
            <ChatComposeBox
              mode="topic"
              :draft-key="composeDraftKey"
              :channel-name="store.currentChannel?.name"
              :channel-color="store.currentChannel?.color"
              :topic-name="currentTopicDetail.title"
              :allow-send="store.currentChannel?.channel_type !== 'announce' || isAdmin"
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
              :messages="displayDmMessages as any"
              :loading="messageListLoading"
              :dm-partner-name="currentDMPartner.partner_name"
            >
              <template #recipientActions>
                <el-dropdown
                  trigger="click"
                  @click.stop
                >
                  <button
                    type="button"
                    class="recipient-bar__menu-btn"
                    :title="t('workshop.more')"
                  >
                    <MoreVertical :size="16" />
                  </button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        @click="
                          copyAbsoluteWorkshopHref({
                            currentChannelId: null,
                            currentTopicId: null,
                            currentDMPartnerId: store.currentDMPartnerId,
                            showChannelBrowser: false,
                            workshopHomeViewActive: false,
                            mainChannelFeedActive: false,
                          })
                        "
                      >
                        {{ t('workshop.copyLink') }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </ChatMessageList>
            <ChatComposeBox
              mode="dm"
              :draft-key="composeDraftKey"
              :dm-partner-name="currentDMPartner.partner_name"
              @send="handleSendDM"
              @typing="handleTypingDM"
              @new-d-m="handleStartDMPicker"
            />
          </template>
        </div>
      </div>

      <!-- Right sidebar -->
      <div
        v-if="showRightSidebar"
        class="ws-column-right"
      >
        <ChannelMemberList
          v-if="store.currentChannelId"
          @start-dm="handleStartDM"
          @view-profile="handleContactViewProfile"
          @manage-user="handleManageUserFromDirectory"
        />
        <div
          v-else
          class="ws-right-contacts"
        >
          <div class="ws-right-contacts__header">
            <span class="ws-right-contacts__label">{{ t('workshop.contacts') }}</span>
            <span class="ws-right-contacts__count">
              {{ contactsOnlineCount }} {{ t('workshop.online') }}
            </span>
          </div>
          <div class="ws-right-contacts__search">
            <el-input
              v-model="contactsSearchInput"
              type="search"
              clearable
              size="small"
              :placeholder="t('workshop.searchMembers')"
            />
          </div>
          <div class="ws-right-contacts__list">
            <template
              v-for="section in contactSections"
              :key="section.key"
            >
              <div
                v-if="section.labelKey"
                class="ws-right-contacts__subhead"
              >
                {{ t(section.labelKey) }}
              </div>
              <div
                v-for="member in section.members"
                :key="`${section.key}-${member.id}`"
              >
                <UserCardPopover
                  :user="{ id: member.id, name: member.name, avatar: member.avatar }"
                  :visible="contactPopoverUserId === member.id"
                  :channel-context="false"
                  @update:visible="contactPopoverUserId = $event ? member.id : null"
                  @start-dm="handleStartDM"
                  @view-profile="handleContactViewProfile"
                  @manage-user="handleManageUserFromDirectory"
                >
                  <div class="ws-right-contacts__row">
                    <span
                      class="ws-right-contacts__presence"
                      :class="{
                        'ws-right-contacts__presence--online': section.key === 'online',
                        'ws-right-contacts__presence--recent': section.key === 'recently_online',
                        'ws-right-contacts__presence--offline': section.key === 'offline',
                      }"
                    />
                    <div class="ws-right-contacts__row-text">
                      <span
                        class="ws-right-contacts__name"
                        :class="{
                          'ws-right-contacts__name--online': section.key === 'online',
                        }"
                      >
                        {{ member.name
                        }}<span
                          v-if="isContactSelf(member.id)"
                          class="ws-right-contacts__you"
                          >{{ t('workshop.you') }}</span
                        >
                      </span>
                      <span
                        v-if="section.key === 'recently_online'"
                        class="ws-right-contacts__last-seen"
                      >
                        {{ contactLastOnlineSubtitle(member.id) }}
                      </span>
                    </div>
                  </div>
                </UserCardPopover>
              </div>
            </template>
            <div
              v-if="store.orgMembers.length === 0"
              class="ws-right-contacts__empty"
            >
              {{ t('workshop.noMembersFound') }}
            </div>
          </div>
          <div
            v-if="store.orgMembersTotal > 0"
            class="ws-right-contacts__footer"
          >
            <span class="ws-right-contacts__loaded">
              {{
                t('workshop.contactsLoadedCount')
                  .replace('{0}', String(store.orgMembers.length))
                  .replace('{1}', String(store.orgMembersTotal))
              }}
            </span>
            <el-button
              v-if="store.orgMembersHasMore"
              text
              size="small"
              type="primary"
              :loading="loadingMoreContacts"
              @click="loadMoreContacts"
            >
              {{ t('workshop.loadMore') }}
            </el-button>
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
      <el-form
        label-position="top"
        class="space-y-4"
      >
        <el-form-item :label="t('workshop.conversationTitle')">
          <el-input
            v-model="newTopicTitle"
            :placeholder="t('workshop.conversationTitlePlaceholder')"
            maxlength="200"
          />
        </el-form-item>
        <el-form-item :label="t('workshop.topicDescription')">
          <el-input
            v-model="newTopicDescription"
            type="textarea"
            :rows="3"
            :placeholder="t('workshop.topicDescriptionPlaceholder')"
            maxlength="1000"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNewTopicDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="creatingTopic"
          :disabled="!newTopicTitle.trim()"
          @click="handleCreateTopic"
        >
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

    <CreateChannelDialog
      v-if="store.createChannelDialogVisible"
      :visible="store.createChannelDialogVisible"
      @update:visible="
        (v: boolean) => {
          if (!v) store.closeCreateChannelDialog()
        }
      "
    />

    <TeachingGroupsManageDialog
      v-if="showTeachingGroupsManage"
      v-model:visible="showTeachingGroupsManage"
      @openChannelSettings="handleOpenChannelSettings"
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

    <el-dialog
      v-model="workshopSettingsDialogVisible"
      :title="settingsPanelTitle"
      width="420px"
      append-to-body
    >
      <p
        v-if="workshopSettingsPanel === 'notifications'"
        class="text-sm text-stone-600 leading-relaxed"
      >
        {{ t('workshop.notificationsSettingsBlurb') }}
      </p>
      <p
        v-else-if="workshopSettingsPanel === 'preferences'"
        class="text-sm text-stone-600 leading-relaxed"
      >
        {{ t('workshop.preferencesSettingsBlurb') }}
      </p>
    </el-dialog>

    <el-dialog
      v-model="showShortcutsHelp"
      :title="t('workshop.keyboardShortcutsTitle')"
      width="400px"
      append-to-body
    >
      <ul class="text-sm text-stone-600 space-y-2 list-disc pl-4">
        <li>{{ t('workshop.shortcutHelp') }}</li>
        <li>{{ t('workshop.phase2RoadmapMovePreview') }}</li>
        <li>{{ t('workshop.phase2RoadmapGroupsAlerts') }}</li>
        <li>{{ t('workshop.phase2RoadmapPlatform') }}</li>
      </ul>
    </el-dialog>

    <el-dialog
      v-model="contactProfileDialogVisible"
      :title="contactProfileMember?.name || ''"
      width="360px"
      append-to-body
    >
      <div
        v-if="contactProfileMember"
        class="flex flex-col gap-3 text-sm text-stone-600"
      >
        <div class="flex items-center gap-3">
          <span class="text-2xl">{{ contactProfileMember.avatar || '👤' }}</span>
          <span class="font-medium text-stone-800">{{ contactProfileMember.name }}</span>
        </div>
        <p class="leading-relaxed">
          {{ t('workshop.readOnlyProfileBlurb') }}
        </p>
      </div>
    </el-dialog>

    <AccountInfoModal
      v-if="showAccountModal"
      v-model:visible="showAccountModal"
    />
  </div>
</template>

<style src="./workshop-chat-page.css" scoped></style>
<style src="./workshop-navbar-actions.css"></style>
