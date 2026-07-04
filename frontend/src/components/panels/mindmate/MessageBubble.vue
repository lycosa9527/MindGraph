<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { ElAvatar, ElButton, ElIcon, ElInput, ElTooltip } from 'element-plus'

import { CopyDocument, Edit, RefreshRight, Share } from '@element-plus/icons-vue'

import { ThumbsDown, ThumbsUp } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { useRenderedMarkdown } from '@/composables/core/useRenderedMarkdown'
import { useMindmateDiagramPreviewImage } from '@/composables/mindmate/useMindmateDiagramPreviewImage'
import type { FeedbackRating, MindMateMessage } from '@/composables/mindmate/useMindMate'
import { useAuthStore } from '@/stores/auth'
import type { ModelLoadPhase } from '@/stores/llmResults'
import { authFetch } from '@/utils/api'
import { canvasEditorPathForRoute } from '@/utils/canvasBackNavigation'
import { extractMindmatePreviewCacheKey } from '@/utils/mindmateDiagramPreviewCache'
import { notifyMindmateDiagramPreviewExpired } from '@/utils/mindmateDiagramPreviewExpiredNotify'
import {
  extractMindmatePreviewUniqueId,
  hasGeneratedDiagramImage,
  needsLibraryFullHint,
  needsLibrarySaveHint,
  parseMindmateDiagramLibraryId,
} from '@/utils/mindmateDiagramMeta'

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
}>()

const emit = defineEmits<{
  (e: 'edit', message: MindMateMessage): void
  (e: 'cancelEdit'): void
  (e: 'saveEdit', content: string): void
  (e: 'copy', content: string): void
  (e: 'regenerate', messageId: string): void
  (e: 'feedback', messageId: string, rating: FeedbackRating): void
  (e: 'share'): void
  (e: 'mouseenter'): void
  (e: 'mouseleave'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const resolvedLibraryId = ref<string | null>(null)

const libraryDiagramId = computed(() => {
  if (props.message.role !== 'assistant' || props.message.isStreaming) {
    return null
  }
  return parseMindmateDiagramLibraryId(props.message.content) ?? resolvedLibraryId.value
})

const showCanvasButton = computed(() => libraryDiagramId.value !== null)

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
    notify.warning(t('mindmate.openCanvasLoginRequired'))
    await router.push({ path: '/auth', query: { redirect: route.fullPath } })
    return
  }
  openingCanvas.value = true
  try {
    const canvasPath = canvasEditorPathForRoute(route.path)
    await router.push({ path: canvasPath, query: { diagramId } })
  } catch {
    notify.error(t('mindmate.openCanvasFailed'))
  } finally {
    openingCanvas.value = false
  }
}

const pageHost = computed(() =>
  typeof window !== 'undefined' ? window.location.host : undefined
)

