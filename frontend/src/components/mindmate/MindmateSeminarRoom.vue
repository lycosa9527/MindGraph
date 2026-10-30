<script setup lang="ts">
/**
 * MindMate collab chatroom — inline seminar mode inside MindMate (/mindmate).
 * Swiss-style layout aligned with MindmateInput. MindMate speaks only when @mentioned.
 */
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { Share2, Sparkles, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import MindmateSeminarBreadcrumb from '@/components/mindmate/MindmateSeminarBreadcrumb.vue'
import MindmateSeminarMessageRow from '@/components/mindmate/MindmateSeminarMessageRow.vue'
import MindmateSeminarBriefStrip from '@/components/mindmate/MindmateSeminarBriefStrip.vue'
import MindmateSeminarComposerTools from '@/components/mindmate/MindmateSeminarComposerTools.vue'
import MindmateSeminarFaceChatCard from '@/components/mindmate/MindmateSeminarFaceChatCard.vue'
import MindmateSeminarFaceChatSession from '@/components/mindmate/MindmateSeminarFaceChatSession.vue'
import MindmateSeminarFaces from '@/components/mindmate/MindmateSeminarFaces.vue'
import MindmateSeminarShareDialog from '@/components/mindmate/MindmateSeminarShareDialog.vue'
import MindmateSeminarSummaryDialog from '@/components/mindmate/MindmateSeminarSummaryDialog.vue'
import MindmateSoftIcon from '@/components/mindmate/MindmateSoftIcon.vue'
import MindmateInput from '@/components/panels/mindmate/MindmateInput.vue'
import { useLanguage, useNotifications } from '@/composables'
import { ensureMarkdownRenderer } from '@/composables/core/lazyMarkdown'
import { rememberJoinedCollabRoom } from '@/composables/mindmate/mindmateSeminarEmbeddedBridge'
import {
  dropLiveCollabRoom,
  mindmateSeminarLiveCovers,
  useLiveMindmateSeminar,
} from '@/composables/mindmate/mindmateSeminarLiveSession'
import {
  addSeminarComposerAttachments,
  addSeminarHighlight,
  bumpSeminarFolderReload,
  clearSeminarServerArtifacts,
  pushSeminarHighlightNotice,
  removeSeminarCitation,
  removeSeminarComposerAttachment,
  replaceSeminarServerArtifacts,
  seminarArtifactsReady,
  seminarComposerAttachments,
  seminarComposerCitations,
  seminarHighlightNotices,
  seminarHighlights,
  seminarMentionRequest,
  seminarSpectator,
  setSeminarLiveMessages,
  setSeminarMessageLocator,
  takeSeminarCitations,
} from '@/composables/mindmate/mindmateSeminarChrome'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import type { MindmateSeminarMessage } from '@/composables/mindmate/useMindmateSeminar'
import { useSeminarMindgraphPrompt } from '@/composables/mindmate/useSeminarMindgraphPrompt'
import { useSeminarVoiceMessage } from '@/composables/mindmate/useSeminarVoiceMessage'
import { createMindmateSeminarOrgBackend } from '@/composables/social/createMindmateSeminarOrgBackend'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'
import {
  confirmMindmateSeminarLeave,
  confirmMindmateSeminarStop,
} from '@/utils/mindmateSeminarConfirm'
import {
  type CollabFeedbackRating,
  collabMessageRowKey,
  lastFinishedAssistantIndex,
  nextCollabFeedback,
  previousCollabUserPrompt,
} from '@/utils/mindmateSeminarDisplay'
import { sameCollabMessageMinute } from '@/utils/mindmateSeminarRead'
import {
  formatMindmateSeminarCode,
  markMindmateSeminarCodeEnded,
  trackLocalMindmateSeminarSession,
  wasMindmateSeminarCodeRecentlyEnded,
} from '@/utils/mindmateSeminarSessions'
import {
  requestMindmateSeminarLeave,
  requestMindmateSeminarStop,
  teardownMindmateSeminarClient,
} from '@/utils/mindmateSeminarTeardown'
import {
  type MindmateMentionCandidate,
  appendMention,
  contentMentionsMindmate,
  ensureMindmateMention,
} from '@/utils/mindmateMention'
import { type SeminarBriefEditPayload, parseSeminarBriefCard } from '@/utils/mindmateSeminarCards'
import {
  listSeminarReplyArtifacts,
  seminarBubblePlainText,
  seminarFolderErrorKey,
  seminarMessageFileToken,
  uploadSeminarBackgroundFile,
} from '@/utils/mindmateSeminarFolder'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'

const props = withDefaults(
  defineProps<{
    roomCode: string
    /** True when embedded in MindmatePanel (seminar mode). */
    embedded?: boolean
    /** Prior 1:1 MindMate thread messages shown above collab room chat. */
    seedMessages?: MindmateSeminarMessage[]
    briefTopic?: string
    briefGoals?: string[]
    members?: SeminarGroupMember[]
  }>(),
  {
    embedded: true,
    seedMessages: () => [],
    briefTopic: '',
    briefGoals: () => [],
    members: () => [],
  }
)

const emit = defineEmits<{
  (e: 'ended', reason: 'expired' | 'host' | 'left'): void
  (
    e: 'roomMeta',
    payload: {
      title: string
      visibility: string
      sessionId: string
      code: string
      ownerId: number
    }
  ): void
  (e: 'goalsChange', goals: string[]): void
  (e: 'topicChange', topic: string): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { displayName: mindmateAgentName, avatarUrl: mindmateAvatarUrl } = useMindMateBranding()

const normalizedCode = computed(() => formatMindmateSeminarCode(props.roomCode))

const isSpectator = computed(() => {
  const selfId = Number(authStore.user?.id || 0)
  if (!selfId) {
    return false
  }
  const self = props.members.find((member) => member.userId === selfId)
  return self?.role === 'observer'
})

watch(
  isSpectator,
  (value) => {
    seminarSpectator.value = value
  },
  { immediate: true }
)

const {
  messages,
  hasOlder,
  room,
  connected,
  connectionStatus,
  isStreaming,
  isHost,
  canSend,
  canRetryConnection,
  connect,
  replaceMessageContent,
  sendSeminarMessage,
  sendSeminarMinutes,
  seedRoom,
  loadOlderMessages,
  retryConnection,
  readCursors,
} = useLiveMindmateSeminar(normalizedCode.value, {
  onSessionEnded: (reason) => {
    roomEndNotified = true
    emit('ended', reason)
  },
  seedMessages: () => props.seedMessages ?? [],
})

provide('mindmateSeminarMessages', messages)

watch(
  messages,
  (value) => {
    setSeminarLiveMessages(value)
  },
  { immediate: true, deep: true }
)

let briefGoalsKey: string | null = null
let briefTopicKey: string | null = null
watch(
  messages,
  (rows) => {
    const card = rows
      .map((row) => parseSeminarBriefCard(row.content || ''))
      .find((item) => item != null)
    if (!card) {
      return
    }
    if (card.topic !== briefTopicKey) {
      briefTopicKey = card.topic
      emit('topicChange', card.topic)
    }
    const key = card.goals.join('\n')
    if (key === briefGoalsKey) {
      return
    }
    briefGoalsKey = key
    emit('goalsChange', card.goals)
  },
  { immediate: true }
)

const {
  recording: voiceRecording,
  start: startVoiceMessage,
  stop: stopVoiceMessage,
  cancel: cancelVoiceMessage,
  noteRelease: noteVoiceRelease,
} = useSeminarVoiceMessage()
const faceChatOpen = ref(false)
const faceChatLive = ref(false)
const summaryOpen = ref(false)
const summaryPreselect = ref<string[]>([])
const replyQuote = ref<{ author: string; text: string } | null>(null)
const selectMode = ref(false)
const selectedKeys = ref<string[]>([])
const mentionRoster = createMindmateSeminarOrgBackend(
  () => room.value?.code || normalizedCode.value,
  () => room.value?.visibility || 'organization',
  undefined,
  () => room.value?.sessionId || ''
)

const mentionCandidates = computed((): MindmateMentionCandidate[] => {
  const agentName = mindmateAgentName.value.trim() || 'MindMate'
  const agent: MindmateMentionCandidate = {
    id: 'agent-mindmate',
    name: agentName,
    avatar: '✨',
    kind: 'agent',
  }
  const people = mentionRoster.members.value.map((member) => ({
    id: `user-${member.id}`,
    name: member.name,
    avatar: member.avatar,
    kind: 'user' as const,
  }))
  return [agent, ...people]
})

let joinGeneration = 0
let roomEndNotified = false
const stoppingRoom = ref(false)
const leavingRoom = ref(false)
const savingBrief = ref(false)
const fileDragDepth = ref(0)
const dragOverInput = ref(false)
const uploadingFiles = ref(false)
const attachingFiles = ref(false)

const inputText = ref('')
const composerRef = ref<{ focus: (place?: 'end') => void } | null>(null)

watch(seminarMentionRequest, (request) => {
  if (!request || isSpectator.value) {
    return
  }
  inputText.value = appendMention(inputText.value, request.name)
  seminarMentionRequest.value = null
  void nextTick(() => {
    composerRef.value?.focus('end')
    requestAnimationFrame(() => {
      composerRef.value?.focus('end')
    })
  })
})
const joining = ref(false)
const followTranscript = ref(true)
const showShareModal = ref(false)
const shareScope = ref<'all' | 'selected'>('all')
const feedbackByKey = ref<Record<string, CollabFeedbackRating>>({})

const mindmateTagged = ref(false)
const mindgraphTagged = ref(false)
const { generateAndShare: generateSeminarDiagram, isGenerating: mindgraphGenerating } =
  useSeminarMindgraphPrompt()

const inputPlaceholder = computed(() => {
  if (mindgraphTagged.value) {
    return t('mindmate.composer.mindgraphHint', '输入生成思维图示的指令，如：用双气泡图对比...')
  }
  return t('mindmate.collabInputPlaceholderSeminar', '发送消息或@MindMate ')
})
const citations = seminarComposerCitations

const showConnectionBanner = computed(
  () => connectionStatus.value === 'reconnecting' || connectionStatus.value === 'failed'
)

const connectionBannerText = computed(() => {
  if (connectionStatus.value === 'reconnecting') {
    return t('mindmate.collabReconnecting')
  }
  return t('mindmate.collabConnectionLost')
})

const roomTitle = computed(() => room.value?.title || t('mindmate.collabPill'))

async function parseJoinErrorDetail(response: Response): Promise<string> {
  try {
    const err = (await response.json()) as { detail?: string }
    return err.detail?.trim() || t('mindmate.collabJoinFailed')
  } catch {
    return t('mindmate.collabJoinFailed')
  }
}

let viewActive = true

const headerSubtitle = computed(() => {
  if (room.value?.visibility === 'network') {
    return ''
  }
  return `${normalizedCode.value} · ${room.value?.visibility || ''}`
})

async function joinRoomAndConnect(): Promise<void> {
  const code = normalizedCode.value
  if (!code) {
    return
  }
  if (wasMindmateSeminarCodeRecentlyEnded(code)) {
    dropLiveCollabRoom(code)
    if (viewActive) {
      emit('ended', 'host')
    }
    return
  }
  if (mindmateSeminarLiveCovers(code)) {
    rememberJoinedCollabRoom(code)
    return
  }
  const generation = ++joinGeneration
  if (viewActive) {
    joining.value = true
  }
  try {
    const response = await authFetch(`/api/mindmate/seminar/join?code=${encodeURIComponent(code)}`, {
      method: 'POST',
    })
    if (generation !== joinGeneration) {
      return
    }
    if (!response.ok) {
      const hostJustEnded = wasMindmateSeminarCodeRecentlyEnded(code)
      if (response.status === 409) {
        dropLiveCollabRoom(code)
        if (viewActive) {
          notify.error(await parseJoinErrorDetail(response))
          emit('ended', 'left')
        }
        return
      }
      if (response.status === 404 || hostJustEnded) {
        markMindmateSeminarCodeEnded(code)
        dropLiveCollabRoom(code)
        teardownMindmateSeminarClient(code, { removeFromHistory: true })
        if (viewActive) {
          emit('ended', 'host')
          if (!hostJustEnded) {
            notify.error(await parseJoinErrorDetail(response))
          }
        }
        return
      }
      dropLiveCollabRoom(code)
      if (viewActive) {
        notify.error(await parseJoinErrorDetail(response))
        emit('ended', 'left')
      }
      return
    }
    const data = (await response.json()) as Record<string, unknown>
    if (generation !== joinGeneration) {
      return
    }
    trackLocalMindmateSeminarSession({
      session_id: String(data.session_id || ''),
      code: String(data.code || code),
      title: String(data.title || t('mindmate.collabPill')),
      owner_user_id: Number(data.owner_user_id || 0),
      participant_count: Number(data.participant_count || 0),
      visibility: String(data.visibility || 'organization'),
      expires_at: (data.expires_at as string | null) ?? null,
    })
    seedRoom({
      sessionId: String(data.session_id || ''),
      code: String(data.code || code),
      title: String(data.title || t('mindmate.collabPill')),
      visibility: String(data.visibility || 'organization'),
      ownerId: Number(data.owner_user_id || 0),
    })
    connect()
    rememberJoinedCollabRoom(code)
  } catch {
    dropLiveCollabRoom(code)
    if (viewActive) {
      notify.errorKey('mindgraphLanding.networkErrorJoin')
      emit('ended', 'left')
    }
  } finally {
    if (viewActive) {
      joining.value = false
    }
  }
}

function locateHighlightMessage(messageId: number): void {
  const root = messagesScrollEl.value
  if (!root) {
    return
  }
  const target = root.querySelector(`[data-collab-message-id="${messageId}"]`)
  target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

onUnmounted(() => {
  viewActive = false
  seminarSpectator.value = false
  setSeminarLiveMessages([])
  setSeminarMessageLocator(null)
})

onMounted(() => {
  setSeminarMessageLocator(locateHighlightMessage)
  void ensureMarkdownRenderer()
  followTranscript.value = true
  void joinRoomAndConnect()
  void scrollTranscriptToBottom()
})

watch(
  room,
  (value) => {
    if (value) {
      trackLocalMindmateSeminarSession({
        session_id: value.sessionId,
        code: value.code,
        title: value.title,
        owner_user_id: value.ownerId,
        visibility: value.visibility,
      })
      emit('roomMeta', {
        title: value.title,
        visibility: value.visibility,
        sessionId: value.sessionId,
        code: value.code,
        ownerId: value.ownerId,
      })
    }
  },
  { immediate: true }
)

let replyArtifactLoad = 0

watch(
  () => room.value?.sessionId,
  (sessionId) => {
    const ticket = ++replyArtifactLoad
    clearSeminarServerArtifacts()
    if (!sessionId) {
      return
    }
    void mentionRoster.fetchMembers({ limit: 200 })
    void listSeminarReplyArtifacts(sessionId)
      .then((rows) => {
        if (ticket === replyArtifactLoad) {
          replaceSeminarServerArtifacts(rows)
          seminarArtifactsReady.value = true
        }
      })
      .catch(() => {
        /* leave the artifact list empty until the next load */
      })
  }
)

async function leaveRoom() {
  const sessionId = room.value?.sessionId
  if (!sessionId || leavingRoom.value || isHost.value) {
    return
  }
  const confirmed = await confirmMindmateSeminarLeave(t)
  if (!confirmed) {
    return
  }
  leavingRoom.value = true
  const code = normalizedCode.value
  try {
    const ok = await requestMindmateSeminarLeave(sessionId)
    if (!ok) {
      notify.errorKey('mindmate.collabLeaveFailed')
      return
    }
    dropLiveCollabRoom(code)
    teardownMindmateSeminarClient(code, { removeFromHistory: true })
    emit('ended', 'left')
    notify.successKey('mindmate.collabLeft')
  } catch {
    notify.errorKey('mindmate.collabLeaveFailed')
  } finally {
    leavingRoom.value = false
  }
}

async function stopRoom() {
  const sessionId = room.value?.sessionId
  if (!sessionId || stoppingRoom.value) {
    return
  }
  const confirmed = await confirmMindmateSeminarStop(t)
  if (!confirmed) {
    return
  }
  stoppingRoom.value = true
  const code = normalizedCode.value
  try {
    const ok = await requestMindmateSeminarStop(sessionId)
    if (!ok) {
      notify.errorKey('collab.endFailed')
      return
    }
    dropLiveCollabRoom(code)
    if (roomEndNotified) {
      return
    }
    emit('ended', 'host')
    notify.successKey('mindmate.collabStopped')
  } catch {
    notify.errorKey('collab.endFailed')
  } finally {
    stoppingRoom.value = false
  }
}

function locateBriefCard(): void {
  const card = messagesScrollEl.value?.querySelector('[data-seminar-brief-card]')
  card?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function openSummary(keys: string[] = []): void {
  if (isSpectator.value) {
    return
  }
  summaryPreselect.value = keys
  summaryOpen.value = true
}

function quoteReply(quote: { author: string; text: string }): void {
  replyQuote.value = quote
}

function beginMultiSelect(key: string): void {
  selectMode.value = true
  if (!selectedKeys.value.includes(key)) {
    selectedKeys.value = [...selectedKeys.value, key]
  }
}

function toggleSelected(key: string): void {
  selectedKeys.value = selectedKeys.value.includes(key)
    ? selectedKeys.value.filter((item) => item !== key)
    : [...selectedKeys.value, key]
}

function cancelSelect(): void {
  selectMode.value = false
  selectedKeys.value = []
}

function shareTranscript(): void {
  shareScope.value = 'all'
  showShareModal.value = true
}

function shareSelected(): void {
  if (selectedKeys.value.length === 0) {
    return
  }
  shareScope.value = 'selected'
  showShareModal.value = true
}

function selectedRows() {
  const keys = new Set(selectedKeys.value)
  return transcript.value.filter((row) => keys.has(row.key))
}

function pinSelected(): void {
  const sessionId = room.value?.sessionId?.trim()
  if (!sessionId) {
    return
  }
  for (const row of selectedRows()) {
    if (row.kind !== 'message') {
      continue
    }
    const text = seminarBubblePlainText(row.msg.content).slice(0, 2000)
    if (!text) {
      continue
    }
    const authorName =
      row.msg.role === 'assistant'
        ? mindmateAgentName.value
        : row.msg.username?.trim() || t('mindmate.highlights.you')
    const added = addSeminarHighlight(sessionId, {
      text,
      authorName,
      messageId: row.msg.id ?? null,
      createdByUserId: Number(authStore.user?.id) || null,
      createdByName: authStore.user?.username || t('mindmate.highlights.you'),
      messageAt: row.msg.created_at || '',
    })
    if (added) {
      pushSeminarHighlightNotice(sessionId, {
        kind: 'set',
        ownMessage: isOwnMessage(row.msg),
        authorName,
      })
    }
  }
  notify.successKey('mindmate.highlights.added')
  cancelSelect()
}

function postSummary(content: string): void {
  if (isSpectator.value || joining.value) {
    return
  }
  if (!room.value?.sessionId) {
    notify.warningKey('mindmate.collabNotConnected')
    return
  }
  followTranscript.value = true
  sendSeminarMinutes(content)
  summaryOpen.value = false
}

function onSeminarVoice(): void {
  if (isSpectator.value) {
    return
  }
  cancelVoiceMessage()
  faceChatOpen.value = true
}

function startFaceChat(): void {
  faceChatOpen.value = false
  faceChatLive.value = true
}

async function onVoicePress(): Promise<void> {
  if (isSpectator.value) {
    return
  }
  const result = await startVoiceMessage()
  if (result instanceof File) {
    await sendVoiceFile(result)
    return
  }
  if (result === null) {
    notify.warningKey('mindmate.composer.voiceTooShort')
  }
}

async function onVoiceRelease(send: boolean): Promise<void> {
  if (!voiceRecording.value) {
    noteVoiceRelease(send)
    return
  }
  if (!send) {
    cancelVoiceMessage()
    return
  }
  const file = await stopVoiceMessage()
  if (!file) {
    notify.warningKey('mindmate.composer.voiceTooShort')
    return
  }
  await sendVoiceFile(file)
}

async function saveBriefCard(
  payload: SeminarBriefEditPayload,
  done: (ok: boolean) => void
): Promise<void> {
  const sessionId = room.value?.sessionId
  if (!sessionId || savingBrief.value) {
    done(false)
    return
  }
  savingBrief.value = true
  try {
    const response = await authFetch('/api/mindmate/seminar/brief', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        topic: payload.topic,
        goals: payload.goals,
      }),
    })
    if (!response.ok) {
      notify.errorKey('mindmate.briefCard.saveFailed')
      done(false)
      return
    }
    const body = (await response.json()) as {
      message_id?: number
      content?: string
      title?: string
    }
    const messageId = Number(body.message_id)
    const content = String(body.content || '')
    if (Number.isFinite(messageId) && content) {
      replaceMessageContent(messageId, content)
    }
    const title = String(body.title || '').trim()
    if (title && room.value) {
      emit('roomMeta', {
        title,
        visibility: room.value.visibility,
        sessionId,
        code: room.value.code,
        ownerId: room.value.ownerId,
      })
    }
    done(true)
  } catch {
    notify.errorKey('mindmate.briefCard.saveFailed')
    done(false)
  } finally {
    savingBrief.value = false
  }
}

async function sendVoiceFile(file: File): Promise<void> {
  const sessionId = room.value?.sessionId
  if (!sessionId || !canSend.value || joining.value || attachingFiles.value) {
    return
  }
  attachingFiles.value = true
  try {
    const saved = await uploadSeminarBackgroundFile(sessionId, file, { listed: false })
    followTranscript.value = true
    sendSeminarMessage(seminarMessageFileToken(saved.id, saved.filename), { toMindmate: false })
  } catch (error) {
    notify.errorKey(seminarFolderErrorKey(error))
  } finally {
    attachingFiles.value = false
  }
}

function dragHasFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes('Files')
}

