<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElButton, ElIcon, ElInput } from 'element-plus'

import { CopyDocument, Edit, RefreshRight, Share } from '@element-plus/icons-vue'

import { Download, ThumbsDown, ThumbsUp } from '@lucide/vue'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  confirmCanvasLibraryDiagramOpen,
  decideCanvasLibraryDiagramOpen,
} from '@/composables/canvasPage/canvasLibraryDiagramOpen'
import { useRenderedMarkdown } from '@/composables/core/useRenderedMarkdown'
import type { FeedbackRating, MindMateMessage } from '@/composables/mindmate/useMindMate'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import { useMindmateDiagramPreviewImage } from '@/composables/mindmate/useMindmateDiagramPreviewImage'
import { useAuthStore } from '@/stores/auth'
import type { ModelLoadPhase } from '@/stores/llmResults'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { authFetch } from '@/utils/api'
import { canvasEditorPathForRoute } from '@/utils/canvasBackNavigation'
import { formatCollabMessageStamp } from '@/utils/mindmateSeminarRead'
import {
  extractMindmatePreviewUniqueId,
  hasGeneratedDiagramImage,
  needsLibraryFullHint,
  needsLibrarySaveHint,
  parseMindmateDiagramLibraryId,
} from '@/utils/mindmateDiagramMeta'
import { extractMindmatePreviewCacheKey } from '@/utils/mindmateDiagramPreviewCache'
import { notifyMindmateDiagramPreviewExpired } from '@/utils/mindmateDiagramPreviewExpiredNotify'
import { formatSeminarFileSize } from '@/utils/mindmateSeminarFolder'
import { isTeachingInstructionReply } from '@/utils/mindmateTeachingDesignFlag'
import { resolveUserAvatarEmoji, userAvatarImageSrc } from '@/utils/userAvatarEmoji'

import MindmateAgentAvatar from './MindmateAgentAvatar.vue'

