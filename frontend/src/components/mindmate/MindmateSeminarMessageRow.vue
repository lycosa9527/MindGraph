<script setup lang="ts">
/**
 * One seminar transcript row: peer / own / MindMate.
 * MindMate teaching-instruction markers become Word / canvas actions, not raw tags.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import seminarAssistantAvatar from '@/assets/seminar/seminar-assistant.svg'
import ImagePreviewModal from '@/components/common/ImagePreviewModal.vue'
import MindmateSeminarAssistantToolbar from '@/components/mindmate/MindmateSeminarAssistantToolbar.vue'
import MindmateSeminarMessageStamp from '@/components/mindmate/MindmateSeminarMessageStamp.vue'
import MindmateMentionMenu from '@/components/mindmate/MindmateMentionMenu.vue'
import MindmateSeminarBubbleActions from '@/components/mindmate/MindmateSeminarBubbleActions.vue'
import MindmateSeminarDiagramCard from '@/components/mindmate/MindmateSeminarDiagramCard.vue'
import MindmateSeminarFileCard from '@/components/mindmate/MindmateSeminarFileCard.vue'
import MindmateSeminarInfoCard from '@/components/mindmate/MindmateSeminarInfoCard.vue'
import MindmateSeminarSummaryCard from '@/components/mindmate/MindmateSeminarSummaryCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  confirmCanvasLibraryDiagramOpen,
  decideCanvasLibraryDiagramOpen,
} from '@/composables/canvasPage/canvasLibraryDiagramOpen'
import { useRenderedMarkdown } from '@/composables/core/useRenderedMarkdown'
import {
  addSeminarHighlight,
  openSeminarDoc,
  openSeminarTaskPane,
  pushSeminarHighlightNotice,
  removeSeminarHighlight,
  requestSeminarMention,
  seminarArtifactsReady,
  seminarFileDocId,
  seminarHighlights,
  seminarServerArtifacts,
  seminarSpectator,
  upsertSeminarServerArtifact,
} from '@/composables/mindmate/mindmateSeminarChrome'
import type { MindmateSeminarMessage } from '@/composables/mindmate/useMindmateSeminar'
import { useAuthStore } from '@/stores/auth'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useTeachingDesignExportStore } from '@/stores/teachingDesignExport'
import { canvasEditorPathForRoute } from '@/utils/canvasBackNavigation'
import { copyMindmateAssistantMessage } from '@/utils/copyMindmateMessage'
import {
  collabDiagramSaveFailureKey,
  saveCollabDiagramToLibrary,
  saveSharedCanvasDiagram,
} from '@/utils/mindmateSeminarDiagramLibrary'
import {
  type CollabFeedbackRating,
  collabAssistantLibraryDiagramId,
  collabAssistantOffersCanvasEdit,
  displayMindmateSeminarContent,
  shouldShowCollabWordTemplateExport,
} from '@/utils/mindmateSeminarDisplay'
import { type CollabReadCursor, formatCollabMessageStamp } from '@/utils/mindmateSeminarRead'
import {
  extractFirstMarkdownImageUrl,
  extractMindmatePreviewUniqueId,
  hasGeneratedDiagramImage,
  parseMindmateDiagramLibraryId,
} from '@/utils/mindmateDiagramMeta'
import {
  type SeminarBriefEditPayload,
  parseSeminarBriefCard,
  parseSeminarSummaryCard,
} from '@/utils/mindmateSeminarCards'
import {
  archiveSeminarReplyDocx,
  fetchSeminarBackgroundBlob,
  isSeminarVoiceFilename,
  seminarBubblePlainText,
  splitSeminarMessageFiles,
} from '@/utils/mindmateSeminarFolder'
import {
  TEACHING_INSTRUCTION_KIND,
  stripTeachingDesignFlags,
} from '@/utils/mindmateTeachingDesignFlag'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const props = withDefaults(
  defineProps<{
    message: MindmateSeminarMessage
    isOwn: boolean
    userPrompt?: string
    agentName: string
    agentAvatarUrl: string
    regenerateDisabled?: boolean
    feedback?: CollabFeedbackRating
    sessionId?: string
    readCursors?: readonly CollabReadCursor[]
    /**
     * False on a closed seminar. Default true: an omitted Boolean prop is cast
     * to false, and the live room does not pass this prop.
     */
    live?: boolean
    selectMode?: boolean
    selected?: boolean
    briefEditable?: boolean
    briefSaving?: boolean
    /**
     * False when an earlier message in this clock minute already shows the time.
     * Default true: an omitted Boolean prop is cast to false.
     */
    showTime?: boolean
  }>(),
  {
    live: true,
    showTime: true,
  }
)