function onRoomDragEnter(event: DragEvent): void {
  if (isSpectator.value || !dragHasFiles(event)) {
    return
  }
  const root = event.currentTarget
  const previous = event.relatedTarget
  if (root instanceof HTMLElement && previous instanceof Node && root.contains(previous)) {
    return
  }
  fileDragDepth.value = 1
}

function dropPointInInput(event: DragEvent): boolean {
  const root = event.currentTarget
  if (!(root instanceof HTMLElement)) {
    return false
  }
  const input = root.querySelector('.mindmate-seminar-room__input')
  if (!(input instanceof HTMLElement)) {
    return false
  }
  const rect = input.getBoundingClientRect()
  return (
    event.clientX >= rect.left &&
    event.clientX <= rect.right &&
    event.clientY >= rect.top &&
    event.clientY <= rect.bottom
  )
}

function onRoomDragOver(event: DragEvent): void {
  if (!dragHasFiles(event) || !event.dataTransfer) {
    return
  }
  dragOverInput.value = dropPointInInput(event)
  event.dataTransfer.dropEffect = 'copy'
}

function onRoomDragLeave(event: DragEvent): void {
  if (!dragHasFiles(event)) {
    return
  }
  const root = event.currentTarget
  const next = event.relatedTarget
  if (root instanceof HTMLElement && next instanceof Node && root.contains(next)) {
    return
  }
  fileDragDepth.value = 0
  dragOverInput.value = false
}