const props = defineProps<{
  message: MindMateMessage
  userAvatar: string
  isEditing?: boolean
  editingContent?: string
  isHovered?: boolean
  isLastAssistant?: boolean
  hasPreviousUserMessage?: boolean
  isLoading?: boolean
  agentLoadPhase?: ModelLoadPhase
  exportingWordTemplate?: boolean
  selectMode?: boolean
  selected?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', message: MindMateMessage): void
  (e: 'cancelEdit'): void
  (e: 'saveEdit', content: string): void
  (e: 'copy', content: string): void
  (e: 'regenerate', messageId: string): void
  (e: 'feedback', messageId: string, rating: FeedbackRating): void
  (e: 'share', messageId: string): void
  (e: 'toggleSelect'): void
  (e: 'exportWordTemplate', message: MindMateMessage): void
  (e: 'mouseenter'): void
  (e: 'mouseleave'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { displayName: mindmateName, avatarUrl: mindmateAvatarUrl } = useMindMateBranding('md')
const savedDiagramsStore = useSavedDiagramsStore()
const route = useRoute()
const router = useRouter()

const resolvedLibraryId = ref<string | null>(null)

const isMindGraphReply = computed(() => {
  if (props.message.role !== 'assistant') {
    return false
  }
  const content = props.message.content
  return hasGeneratedDiagramImage(content) || parseMindmateDiagramLibraryId(content) !== null
})

const agentLabel = computed(() =>
  isMindGraphReply.value ? t('mindmate.composer.mindgraph') : mindmateName.value
)

const messageStamp = computed(() =>
  formatCollabMessageStamp(
    props.message.timestamp ? new Date(props.message.timestamp).toISOString() : undefined
  )
)

const userPhoto = computed(() => userAvatarImageSrc(props.userAvatar))

const userEmoji = computed(() => resolveUserAvatarEmoji(props.userAvatar))

function onRowClick(): void {
  if (props.selectMode) {
    emit('toggleSelect')
  }
}

const libraryDiagramId = computed(() => {
  if (props.message.role !== 'assistant' || props.message.isStreaming) {
    return null
  }
  return parseMindmateDiagramLibraryId(props.message.content) ?? resolvedLibraryId.value
})

const showCanvasButton = computed(() => libraryDiagramId.value !== null)

const showWordTemplateExport = computed(() => {
  if (props.message.role !== 'assistant' || props.message.isStreaming) {
    return false
  }
  return (
    Boolean(props.message.exportWordTemplate) || isTeachingInstructionReply(props.message.content)
  )
})

const showLibrarySaveHint = computed(() => {
  if (props.message.role !== 'assistant' || props.message.isStreaming || !props.isLastAssistant) {
    return false
  }
  if (resolvedLibraryId.value) {
    return false
  }
  return needsLibrarySaveHint(props.message.content)
})

const showLibraryFullHint = computed(() => {
  if (props.message.role !== 'assistant' || props.message.isStreaming || !props.isLastAssistant) {
    return false
  }
  return needsLibraryFullHint(props.message.content)
})

/** Preview image present but no embedded library uuid — resolve via skip/claim API. */
const needsLibraryIdResolve = computed(() => {
  if (props.message.role !== 'assistant' || props.message.isStreaming) {
    return false
  }
  const content = props.message.content
  return hasGeneratedDiagramImage(content) && parseMindmateDiagramLibraryId(content) === null
})

const librarySaveHintText = ref<string | null>(null)
let libraryMetaRequestId = 0

const previewMetaCache = new Map<
  string,
  { diagramId?: string; notice?: string; missing?: boolean }
>()

async function tryClaimLibraryPreview(uniqueId: string): Promise<string | null> {
  if (!authStore.isAuthenticated) {
    return null
  }
  try {
    const claimRes = await authFetch(
      `/api/generation_library_claim/${encodeURIComponent(uniqueId)}`,
      { method: 'POST' }
    )
    if (!claimRes.ok) {
      return null
    }
    const claimData = (await claimRes.json()) as { diagram_id?: string }
    const claimed = claimData.diagram_id?.trim()
    return claimed || null
  } catch {
    return null
  }
}

watch(
  () => [needsLibraryIdResolve.value, props.message.content, props.isLastAssistant] as const,
  async ([needsResolve, content, isLastAssistant]) => {
    if (!needsResolve) {
      resolvedLibraryId.value = null
      librarySaveHintText.value = null
      return
    }
    const uniqueId = extractMindmatePreviewUniqueId(content)
    if (!uniqueId) {
      resolvedLibraryId.value = null
      librarySaveHintText.value = null
      return
    }
    const cached = previewMetaCache.get(uniqueId)
    if (cached?.diagramId) {
      resolvedLibraryId.value = cached.diagramId
      librarySaveHintText.value = null
      return
    }
    if (cached?.missing) {
      resolvedLibraryId.value = null
      librarySaveHintText.value = null
      return
    }
    const requestId = ++libraryMetaRequestId
    try {
      const response = await authFetch(
        `/api/generation_library_skip/${encodeURIComponent(uniqueId)}`
      )
      if (requestId !== libraryMetaRequestId) {
        return
      }
      if (!response.ok) {
        previewMetaCache.set(uniqueId, { missing: true })
        resolvedLibraryId.value = null
        librarySaveHintText.value = null
        return
      }
      const data = (await response.json()) as {
        notice?: string
        diagram_id?: string
        reason?: string
      }
      const diagramId = data.diagram_id?.trim()
      if (diagramId) {
        previewMetaCache.set(uniqueId, { diagramId })
        resolvedLibraryId.value = diagramId
        librarySaveHintText.value = null
        return
      }
      if (
        authStore.isAuthenticated &&
        (data.reason === 'no_user' || data.reason === 'save_error')
      ) {
        const claimed = await tryClaimLibraryPreview(uniqueId)
        if (requestId !== libraryMetaRequestId) {
          return
        }
        if (claimed) {
          previewMetaCache.set(uniqueId, { diagramId: claimed })
          resolvedLibraryId.value = claimed
          librarySaveHintText.value = null
          return
        }
      }
      const notice = data.notice?.trim()
      if (notice) {
        previewMetaCache.set(uniqueId, { notice })
        librarySaveHintText.value = isLastAssistant ? notice : null
        resolvedLibraryId.value = null
        return
      }
      previewMetaCache.set(uniqueId, { missing: true })
      resolvedLibraryId.value = null
      librarySaveHintText.value = null
    } catch {
      if (requestId === libraryMetaRequestId) {
        resolvedLibraryId.value = null
        librarySaveHintText.value = null
      }
    }
  },
  { immediate: true }
)

const openingCanvas = ref(false)

async function openInCanvas() {
  const diagramId = libraryDiagramId.value
  if (!diagramId || openingCanvas.value) {
    return
  }
  if (!authStore.isAuthenticated) {
    notify.warningKey('mindmate.openCanvasLoginRequired')
    await router.push({ path: '/auth', query: { redirect: route.fullPath } })
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

  openingCanvas.value = true
  try {
    const canvasPath = canvasEditorPathForRoute(route.path)
    await router.push({ path: canvasPath, query: { diagramId } })
  } catch {
    notify.errorKey('mindmate.openCanvasFailed')
  } finally {
    openingCanvas.value = false
  }
}

const pageHost = computed(() => (typeof window !== 'undefined' ? window.location.host : undefined))

const { displayContent: mindmateDisplayContent, previewUnavailable } =
  useMindmateDiagramPreviewImage({
    content: () => props.message.content,
    isStreaming: () => Boolean(props.message.isStreaming),
    pageHost: () => pageHost.value,
    libraryDiagramId: () => libraryDiagramId.value,
  })

watch(
  () =>
    [
      previewUnavailable.value,
      libraryDiagramId.value,
      props.message.isStreaming,
      props.message.content,
    ] as const,
  ([unavailable, diagramId, isStreaming]) => {
    if (isStreaming || !unavailable || !diagramId) {
      return
    }
    const cacheKey = extractMindmatePreviewCacheKey(props.message.content)
    if (!cacheKey) {
      return
    }
    notifyMindmateDiagramPreviewExpired({
      cacheKey,
      message: t('mindmate.diagramPreviewExpired'),
      onOpenCanvas: openInCanvas,
      notify,
    })
  }
)

const { html: renderedMarkdownHtml } = useRenderedMarkdown(() => mindmateDisplayContent.value, {
  stripThinkBlocks: true,
})

// Local editing state
const localEditingContent = ref(props.editingContent || props.message.content)

const editInputRef = ref<InstanceType<typeof ElInput> | null>(null)

function fitEditTextarea(): void {
  const root = editInputRef.value?.$el
  const ta = root instanceof HTMLElement ? root.querySelector('textarea') : null
  if (!(ta instanceof HTMLTextAreaElement)) {
    return
  }
  const style = getComputedStyle(ta)
  const parsedLine = Number.parseFloat(style.lineHeight)
  const line = Number.isFinite(parsedLine) ? parsedLine : 21
  const pad =
    (Number.parseFloat(style.paddingTop) || 0) + (Number.parseFloat(style.paddingBottom) || 0)
  const maxHeight = line * 4 + pad
  ta.style.height = 'auto'
  const needed = ta.scrollHeight
  ta.style.height = `${Math.min(Math.max(needed, line * 2 + pad), maxHeight)}px`
  ta.style.maxHeight = `${maxHeight}px`
  ta.style.overflowY = needed > maxHeight + 1 ? 'auto' : 'hidden'
}

// Watch editingContent prop
watch(localEditingContent, () => {
  void nextTick(fitEditTextarea)
})

watch(
  () => props.isEditing,
  (editing) => {
    if (editing) {
      void nextTick(fitEditTextarea)
    }
  }
)

watch(
  () => props.editingContent,
  (newVal) => {
    if (newVal !== undefined) {
      localEditingContent.value = newVal
    }
  }
)

// Get file icon based on type
function documentBadge(filename: string): { label: string; color: string } {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  if (ext === 'pdf') {
    return { label: 'PDF', color: '#e11d48' }
  }
  if (ext === 'doc' || ext === 'docx') {
    return { label: 'DOC', color: '#3b82f6' }
  }
  if (ext === 'xls' || ext === 'xlsx') {
    return { label: 'XLS', color: '#16a34a' }
  }
  if (ext === 'ppt' || ext === 'pptx') {
    return { label: 'PPT', color: '#ea580c' }
  }
  return { label: 'DOC', color: '#94a3b8' }
}

function documentMeta(file: { size: number }, sentAt: number): string {
  const parts: string[] = []
  if (file.size > 0) {
    parts.push(formatSeminarFileSize(file.size))
  }
  const time = formatCollabMessageStamp(new Date(sentAt).toISOString())
  if (time) {
    parts.push(time)
  }
  return parts.join(' · ')
}

function downloadDmFile(file: { name: string; preview_url?: string }): void {
  if (!file.preview_url) {
    return
  }
  const anchor = document.createElement('a')
  anchor.href = file.preview_url
  anchor.download = file.name
  anchor.target = '_blank'
  anchor.rel = 'noopener'
  anchor.click()
}

function getFileIcon(type: string): string {
  switch (type) {
    case 'image':
      return '🖼️'
    case 'audio':
      return '🎵'
    case 'video':
      return '🎬'
    case 'document':
      return '📄'
    default:
      return '📎'
  }
}

function handleSaveEdit() {
  emit('saveEdit', localEditingContent.value.trim())
}

function handleCancelEdit() {
  localEditingContent.value = props.message.content
  emit('cancelEdit')
}

// Image preview state
const showImagePreview = ref(false)
const previewImageUrl = ref('')

// Handle click on markdown content to detect image clicks
function handleMarkdownClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (target.tagName === 'IMG') {
    const imgSrc = (target as HTMLImageElement).src
    if (imgSrc) {
      previewImageUrl.value = imgSrc
      showImagePreview.value = true
    }
  }
}
</script>

<template>
  <div
    class="message-wrapper group"
    :class="[
      message.role === 'user' ? 'user-message' : 'assistant-message',
      { 'is-selecting': selectMode, 'is-selected': selected },
    ]"
    @mouseenter="emit('mouseenter')"
    @mouseleave="emit('mouseleave')"
    @click="onRowClick"
  >
    <button
      v-if="selectMode"
      type="button"
      class="mm-dm-check"
      :class="{ 'is-on': selected }"
      :aria-pressed="selected"
      @click.stop="emit('toggleSelect')"
    />
    <div
      class="mm-dm-row"
      :class="message.role === 'user' ? 'is-own' : 'is-agent'"
    >
      <MindmateAgentAvatar
        v-if="
          message.role !== 'user' &&
          !isMindGraphReply &&
          agentLoadPhase &&
          agentLoadPhase !== 'idle'
        "
        :size="36"
        avatar-class="mindmate-avatar"
        :phase="agentLoadPhase"
      />
      <div
        v-else
        class="mm-dm-avatar"
        :class="{ 'is-agent': message.role !== 'user', 'is-graph': isMindGraphReply }"
      >
        <img
          v-if="isMindGraphReply"
          :src="mindgraphLogo"
          alt="MindGraph"
          class="mm-dm-avatar__img"
        />
        <img
          v-else-if="message.role !== 'user'"
          :src="mindmateAvatarUrl"
          :alt="mindmateName"
          class="mm-dm-avatar__img"
        />
        <img
          v-else-if="userPhoto"
          :src="userPhoto"
          alt=""
          class="mm-dm-avatar__img"
        />
        <span
          v-else
          class="mm-dm-avatar__emoji"
          aria-hidden="true"
        >
          {{ userEmoji }}
        </span>
      </div>

      <!-- Content -->
      <div
        class="message-content-wrapper mm-dm-body"
        :class="message.role === 'user' ? 'is-own' : 'is-agent'"
      >
        <div
          v-if="message.role !== 'user'"
          class="mm-dm-meta"
        >
          <span class="mm-dm-meta__name">{{ agentLabel }}</span>
          <time v-if="messageStamp">{{ messageStamp }}</time>
        </div>
        <!-- User message editing -->
        <template v-if="message.role === 'user' && isEditing">
          <div class="edit-input-wrapper">
            <ElInput
              :key="`${message.id}-edit`"
              ref="editInputRef"
              v-model="localEditingContent"
              type="textarea"
              :rows="2"
              @keydown.enter.exact.prevent="handleSaveEdit"
              @keydown.esc.prevent="handleCancelEdit"
            />
            <div class="edit-input-wrapper__actions">
              <ElButton
                size="small"
                @click="handleCancelEdit"
              >
                <I18nText
                  k="common.cancel"
                  dense
                />
              </ElButton>
              <ElButton
                type="primary"
                size="small"
                @click="handleSaveEdit"
              >
                <I18nText
                  k="common.save"
                  dense
                />
              </ElButton>
            </div>
          </div>
        </template>

        <!-- Message content -->
        <template v-else>
          <div
            class="message-content relative mm-dm-bubble"
            :class="[
              message.role === 'user' ? 'mm-dm-bubble--own' : 'mm-dm-bubble--agent',
              message.isStreaming ? 'streaming' : '',
            ]"
          >
            <!-- User message - plain text with files -->
            <template v-if="message.role === 'user'">
              <!-- Attached files -->
              <div
                v-if="message.files && message.files.length > 0"
                class="message-files flex flex-col gap-2 mb-2"
              >
                <template
                  v-for="file in message.files"
                  :key="file.id"
                >
                  <div
                    v-if="file.type === 'document'"
                    class="mm-dm-doc"
                  >
                    <span
                      class="mm-dm-doc__badge"
                      :style="{ background: documentBadge(file.name).color }"
                    >
                      {{ documentBadge(file.name).label }}
                    </span>
                    <span class="mm-dm-doc__text">
                      <span class="mm-dm-doc__name">{{ file.name }}</span>
                      <span
                        v-if="documentMeta(file, message.timestamp)"
                        class="mm-dm-doc__meta"
                      >
                        {{ documentMeta(file, message.timestamp) }}
                      </span>
                    </span>
                    <button
                      v-if="file.preview_url"
                      type="button"
                      class="mm-dm-doc__download"
                      :aria-label="t('mindmate.docViewer.download')"
                      @click.stop="downloadDmFile(file)"
                    >
                      <Download
                        :size="16"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                  <div
                    v-else
                    class="file-attachment flex items-center gap-1.5 px-2 py-1 bg-white/20 rounded text-xs"
                  >
                    <img
                      v-if="file.preview_url"
                      :src="file.preview_url"
                      :alt="file.name"
                      class="w-6 h-6 object-cover rounded"
                    />
                    <span v-else>{{ getFileIcon(file.type) }}</span>
                    <span class="max-w-[80px] truncate">{{ file.name }}</span>
                  </div>
                </template>
              </div>
              <p class="whitespace-pre-wrap text-sm leading-normal m-0">
                {{ message.content }}
              </p>
            </template>

            <!-- Assistant message - markdown rendered -->
            <template v-else>
              <!-- eslint-disable vue/no-v-html -- DOMPurify in renderRichMarkdownHtml pipeline -->
              <div
                class="markdown-content text-sm leading-normal"
                @click="handleMarkdownClick"
                v-html="renderedMarkdownHtml"
              />
              <!-- eslint-enable vue/no-v-html -->
              <p
                v-if="showLibraryFullHint"
                class="mindmate-library-save-hint mt-2"
              >
                <I18nText k="mindmate.diagramLibraryFull" />
              </p>
              <p
                v-else-if="showLibrarySaveHint && librarySaveHintText"
                class="mindmate-library-save-hint mt-2"
              >
                {{ librarySaveHintText }}
              </p>
              <!-- Streaming cursor -->
              <span
                v-if="message.isStreaming"
                class="inline-block w-0.5 h-4 bg-current animate-pulse ml-1"
              />
            </template>
          </div>

          <!-- User message actions (on hover) -->
          <div
            v-if="message.role === 'user'"
            class="message-actions flex gap-1 mt-1 px-1 justify-end"
            :style="{
              opacity: isHovered ? 1 : 0,
            }"
            @click.stop
          >
            <I18nTooltip k="mindmate.tooltip.edit">
              <ElButton
                text
                circle
                @click="emit('edit', message)"
              >
                <ElIcon :size="16"><Edit /></ElIcon>
              </ElButton>
            </I18nTooltip>
            <I18nTooltip k="mindmate.tooltip.copy">
              <ElButton
                text
                circle
                @click="emit('copy', message.content)"
              >
                <ElIcon :size="16"><CopyDocument /></ElIcon>
              </ElButton>
            </I18nTooltip>
            <I18nTooltip k="mindmate.tooltip.share">
              <ElButton
                text
                circle
                @click="emit('share', message.id)"
              >
                <ElIcon :size="16"><Share /></ElIcon>
              </ElButton>
            </I18nTooltip>
          </div>

          <!-- AI message action bar -->
          <div
            v-if="message.role === 'assistant' && !message.isStreaming"
            class="action-bar mt-3 flex flex-wrap items-center gap-1"
            :class="{
              'action-bar-visible': isLastAssistant,
              'action-bar-hover': !isLastAssistant,
            }"
            @click.stop
          >
            <!-- Copy -->
            <I18nTooltip
              k="mindmate.tooltip.copy"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                @click="emit('copy', message.content)"
              >
                <ElIcon :size="18"><CopyDocument /></ElIcon>
              </ElButton>
            </I18nTooltip>

            <!-- Regenerate -->
            <I18nTooltip
              v-if="hasPreviousUserMessage"
              k="mindmate.tooltip.regenerate"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                :disabled="isLoading"
                @click="emit('regenerate', message.id)"
              >
                <ElIcon :size="18"><RefreshRight /></ElIcon>
              </ElButton>
            </I18nTooltip>

            <!-- Like -->
            <I18nTooltip
              k="mindmate.tooltip.like"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                :class="{ 'is-active': message.feedback === 'like' }"
                @click="emit('feedback', message.id, message.feedback === 'like' ? null : 'like')"
              >
                <ThumbsUp :size="16" />
              </ElButton>
            </I18nTooltip>

            <!-- Dislike -->
            <I18nTooltip
              k="mindmate.tooltip.dislike"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                :class="{ 'is-active-dislike': message.feedback === 'dislike' }"
                @click="
                  emit('feedback', message.id, message.feedback === 'dislike' ? null : 'dislike')
                "
              >
                <ThumbsDown :size="16" />
              </ElButton>
            </I18nTooltip>

            <!-- Share -->
            <I18nTooltip
              k="mindmate.tooltip.share"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                @click="emit('share', message.id)"
              >
                <ElIcon :size="18"><Share /></ElIcon>
              </ElButton>
            </I18nTooltip>

            <button
              v-if="showWordTemplateExport"
              type="button"
              class="mindmate-stone-btn action-bar-canvas-btn"
              :class="{ 'is-busy': exportingWordTemplate }"
              :disabled="exportingWordTemplate"
              :title="t('mindmate.tooltip.exportWordTemplate')"
              @click="emit('exportWordTemplate', message)"
            >
              <span class="mindmate-stone-btn__label">
                <I18nText
                  k="mindmate.exportWordTemplate"
                  dense
                />
              </span>
            </button>

            <!-- Open in canvas -->
            <ElButton
              v-if="showCanvasButton"
              size="small"
              class="mindmate-canvas-btn action-bar-canvas-btn"
              :loading="openingCanvas"
              @click="openInCanvas"
            >
              <I18nText
                k="mindmate.openInCanvas"
                dense
              />
            </ElButton>
          </div>
        </template>
      </div>
    </div>

    <!-- Image Preview Modal -->
    <ImagePreviewModal
      v-model:visible="showImagePreview"
      :title="t('mindmate.imagePreview')"
      :image-url="previewImageUrl"
    />
  </div>