const { displayContent: mindmateDisplayContent, previewUnavailable } = useMindmateDiagramPreviewImage({
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

// Watch editingContent prop
watch(
  () => props.editingContent,
  (newVal) => {
    if (newVal !== undefined) {
      localEditingContent.value = newVal
    }
  }
)

// Get file icon based on type
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
    :class="message.role === 'user' ? 'user-message' : 'assistant-message'"
    @mouseenter="emit('mouseenter')"
    @mouseleave="emit('mouseleave')"
  >
    <div
      class="message flex gap-3 items-start"
      :class="message.role === 'user' ? 'flex-row-reverse' : ''"
    >
      <!-- Avatar -->
      <template v-if="message.role === 'user'">
        <ElAvatar
          :size="40"
          class="flex-shrink-0 bg-[#FAFAFA] border-2 border-[#303133] mg-user-avatar-emoji"
        >
          {{ userAvatar }}
        </ElAvatar>
      </template>
      <template v-else>
        <MindmateAgentAvatar
          :size="40"
          avatar-class="mindmate-avatar flex-shrink-0"
          :phase="agentLoadPhase ?? 'idle'"
        />
      </template>

      <!-- Content -->
      <div
        class="message-content-wrapper flex-1"
        :class="message.role === 'user' ? 'flex flex-col items-end' : 'flex flex-col items-start'"
      >
        <!-- User message editing -->
        <template v-if="message.role === 'user' && isEditing">
          <div class="edit-input-wrapper w-full max-w-[70%]">
            <ElInput
              v-model="localEditingContent"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              @keydown.enter.exact.prevent="handleSaveEdit"
              @keydown.esc.prevent="handleCancelEdit"
            />
            <div class="flex gap-2 mt-2 justify-end">
              <ElButton
                size="small"
                @click="handleCancelEdit"
              >
                {{ t('common.cancel') }}
              </ElButton>
              <ElButton
                type="primary"
                size="small"
                @click="handleSaveEdit"
              >
                {{ t('common.save') }}
              </ElButton>
            </div>
          </div>
        </template>

        <!-- Message content -->
        <template v-else>
          <div
            class="message-content max-w-[70%] relative"
            :class="[
              message.role === 'user'
                ? 'bg-[#606266] text-white px-4 py-1.5 rounded-2xl'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-white px-3 py-2 rounded-lg',
              message.isStreaming ? 'streaming' : '',
            ]"
          >
            <!-- User message - plain text with files -->
            <template v-if="message.role === 'user'">
              <!-- Attached files -->
              <div
                v-if="message.files && message.files.length > 0"
                class="message-files flex flex-wrap gap-2 mb-2"
              >
                <div
                  v-for="file in message.files"
                  :key="file.id"
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
                {{ t('mindmate.diagramLibraryFull') }}
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
          >
            <ElTooltip :content="t('mindmate.tooltip.edit')">
              <ElButton
                text
                circle
                size="small"
                @click="emit('edit', message)"
              >
                <ElIcon class="text-xs"><Edit /></ElIcon>
              </ElButton>
            </ElTooltip>
            <ElTooltip :content="t('mindmate.tooltip.copy')">
              <ElButton
                text
                circle
                size="small"
                @click="emit('copy', message.content)"
              >
                <ElIcon class="text-xs"><CopyDocument /></ElIcon>
              </ElButton>
            </ElTooltip>
          </div>

          <!-- AI message action bar -->
          <div
            v-if="message.role === 'assistant' && !message.isStreaming"
            class="action-bar mt-3 flex flex-wrap items-center gap-1"
            :class="{
              'action-bar-visible': isLastAssistant,
              'action-bar-hover': !isLastAssistant,
            }"
          >
            <!-- Copy -->
            <ElTooltip
              :content="t('mindmate.tooltip.copy')"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                @click="emit('copy', message.content)"
              >
                <ElIcon :size="18"><CopyDocument /></ElIcon>
              </ElButton>
            </ElTooltip>

            <!-- Regenerate -->
            <ElTooltip
              v-if="hasPreviousUserMessage"
              :content="t('mindmate.tooltip.regenerate')"
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
            </ElTooltip>

            <!-- Like -->
            <ElTooltip
              :content="t('mindmate.tooltip.like')"
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
            </ElTooltip>

            <!-- Dislike -->
            <ElTooltip
              :content="t('mindmate.tooltip.dislike')"
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
            </ElTooltip>

            <!-- Share -->
            <ElTooltip
              :content="t('mindmate.tooltip.share')"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                @click="emit('share')"
              >
                <ElIcon :size="18"><Share /></ElIcon>
              </ElButton>
            </ElTooltip>

            <!-- Open in canvas -->
            <ElButton
              v-if="showCanvasButton"
              size="small"
              class="mindmate-canvas-btn action-bar-canvas-btn"
              :loading="openingCanvas"
              @click="openInCanvas"
            >
              {{ t('mindmate.openInCanvas') }}
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
</style>
