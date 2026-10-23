<script setup lang="ts">
/**
 * MindMate Panel - AI assistant chat interface (ChatGPT-style)
 * Uses useMindMate composable for SSE streaming
 * Features: Markdown rendering, code highlighting, message actions, stop generation
 */
import { computed, defineAsyncComponent, nextTick, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { ElButton, ElDialog, ElIcon } from 'element-plus'

import { Plus } from '@element-plus/icons-vue'

import { PanelLeftOpen, Share2, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateCollabStartPicker from '@/components/mindmate/MindmateCollabStartPicker.vue'
import MindmateSeminarMemberDialog from '@/components/mindmate/MindmateSeminarMemberDialog.vue'
import MindmateSeminarRosterBar from '@/components/mindmate/MindmateSeminarRosterBar.vue'
import MindmateSeminarShareDialog from '@/components/mindmate/MindmateSeminarShareDialog.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import {
  applyThinkingCoinMutation,
  extractThinkingCoinsFooter,
} from '@/composables/auth/useThinkingCoinSync'
import {
  embeddedCollabRoomCode,
  hydrateEmbeddedCollabRoomCode,
  setEmbeddedCollabRoomCode,
} from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import { dropLiveCollabRoom } from '@/composables/mindmate/mindmateCollabLiveSession'
import {
  applySeminarGroup,
  bumpSeminarFolderReload,
  closeSeminarChrome,
  openSeminarTaskPane,
  seminarMembersPaneOpen,
  toggleSeminarMembersPane,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { useMindMate } from '@/composables/mindmate/useMindMate'
import type { FeedbackRating } from '@/composables/mindmate/useMindMate'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { useMindmateSavedSeminar } from '@/composables/mindmate/useMindmateSavedSeminar'
import { useMindmateSeminarFaces } from '@/composables/mindmate/useMindmateSeminarFaces'
import { useConversations, usePinnedConversations } from '@/composables/queries'
import { useAuthStore, useMindMateStore, useTeachingDesignExportStore } from '@/stores'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import type { MindMateMessage } from '@/stores/mindmateActiveThread'
import { useUIStore } from '@/stores/ui'
import { authFetch } from '@/utils/api'
import { copyMindmateAssistantMessage } from '@/utils/copyMindmateMessage'
import { confirmMindmateCollabStop } from '@/utils/mindmateCollabConfirm'
import {
  notifyMindmateCollabLibraryChanged,
  saveFinishedSeminar,
  shouldRefreshSavedSeminarLibrary,
} from '@/utils/mindmateCollabLibrarySave'
import {
  clearMindmateCollabCodeEnded,
  formatMindmateCollabCode,
  loadLocalMindmateCollabSessions,
  normalizeMindmateCollabCode,
  trackLocalMindmateCollabSession,
  wasMindmateCollabCodeRecentlyEnded,
} from '@/utils/mindmateCollabSessions'
import {
  requestMindmateCollabStop,
  resolveMindmateCollabSessionId,
  shouldRemoveCollabFromHistory,
  teardownMindmateCollabClient,
} from '@/utils/mindmateCollabTeardown'
import {
  isMindmateBlockedDocUpload,
  isMindmateComposerUploadableFile,
} from '@/utils/mindmateComposerUpload'
import {
  hasGeneratedDiagramImage,
  parseMindmateDiagramLibraryId,
} from '@/utils/mindmateDiagramMeta'
import { displayMindmateUserQueryForUi } from '@/utils/mindmateExtensionPageContext'
import {
  type SeminarBrief,
  type SeminarBriefRole,
  filledBriefLines,
  seminarBriefMissing,
  seminarSeedFromBrief,
} from '@/utils/mindmateSeminarBrief'
import {
  seminarBubblePlainText,
  seminarFolderErrorKey,
  uploadSeminarBackgroundFile,
} from '@/utils/mindmateSeminarFolder'
import {
  type SeminarGroupMember,
  addSeminarGroupMembers,
  fetchSeminarGroup,
  removeSeminarGroupMember,
  renameSeminarSession,
  updateSeminarMemberRole,
} from '@/utils/mindmateSeminarGroup'
import { startSeminarRoom } from '@/utils/mindmateSeminarStart'
import { canContinueSavedSeminar } from '@/utils/mindmateSeminarTranscript'

import MindmateHeader from './mindmate/MindmateHeader.vue'
import MindmateInput from './mindmate/MindmateInput.vue'
import MindmateMessages from './mindmate/MindmateMessages.vue'

const MindmateCollabPanel = defineAsyncComponent(
  () => import('@/components/mindmate/MindmateCollabPanel.vue')
)
const MindmateCollabEmbed = defineAsyncComponent(
  () => import('@/components/mindmate/MindmateCollabEmbed.vue')
)
const MindmateCollabBreadcrumb = defineAsyncComponent(
  () => import('@/components/mindmate/MindmateCollabBreadcrumb.vue')
)
const MindmateCollabSavedTranscript = defineAsyncComponent(
  () => import('@/components/mindmate/MindmateCollabSavedTranscript.vue')
)

interface StartedSeminarRoom {
  code: string
  sessionId: string
}

interface MindmateCollabPanelHandle {
  prefillAndAutoJoin: (rawCode: string) => void
  startFromTopic: (
    topic: string,
    visibility?: 'organization' | 'network'
  ) => Promise<StartedSeminarRoom | null>
  startSharedThread: (source: {
    visibility: 'organization' | 'network'
    title: string
    seedMessages: Array<{ role: string; content: string }>
  }) => Promise<StartedSeminarRoom | null>
  openJoinPanel: () => void
  openStartPanel: () => void
}

interface MindmateInputHandle {
  focus: () => void
}

// Props for different display modes
const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
  }>(),
  {
    mode: 'panel',
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

// Computed for mode checks
const isFullpageMode = computed(() => props.mode === 'fullpage')

const { promptLanguage, t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()
const uiStore = useUIStore()
const featureFlagsStore = useFeatureFlagsStore()
const { loadPhase: mindMateLoadPhase } = storeToRefs(mindMateStore)
const teachingDesignExport = useTeachingDesignExportStore()
const { exportingMessageId: exportingWordTemplateId } = storeToRefs(teachingDesignExport)

const showMindmateCollab = computed(() => featureFlagsStore.getFeatureMindmateCollab())
const { canUseOnlineCollab } = useSchoolTierFeatures()
const homeMode = ref<'dialogue' | 'seminar'>('dialogue')
const mindmateInputRef = ref<MindmateInputHandle | null>(null)
const memberDialogOpen = ref(false)
const memberDialogMode = ref<'create' | 'expand'>('create')
const memberBusy = ref(false)
const { faces: seminarFaces } = useMindmateSeminarFaces()
const historyDialogOpen = ref(false)
const historyStarting = ref(false)

const { displayName: defaultMindMateTitle } = useMindMateBranding()

// Typing effect state
const displayTitle = ref(defaultMindMateTitle.value)
const isTypingTitle = ref(false)

// Use MindMate composable for SSE streaming
const mindMate = useMindMate({
  language: promptLanguage.value,
  onError: (error) => {
    notify.error(error)
  },
  onTitleChanged: (title, oldTitle) => {
    animateTitleChange(title, oldTitle)
  },
})

// Local state
const inputText = ref('')
const editingMessageId = ref<string | null>(null)
const editingContent = ref('')
const hoveredMessageId = ref<string | null>(null)
const shareDialogOpen = ref(false)
const fileDragActive = ref(false)
const shareSelectMode = ref(false)
const selectedMessageIds = ref<string[]>([])
const collabPanelRef = ref<MindmateCollabPanelHandle | null>(null)
const collabRoomCode = ref<string | null>(null)
const collabRoomTitle = ref<string | null>(null)
const collabVisibility = ref<'organization' | 'network'>('organization')
const collabSessionId = ref('')
const collabOwnerId = ref<number | null>(null)
const collabSeedMessages = ref<MindmateCollabMessage[]>([])
const seminarGroupMembers = ref<SeminarGroupMember[]>([])
const seminarBriefTopic = ref('')
const seminarBriefGoals = ref<string[]>([])

function onSeminarBriefGoals(goals: string[]): void {
  seminarBriefGoals.value = goals
}

function onSeminarBriefTopic(topic: string): void {
  seminarBriefTopic.value = topic
}

const renamingSeminar = ref(false)
const savedSeminar = useMindmateSavedSeminar()

const isSeminarHost = computed(() => {
  const ownerId = Number(collabOwnerId.value)
  const selfId = Number(authStore.user?.id)
  return ownerId > 0 && selfId > 0 && ownerId === selfId
})

/** Seminar leader role (transferable); falls back to session owner. */
const isSeminarLeader = computed(() => {
  const selfId = Number(authStore.user?.id)
  if (!selfId) {
    return false
  }
  const leader = seminarGroupMembers.value.find((row) => row.isLeader || row.role === 'leader')
  if (leader) {
    return leader.userId === selfId
  }
  return isSeminarHost.value
})

function saveEndedSeminar(sessionId: string, openAfterSave: boolean): void {
  void saveFinishedSeminar(sessionId, { openAfterSave }).then((outcome) => {
    if (outcome === 'saved') {
      notify.successKey('mindmate.collabSaveLibraryDone')
    } else if (outcome === 'failed') {
      notify.errorKey('mindmate.collabSaveLibraryFailed')
    }
  })
}

function mapLibrarySeed(msgs: Array<{ role: string; content: string }>): MindmateCollabMessage[] {
  return msgs
    .filter((message) => message.role === 'user' || message.role === 'assistant')
    .filter((message) => message.content.trim())
    .map((message) => ({
      role: message.role as 'user' | 'assistant',
      content: message.content,
      sender_user_id: message.role === 'user' ? Number(authStore.user?.id) || null : null,
      username: message.role === 'user' ? (authStore.user?.username ?? null) : null,
    }))
}

function mapThreadToCollabSeed(msgs: MindMateMessage[]): MindmateCollabMessage[] {
  return msgs
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && m.content.trim())
    .map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.role === 'user' ? displayMindmateUserQueryForUi(m.content) : m.content,
      sender_user_id: m.role === 'user' ? Number(authStore.user?.id) || null : null,
      username: m.role === 'user' ? (authStore.user?.username ?? null) : null,
    }))
}