async function uploadRoomFiles(files: File[]): Promise<void> {
  const sessionId = room.value?.sessionId
  if (isSpectator.value || !sessionId || files.length === 0 || uploadingFiles.value) {
    return
  }
  uploadingFiles.value = true
  try {
    for (const file of files) {
      await uploadSeminarBackgroundFile(sessionId, file)
    }
    bumpSeminarFolderReload()
    notify.successKey('mindmate.folder.uploaded')
  } catch (error) {
    notify.errorKey(seminarFolderErrorKey(error))
  } finally {
    uploadingFiles.value = false
  }
}

function onRoomDrop(event: DragEvent): void {
  fileDragDepth.value = 0
  const ontoInput = dragOverInput.value || dropPointInInput(event)
  dragOverInput.value = false
  const files = event.dataTransfer?.files
  if (!files || files.length === 0) {
    return
  }
  const picked = Array.from(files)
  if (ontoInput) {
    addSeminarComposerAttachments(picked)
    return
  }
  void uploadRoomFiles(picked)
}

function callSeminarAgent(): void {
  setSeminarAgentTag('mindmate')
}

function setSeminarAgentTag(tag: 'mindmate' | 'mindgraph'): void {
  mindmateTagged.value = tag === 'mindmate'
  mindgraphTagged.value = tag === 'mindgraph'
}

