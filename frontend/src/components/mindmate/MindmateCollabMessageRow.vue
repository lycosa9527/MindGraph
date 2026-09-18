<script setup lang="ts">
/**
 * One seminar transcript row: peer / own / MindMate.
 * MindMate teaching-instruction markers become Word / canvas actions, not raw tags.
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import MindmateCollabAssistantToolbar from '@/components/mindmate/MindmateCollabAssistantToolbar.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  confirmCanvasLibraryDiagramOpen,
  decideCanvasLibraryDiagramOpen,
} from '@/composables/canvasPage/canvasLibraryDiagramOpen'
import { useRenderedMarkdown } from '@/composables/core/useRenderedMarkdown'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { useAuthStore } from '@/stores/auth'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useTeachingDesignExportStore } from '@/stores/teachingDesignExport'
import { canvasEditorPathForRoute } from '@/utils/canvasBackNavigation'
import { copyMindmateAssistantMessage } from '@/utils/copyMindmateMessage'
import {
  type CollabFeedbackRating,
  collabAssistantLibraryDiagramId,
  displayMindmateCollabContent,
  shouldShowCollabWordTemplateExport,
} from '@/utils/mindmateCollabDisplay'
import { TEACHING_INSTRUCTION_KIND } from '@/utils/mindmateTeachingDesignFlag'

const props = defineProps<{
  message: MindmateCollabMessage
  isOwn: boolean
  userPrompt?: string
  agentName: string
  agentAvatarUrl: string
  isLastAssistant?: boolean
  regenerateDisabled?: boolean
  feedback?: CollabFeedbackRating
}>()

const emit = defineEmits<{
  (e: 'regenerate'): void
  (e: 'share'): void
  (e: 'feedback', rating: 'like' | 'dislike'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const teachingDesignExport = useTeachingDesignExportStore()
const { exportingMessageId } = storeToRefs(teachingDesignExport)
const route = useRoute()
const router = useRouter()

const openingCanvas = ref(false)

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

const libraryDiagramId = computed(() => collabAssistantLibraryDiagramId(props.message))

const displayText = computed(() =>
  displayMindmateCollabContent(props.message.content, props.message.role)
)

const { html: renderedMarkdownHtml } = useRenderedMarkdown(() => displayText.value, {
  stripThinkBlocks: true,
})

const isAssistant = computed(() => props.message.role === 'assistant')

const rowClass = computed(() => {
  if (props.isOwn) {
    return 'mindmate-collab-room__msg-row--own'
  }
  if (isAssistant.value) {
    return 'mindmate-collab-room__msg-row--other mindmate-collab-room__msg-row--assistant'
  }
  return 'mindmate-collab-room__msg-row--other'
})

async function handleCopy(): Promise<void> {
  try {
    await copyMindmateAssistantMessage(
      props.message.content,
      typeof window !== 'undefined' ? window.location.host : undefined
    )
    notify.successKey('notification.copied')
  } catch {
    notify.errorKey('notification.copyFailed')
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

async function openInCanvas(): Promise<void> {
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
</script>

<template>
  <div
    class="mindmate-collab-room__msg-row"
    :class="rowClass"
  >
    <div
      v-if="!isOwn"
      class="w-8 h-8 rounded-full shrink-0 overflow-hidden bg-stone-100 border border-stone-200"
    >
      <img
        v-if="isAssistant"
        :src="agentAvatarUrl"
        :alt="agentName"
        class="w-full h-full object-cover"
      />
      <span
        v-else
        class="flex w-full h-full items-center justify-center text-xs font-medium text-stone-600"
        aria-hidden="true"
      >
        {{ (message.username || '?').trim().slice(0, 1).toUpperCase() }}
      </span>
    </div>
    <div class="mindmate-collab-room__msg-body">
      <div
        v-if="isAssistant"
        class="text-[11px] text-stone-500 mb-1 px-1"
      >
        {{ agentName }}
      </div>
      <div
        v-else-if="!isOwn && message.username"
        class="text-[11px] text-stone-500 mb-1 px-1"
      >
        {{ message.username }}
      </div>
      <div
        class="mindmate-collab-room__bubble text-sm rounded-2xl px-3.5 py-2.5 leading-relaxed"
        :class="[
          isOwn
            ? 'bg-stone-800 text-stone-50 text-left'
            : 'bg-stone-100 text-stone-800 border border-stone-200/80',
          message.streaming ? 'mindmate-collab-room__bubble--streaming' : '',
          isAssistant ? '' : 'whitespace-pre-wrap',
        ]"
      >
        <!-- eslint-disable vue/no-v-html -- DOMPurify in renderRichMarkdownHtml pipeline -->
        <div
          v-if="isAssistant"
          class="mindmate-collab-room__markdown"
          v-html="renderedMarkdownHtml"
        />
        <!-- eslint-enable vue/no-v-html -->
        <template v-else>
          {{ message.content }}
        </template>
      </div>
      <MindmateCollabAssistantToolbar
        v-if="isAssistant && !message.streaming"
        :is-last-assistant="Boolean(isLastAssistant)"
        :can-regenerate="Boolean(userPrompt)"
        :regenerate-disabled="Boolean(regenerateDisabled)"
        :feedback="feedback"
        :show-word-template-export="showWordTemplateExport"
        :exporting-word="exportingMessageId === exportMessageId"
        :show-canvas="Boolean(libraryDiagramId)"
        :opening-canvas="openingCanvas"
        @copy="handleCopy"
        @regenerate="emit('regenerate')"
        @feedback="emit('feedback', $event)"
        @share="emit('share')"
        @export-word="handleExportWordTemplate"
        @open-canvas="openInCanvas"
      />
    </div>
  </div>
</template>

<style scoped>
@import '../panels/mindmate/mindmate.css';

.mindmate-collab-room__msg-row {
  display: flex;
  gap: 0.625rem;
  width: 100%;
  min-width: 0;
}

.mindmate-collab-room__msg-row--own {
  flex-direction: row-reverse;
}

.mindmate-collab-room__msg-body {
  min-width: 0;
  max-width: min(85%, 36rem);
  display: flex;
  flex-direction: column;
}

.mindmate-collab-room__msg-row--own .mindmate-collab-room__msg-body {
  align-items: flex-end;
}

.mindmate-collab-room__msg-row--other .mindmate-collab-room__msg-body {
  align-items: flex-start;
}

.mindmate-collab-room__msg-row--assistant .mindmate-collab-room__msg-body {
  flex: 1 1 auto;
  width: 100%;
  max-width: none;
  align-items: stretch;
}

.mindmate-collab-room__bubble {
  display: inline-block;
  max-width: 100%;
  overflow-wrap: break-word;
  word-break: normal;
}

.mindmate-collab-room__msg-row--assistant .mindmate-collab-room__bubble {
  display: block;
  box-sizing: border-box;
  width: 100%;
  max-width: none;
}

.mindmate-collab-room__bubble--streaming::after {
  content: '▍';
  margin-left: 0.1em;
  animation: mmc-caret 1s step-end infinite;
}

@keyframes mmc-caret {
  50% {
    opacity: 0;
  }
}

.mindmate-collab-room__markdown :deep(p) {
  margin: 0 0 0.5em;
}

.mindmate-collab-room__markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.mindmate-collab-room__markdown :deep(pre) {
  overflow-x: auto;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  background: rgba(28, 25, 23, 0.06);
}

.mindmate-collab-room__markdown :deep(code) {
  font-size: 0.85em;
}

.mindmate-collab-room__markdown :deep(ul),
.mindmate-collab-room__markdown :deep(ol) {
  margin: 0 0 0.5em;
  padding-left: 1.25em;
}

.mindmate-collab-room__msg-row--assistant:hover :deep(.action-bar.action-bar-hover) {
  opacity: 1;
}
</style>