function prefillCollabJoin(rawCode: string): void {
  collabPanelRef.value?.prefillAndAutoJoin(rawCode)
}

async function attachShowcasePost(postId: string): Promise<void> {
  const id = postId.trim()
  if (!id) return
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  try {
    mindMate.clearPendingFiles()
    mindMate.startNewConversation()
    const { getShowcasePost } = await import('@/utils/apiClient')
    const { buildShowcaseMindMateAttachment } =
      await import('@/composables/showcase/buildShowcaseMindMateAttachment')
    const post = await getShowcasePost(id)
    const file = await buildShowcaseMindMateAttachment(post)
    if (await isMindmateBlockedDocUpload(file)) {
      notify.warningKey('mindmate.input.docNotSupported')
      return
    }
    const uploaded = await mindMate.uploadFile(file, { allowDocuments: true })
    if (!uploaded) {
      notify.errorKey('showcase.detail.actionFailed')
    }
  } catch {
    notify.errorKey('showcase.detail.actionFailed')
  }
}

defineExpose({ prefillCollabJoin, attachShowcasePost })

// Computed for loading state
const isLoading = computed(
  () => mindMateStore.isGenerating || mindMate.isLoading.value || mindMate.isStreaming.value
)

// User avatar from auth store
const userAvatar = computed(() => authStore.user?.avatar?.trim() || '')

// Check if welcome message should be shown
const showWelcome = computed(() => {
  return !mindMate.hasMessages.value && !mindMate.isLoading.value && !mindMate.isStreaming.value
})

const inConversation = computed(
  () =>
    Boolean(mindMateStore.currentConversationId) ||
    mindMate.hasMessages.value ||
    mindMate.isLoading.value ||
    mindMate.isStreaming.value
)

const isCollabChatroomMode = computed(() => Boolean(collabRoomCode.value))

const showHomeModeSwitch = computed(() => showWelcome.value && !isCollabChatroomMode.value)

function requireCollabTier(): boolean {
  if (canUseOnlineCollab.value) {
    return true
  }
  notify.warningKey('auth.schoolTierFeatureUnavailable')
  return false
}

const collabSessionTitle = computed(
  () => collabRoomTitle.value || mindMateStore.conversationTitle || t('mindmate.collabPill')
)

const canStopCollabSession = computed(() => isSeminarLeader.value)

function handleCollabSessionStarted(payload: {
  code: string
  visibility?: 'organization' | 'network'
  ownerUserId?: number
  seedThread?: boolean
  title?: string
  seedMessages?: Array<{ role: string; content: string }>
}) {
  if (wasMindmateCollabCodeRecentlyEnded(payload.code)) {
    notify.infoKey('mindmate.collabRoomEndedHost')
    return
  }
  if (payload.seedMessages?.length) {
    collabSeedMessages.value = mapLibrarySeed(payload.seedMessages)
  } else if (payload.seedThread) {
    collabSeedMessages.value = mapThreadToCollabSeed(mindMate.messages.value)
  } else {
    collabSeedMessages.value = []
  }
  collabRoomCode.value = payload.code
  if (payload.visibility === 'network' || payload.visibility === 'organization') {
    collabVisibility.value = payload.visibility
  }
  if (payload.ownerUserId != null && payload.ownerUserId > 0) {
    collabOwnerId.value = payload.ownerUserId
  } else {
    collabOwnerId.value = null
  }
  collabRoomTitle.value = payload.title || mindMateStore.conversationTitle || null
  savedSeminar.clear()
  setEmbeddedCollabRoomCode(payload.code)
}

function exitCollabChatroomMode(options: { removeFromHistory?: boolean } = {}) {
  const code = collabRoomCode.value
  collabRoomCode.value = null
  collabRoomTitle.value = null
  collabVisibility.value = 'organization'
  collabSessionId.value = ''
  collabOwnerId.value = null
  collabSeedMessages.value = []
  seminarGroupMembers.value = []
  seminarBriefTopic.value = ''
  seminarBriefGoals.value = []
  closeSeminarChrome()
  teardownMindmateCollabClient(code, options)
}