const emit = defineEmits<{
  (e: 'regenerate'): void
  (e: 'share'): void
  (e: 'feedback', rating: 'like' | 'dislike'): void
  (e: 'reply', quote: { author: string; text: string }): void
  (e: 'multi'): void
  (e: 'toggleSelect'): void
  (e: 'saveBrief', payload: SeminarBriefEditPayload, done: (ok: boolean) => void): void
}>()

function onSaveBrief(payload: SeminarBriefEditPayload, done: (ok: boolean) => void): void {
  emit('saveBrief', payload, done)
}

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const teachingDesignExport = useTeachingDesignExportStore()
const { exportingMessageId } = storeToRefs(teachingDesignExport)
const route = useRoute()
const router = useRouter()

const openingCanvas = ref(false)
const convertingDocument = ref(false)
const showImagePreview = ref(false)
const previewImageUrl = ref('')
const bubbleEl = ref<HTMLElement | null>(null)
const rowHot = ref(false)

const exportMessageId = computed(() => {
  if (props.message.id != null) {
    return `collab-${props.message.id}`
  }
  if (props.message.clientKey) {
    return props.message.clientKey
  }
  return `collab-${props.message.role}-${props.message.content.length}`
})

const showWordTemplateExport = computed(() => shouldShowCollabWordTemplateExport(props.message))

const showConvertToDocument = computed(() => {
  if (props.message.role !== 'assistant' || props.message.streaming || props.message.id == null) {
    return false
  }
  if (showWordTemplateExport.value) {
    return false
  }
  return stripTeachingDesignFlags(props.message.content).trim().length > 0
})

const libraryDiagramId = computed(() => collabAssistantLibraryDiagramId(props.message))

const showCanvasEdit = computed(() => collabAssistantOffersCanvasEdit(props.message))

const displayText = computed(() =>
  displayMindmateSeminarContent(props.message.content, props.message.role)
)

const messageBody = computed(() => splitSeminarMessageFiles(displayText.value))

const sharedCanvasId = computed(() => {
  if (props.message.role !== 'user' || props.message.streaming) {
    return null
  }
  return parseMindmateDiagramLibraryId(props.message.content)
})

const sharedCanvasImage = computed(() =>
  sharedCanvasId.value ? extractFirstMarkdownImageUrl(props.message.content) : null
)

const userBubbleText = computed(() => {
  if (!sharedCanvasId.value) {
    return messageBody.value.text
  }
  return messageBody.value.text
    .replace(/!\[[^\]]*]\([^)]+\)/g, '')
    .replace(/<!--\s*mg-diagram-id:[a-f0-9-]+\s*-->/gi, '')
    .trim()
})
const voiceSrc = ref<Record<string, string>>({})

watch(
  () => messageBody.value.files.map((file) => file.id).join(','),
  () => {
    void loadVoiceClips()
  },
  { immediate: true }
)

async function loadVoiceClips(): Promise<void> {
  const sessionId = props.sessionId?.trim()
  if (!sessionId) {
    return
  }
  for (const file of messageBody.value.files) {
    if (!isSeminarVoiceFilename(file.filename) || voiceSrc.value[file.id]) {
      continue
    }
    try {
      const blob = await fetchSeminarBackgroundBlob(sessionId, file.id)
      voiceSrc.value = { ...voiceSrc.value, [file.id]: URL.createObjectURL(blob) }
    } catch {
      voiceSrc.value = { ...voiceSrc.value, [file.id]: '' }
    }
  }
}

onUnmounted(() => {
  Object.values(voiceSrc.value).forEach((url) => {
    if (url) {
      URL.revokeObjectURL(url)
    }
  })
})

const { html: renderedMarkdownHtml } = useRenderedMarkdown(() => messageBody.value.text, {
  stripThinkBlocks: true,
})

const isAssistant = computed(() => props.message.role === 'assistant')

const showPersonAvatar = computed(() => props.live !== false)

const isMindGraphReply = computed(() => {
  if (!isAssistant.value) {
    return false
  }
  const content = props.message.content
  return hasGeneratedDiagramImage(content) || parseMindmateDiagramLibraryId(content) !== null
})