function clearSeminarTag(tag: 'mindmate' | 'mindgraph'): void {
  if (tag === 'mindmate') {
    mindmateTagged.value = false
    return
  }
  mindgraphTagged.value = false
}

async function handleSend() {
  if (isSpectator.value) {
    return
  }
  if (mindgraphTagged.value) {
    const prompt = inputText.value.trim()
    const sessionId = room.value?.sessionId ?? ''
    if (!prompt || !sessionId || mindgraphGenerating.value || !canSend.value || joining.value) {
      return
    }
    inputText.value = ''
    const shared = await generateSeminarDiagram(sessionId, prompt)
    if (!shared) {
      inputText.value = prompt
    }
    return
  }
  const typed = inputText.value.trim()
  const cited = takeSeminarCitations()
  const attached = [...seminarComposerAttachments.value]
  if (
    (!typed && !replyQuote.value && cited.length === 0 && attached.length === 0) ||
    !canSend.value ||
    joining.value ||
    attachingFiles.value
  ) {
    if (cited.length > 0) {
      seminarComposerCitations.value = [...cited, ...seminarComposerCitations.value]
    }
    return
  }
  let fileBlock = ''
  if (attached.length > 0) {
    const sessionId = room.value?.sessionId
    if (!sessionId) {
      seminarComposerCitations.value = [...cited, ...seminarComposerCitations.value]
      return
    }
    attachingFiles.value = true
    try {
      const tokens: string[] = []
      for (const item of attached) {
        const saved = await uploadSeminarBackgroundFile(sessionId, item.file, { listed: false })
        tokens.push(seminarMessageFileToken(saved.id, saved.filename))
      }
      fileBlock = tokens.join('\n')
      const sentKeys = new Set(attached.map((item) => item.key))
      seminarComposerAttachments.value = seminarComposerAttachments.value.filter(
        (item) => !sentKeys.has(item.key)
      )
    } catch (error) {
      seminarComposerCitations.value = [...cited, ...seminarComposerCitations.value]
      notify.errorKey(seminarFolderErrorKey(error))
      return
    } finally {
      attachingFiles.value = false
    }
  }
  followTranscript.value = true
  const addressed =
    mindmateTagged.value || mindgraphTagged.value
      ? ensureMindmateMention(typed, mindmateAgentName.value)
      : typed
  const citeBlock = cited.map((item) => `📎 ${item.filename}`).join('\n')
  const quote = replyQuote.value
  const quoteBlock = quote
    ? `${t('mindmate.bubble.replying', { name: quote.author })}\n${quote.text}`
    : ''
  const content = [quoteBlock, addressed, citeBlock, fileBlock].filter(Boolean).join('\n\n')
  replyQuote.value = null
  const toMindmate =
    mindmateTagged.value ||
    mindgraphTagged.value ||
    contentMentionsMindmate(content, [mindmateAgentName.value])
  sendSeminarMessage(content, { toMindmate })
  inputText.value = ''
}