function handleCollabEnded(reason: 'idle' | 'host' | 'left' = 'left') {
  const sessionId = resolveMindmateCollabSessionId(collabSessionId.value, collabRoomCode.value)
  const selfId = Number(authStore.user?.id)
  const ownsRoom =
    (collabOwnerId.value != null && collabOwnerId.value === selfId) ||
    loadLocalMindmateCollabSessions().some(
      (row) => row.session_id === sessionId && row.owner_user_id === selfId
    )
  exitCollabChatroomMode({ removeFromHistory: shouldRemoveCollabFromHistory(reason) })
  if (shouldRefreshSavedSeminarLibrary(reason)) {
    notifyMindmateCollabLibraryChanged()
  }
  if (!ownsRoom || !sessionId) {
    return
  }
  if (reason === 'host') {
    saveEndedSeminar(sessionId, true)
  }
}

const savedSeminarOwned = ref(false)

watch(
  () => savedSeminar.sessionId.value,
  () => {
    savedSeminarOwned.value = false
  }
)

const showContinueSession = computed(() =>
  canContinueSavedSeminar(
    savedSeminar.sessionId.value,
    savedSeminarOwned.value,
    isCollabChatroomMode.value
  )
)

function onSavedSeminarOwnership(owned: boolean): void {
  savedSeminarOwned.value = owned
}

function enterLiveSeminar(payload: {
  code: string
  visibility?: string
  ownerUserId?: number
  title?: string
  sessionId?: string
  expiresAt?: string | null
}): void {
  const code = formatMindmateCollabCode(payload.code)
  clearMindmateCollabCodeEnded(code)
  trackLocalMindmateCollabSession({
    session_id: payload.sessionId || '',
    code,
    title: payload.title || t('mindmate.collabPill'),
    owner_user_id: payload.ownerUserId,
    visibility: payload.visibility,
    expires_at: payload.expiresAt,
    live: true,
  })
  if (payload.sessionId) {
    collabSessionId.value = payload.sessionId
  }
  notifyMindmateCollabLibraryChanged()
  handleCollabSessionStarted({
    code,
    visibility:
      payload.visibility === 'network' || payload.visibility === 'organization'
        ? payload.visibility
        : 'organization',
    ownerUserId: payload.ownerUserId,
    title: payload.title,
  })
}

function onSavedSeminarLive(payload: {
  code: string
  visibility?: string
  title?: string
  ownerUserId?: number
}): void {
  enterLiveSeminar({
    code: payload.code,
    visibility: payload.visibility,
    title: payload.title,
    ownerUserId: payload.ownerUserId,
    sessionId: savedSeminar.sessionId.value || '',
  })
}

async function continueSavedSeminar(): Promise<void> {
  const sessionId = savedSeminar.sessionId.value
  if (!canContinueSavedSeminar(sessionId, savedSeminarOwned.value, isCollabChatroomMode.value)) {
    return
  }
  try {
    const response = await authFetch('/api/mindmate/collab/reopen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
    if (!response.ok) {
      const err = (await response.json().catch(() => ({}))) as { detail?: string }
      if (err.detail) {
        notify.error(err.detail)
      } else {
        notify.errorKey('mindmate.collabStartFailed')
      }
      return
    }
    const data = (await response.json()) as {
      code?: string
      visibility?: string
      title?: string
      owner_user_id?: number
      session_id?: string
      expires_at?: string | null
    }
    if (!data.code) {
      notify.errorKey('mindmate.collabStartFailed')
      return
    }
    enterLiveSeminar({
      code: data.code,
      visibility: data.visibility,
      title: data.title,
      ownerUserId: data.owner_user_id,
      sessionId: data.session_id || sessionId || undefined,
      expiresAt: data.expires_at,
    })
  } catch {
    notify.errorKey('mindmate.collabStartFailed')
  }
}

function handleCollabRoomMeta(payload: {
  title: string
  visibility: string
  sessionId?: string
  ownerId?: number
}) {
  collabRoomTitle.value = payload.title
  if (payload.visibility === 'network' || payload.visibility === 'organization') {
    collabVisibility.value = payload.visibility
  }
  if (payload.sessionId) {
    collabSessionId.value = payload.sessionId
  }
  if (payload.ownerId != null) {
    collabOwnerId.value = payload.ownerId
  }
}

async function endCollabSession(): Promise<void> {
  if (!isCollabChatroomMode.value) {
    return
  }
  const confirmed = await confirmMindmateCollabStop(t)
  if (!confirmed) {
    return
  }
  const sessionId = resolveMindmateCollabSessionId(collabSessionId.value, collabRoomCode.value)
  dropLiveCollabRoom(collabRoomCode.value || '')
  exitCollabChatroomMode({ removeFromHistory: true })
  if (!sessionId) {
    notify.successKey('mindmate.collabStopped')
    return
  }
  void requestMindmateCollabStop(sessionId)
    .then((ok) => {
      if (ok) {
        notify.successKey('mindmate.collabStopped')
        saveEndedSeminar(sessionId, true)
      } else {
        notify.errorKey('collab.endFailed')
      }
    })
    .catch(() => {
      notify.errorKey('collab.endFailed')
    })
}

function syncHeaderTitleFromBranding() {
  if (isTypingTitle.value) {
    return
  }
  if (showWelcome.value) {
    displayTitle.value = defaultMindMateTitle.value
  }
}

watch(defaultMindMateTitle, () => {
  syncHeaderTitleFromBranding()
})

watch(showWelcome, (welcome) => {
  if (welcome) {
    syncHeaderTitleFromBranding()
  }
})

if (isFullpageMode.value) {
  hydrateEmbeddedCollabRoomCode()
}

watch(
  embeddedCollabRoomCode,
  (code) => {
    if (!code) {
      if (collabRoomCode.value) {
        exitCollabChatroomMode()
      }
      return
    }
    if (!isFullpageMode.value || code === collabRoomCode.value) {
      return
    }
    if (wasMindmateCollabCodeRecentlyEnded(code)) {
      return
    }
    collabRoomCode.value = code
    const localRow = loadLocalMindmateCollabSessions().find(
      (row) => normalizeMindmateCollabCode(row.code) === normalizeMindmateCollabCode(code)
    )
    if (localRow?.visibility === 'network' || localRow?.visibility === 'organization') {
      collabVisibility.value = localRow.visibility
    }
    if (localRow?.title) {
      collabRoomTitle.value = localRow.title
    }
  },
  { immediate: true }
)

// In panel mode (canvas mini-mindmate): fetch conversations from Dify and sync to store
// ChatHistory sidebar is not mounted on canvas, so we must fetch here
const { data: conversationsData, isLoading: isLoadingConversationsQuery } = useConversations()
const { data: pinnedData } = usePinnedConversations()

const historyLoading = computed(() =>
  props.mode === 'panel' ? isLoadingConversationsQuery.value : mindMate.isLoadingConversations.value
)

watch(
  [conversationsData, pinnedData],
  ([convs, pinned]) => {
    if (convs && pinned !== undefined) {
      mindMateStore.syncConversationsFromQuery(convs, pinned)
    }
  },
  { immediate: true }
)

// Watch for title changes to sync display (from store)
watch(
  () => mindMateStore.conversationTitle,
  (newTitle) => {
    if (!isTypingTitle.value && newTitle !== displayTitle.value) {
      displayTitle.value = newTitle
    }
  }
)

// Typing animation for title changes
async function animateTitleChange(newTitle: string, oldTitle?: string) {
  if (isTypingTitle.value) return
  isTypingTitle.value = true

  // Use provided oldTitle or current displayTitle
  const currentTitle = oldTitle ?? displayTitle.value

  // Clear old title character by character
  for (let i = currentTitle.length; i >= 0; i--) {
    displayTitle.value = currentTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 20))
  }

  // Type new title character by character
  for (let i = 0; i <= newTitle.length; i++) {
    displayTitle.value = newTitle.substring(0, i)
    await new Promise((resolve) => setTimeout(resolve, 30))
  }

  isTypingTitle.value = false
}