const speakerName = computed(() =>
  isMindGraphReply.value ? t('mindmate.composer.mindgraph') : props.agentName
)

const speakerAvatar = computed(() =>
  isMindGraphReply.value ? mindgraphLogo : props.agentAvatarUrl
)

function authorLabel(): string {
  if (isAssistant.value) {
    return speakerName.value
  }
  if (props.isOwn) {
    return authStore.user?.username || t('mindmate.highlights.you')
  }
  return props.message.username || t('mindmate.collabPokeSomeone')
}

const selfUserId = computed(() => Number(authStore.user?.id) || 0)

const messageHighlights = computed(() => {
  const messageId = props.message.id
  if (!messageId) {
    return []
  }
  return seminarHighlights.value.filter((item) => item.messageId === messageId)
})

const highlightState = computed<'none' | 'mine' | 'other'>(() => {
  const rows = messageHighlights.value
  if (!rows.length) {
    return 'none'
  }
  if (rows.some((item) => item.createdByUserId === selfUserId.value && selfUserId.value > 0)) {
    return 'mine'
  }
  return 'other'
})

function pinHighlight(): void {
  const sessionId = props.sessionId?.trim()
  if (!sessionId || highlightState.value === 'other') {
    return
  }
  if (highlightState.value === 'mine') {
    const mine = messageHighlights.value.filter((item) => item.createdByUserId === selfUserId.value)
    for (const item of mine) {
      removeSeminarHighlight(sessionId, item.id)
    }
    pushSeminarHighlightNotice(sessionId, {
      kind: 'cancel',
      ownMessage: props.isOwn,
      authorName: authorLabel(),
    })
    return
  }
  const selection = window.getSelection()?.toString().trim() || ''
  const anchor = window.getSelection()?.anchorNode
  const inBubble = Boolean(selection && bubbleEl.value && anchor && bubbleEl.value.contains(anchor))
  const text = inBubble ? selection : messageBody.value.text
  if (!text) {
    return
  }
  const added = addSeminarHighlight(sessionId, {
    text: text.slice(0, 2000),
    authorName: authorLabel(),
    messageId: props.message.id ?? null,
    createdByUserId: selfUserId.value || null,
    createdByName: authStore.user?.username || t('mindmate.highlights.you'),
    messageAt: props.message.created_at || '',
  })
  if (!added) {
    return
  }
  pushSeminarHighlightNotice(sessionId, {
    kind: 'set',
    ownMessage: props.isOwn,
    authorName: authorLabel(),
  })
  openSeminarTaskPane('highlights')
  notify.successKey('mindmate.highlights.added')
}

const ownDisplayName = computed(() => authStore.user?.username || props.message.username || '')

const ownSurname = computed(() => seminarAvatarSurname(ownDisplayName.value))

const peerSurname = computed(() => seminarAvatarSurname(props.message.username))

const ownTone = computed(() => seminarAvatarTone(authStore.user?.id ?? ownDisplayName.value))

const peerTone = computed(() =>
  seminarAvatarTone(props.message.sender_user_id ?? props.message.username)
)

const messageStamp = computed(() => formatCollabMessageStamp(props.message.created_at))

const briefCard = computed(() => parseSeminarBriefCard(props.message.content))

const summaryCard = computed(() => parseSeminarSummaryCard(props.message.content))

const mentionMenu = ref<{ x: number; y: number; name: string } | null>(null)

const mentionName = computed(() => {
  if (props.isOwn || summaryCard.value || isMindGraphReply.value) {
    return ''
  }
  if (isAssistant.value) {
    return speakerName.value.trim()
  }
  return (props.message.username || '').trim()
})

const canMentionAvatar = computed(() => Boolean(mentionName.value) && !seminarSpectator.value)

function onAvatarContextMenu(event: MouseEvent): void {
  if (!canMentionAvatar.value) {
    return
  }
  event.preventDefault()
  mentionMenu.value = {
    x: event.clientX,
    y: event.clientY,
    name: mentionName.value,
  }
}

function chooseMention(): void {
  const name = mentionMenu.value?.name || ''
  mentionMenu.value = null
  if (name) {
    requestSeminarMention(name)
  }
}