function handleRegenerate(prompt: string | undefined): void {
  const text = prompt?.trim()
  if (!text || !canSend.value || joining.value || isSpectator.value) {
    return
  }
  sendSeminarMessage(text, { toMindmate: true })
}

function handleFeedback(key: string, clicked: 'like' | 'dislike'): void {
  const next = nextCollabFeedback(feedbackByKey.value[key], clicked)
  feedbackByKey.value = { ...feedbackByKey.value, [key]: next }
  const thanksKey =
    next === 'like'
      ? 'notification.feedbackThanks'
      : next === 'dislike'
        ? 'notification.feedbackThanksDislike'
        : 'notification.feedbackCancelled'
  notify.successKey(thanksKey)
}

function handleRetryConnection(): void {
  if (joining.value) {
    return
  }
  if (room.value?.sessionId) {
    retryConnection()
    return
  }
  void joinRoomAndConnect()
}

function isOwnMessage(msg: MindmateSeminarMessage): boolean {
  if (msg.role !== 'user') {
    return false
  }
  const selfId = Number(authStore.user?.id)
  const senderId = Number(msg.sender_user_id)
  return selfId > 0 && senderId === selfId
}

const lastAssistantIdx = computed(() => lastFinishedAssistantIndex(messages.value))

function shareAuthorName(msg: MindmateSeminarMessage): string {
  if (msg.role === 'assistant') {
    return mindmateAgentName.value.trim() || 'MindMate'
  }
  if (isOwnMessage(msg)) {
    return authStore.user?.username || t('mindmate.highlights.you')
  }
  return msg.username?.trim() || t('mindmate.highlights.you')
}

const shareLines = computed(() => {
  const highlighted = new Set(
    seminarHighlights.value
      .map((item) => item.messageId)
      .filter((id): id is number => typeof id === 'number' && id > 0)
  )
  const scoped =
    shareScope.value === 'selected'
      ? messages.value
          .map((msg, index) => ({ msg, index }))
          .filter((row) => selectedKeys.value.includes(collabMessageRowKey(row.msg, row.index)))
      : messages.value.map((msg, index) => ({ msg, index }))
  return scoped
    .filter(
      (row) => !row.msg.streaming && seminarBubblePlainText(row.msg.content).trim().length > 0
    )
    .map((row) => ({
      key: collabMessageRowKey(row.msg, row.index),
      role: row.msg.role,
      authorName: shareAuthorName(row.msg),
      content: seminarBubblePlainText(row.msg.content),
      createdAt: row.msg.created_at || '',
      highlighted: typeof row.msg.id === 'number' && highlighted.has(row.msg.id),
    }))
})

const shareMemberCount = computed(() => {
  if (props.members.length > 0) {
    return props.members.length
  }
  return new Set(shareLines.value.map((line) => line.authorName)).size
})

function highlightInstant(iso: string | undefined): number | null {
  if (!iso) {
    return null
  }
  const time = Date.parse(iso)
  return Number.isNaN(time) ? null : time
}

const transcript = computed(() => {
  let previousCreatedAt: string | undefined
  const messageRows = messages.value.map((msg, idx) => {
    const showTime = !sameCollabMessageMinute(msg.created_at, previousCreatedAt)
    if (msg.created_at && !Number.isNaN(Date.parse(msg.created_at))) {
      previousCreatedAt = msg.created_at
    }
    return {
      kind: 'message' as const,
      key: collabMessageRowKey(msg, idx),
      msg,
      isOwn: isOwnMessage(msg),
      isLastAssistant: idx === lastAssistantIdx.value,
      showTime,
      userPrompt:
        msg.role === 'assistant' ? previousCollabUserPrompt(messages.value, idx) : undefined,
    }
  })
  const notices = [...seminarHighlightNotices.value].sort(
    (left, right) =>
      (highlightInstant(left.createdAt) ?? 0) - (highlightInstant(right.createdAt) ?? 0)
  )
  const merged: Array<
    (typeof messageRows)[number] | { kind: 'notice'; key: string; notice: (typeof notices)[number] }
  > = []
  let noticeIndex = 0
  for (const row of messageRows) {
    const at = highlightInstant(row.msg.created_at)
    while (noticeIndex < notices.length && at != null) {
      const noticeAt = highlightInstant(notices[noticeIndex].createdAt)
      if (noticeAt == null || noticeAt > at) {
        break
      }
      const notice = notices[noticeIndex]
      merged.push({ kind: 'notice', key: notice.id, notice })
      noticeIndex += 1
    }
    merged.push(row)
  }
  while (noticeIndex < notices.length) {
    const notice = notices[noticeIndex]
    merged.push({ kind: 'notice', key: notice.id, notice })
    noticeIndex += 1
  }
  return merged
})