// Start a new conversation
async function startNewConversation() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  if (isCollabChatroomMode.value) {
    exitCollabChatroomMode()
  }
  savedSeminar.clear()
  homeMode.value = 'dialogue'
  mindMate.startNewConversation()
  cancelShareSelect()
  displayTitle.value = defaultMindMateTitle.value
}

// Load a conversation from history
async function loadConversationFromHistory(convId: string) {
  if (isCollabChatroomMode.value) {
    exitCollabChatroomMode()
  }
  savedSeminar.clear()
  cancelShareSelect()
  await mindMate.loadConversation(convId)
}

// Delete a conversation
async function deleteConversationFromHistory(convId: string) {
  const success = await mindMate.deleteConversation(convId)
  if (success) {
    notify.successKey('notification.conversationDeleted')
  } else {
    notify.errorKey('notification.deleteFailed')
  }
}

// Send message using composable
async function sendMessage() {
  if ((!inputText.value.trim() && mindMate.pendingFiles.value.length === 0) || isLoading.value)
    return

  const message = inputText.value.trim()
  if (showHomeModeSwitch.value && homeMode.value === 'seminar') {
    return
  }

  inputText.value = ''
  await mindMate.sendMessage(message)
}

const pendingSeminarBrief = ref<SeminarBrief | null>(null)

function seminarLabels() {
  const roleLabels = {
    leader: t('mindmate.home.brief.role.leader'),
    leadPrep: t('mindmate.home.brief.role.leadPrep'),
    coPrep: t('mindmate.home.brief.role.coPrep'),
    expert: t('mindmate.home.brief.role.expert'),
    researcher: t('mindmate.home.brief.role.researcher'),
    observer: t('mindmate.home.brief.role.observer'),
    none: t('mindmate.home.brief.role.none'),
  } as Record<SeminarBriefRole, string>
  return {
    topic: t('mindmate.home.brief.topic'),
    goals: t('mindmate.home.brief.goals'),
    participants: t('mindmate.home.brief.participants'),
    resources: t('mindmate.home.brief.resources'),
    roleLabels,
    visibilityOrg: t('mindmate.home.brief.visibilityOrg'),
    visibilityNetwork: t('mindmate.home.brief.visibilityNetwork'),
    skipRoles: t('mindmate.home.brief.skipRoles'),
    skipResources: t('mindmate.home.brief.skipResources'),
    pendingConsent: t('mindmate.home.brief.pendingConsent'),
  }
}

function takeSeminarBrief(brief: SeminarBrief): SeminarBrief | null {
  const hostUserId = Number(authStore.user?.id) || 0
  const missing = seminarBriefMissing(brief, hostUserId)
  if (missing.length === 0) {
    pendingSeminarBrief.value = brief
    return brief
  }
  const labels = seminarLabels()
  const titleBySection = {
    topic: labels.topic,
    goals: labels.goals,
    participants: labels.participants,
    resources: labels.resources,
  }
  const parts = missing
    .map((section) => titleBySection[section])
    .join(t('mindmate.home.brief.joiner'))
  notify.warningKey('mindmate.home.brief.required', { parts })
  return null
}

async function uploadBriefResources(sessionId: string, files: File[]): Promise<boolean> {
  if (files.length === 0) {
    return true
  }
  for (const file of files) {
    let lastError: unknown = null
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        await uploadSeminarBackgroundFile(sessionId, file)
        lastError = null
        break
      } catch (error) {
        lastError = error
      }
    }
    if (lastError != null) {
      notify.errorKey(seminarFolderErrorKey(lastError))
      return false
    }
  }
  return true
}

const seminarMemberIds = computed(() => seminarFaces.value.map((face) => face.userId))

watch(collabSessionId, (sessionId) => {
  if (!sessionId) {
    return
  }
  void loadSeminarGroup(sessionId)
})

async function loadSeminarGroup(sessionId: string): Promise<void> {
  const group = await fetchSeminarGroup(sessionId)
  if (!group || collabSessionId.value !== sessionId) {
    return
  }
  seminarGroupMembers.value = group.members
  if (group.ownerUserId > 0) {
    collabOwnerId.value = group.ownerUserId
  }
  if (group.title) {
    collabRoomTitle.value = group.title
  }
  if (group.briefTopic) {
    seminarBriefTopic.value = group.briefTopic
  }
  if (group.briefGoals.length) {
    seminarBriefGoals.value = group.briefGoals
  }
  applySeminarGroup(
    group.members
      .filter((member) => member.online)
      .map((member) => ({
        userId: member.userId,
        name: member.name,
        avatar: member.avatar,
      }))
  )
}

async function openSeminarFromBrief(
  brief: SeminarBrief,
  options?: { includeThread?: boolean }
): Promise<void> {
  if (!requireCollabTier() || !takeSeminarBrief(brief) || memberBusy.value) {
    return
  }
  memberBusy.value = true
  try {
    const seeded = seminarSeedFromBrief(brief, seminarLabels())
    const threadSeed = options?.includeThread
      ? mapThreadToCollabSeed(mindMate.messages.value).map((message) => ({
          role: message.role,
          content: message.content,
        }))
      : []
    const selfUserId = Number(authStore.user?.id)
    const userIds = brief.participants
      .map((row) => row.userId)
      .filter((userId) => userId !== selfUserId)
    const memberRoles: Record<number, SeminarBriefRole> = {}
    for (const row of brief.participants) {
      memberRoles[row.userId] = row.role
    }
    const goals = filledBriefLines(brief.goals)
    const topic = brief.topic.trim()
    seminarBriefTopic.value = topic
    seminarBriefGoals.value = goals
    const room = await openStartedSeminar(brief.visibility, {
      ...seeded,
      seedMessages: [...threadSeed, ...seeded.seedMessages],
      memberUserIds: userIds,
      memberRoles,
      briefTopic: topic,
      briefGoals: goals,
      closeGroup: true,
    })
    if (!room) {
      return
    }
    const uploaded = await uploadBriefResources(room.sessionId, brief.resourceFiles)
    if (uploaded && brief.resourceFiles.length > 0) {
      bumpSeminarFolderReload()
    }
    openSeminarTaskPane('files')
    pendingSeminarBrief.value = null
    inputText.value = ''
    await Promise.all(userIds.map((userId) => pokeSeminarMember(room.sessionId, userId)))
    await loadSeminarGroup(room.sessionId)
  } finally {
    memberBusy.value = false
  }
}