const rowClass = computed(() => {
  if (props.isOwn) {
    return 'mindmate-seminar-room__msg-row--own'
  }
  if (isAssistant.value) {
    return 'mindmate-seminar-room__msg-row--other mindmate-seminar-room__msg-row--assistant'
  }
  return 'mindmate-seminar-room__msg-row--other'
})

function handleMarkdownClick(event: MouseEvent): void {
  const target = event.target
  if (!(target instanceof HTMLImageElement)) {
    return
  }
  const imgSrc = target.currentSrc || target.src
  if (!imgSrc) {
    return
  }
  previewImageUrl.value = imgSrc
  showImagePreview.value = true
}

async function handleCopy(): Promise<void> {
  try {
    if (isAssistant.value) {
      await copyMindmateAssistantMessage(
        props.message.content,
        typeof window !== 'undefined' ? window.location.host : undefined
      )
    } else {
      await navigator.clipboard.writeText(seminarBubblePlainText(props.message.content))
    }
    notify.successKey('notification.copied')
  } catch {
    notify.errorKey('notification.copyFailed')
  }
}

function emitReply(): void {
  const text = seminarBubblePlainText(props.message.content).replace(/\s+/g, ' ').trim()
  if (!text) {
    return
  }
  emit('reply', { author: authorLabel(), text: text.slice(0, 180) })
}

function onRowClick(event: MouseEvent): void {
  if (!props.selectMode) {
    return
  }
  const target = event.target
  if (target instanceof Element && target.closest('button, a, audio, input, textarea')) {
    return
  }
  emit('toggleSelect')
}

const teachingArchiveStarted = new Set<number>()

watch(
  () => {
    const messageId = props.message.id
    if (!seminarArtifactsReady.value || !showWordTemplateExport.value || messageId == null) {
      return false
    }
    return !seminarServerArtifacts.value.some((file) => file.sourceMessageId === messageId)
  },
  (missing) => {
    const sessionId = props.sessionId?.trim() ?? ''
    const messageId = props.message.id
    if (!missing || !sessionId || messageId == null || teachingArchiveStarted.has(messageId)) {
      return
    }
    teachingArchiveStarted.add(messageId)
    void archiveSeminarReplyDocx(sessionId, messageId)
      .then((file) => {
        upsertSeminarServerArtifact(file)
      })
      .catch(() => {
        teachingArchiveStarted.delete(messageId)
      })
  },
  { immediate: true }
)

async function handleConvertToDocument(): Promise<void> {
  const sessionId = props.sessionId?.trim() ?? ''
  const messageId = props.message.id
  if (!sessionId || messageId == null || convertingDocument.value) {
    return
  }
  convertingDocument.value = true
  try {
    const file = await archiveSeminarReplyDocx(sessionId, messageId)
    upsertSeminarServerArtifact(file)
    openSeminarDoc({
      id: seminarFileDocId(file.id),
      kind: 'file',
      title: file.filename,
      fileId: file.id,
      filename: file.filename,
      contentType: file.contentType,
    })
    notify.successKey('mindmate.convertToDocumentOk')
  } catch {
    notify.errorKey('mindmate.convertToDocumentFail')
  } finally {
    convertingDocument.value = false
  }
}

function handleExportWordTemplate(): void {
  void teachingDesignExport.exportAssistantMessage(
    {
      id: exportMessageId.value,
      role: 'assistant',
      content: props.message.content,
      timestamp: Date.now(),
      replyKind: TEACHING_INSTRUCTION_KIND,
      exportWordTemplate: true,
    },
    props.userPrompt
  )
}

async function resolveCanvasDiagramId(): Promise<string | null> {
  const sessionId = props.sessionId?.trim() ?? ''
  const sharedId = sharedCanvasId.value
  if (sharedId && sessionId) {
    const saved = await saveSharedCanvasDiagram(sessionId, sharedId)
    if (!saved.ok) {
      notify.errorKey(collabDiagramSaveFailureKey(saved.reason))
      return null
    }
    return saved.diagramId
  }
  const previewId = extractMindmatePreviewUniqueId(props.message.content)
  if (previewId && sessionId) {
    const saved = await saveCollabDiagramToLibrary(sessionId, previewId)
    if (!saved.ok) {
      notify.errorKey(collabDiagramSaveFailureKey(saved.reason))
      return null
    }
    return saved.diagramId
  }
  return libraryDiagramId.value
}