function highlightNoticeText(notice: {
  kind: 'set' | 'cancel' | 'shelf'
  ownMessage: boolean
  authorName: string
  title?: string
  destination?: 'resource' | 'artifact' | 'removed'
  shelf?: 'resource' | 'artifact'
}): string {
  if (notice.kind === 'shelf') {
    const title = notice.title || ''
    if (notice.destination === 'resource') {
      return notice.ownMessage
        ? t('mindmate.shelf.noticeResourceOwn', { title })
        : t('mindmate.shelf.noticeResourceOther', { name: notice.authorName, title })
    }
    if (notice.destination === 'removed' && notice.shelf === 'resource') {
      return notice.ownMessage
        ? t('mindmate.shelf.noticeRemovedResourceOwn', { title })
        : t('mindmate.shelf.noticeRemovedResourceOther', { name: notice.authorName, title })
    }
    if (notice.destination === 'removed') {
      return notice.ownMessage
        ? t('mindmate.shelf.noticeRemovedOwn', { title })
        : t('mindmate.shelf.noticeRemovedOther', { name: notice.authorName, title })
    }
    return notice.ownMessage
      ? t('mindmate.shelf.noticeArtifactOwn', { title })
      : t('mindmate.shelf.noticeArtifactOther', { name: notice.authorName, title })
  }
  if (notice.kind === 'set') {
    return notice.ownMessage
      ? t('mindmate.highlights.noticeSetOwn')
      : t('mindmate.highlights.noticeSetOther', { name: notice.authorName })
  }
  return notice.ownMessage
    ? t('mindmate.highlights.noticeCancelOwn')
    : t('mindmate.highlights.noticeCancelOther', { name: notice.authorName })
}

const messagesScrollEl = ref<HTMLElement | null>(null)
let programmaticScroll = false