function openAddSeminarMembers(): void {
  memberDialogMode.value = 'expand'
  memberDialogOpen.value = true
}

async function pokeSeminarMember(sessionId: string, userId: number): Promise<void> {
  try {
    await authFetch('/api/mindmate/collab/poke', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, target_user_id: userId }),
    })
  } catch {
    // The room is already open. A missed nudge does not undo the group.
  }
}

async function openStartedSeminar(
  visibility: 'organization' | 'network',
  source: {
    title: string
    seedMessages: Array<{ role: string; content: string }>
    memberUserIds?: number[]
    memberRoles?: Record<number, SeminarBriefRole>
    briefTopic?: string
    briefGoals?: string[]
    closeGroup?: boolean
  }
): Promise<StartedSeminarRoom | null> {
  const result = await startSeminarRoom({
    visibility,
    title: source.title,
    seedMessages: source.seedMessages,
    memberUserIds: source.memberUserIds,
    memberRoles: source.memberRoles,
    briefTopic: source.briefTopic,
    briefGoals: source.briefGoals,
    closeGroup: source.closeGroup,
  })
  if (!result.ok) {
    if (result.detail) {
      notify.error(result.detail)
    } else {
      notify.errorKey('mindmate.collabStartFailed')
    }
    return null
  }
  const formatted = formatMindmateCollabCode(result.room.code)
  applyThinkingCoinMutation(extractThinkingCoinsFooter(result.room.body))
  notify.successKey('mindmate.collabStarted')
  notifyMindmateCollabLibraryChanged()
  trackLocalMindmateCollabSession({
    session_id: result.room.sessionId,
    code: formatted,
    title: result.room.title || source.title || t('mindmate.collabPill'),
    owner_user_id: result.room.ownerUserId,
    participant_count: result.room.participantCount,
    visibility: result.room.visibility || visibility,
    expires_at: result.room.expiresAt,
  })
  if (result.room.briefTopic) {
    seminarBriefTopic.value = result.room.briefTopic
  }
  if (result.room.briefGoals.length) {
    seminarBriefGoals.value = result.room.briefGoals
  }
  handleCollabSessionStarted({
    code: formatted,
    visibility,
    ownerUserId: result.room.ownerUserId > 0 ? result.room.ownerUserId : undefined,
    title: result.room.title || source.title,
    seedMessages: source.seedMessages,
  })
  collabSessionId.value = result.room.sessionId
  return { code: formatted, sessionId: result.room.sessionId }
}

async function renameCurrentSeminar(title: string): Promise<void> {
  const sessionId = collabSessionId.value
  if (!sessionId || !isSeminarHost.value || renamingSeminar.value) {
    return
  }
  renamingSeminar.value = true
  try {
    const next = await renameSeminarSession(sessionId, title)
    if (!next) {
      notify.errorKey('mindmate.home.renameSeminarFailed')
      return
    }
    collabRoomTitle.value = next
    notify.successKey('mindmate.home.renameSeminarSaved')
  } finally {
    renamingSeminar.value = false
  }
}

async function onSeminarMemberRoleChange(userId: number, role: SeminarBriefRole): Promise<void> {
  const sessionId = collabSessionId.value
  if (!sessionId || !isSeminarLeader.value || memberBusy.value) {
    return
  }
  memberBusy.value = true
  try {
    const ok = await updateSeminarMemberRole(sessionId, userId, role)
    if (!ok) {
      notify.errorKey('mindmate.group.roleUpdateFailed')
      return
    }
    await loadSeminarGroup(sessionId)
  } finally {
    memberBusy.value = false
  }
}

async function onSeminarMemberRemove(userId: number): Promise<void> {
  const sessionId = collabSessionId.value
  if (!sessionId || !isSeminarLeader.value || memberBusy.value) {
    return
  }
  memberBusy.value = true
  try {
    const ok = await removeSeminarGroupMember(sessionId, userId)
    if (!ok) {
      notify.errorKey('mindmate.group.memberRemoveFailed')
      return
    }
    await loadSeminarGroup(sessionId)
  } finally {
    memberBusy.value = false
  }
}

async function onSeminarMembersConfirm(userIds: number[]): Promise<void> {
  if (memberDialogMode.value === 'expand') {
    await expandSeminarGroup(userIds)
    return
  }
  await formSeminarGroup(userIds)
}

async function expandSeminarGroup(userIds: number[]): Promise<void> {
  const sessionId = collabSessionId.value
  if (!sessionId || memberBusy.value || userIds.length === 0) {
    return
  }
  memberBusy.value = true
  try {
    const ok = await addSeminarGroupMembers(sessionId, userIds)
    if (!ok) {
      notify.errorKey('mindmate.group.membersAddFailed')
      return
    }
    memberDialogOpen.value = false
    notify.successKey('mindmate.group.membersAdded')
    await loadSeminarGroup(sessionId)
  } finally {
    memberBusy.value = false
  }
}

async function formSeminarGroup(userIds: number[]): Promise<void> {
  const brief = pendingSeminarBrief.value
  if (!brief || memberBusy.value) {
    return
  }
  memberBusy.value = true
  try {
    const seeded = seminarSeedFromBrief(brief, seminarLabels())
    const room = await openStartedSeminar('organization', {
      ...seeded,
      memberUserIds: userIds,
    })
    if (!room) {
      return
    }
    const uploaded = await uploadBriefResources(room.sessionId, brief.resourceFiles)
    if (uploaded && brief.resourceFiles.length > 0) {
      bumpSeminarFolderReload()
    }
    openSeminarTaskPane('files')
    pendingSeminarBrief.value = null
    inputText.value = ''
    memberDialogOpen.value = false
    await Promise.all(userIds.map((userId) => pokeSeminarMember(room.sessionId, userId)))
  } finally {
    memberBusy.value = false
  }
}

async function startSeminarFromHistory(payload: {
  visibility: 'organization' | 'network'
  title: string
  seedMessages: Array<{ role: string; content: string }>
}): Promise<void> {
  historyStarting.value = true
  try {
    const room = await openStartedSeminar(payload.visibility, {
      title: payload.title,
      seedMessages: payload.seedMessages,
    })
    if (room) {
      historyDialogOpen.value = false
    }
  } finally {
    historyStarting.value = false
  }
}

// Handle suggestion bubble click
function handleSuggestionSelect(suggestion: string) {
  inputText.value = suggestion
  // Focus the input and optionally send immediately
  nextTick(() => {
    sendMessage()
  })
}

// Handle file selection
async function handleFileSelect(files: FileList) {
  if (!files || files.length === 0) return

  for (const file of Array.from(files)) {
    await mindMate.uploadFile(file)
  }
}

function dragHasFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes('Files')
}

function fileDragBlocked(): boolean {
  return showWelcome.value && homeMode.value === 'seminar'
}

function onFileDragEnter(event: DragEvent): void {
  if (fileDragBlocked() || !dragHasFiles(event)) {
    return
  }
  const root = event.currentTarget
  const previous = event.relatedTarget
  if (root instanceof HTMLElement && previous instanceof Node && root.contains(previous)) {
    return
  }
  fileDragActive.value = true
}