</template>

<style scoped>
@import './mindmate.css';

.mm-dm-check {
  position: absolute;
  left: 0;
  top: 8px;
  width: 18px;
  height: 18px;
  border: 1.5px solid #d6d3d1;
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
}

.mm-dm-check.is-on {
  border-color: #6d5efc;
  background: #6d5efc;
  box-shadow: inset 0 0 0 3px #fff;
}

.message-wrapper.is-selecting {
  position: relative;
  padding-left: 28px;
}

.message-wrapper.is-selected :deep(.mm-dm-bubble--own) {
  outline: 2px solid #c4b5fd;
}

.mm-dm-avatar__emoji {
  font-size: 22px;
  line-height: 1;
}

.message-actions :deep(.el-button.is-circle) {
  width: 32px;
  height: 32px;
}

.mm-dm-body.is-own:has(.edit-input-wrapper) {
  flex: 1 1 auto;
  width: auto;
  max-width: 100%;
  align-items: stretch;
}

.edit-input-wrapper {
  width: 100%;
  min-width: min(100%, 320px);
  padding: 10px 12px 8px;
  border: 1px solid #e9e5ff;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(109, 94, 252, 0.08);
}

.edit-input-wrapper :deep(.el-textarea__inner) {
  padding: 4px 0;
  border: none;
  box-shadow: none;
  background: transparent;
  color: #1c1917;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
}