async function openInCanvas(): Promise<void> {
  if (openingCanvas.value) {
    return
  }
  if (!authStore.isAuthenticated) {
    notify.warningKey('mindmate.openCanvasLoginRequired')
    await router.push({ path: '/auth', query: { redirect: route.fullPath } })
    return
  }

  openingCanvas.value = true
  try {
    const diagramId = await resolveCanvasDiagramId()
    if (!diagramId) {
      if (!extractMindmatePreviewUniqueId(props.message.content)) {
        notify.errorKey('mindmate.openCanvasNoLibraryId')
      }
      return
    }

    const currentId = savedDiagramsStore.activeDiagramId?.trim() ?? ''
    const decision = decideCanvasLibraryDiagramOpen(route.path, currentId, diagramId)
    if (decision === 'noop') {
      return
    }
    if (decision === 'confirm') {
      const targetTitle =
        savedDiagramsStore.diagrams.find((row) => row.id === diagramId)?.title?.trim() || diagramId
      const currentTitle =
        savedDiagramsStore.diagrams.find((row) => row.id === currentId)?.title?.trim() || currentId
      const accepted = await confirmCanvasLibraryDiagramOpen({
        title: t('mindmate.openCanvasSwitchTitle'),
        message: t('mindmate.openCanvasSwitchBody', {
          target: targetTitle,
          current: currentTitle,
        }),
        confirmButtonText: t('mindmate.openCanvasSwitchOk'),
        cancelButtonText: t('common.cancel'),
      })
      if (!accepted) {
        return
      }
    }

    const canvasPath = canvasEditorPathForRoute(route.path)
    await router.push({ path: canvasPath, query: { diagramId } })
  } catch {
    notify.errorKey('mindmate.openCanvasFailed')
  } finally {
    openingCanvas.value = false
  }
}
</script>