function onFileDragOver(event: DragEvent): void {
  if (!fileDragActive.value || !event.dataTransfer) {
    return
  }
  event.dataTransfer.dropEffect = 'copy'
}

function onFileDragLeave(event: DragEvent): void {
  const root = event.currentTarget
  const next = event.relatedTarget
  if (root instanceof HTMLElement && next instanceof Node && root.contains(next)) {
    return
  }
  fileDragActive.value = false
}

function onFileDrop(event: DragEvent): void {
  fileDragActive.value = false
  if (fileDragBlocked()) {
    return
  }
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  const files = event.dataTransfer?.files
  if (!files || files.length === 0) {
    return
  }
  const allowed = Array.from(files).filter((file) => isMindmateComposerUploadableFile(file))
  if (allowed.length < files.length) {
    notify.errorKey('mindmate.input.unsupportedFile')
  }
  if (allowed.length === 0) {
    return
  }
  const transfer = new DataTransfer()
  allowed.forEach((file) => transfer.items.add(file))
  void handleFileSelect(transfer.files)
}

// Stop generation
function stopGeneration() {
  mindMate.stopGeneration()
}

// Copy message to clipboard (diagram answers copy the PNG)
async function copyMessage(content: string) {
  try {
    await copyMindmateAssistantMessage(
      content,
      typeof window !== 'undefined' ? window.location.host : undefined
    )
    notify.successKey('notification.copied')
  } catch {
    notify.errorKey('notification.copyFailed')
  }
}

// Regenerate message
function regenerateMessage(messageId: string) {
  mindMate.regenerateMessage(messageId)
}

// Handle like/dislike feedback
async function handleFeedback(messageId: string, rating: FeedbackRating) {
  const message = mindMate.messages.value.find((m) => m.id === messageId)
  if (!message) return

  // Toggle if same rating clicked again
  const newRating = message.feedback === rating ? null : rating

  const success = await mindMate.submitFeedback(messageId, newRating)
  if (success) {
    notify.success(
      newRating === 'like'
        ? t('notification.feedbackThanks')
        : newRating === 'dislike'
          ? t('notification.feedbackThanksDislike')
          : t('notification.feedbackCancelled')
    )
  }
}

// Open share modal
function cancelShareSelect(): void {
  shareSelectMode.value = false
  selectedMessageIds.value = []
  shareDialogOpen.value = false
}

function beginShareSelect(messageId: string): void {
  shareSelectMode.value = true
  if (!selectedMessageIds.value.includes(messageId)) {
    selectedMessageIds.value = [...selectedMessageIds.value, messageId]
  }
}

function toggleShareSelect(messageId: string): void {
  selectedMessageIds.value = selectedMessageIds.value.includes(messageId)
    ? selectedMessageIds.value.filter((id) => id !== messageId)
    : [...selectedMessageIds.value, messageId]
}

function openSelectedShare(): void {
  if (selectedMessageIds.value.length === 0) {
    return
  }
  shareDialogOpen.value = true
}

const shareLines = computed(() => {
  const chosen = new Set(selectedMessageIds.value)
  const selfName = authStore.user?.username || t('mindmate.highlights.you')
  return mindMate.messages.value
    .filter(
      (message) =>
        chosen.has(message.id) && (message.role === 'user' || message.role === 'assistant')
    )
    .map((message) => {
      const mindgraph =
        message.role === 'assistant' &&
        (hasGeneratedDiagramImage(message.content) ||
          parseMindmateDiagramLibraryId(message.content) !== null)
      const authorName =
        message.role === 'user'
          ? selfName
          : mindgraph
            ? t('mindmate.composer.mindgraph')
            : defaultMindMateTitle.value
      return {
        key: message.id,
        role: message.role === 'user' ? ('user' as const) : ('assistant' as const),
        authorName,
        content: seminarBubblePlainText(
          message.role === 'user' ? displayMindmateUserQueryForUi(message.content) : message.content
        ),
        createdAt: message.timestamp ? new Date(message.timestamp).toISOString() : '',
        highlighted: false,
      }
    })
    .filter((line) => line.content.trim().length > 0)
})

const shareMemberCount = computed(
  () => new Set(shareLines.value.map((line) => line.authorName)).size
)

function previousUserPrompt(messageId: string): string | undefined {
  const msgIndex = mindMate.messages.value.findIndex((item) => item.id === messageId)
  for (let index = msgIndex - 1; index >= 0; index -= 1) {
    if (mindMate.messages.value[index].role === 'user') {
      return mindMate.messages.value[index].content
    }
  }
  return undefined
}

function exportWordTemplate(message: MindMateMessage) {
  void teachingDesignExport.exportAssistantMessage(message, previousUserPrompt(message.id))
}

// Start editing message
function startEdit(message: { id: string; content: string }) {
  editingMessageId.value = message.id
  editingContent.value = message.content
}

// Cancel editing
function cancelEdit() {
  editingMessageId.value = null
  editingContent.value = ''
}

// Save edited message
async function saveEdit(content: string) {
  if (!editingMessageId.value || !content.trim()) {
    cancelEdit()
    return
  }

  const messageId = editingMessageId.value
  editingMessageId.value = null
  editingContent.value = ''

  // Remove the edited user message and resend
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex !== -1) {
    mindMate.messages.value = mindMate.messages.value.slice(0, msgIndex)
  }

  await mindMate.sendMessage(content, false)
}

// Get previous user message for regeneration context
function hasPreviousUserMessage(messageId: string): boolean {
  const msgIndex = mindMate.messages.value.findIndex((m) => m.id === messageId)
  if (msgIndex <= 0) return false

  for (let i = msgIndex - 1; i >= 0; i--) {
    if (mindMate.messages.value[i].role === 'user') {
      return true
    }
  }
  return false
}

// Check if a message is the last assistant message
function isLastAssistantMessage(messageId: string): boolean {
  const assistantMessages = mindMate.messages.value.filter((m) => m.role === 'assistant')
  if (assistantMessages.length === 0) return false
  return assistantMessages[assistantMessages.length - 1].id === messageId
}
</script>