.edit-input-wrapper__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.edit-input-wrapper__actions :deep(.el-button) {
  height: 32px;
  margin: 0;
  padding: 0 14px;
  border-radius: 8px;
}

.edit-input-wrapper__actions :deep(.el-button--primary) {
  --el-button-bg-color: #6d5efc;
  --el-button-border-color: #6d5efc;
  --el-button-hover-bg-color: #5b4fe8;
  --el-button-hover-border-color: #5b4fe8;
}

:global(.dark) .edit-input-wrapper {
  border-color: #3f3f46;
  background: #1f2937;
  box-shadow: none;
}

:global(.dark) .edit-input-wrapper :deep(.el-textarea__inner) {
  color: #f5f5f4;
}

.mm-dm-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.mm-dm-row.is-own {
  flex-direction: row-reverse;
}

.mm-dm-avatar {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  flex-shrink: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ede9fe;
}

.mm-dm-avatar.is-agent {
  background: linear-gradient(145deg, #a78bfa 0%, #6d5efc 100%);
}

.mm-dm-avatar.is-graph {
  background: #fff;
  box-shadow: inset 0 0 0 1px #ece9f5;
}

.mm-dm-avatar__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mm-dm-avatar__surname {
  width: 100%;
  height: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 650;
  line-height: 1;
}

.mm-dm-body {
  min-width: 0;
  max-width: min(78%, 36rem);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mm-dm-body.is-own {
  align-items: flex-end;
}

.mm-dm-body.is-agent {
  align-items: flex-start;
  flex: 1 1 auto;
  max-width: min(100%, 36rem);
}

.mm-dm-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 0 4px;
  font-size: 12px;
  line-height: 1.3;
}

.mm-dm-meta__name {
  font-weight: 600;
  color: #57534e;
}

.mm-dm-meta time {
  color: #a8a29e;
  font-weight: 400;
}

.mm-dm-bubble--own {
  background: #ede9fe;
  color: #1c1917;
  border-top-right-radius: 6px;
  border-radius: 16px;
  padding: 10px 14px;
  max-width: 100%;
  width: fit-content;
}

.mm-dm-bubble--agent {
  background: transparent;
  color: #1c1917;
  border-radius: 0;
  padding: 0 4px;
  width: fit-content;
  max-width: 100%;
}

.mm-dm-bubble--own .whitespace-pre-wrap {
  color: inherit;
}

.mm-dm-doc {
  display: flex;
  align-items: center;
  gap: 8px;
  width: max-content;
  max-width: min(22rem, 100%);
  padding: 8px 8px 8px 10px;
  border: 1px solid #efeae4;
  border-radius: 12px;
  background: #fff;
  color: #1c1917;
}

.mm-dm-doc__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.mm-dm-doc__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.mm-dm-doc__name {
  overflow: hidden;
  max-width: 15rem;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-dm-doc__meta {
  color: #a8a29e;
  font-size: 12px;
  line-height: 1.3;
}

.mm-dm-doc__download {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 999px;
  background: #f5f3ff;
  color: #7c3aed;
  cursor: pointer;
}
</style>