function isMessagesNearBottom(): boolean {
  const el = messagesScrollEl.value
  if (!el) {
    return true
  }
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

function scrollMessagesToBottom(): void {
  const el = messagesScrollEl.value
  if (!el) {
    return
  }
  programmaticScroll = true
  el.scrollTop = el.scrollHeight
}

function releaseProgrammaticScroll(): void {
  requestAnimationFrame(() => {
    programmaticScroll = false
  })
}

async function scrollTranscriptToBottom(): Promise<void> {
  await nextTick()
  scrollMessagesToBottom()
  requestAnimationFrame(() => {
    scrollMessagesToBottom()
    releaseProgrammaticScroll()
  })
}

function onMessagesScroll(): void {
  if (programmaticScroll) {
    return
  }
  followTranscript.value = isMessagesNearBottom()
  const el = messagesScrollEl.value
  if (!el || el.scrollTop >= 80 || el.scrollHeight <= el.clientHeight) {
    return
  }
  if (!hasOlder.value) {
    return
  }
  void loadOlderKeepingPlace()
}

async function loadOlderKeepingPlace(): Promise<void> {
  const el = messagesScrollEl.value
  if (!el) {
    return
  }
  const beforeHeight = el.scrollHeight
  const beforeTop = el.scrollTop
  followTranscript.value = false
  await loadOlderMessages()
  await nextTick()
  const grown = el.scrollHeight - beforeHeight
  if (grown <= 0) {
    return
  }
  programmaticScroll = true
  el.scrollTop = beforeTop + grown
  releaseProgrammaticScroll()
}

watch(messages, () => {
  if (!followTranscript.value) {
    return
  }
  void scrollTranscriptToBottom()
})

watch(seminarHighlightNotices, () => {
  if (!followTranscript.value) {
    return
  }
  void scrollTranscriptToBottom()
})
</script>

<template>
  <div
    class="mindmate-seminar-room flex flex-1 min-h-0 min-w-0 w-full overflow-hidden"
    :class="{
      'mindmate-seminar-room--embedded': embedded,
    }"
  >
    <div
      class="mindmate-seminar-room__main flex flex-col flex-1 min-h-0 min-w-0"
      @dragenter.prevent="onRoomDragEnter"
      @dragover.prevent="onRoomDragOver"
      @dragleave="onRoomDragLeave"
      @drop.prevent="onRoomDrop"
    >
      <div
        v-if="fileDragDepth > 0"
        class="mindmate-seminar-room__drop"
        :class="{ 'mindmate-seminar-room__drop--input': dragOverInput }"
      >
        <I18nText :k="dragOverInput ? 'mindmate.input.dropHint' : 'mindmate.folder.dropHint'" />
      </div>
      <header
        v-if="!embedded"
        class="mindmate-seminar-room__header shrink-0 px-4 py-3 border-b border-stone-200 bg-white flex items-center justify-between gap-3"
      >
        <div class="min-w-0 flex-1">
          <MindmateSeminarBreadcrumb
            :visibility="room?.visibility || 'organization'"
            :session-title="roomTitle"
          />
          <p
            v-if="headerSubtitle"
            class="text-[11px] text-stone-400 truncate mt-0.5"
          >
            {{ headerSubtitle }}
          </p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <MindmateSeminarFaces />
          <ElButton
            v-if="!isHost"
            class="mindmate-seminar-room__end-btn shrink-0"
            size="small"
            :disabled="leavingRoom"
            @click="leaveRoom"
          >
            <I18nText
              k="mindmate.collabLeaveSeminar"
              dense
            />
          </ElButton>
          <ElButton
            v-if="isHost"
            class="mindmate-seminar-room__end-btn shrink-0"
            size="small"
            :disabled="stoppingRoom"
            @click="stopRoom"
          >
            <I18nText
              k="mindmate.collabEndSeminar"
              dense
            />
          </ElButton>
        </div>
      </header>

      <MindmateSeminarBriefStrip
        v-if="briefTopic || briefGoals.length"
        :topic="briefTopic"
        :goals="briefGoals"
        @locate="locateBriefCard"
      />

      <div
        v-if="showConnectionBanner"
        class="text-xs px-4 py-2 text-center shrink-0 border-b flex items-center justify-center gap-3"
        :class="
          connectionStatus === 'reconnecting'
            ? 'bg-sky-50 text-sky-800 border-sky-100'
            : 'bg-rose-50 text-rose-800 border-rose-100'
        "
      >
        <span>{{ connectionBannerText }}</span>
        <button
          v-if="canRetryConnection"
          type="button"
          class="underline font-medium hover:opacity-80"
          @click="handleRetryConnection"
        >
          <I18nText k="mindmate.collabRetryConnection" />
        </button>
      </div>

      <div class="mindmate-seminar-room__messages">
        <div
          ref="messagesScrollEl"
          class="mindmate-seminar-room__messages-scroll"
          @scroll="onMessagesScroll"
        >
          <div class="mindmate-seminar-room__messages-inner">
            <div
              v-if="joining && !connected"
              class="text-sm text-stone-500 text-center py-12"
            >
              <I18nText k="mindmate.collabJoining" />
            </div>

            <template
              v-for="row in transcript"
              :key="row.key"
            >
              <p
                v-if="row.kind === 'notice'"
                class="mm-highlight-notice"
              >
                <span>{{ highlightNoticeText(row.notice) }}</span>
              </p>
              <MindmateSeminarMessageRow
                v-else
                :message="row.msg"
                :is-own="row.isOwn"
                :user-prompt="row.userPrompt"
                :agent-name="mindmateAgentName"
                :agent-avatar-url="mindmateAvatarUrl"
                :regenerate-disabled="!canSend || joining || isStreaming"
                :feedback="feedbackByKey[row.key]"
                :session-id="room?.sessionId || ''"
                :read-cursors="readCursors"
                :select-mode="selectMode"
                :selected="selectedKeys.includes(row.key)"
                :brief-editable="isHost"
                :brief-saving="savingBrief"
                :show-time="row.showTime"
                @save-brief="saveBriefCard"
                @regenerate="handleRegenerate(row.userPrompt)"
                @share="shareTranscript"
                @feedback="handleFeedback(row.key, $event)"
                @reply="quoteReply"
                @multi="beginMultiSelect(row.key)"
                @toggle-select="toggleSelected(row.key)"
              />
            </template>
          </div>
        </div>
      </div>

      <div
        class="mindmate-seminar-room__input shrink-0 bg-white mt-auto min-w-0 w-full"
        :class="{ 'mindmate-seminar-room__input--file': dragOverInput }"
      >
        <div class="mindmate-seminar-room__input-inner">
          <div
            v-if="selectMode"
            class="mindmate-seminar-room__select-bar"
          >
            <span
              ><I18nText
                k="mindmate.bubble.selected"
                :params="{ n: selectedKeys.length }"
            /></span>
            <button
              v-if="!isSpectator"
              type="button"
              @click="pinSelected"
            >
              <MindmateSoftIcon
                name="highlights"
                :size="14"
              />
              <I18nText k="mindmate.bubble.pinSelected" />
            </button>
            <button
              v-if="!isSpectator"
              type="button"
              @click="openSummary(selectedKeys)"
            >
              <Sparkles
                :size="14"
                aria-hidden="true"
              />
              <I18nText k="mindmate.bubble.summarizeSelected" />
            </button>
            <button
              type="button"
              @click="shareSelected"
            >
              <Share2
                :size="14"
                aria-hidden="true"
              />
              <I18nText k="mindmate.tooltip.share" />
            </button>
            <button
              type="button"
              @click="cancelSelect"
            >
              <X
                :size="14"
                aria-hidden="true"
              />
              <I18nText k="mindmate.bubble.cancelSelect" />
            </button>
          </div>
          <button
            v-if="replyQuote && !isSpectator"
            type="button"
            class="mindmate-seminar-room__reply"
            @click="replyQuote = null"
          >
            <span class="mindmate-seminar-room__reply-label">
              <I18nText
                k="mindmate.bubble.replying"
                :params="{ name: replyQuote.author }"
              />
            </span>
            <span class="mindmate-seminar-room__reply-text">{{ replyQuote.text }}</span>
            <span class="mindmate-seminar-room__citation-x">×</span>
          </button>
          <div
            v-if="!isSpectator && seminarComposerAttachments.length > 0"
            class="mindmate-seminar-room__citations"
          >
            <button
              v-for="item in seminarComposerAttachments"
              :key="item.key"
              type="button"
              class="mindmate-seminar-room__citation"
              @click="removeSeminarComposerAttachment(item.key)"
            >
              <span class="mindmate-seminar-room__citation-name">{{ item.name }}</span>
              <span class="mindmate-seminar-room__citation-x">×</span>
            </button>
          </div>
          <div
            v-if="!isSpectator && citations.length > 0"
            class="mindmate-seminar-room__citations"
          >
            <button
              v-for="item in citations"
              :key="item.fileId"
              type="button"
              class="mindmate-seminar-room__citation"
              @click="removeSeminarCitation(item.fileId)"
            >
              <span class="mindmate-seminar-room__citation-name">📎 {{ item.filename }}</span>
              <span class="mindmate-seminar-room__citation-x">×</span>
            </button>
          </div>
          <p
            v-if="isSpectator"
            class="text-center text-xs text-stone-400 py-3"
          >
            <I18nText k="mindmate.seminar.spectatorHint" />
          </p>
          <MindmateInput
            v-if="!isSpectator"
            ref="composerRef"
            :input-text="inputText"
            mode="fullpage"
            seminar-composer
            :is-loading="
              joining || attachingFiles || mindgraphGenerating || connectionStatus === 'connecting'
            "
            :is-streaming="isStreaming"
            :show-file-upload="false"
            :placeholder="inputPlaceholder"
            enable-mentions
            :mention-candidates="mentionCandidates"
            :seminar-mindmate-tag="mindmateTagged"
            :seminar-mindgraph-tag="mindgraphTagged"
            :seminar-agent-name="mindmateAgentName"
            :seminar-voice-recording="voiceRecording"
            @update:input-text="inputText = $event"
            @send="handleSend"
            @clear-seminar-tag="clearSeminarTag"
            @seminar-voice-press="onVoicePress"
            @seminar-voice-release="onVoiceRelease"
          >
            <template #seminarTools>
              <MindmateSeminarComposerTools
                :agent-name="mindmateAgentName"
                @agent="callSeminarAgent"
                @mindmate-tag="setSeminarAgentTag('mindmate')"
                @mindgraph-tag="setSeminarAgentTag('mindgraph')"
                @voice="onSeminarVoice"
                @summary="openSummary()"
                @upload="uploadRoomFiles"
              />
            </template>
          </MindmateInput>
        </div>
      </div>
    </div>

    <MindmateSeminarSummaryDialog
      :open="summaryOpen && !isSpectator"
      :messages="messages"
      :preselect-keys="summaryPreselect"
      :topic="briefTopic"
      :goals="briefGoals"
      :members="members"
      :highlights="seminarHighlights"
      :session-id="room?.sessionId || ''"
      @close="summaryOpen = false"
      @send="postSummary"
    />

    <MindmateSeminarFaceChatCard
      :open="faceChatOpen"
      @close="faceChatOpen = false"
      @start="startFaceChat"
    />

    <MindmateSeminarFaceChatSession
      :open="faceChatLive && !isSpectator"
      :session-id="room?.sessionId || ''"
      :topic="briefTopic"
      :goals="briefGoals"
      @close="faceChatLive = false"
      @send="postSummary"
    />

    <MindmateSeminarShareDialog
      :open="showShareModal"
      :title="roomTitle"
      :lines="shareLines"
      :member-count="shareMemberCount"
      @close="showShareModal = false"
    />
  </div>