<template>
  <div
    v-if="briefCard"
    class="mindmate-seminar-room__msg-row mindmate-seminar-room__msg-row--card"
    :data-seminar-brief-card="briefCard ? '' : undefined"
  >
    <MindmateSeminarInfoCard
      v-if="briefCard"
      :model="briefCard"
      :editable="briefEditable"
      :saving="briefSaving"
      @save="onSaveBrief"
    />
  </div>
  <div
    v-else
    class="mindmate-seminar-room__msg-row"
    :class="[
      rowClass,
      {
        'is-selected': selected,
        'is-selecting': selectMode,
        'is-continued': !showTime,
      },
    ]"
    :data-collab-message-id="message.id || undefined"
    @click="onRowClick"
    @mouseenter="rowHot = true"
    @mouseleave="rowHot = false"
  >
    <button
      v-if="selectMode"
      type="button"
      class="mindmate-seminar-room__check"
      :class="{ 'is-on': selected }"
      :aria-pressed="selected"
      @click.stop="emit('toggleSelect')"
    />
    <div
      v-if="isAssistant || showPersonAvatar"
      class="mindmate-seminar-room__avatar"
      :class="{
        'is-assistant': isAssistant && !summaryCard,
        'is-minutes': Boolean(summaryCard),
        'is-graph': isMindGraphReply,
        'is-mentionable': canMentionAvatar,
      }"
      @contextmenu="onAvatarContextMenu"
    >
      <img
        v-if="summaryCard"
        :src="seminarAssistantAvatar"
        :alt="summaryCard.author || t('mindmate.summary.author')"
        class="mindmate-seminar-room__avatar-img"
      />
      <img
        v-else-if="isAssistant"
        :src="speakerAvatar"
        :alt="speakerName"
        class="mindmate-seminar-room__avatar-img"
      />
      <span
        v-else-if="isOwn"
        class="mindmate-seminar-room__avatar-surname"
        :style="{ background: ownTone.background, color: ownTone.color }"
        aria-hidden="true"
      >
        {{ ownSurname }}
      </span>
      <span
        v-else
        class="mindmate-seminar-room__avatar-surname"
        :style="{ background: peerTone.background, color: peerTone.color }"
        aria-hidden="true"
      >
        {{ peerSurname }}
      </span>
    </div>
    <MindmateMentionMenu
      v-if="mentionMenu"
      :x="mentionMenu.x"
      :y="mentionMenu.y"
      :name="mentionMenu.name"
      @choose="chooseMention"
      @close="mentionMenu = null"
    />
    <div class="mindmate-seminar-room__msg-body">
      <div
        v-if="isAssistant"
        class="mindmate-seminar-room__meta"
      >
        <span class="mindmate-seminar-room__meta-name">{{
          summaryCard?.author || speakerName
        }}</span>
        <span
          v-if="showTime && messageStamp"
          class="mindmate-seminar-room__meta-time"
          >{{ messageStamp }}</span
        >
      </div>
      <div
        v-else-if="!isOwn && message.username"
        class="mindmate-seminar-room__meta"
      >
        <span class="mindmate-seminar-room__meta-name">{{ message.username }}</span>
        <span
          v-if="showTime && messageStamp"
          class="mindmate-seminar-room__meta-time"
          >{{ messageStamp }}</span
        >
      </div>
      <div
        ref="bubbleEl"
        class="mindmate-seminar-room__bubble text-sm leading-relaxed"
        :class="[
          isOwn
            ? 'mindmate-seminar-room__bubble--own'
            : isAssistant
              ? 'mindmate-seminar-room__bubble--assistant'
              : 'mindmate-seminar-room__bubble--peer',
          message.streaming ? 'mindmate-seminar-room__bubble--streaming' : '',
          sharedCanvasId ? 'mindmate-seminar-room__bubble--diagram' : '',
          messageBody.files.length && !userBubbleText && !sharedCanvasId
            ? 'mindmate-seminar-room__bubble--files'
            : '',
          isAssistant || sharedCanvasId || messageBody.files.length ? '' : 'whitespace-pre-wrap',
        ]"
      >
        <div
          v-if="messageBody.files.length > 0"
          class="mindmate-seminar-room__msg-files"
        >
          <template
            v-for="file in messageBody.files"
            :key="file.id"
          >
            <audio
              v-if="isSeminarVoiceFilename(file.filename) && voiceSrc[file.id]"
              class="mindmate-seminar-room__voice"
              :src="voiceSrc[file.id]"
              controls
              preload="metadata"
            />
            <MindmateSeminarFileCard
              v-else-if="sessionId"
              :session-id="sessionId"
              :file-id="file.id"
              :filename="file.filename"
              :sent-at="message.created_at"
            />
          </template>
        </div>
        <MindmateSeminarSummaryCard
          v-if="summaryCard"
          :model="summaryCard"
        />
        <!-- eslint-disable vue/no-v-html -- DOMPurify in renderRichMarkdownHtml pipeline -->
        <div
          v-else-if="isAssistant"
          class="mindmate-seminar-room__markdown"
          @click="handleMarkdownClick"
          v-html="renderedMarkdownHtml"
        />
        <!-- eslint-enable vue/no-v-html -->
        <template v-else-if="userBubbleText || sharedCanvasId">
          <MindmateSeminarDiagramCard
            v-if="sharedCanvasId && sessionId"
            :session-id="sessionId"
            :diagram-id="sharedCanvasId"
            :caption="userBubbleText"
            :thumbnail-url="sharedCanvasImage"
            :opening="openingCanvas"
            @open="openInCanvas"
          />
          <template v-else>{{ userBubbleText }}</template>
        </template>
      </div>
      <div
        v-if="!message.streaming && isOwn"
        class="mindmate-seminar-room__stamp-row mindmate-seminar-room__stamp-row--own"
        :class="{
          'is-action-slot': live !== false,
          'is-hot': rowHot && live !== false,
        }"
      >
        <MindmateSeminarBubbleActions
          v-if="live !== false"
          inline
          :open="rowHot"
          :highlight-state="highlightState"
          @copy="handleCopy"
          @reply="emitReply"
          @highlight="pinHighlight"
          @multi="emit('multi')"
        />
        <MindmateSeminarMessageStamp
          :message-id="message.id"
          :created-at="message.created_at"
          :sender-user-id="message.sender_user_id"
          :is-own="isOwn"
          :read-cursors="live === false ? [] : readCursors"
          :show-receipt="live !== false"
          :show-time="showTime"
        />
      </div>
      <div
        v-else-if="!message.streaming && !isAssistant && live !== false"
        class="mindmate-seminar-room__action-slot"
      >
        <MindmateSeminarBubbleActions
          :open="rowHot"
          :highlight-state="highlightState"
          @copy="handleCopy"
          @reply="emitReply"
          @highlight="pinHighlight"
          @multi="emit('multi')"
        />
      </div>
      <MindmateSeminarAssistantToolbar
        v-if="isAssistant && !message.streaming && !summaryCard"
        :live-actions="live !== false"
        :can-regenerate="Boolean(userPrompt)"
        :regenerate-disabled="Boolean(regenerateDisabled)"
        :feedback="feedback"
        :show-word-template-export="showWordTemplateExport"
        :show-convert-to-document="showConvertToDocument"
        :converting-document="convertingDocument"
        :exporting-word="exportingMessageId === exportMessageId"
        :show-canvas="showCanvasEdit"
        :opening-canvas="openingCanvas"
        :highlight-state="highlightState"
        @copy="handleCopy"
        @regenerate="emit('regenerate')"
        @feedback="emit('feedback', $event)"
        @reply="emitReply"
        @highlight="pinHighlight"
        @multi="emit('multi')"
        @export-word="handleExportWordTemplate"
        @convert-document="handleConvertToDocument"
        @open-canvas="openInCanvas"
      />
    </div>
  </div>
  <ImagePreviewModal
    v-if="isAssistant"
    v-model:visible="showImagePreview"
    :title="t('mindmate.imagePreview')"
    :image-url="previewImageUrl"
  />