<template>
  <div
    class="mindmate-panel bg-white dark:bg-gray-800 flex flex-col h-full min-w-0 overflow-hidden"
    :class="{
      'border-l border-gray-200 dark:border-gray-700 shadow-lg': !isFullpageMode,
      'panel-mode': !isFullpageMode,
      'welcome-mode': showWelcome,
    }"
  >
    <!-- Full page: expand when sidebar hidden + left-aligned title + new chat -->
    <div
      v-if="isFullpageMode"
      class="mindmate-fullpage-toolbar flex items-center h-12 px-3 gap-2 border-b border-stone-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0"
      :class="{ 'mindmate-fullpage-toolbar--welcome': showWelcome && !isCollabChatroomMode }"
    >
      <button
        v-if="uiStore.sidebarCollapsed"
        type="button"
        class="mindmate-toolbar-icon shrink-0"
        :title="t('sidebar.expandSidebar')"
        :aria-label="t('sidebar.expandSidebar')"
        @click="uiStore.toggleSidebar()"
      >
        <PanelLeftOpen
          :size="16"
          aria-hidden="true"
        />
      </button>
      <MindmateCollabBreadcrumb
        v-if="isCollabChatroomMode"
        class="flex-1 min-w-0 text-left"
        tone="toolbar"
        :visibility="collabVisibility"
        :session-title="collabSessionTitle"
        :can-rename="isSeminarHost"
        :renaming="renamingSeminar"
        @rename="renameCurrentSeminar"
      />
      <h1
        v-else-if="!showWelcome"
        class="mindmate-toolbar-title flex-1 min-w-0 truncate text-left"
        :class="{ 'typing-cursor': isTypingTitle }"
      >
        {{ displayTitle }}
      </h1>
      <div
        v-else
        class="flex-1"
      />
      <MindmateCollabPanel
        v-if="
          showMindmateCollab &&
          !isCollabChatroomMode &&
          !showWelcome &&
          !savedSeminar.sessionId.value
        "
        ref="collabPanelRef"
        :in-conversation="inConversation"
        :conversation-title="mindMateStore.conversationTitle || displayTitle"
        :get-seed-messages="() => mapThreadToCollabSeed(mindMate.messages.value)"
        embed-in-panel
        @session-started="handleCollabSessionStarted"
        @launch-brief="openSeminarFromBrief($event, { includeThread: true })"
      />
      <div class="mindmate-toolbar-actions flex items-center gap-1.5 shrink-0">
        <MindmateSeminarRosterBar
          v-if="isCollabChatroomMode"
          :members-open="seminarMembersPaneOpen"
          :members="seminarGroupMembers"
          :is-leader="isSeminarLeader"
          :self-user-id="Number(authStore.user?.id) || 0"
          :busy="memberBusy"
          @toggle-members="toggleSeminarMembersPane"
          @add-members="openAddSeminarMembers"
          @change-role="onSeminarMemberRoleChange"
          @remove-member="onSeminarMemberRemove"
        />
        <button
          v-if="isCollabChatroomMode && canStopCollabSession"
          type="button"
          class="mindmate-toolbar-text mindmate-toolbar-end shrink-0"
          @click="endCollabSession"
        >
          <I18nText
            k="mindmate.collabEndSeminar"
            dense
          />
        </button>
        <el-button
          v-if="showContinueSession"
          class="continue-session-btn shrink-0"
          size="small"
          @click="continueSavedSeminar"
        >
          <I18nText
            k="mindmate.collabContinueSession"
            dense
          />
        </el-button>
        <el-button
          class="new-chat-btn shrink-0"
          :disabled="!authStore.isAuthenticated"
          @click="startNewConversation"
        >
          <ElIcon class="mr-1"><Plus /></ElIcon>
          <I18nText
            k="mindmate.newChat"
            dense
          />
        </el-button>
      </div>
    </div>
    <MindmateHeader
      v-if="!isFullpageMode"
      :mode="mode"
      :title="displayTitle"
      :is-typing="isTypingTitle"
      :is-authenticated="authStore.isAuthenticated"
      :conversations="mindMate.conversations.value"
      :is-loading-history="historyLoading"
      :current-conversation-id="mindMateStore.currentConversationId"
      :show-contacts-toggle="isCollabChatroomMode"
      :members-open="seminarMembersPaneOpen"
      :show-continue-session="showContinueSession"
      @continue-session="continueSavedSeminar"
      @new-conversation="startNewConversation"
      @close="emit('close')"
      @load-history="loadConversationFromHistory"
      @delete-history="deleteConversationFromHistory"
      @toggle-members="toggleSeminarMembersPane"
      @add-members="openAddSeminarMembers"
    />

    <MindmateCollabSavedTranscript
      v-if="savedSeminar.sessionId.value && !isCollabChatroomMode"
      class="flex-1 min-h-0 min-w-0"
      :session-id="savedSeminar.sessionId.value"
      @ownership="onSavedSeminarOwnership"
      @live="onSavedSeminarLive"
    />

    <!-- Collab chatroom mode (chat + right member column) -->
    <MindmateCollabEmbed
      v-else-if="isCollabChatroomMode && collabRoomCode"
      class="flex-1 min-h-0 min-w-0"
      :room-code="collabRoomCode"
      :seed-messages="collabSeedMessages"
      :members="seminarGroupMembers"
      :is-leader="isSeminarLeader"
      :self-user-id="Number(authStore.user?.id) || 0"
      :member-busy="memberBusy"
      :brief-topic="seminarBriefTopic"
      :brief-goals="seminarBriefGoals"
      @ended="handleCollabEnded"
      @room-meta="handleCollabRoomMeta"
      @goals-change="onSeminarBriefGoals"
      @topic-change="onSeminarBriefTopic"
      @add-members="openAddSeminarMembers"
      @change-role="onSeminarMemberRoleChange"
      @remove-member="onSeminarMemberRemove"
    />

    <template v-else>
      <div
        class="mindmate-stage"
        :class="{
          'mindmate-stage--welcome': showWelcome && isFullpageMode,
          'mindmate-stage--seminar': showWelcome && isFullpageMode && homeMode === 'seminar',
          'mindmate-stage--thread': !showWelcome && isFullpageMode,
        }"
        @dragenter.prevent="onFileDragEnter"
        @dragover.prevent="onFileDragOver"
        @dragleave="onFileDragLeave"
        @drop.prevent="onFileDrop"
      >
        <div
          v-if="fileDragActive"
          class="mm-file-drop"
        >
          <I18nText k="mindmate.input.dropHint" />
        </div>
        <MindmateMessages
          :mode="mode"
          :messages="mindMate.messages.value"
          :user-avatar="userAvatar"
          :show-welcome="showWelcome"
          :show-mode-switch="showHomeModeSwitch"
          :home-mode="homeMode"
          :is-loading="mindMate.isLoading.value"
          :is-streaming="mindMate.isStreaming.value"
          :load-phase="mindMateLoadPhase"
          :is-loading-history="mindMate.isLoadingHistory.value"
          :editing-message-id="editingMessageId"
          :editing-content="editingContent"
          :hovered-message-id="hoveredMessageId"
          :select-mode="shareSelectMode"
          :selected-message-ids="selectedMessageIds"
          :is-last-assistant-message="isLastAssistantMessage"
          :has-previous-user-message="hasPreviousUserMessage"
          :exporting-word-template-id="exportingWordTemplateId"
          @update:home-mode="homeMode = $event"
          @edit="startEdit"
          @cancel-edit="cancelEdit"
          @save-edit="saveEdit"
          @copy="copyMessage"
          @regenerate="regenerateMessage"
          @feedback="handleFeedback"
          @share="beginShareSelect"
          @toggle-select="toggleShareSelect"
          @export-word-template="exportWordTemplate"
          @message-hover="hoveredMessageId = $event"
        />

        <div class="mindmate-input-section">
          <div
            v-if="shareSelectMode"
            class="mm-dm-select-bar"
          >
            <span
              ><I18nText
                k="mindmate.bubble.selected"
                :params="{ n: selectedMessageIds.length }"
            /></span>
            <button
              type="button"
              :disabled="selectedMessageIds.length === 0"
              @click="openSelectedShare"
            >
              <Share2
                :size="14"
                aria-hidden="true"
              />
              <I18nText k="mindmate.tooltip.share" />
            </button>
            <button
              type="button"
              @click="cancelShareSelect"
            >
              <X
                :size="14"
                aria-hidden="true"
              />
              <I18nText k="mindmate.bubble.cancelSelect" />
            </button>
          </div>
          <MindmateInput
            ref="mindmateInputRef"
            v-model:input-text="inputText"
            :mode="mode"
            :is-loading="isLoading"
            :is-streaming="mindMate.isStreaming.value"
            :is-uploading="mindMate.isUploading.value"
            :pending-files="mindMate.pendingFiles.value"
            :show-suggestions="showWelcome"
            :home-mode="homeMode"
            :show-file-upload="isFullpageMode && !(showWelcome && homeMode === 'seminar')"
            :placeholder="
              showWelcome && homeMode === 'seminar' ? t('mindmate.home.seminarPlaceholder') : ''
            "
            @send="sendMessage"
            @stop="stopGeneration"
            @upload="handleFileSelect"
            @remove-file="mindMate.removeFile"
            @suggestion-select="handleSuggestionSelect"
            @seminar-start="openSeminarFromBrief"
          />
        </div>
      </div>

      <MindmateSeminarShareDialog
        :open="shareDialogOpen"
        :title="mindMate.conversationTitle.value || displayTitle"
        :lines="shareLines"
        :member-count="shareMemberCount"
        @close="shareDialogOpen = false"
      />
    </template>

    <MindmateSeminarMemberDialog
      v-model="memberDialogOpen"
      :busy="memberBusy"
      :allow-external="true"
      :exclude-ids="memberDialogMode === 'expand' ? seminarMemberIds : []"
      :title-key="
        memberDialogMode === 'expand'
          ? 'mindmate.home.addMembers'
          : 'mindmate.home.memberDialogTitle'
      "
      :hint-key="
        memberDialogMode === 'expand'
          ? 'mindmate.home.addMembersHint'
          : 'mindmate.home.memberDialogHint'
      "
      :confirm-key="
        memberDialogMode === 'expand'
          ? 'mindmate.home.addMembersConfirm'
          : 'mindmate.home.memberDialogConfirm'
      "
      @confirm="onSeminarMembersConfirm"
    />
    <ElDialog
      v-model="historyDialogOpen"
      width="420px"
      append-to-body
      :title="t('mindmate.home.seminarSuggestHistory')"
    >
      <MindmateCollabStartPicker
        :show-header="false"
        :starting="historyStarting"
        @start="startSeminarFromHistory"
        @back="historyDialogOpen = false"
      />
    </ElDialog>
  </div>