</template>

<style scoped>
.mindmate-seminar-room {
  flex-direction: column;
  background: #f7f8fa;
}

.mindmate-seminar-room__main {
  position: relative;
  background: #f7f8fa;
}

.mindmate-seminar-room__drop {
  position: absolute;
  inset: 12px;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed #d6d3d1;
  border-radius: 16px;
  background: rgba(245, 245, 244, 0.92);
  color: #44403c;
  font-size: 14px;
  font-weight: 600;
  pointer-events: none;
}

.mindmate-seminar-room:not(.mindmate-seminar-room--embedded) :deep(.mm-brief-rail) {
  top: 3.75rem;
}

.mindmate-seminar-room__messages {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
}

.mindmate-seminar-room__messages-scroll {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.mindmate-seminar-room__messages-inner {
  width: 100%;
  min-width: 0;
  max-width: none;
  margin: 0;
  padding: 1.25rem 1.25rem 1.75rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.mm-highlight-notice {
  display: flex;
  justify-content: center;
  margin: 8px 0 2px;
}

.mm-highlight-notice span {
  display: inline-block;
  max-width: 100%;
  padding: 6px 14px;
  border-radius: 8px;
  background: #e7edfb;
  color: #5c6eb5;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
}

.mindmate-seminar-room__end-btn {
  --el-button-bg-color: #f5f5f4;
  --el-button-border-color: #e7e5e4;
  --el-button-hover-bg-color: #e7e5e4;
  --el-button-hover-border-color: #d6d3d1;
  --el-button-hover-text-color: #1c1917;
  --el-button-active-bg-color: #d6d3d1;
  --el-button-active-border-color: #a8a29e;
  --el-button-text-color: #44403c;
  font-weight: 500;
  border-radius: 9999px;
  height: auto;
  min-height: 32px;
  padding-top: 4px;
  padding-bottom: 4px;
  line-height: 1.15;
}

.mindmate-seminar-room__input {
  background: transparent;
}

.mindmate-seminar-room__input--file {
  outline: 2px dashed #d6d3d1;
  outline-offset: -8px;
}

.mindmate-seminar-room__input-inner {
  max-width: none;
  width: 100%;
  min-width: 0;
  margin: 0;
  padding: 0.75rem 20px 1.25rem;
  padding-bottom: max(1.25rem, env(safe-area-inset-bottom, 0px));
  box-sizing: border-box;
}

.mindmate-seminar-room:not(.mindmate-seminar-room--embedded) .mindmate-seminar-room__input-inner {
  padding-bottom: max(1.5rem, env(safe-area-inset-bottom, 0px));
}

.mindmate-seminar-room__input :deep(.input-area-fullpage) {
  padding-top: 0;
  padding-left: 0;
  padding-right: 0;
  padding-bottom: 0;
  /* 90% of input-inner; beat global .input-area-fullpage { max-width: 680px }. */
  width: 90% !important;
  max-width: 90% !important;
  margin: 0 auto !important;
}

.mindmate-seminar-room__input :deep(.input-container-fullpage) {
  width: 100%;
  max-width: none;
  border-radius: 18px;
  border-color: #e7e5e4;
  background: #fff;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.06);
}

.mindmate-seminar-room__citations {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  width: 90%;
  max-width: 90%;
  margin: 0 auto 8px;
}

.mindmate-seminar-room__citation {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  height: 28px;
  padding: 0 10px;
  border: 1px solid #e7e5e4;
  border-radius: 999px;
  background: #f5f5f4;
  color: #44403c;
  font-size: 12px;
  cursor: pointer;
}

.mindmate-seminar-room__citation-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mindmate-seminar-room__citation-x {
  opacity: 0.7;
}

.mindmate-seminar-room__select-bar,
.mindmate-seminar-room__reply {
  width: 90%;
  max-width: 90%;
  margin: 0 auto 8px;
}

.mindmate-seminar-room__select-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: #44403c;
  font-size: 13px;
}

.mindmate-seminar-room__select-bar button,
.mindmate-seminar-room__reply {
  border: 1px solid #e7e5e4;
  border-radius: 999px;
  background: #fff;
  color: #44403c;
  font-size: 12px;
  cursor: pointer;
}

.mindmate-seminar-room__select-bar button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
}

.mindmate-seminar-room__select-bar button:hover,
.mindmate-seminar-room__reply:hover {
  border-color: #d6d3d1;
  background: #f5f5f4;
  color: #1c1917;
}

.mindmate-seminar-room__reply {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 4px 10px;
  text-align: left;
}

.mindmate-seminar-room__reply-label {
  flex: 0 0 auto;
  color: #57534e;
  font-weight: 650;
}

.mindmate-seminar-room__reply-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