</template>

<style scoped>
@import '../panels/mindmate/mindmate.css';

.mindmate-seminar-room__bubble--diagram {
  display: block;
  box-sizing: border-box;
  width: min(22.5rem, 100%);
  max-width: 100%;
  padding: 8px;
  white-space: normal;
}

.mindmate-seminar-room__msg-row {
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  width: 100%;
  min-width: 0;
  position: relative;
}

.mindmate-seminar-room__msg-row.is-continued {
  margin-top: -0.35rem;
}

.mindmate-seminar-room__msg-row.is-selecting {
  padding-left: 28px;
}

.mindmate-seminar-room__msg-row.is-selected .mindmate-seminar-room__bubble--own,
.mindmate-seminar-room__msg-row.is-selected .mindmate-seminar-room__bubble--peer {
  outline: 2px solid #c4b5fd;
}

.mindmate-seminar-room__check {
  position: absolute;
  left: 0;
  top: 10px;
  width: 18px;
  height: 18px;
  border: 1.5px solid #d6d3d1;
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
}

.mindmate-seminar-room__check.is-on {
  border-color: #6d5efc;
  background: #6d5efc;
  box-shadow: inset 0 0 0 3px #fff;
}

.mindmate-seminar-room__msg-body {
  position: relative;
}

.mindmate-seminar-room__msg-row--card {
  display: flex;
  justify-content: center;
}

.mindmate-seminar-room__msg-row--card > :deep(*) {
  width: 70%;
  max-width: 100%;
  flex: 0 0 70%;
}

.mindmate-seminar-room__avatar {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 9999px;
  flex-shrink: 0;
  overflow: hidden;
  background: #ede9fe;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 2px #fff;
}