</template>

<style>
@import './mindmate/mindmate-welcome-layout.css';
</style>

<style scoped>
@import './mindmate/mindmate.css';

.mindmate-toolbar-title {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  color: #1c1917;
}

.dark .mindmate-toolbar-title {
  color: #f9fafb;
}

.mindmate-toolbar-icon,
.mindmate-toolbar-text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  border: 1px solid #e9e5ff;
  border-radius: 10px;
  background: #fff;
  color: #6d5efc;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.mindmate-toolbar-icon {
  width: 32px;
  padding: 0;
}

.mindmate-toolbar-text {
  padding: 0 10px;
}

.mindmate-toolbar-icon:hover,
.mindmate-toolbar-text:hover {
  border-color: #c4b5fd;
  color: #5b4eeb;
  background: #f5f3ff;
}

.mindmate-toolbar-text.mindmate-toolbar-end:hover {
  border-color: #fca5a5;
  color: #dc2626;
  background: #fef2f2;
}

.mindmate-toolbar-icon:disabled,
.mindmate-toolbar-text:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.dark .mindmate-toolbar-icon,
.dark .mindmate-toolbar-text {
  border-color: #5b21b6;
  background: #2e1065;
  color: #ddd6fe;
}

.dark .mindmate-toolbar-icon:hover,
.dark .mindmate-toolbar-text:hover {
  border-color: #7c3aed;
  background: #4c1d95;
  color: #ede9fe;
}

.dark .mindmate-toolbar-text.mindmate-toolbar-end:hover {
  border-color: #f87171;
  color: #fecaca;
  background: #7f1d1d;
}

.mindmate-panel.welcome-mode .mindmate-fullpage-toolbar--welcome {
  position: relative;
  z-index: 20;
  background: transparent;
  border-bottom-color: transparent;
}

.mindmate-panel.welcome-mode .mindmate-toolbar-actions {
  position: relative;
  z-index: 21;
}

.mindmate-panel.welcome-mode .new-chat-btn.el-button,
.mindmate-panel.welcome-mode .continue-session-btn.el-button {
  --el-button-bg-color: #ede9fe;
  --el-button-border-color: #c4b5fd;
  --el-button-hover-bg-color: #ddd6fe;
  --el-button-hover-border-color: #a78bfa;
  --el-button-hover-text-color: #4c1d95;
  --el-button-active-bg-color: #c4b5fd;
  --el-button-active-border-color: #8b5cf6;
  --el-button-text-color: #5b21b6;
  height: 32px;
  min-height: 32px;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 10px;
  border-width: 1px;
  border-style: solid;
  background: #ede9fe;
  box-shadow: 0 1px 2px rgba(91, 33, 182, 0.08);
}

.new-chat-btn.el-button,
.continue-session-btn.el-button {
  --el-button-bg-color: #ede9fe;
  --el-button-border-color: #c4b5fd;
  --el-button-hover-bg-color: #ddd6fe;
  --el-button-hover-border-color: #a78bfa;
  --el-button-hover-text-color: #4c1d95;
  --el-button-active-bg-color: #c4b5fd;
  --el-button-active-border-color: #8b5cf6;
  --el-button-text-color: #5b21b6;
  font-weight: 600;
  border-radius: 10px;
  height: 32px;
  min-height: 32px;
  padding: 0 12px;
  font-size: 13px;
  line-height: 1.2;
  background: #ede9fe;
  box-shadow: 0 1px 2px rgba(91, 33, 182, 0.08);
}

.dark .new-chat-btn.el-button,
.dark .continue-session-btn.el-button {
  --el-button-bg-color: #312e81;
  --el-button-border-color: #6366f1;
  --el-button-hover-bg-color: #3730a3;
  --el-button-hover-border-color: #818cf8;
  --el-button-hover-text-color: #e0e7ff;
  --el-button-active-bg-color: #4338ca;
  --el-button-active-border-color: #a5b4fc;
  --el-button-text-color: #e0e7ff;
  background: #312e81;
}

.dark .mindmate-panel.welcome-mode .new-chat-btn.el-button,
.dark .mindmate-panel.welcome-mode .continue-session-btn.el-button {
  --el-button-bg-color: #312e81;
  --el-button-border-color: #6366f1;
  --el-button-hover-bg-color: #3730a3;
  --el-button-hover-border-color: #818cf8;
  --el-button-hover-text-color: #e0e7ff;
  --el-button-active-bg-color: #4338ca;
  --el-button-active-border-color: #a5b4fc;
  --el-button-text-color: #e0e7ff;
  background: #312e81;
}
</style>