.mindmate-seminar-room__avatar.is-assistant {
  background: linear-gradient(145deg, #a78bfa 0%, #6d5efc 100%);
}

.mindmate-seminar-room__avatar.is-minutes {
  background: #14635c;
}

.mindmate-seminar-room__avatar.is-graph {
  background: #fff;
  box-shadow: inset 0 0 0 1px #ece9f5;
}

.mindmate-seminar-room__avatar.is-mentionable {
  cursor: context-menu;
}

.mindmate-seminar-room__avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mindmate-seminar-room__avatar-surname {
  font-size: 0.85rem;
  line-height: 1;
  font-weight: 650;
  user-select: none;
  width: 100%;
  height: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.mindmate-seminar-room__msg-row--own {
  flex-direction: row-reverse;
}

.mindmate-seminar-room__msg-body {
  min-width: 0;
  max-width: min(78%, 36rem);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mindmate-seminar-room__msg-row--own .mindmate-seminar-room__msg-body {
  display: grid;
  justify-items: end;
}

.mindmate-seminar-room__msg-row--other .mindmate-seminar-room__msg-body {
  align-items: flex-start;
}

.mindmate-seminar-room__msg-row--assistant .mindmate-seminar-room__msg-body {
  flex: 1 1 0;
  width: auto;
  max-width: min(100%, 36rem);
  min-width: 0;
  align-items: flex-start;
}

.mindmate-seminar-room__meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 0 4px;
  font-size: 12px;
  line-height: 1.3;
}

.mindmate-seminar-room__meta-name {
  font-weight: 600;
  color: #57534e;
}

.mindmate-seminar-room__meta-time {
  color: #a8a29e;
  font-weight: 400;
}

.mindmate-seminar-room__bubble {
  display: inline-block;
  width: fit-content;
  max-width: 100%;
  overflow-wrap: break-word;
  word-break: normal;
  border-radius: 16px;
  padding: 10px 14px;
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.04);
}

.mindmate-seminar-room__bubble--own {
  background: #ede9fe;
  color: #1c1917;
  border: none;
  box-shadow: none;
  border-top-right-radius: 6px;
}

.mindmate-seminar-room__bubble--peer {
  background: #f0f0f0;
  color: #1c1917;
  border: none;
  box-shadow: none;
  border-top-left-radius: 6px;
}

.mindmate-seminar-room__bubble--assistant {
  background: transparent;
  color: #1c1917;
  border: none;
  border-radius: 0;
  box-shadow: none;
  padding: 0 4px;
}

.mindmate-seminar-room__msg-row--assistant .mindmate-seminar-room__bubble {
  display: block;
  box-sizing: border-box;
  width: fit-content;
  max-width: 100%;
}

.mindmate-seminar-room__msg-row--assistant:has(.mm-sum-card) .mindmate-seminar-room__msg-body {
  width: 100%;
  max-width: none;
}

.mindmate-seminar-room__msg-row--assistant:has(.mm-sum-card) .mindmate-seminar-room__bubble {
  width: 60%;
  max-width: 60%;
}

.mindmate-seminar-room__stamp-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 0;
  min-height: 0;
}

.mindmate-seminar-room__stamp-row :deep(.mindmate-seminar-stamp) {
  margin-top: 0;
}

.mindmate-seminar-room__stamp-row--own {
  justify-content: flex-end;
  width: 100%;
}

.mindmate-seminar-room__stamp-row--own.is-action-slot,
.mindmate-seminar-room__action-slot {
  position: relative;
  min-height: 0;
}

.mindmate-seminar-room__action-slot {
  height: 0;
}

.mindmate-seminar-room__stamp-row--own.is-hot :deep(.mindmate-seminar-stamp) {
  visibility: hidden;
}

.mindmate-seminar-room__stamp-row--own.is-action-slot :deep(.mm-bubble-actions),
.mindmate-seminar-room__action-slot :deep(.mm-bubble-actions) {
  position: absolute;
  bottom: 0;
  left: 0;
  z-index: 3;
  margin: 0;
}

.mindmate-seminar-room__stamp-row--own.is-action-slot :deep(.mm-bubble-actions) {
  right: 0;
  left: auto;
}

.mindmate-seminar-room__bubble--files {
  display: block;
  box-sizing: border-box;
  width: fit-content;
  max-width: 100%;
  padding: 8px;
  white-space: normal;
  background: transparent;
}

.mindmate-seminar-room__msg-files {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: fit-content;
  max-width: 100%;
}

.mindmate-seminar-room__voice {
  display: block;
  width: 220px;
  max-width: 100%;
  height: 36px;
}

.mindmate-seminar-room__bubble--streaming::after {
  content: '▍';
  margin-left: 0.1em;
  animation: mmc-caret 1s step-end infinite;
}

@keyframes mmc-caret {
  50% {
    opacity: 0;
  }
}

.mindmate-seminar-room__markdown {
  min-width: 0;
  max-width: 100%;
}

.mindmate-seminar-room__markdown :deep(img) {
  display: block;
  box-sizing: border-box;
  width: 20rem;
  max-width: 100%;
  height: auto;
  max-height: 14rem;
  object-fit: contain;
  object-position: left center;
  border-radius: 8px;
  margin: 0.5rem 0;
  cursor: zoom-in;
}

.mindmate-seminar-room__markdown :deep(p) {
  margin: 0 0 0.5em;
}

.mindmate-seminar-room__markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.mindmate-seminar-room__markdown :deep(pre) {
  overflow-x: auto;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  background: rgba(28, 25, 23, 0.06);
}

.mindmate-seminar-room__markdown :deep(code) {
  font-size: 0.85em;
}

.mindmate-seminar-room__markdown :deep(ul),
.mindmate-seminar-room__markdown :deep(ol) {
  margin: 0 0 0.5em;
  padding-left: 1.25em;
}
</style>
