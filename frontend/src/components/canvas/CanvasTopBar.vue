<script setup lang="ts">
/**
 * CanvasTopBar - Top navigation bar for canvas page
 * Uses Element Plus components for polished menu bar
 * Migrated from prototype MindGraphCanvasPage top bar
 *
 * Enhanced with Save to Gallery functionality:
 * - Saves diagram to user's library
 * - Shows slot management modal when library is full
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElInput,
  ElMessageBox,
  ElTooltip,
} from 'element-plus'

import { ChatDotRound, Download } from '@element-plus/icons-vue'

import {
  ArrowLeft,
  FileImage,
  FileJson,
  FileText,
  ImageDown,
  RotateCcw,
  Share2,
} from 'lucide-vue-next'

import CanvasToolbar from '@/components/canvas/CanvasToolbar.vue'
import DiagramSlotFullModal from '@/components/canvas/DiagramSlotFullModal.vue'
import { useFeatureFlags } from '@/composables'
import {
  eventBus,
  getDefaultDiagramName,
  useDiagramSpecForSave,
  useNotifications,
} from '@/composables'
import type { SnapshotMetadata } from '@/composables'
import { useLanguage } from '@/composables'
import { CANVAS_TOP_BAR } from '@/config/uiConfig'
import { useAuthStore, useDiagramStore, useLLMResultsStore, usePanelsStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { CANVAS_ENTRY_PATH_KEY, isMindGraphLandingPath } from '@/utils/canvasBackNavigation'

const notify = useNotifications()

const topBarRootRef = ref<HTMLElement | null>(null)
/** Icon-only for MindMate / reset / export (first tier — wider breakpoint). */
const compactTopBarActions = ref(false)
/** Icon-only editing toolbar labels (second tier — narrower breakpoint). */
const compactCanvasToolbar = ref(false)

let topBarResizeObserver: ResizeObserver | null = null

function updateCompactFromTopBarWidth(width: number): void {
  const w = width > 0 ? width : 0
  compactTopBarActions.value = w > 0 && w < CANVAS_TOP_BAR.COMPACT_RIGHT_ACTIONS_BREAKPOINT_PX
  compactCanvasToolbar.value = w > 0 && w < CANVAS_TOP_BAR.COMPACT_TOOLBAR_BREAKPOINT_PX
}

const props = defineProps<{
  autoSavedStatus?: string | null
  slotFullAndNewDiagram?: boolean
  isDirty?: boolean
  isSaving?: boolean
  /** Snapshot badges to display next to the filename */
  snapshots?: SnapshotMetadata[]
  /** Currently active (recalled) snapshot version */
  activeSnapshotVersion?: number | null
  /** Active workshop session code (passed from CanvasPage) */
  workshopCode?: string | null
  /** True when the current user is a collab guest (not the diagram owner) */
  isCollabGuest?: boolean
  /** True when the current user is a viewer (read-only role in the workshop) */
  isViewer?: boolean
  /** Workshop role: "host" | "editor" | "viewer" */
  workshopRole?: string | null
}>()

const emit = defineEmits<{
  saveRequested: []
  snapshotRecall: [versionNumber: number]
  snapshotDelete: [versionNumber: number]
}>()

const route = useRoute()
const router = useRouter()
const { promptLanguage, t, currentLanguage } = useLanguage()
const diagramStore = useDiagramStore()

const savedDiagramsStore = useSavedDiagramsStore()
const authStore = useAuthStore()
const panelsStore = usePanelsStore()

const { featureCommunity } = useFeatureFlags()

/** Native tooltip: status text + action hint (replaces duplicate :title bindings) */
const autoSaveHoverTitle = computed(() => {
  const status = props.autoSavedStatus
  if (!status) return undefined
  const hint = props.slotFullAndNewDiagram
    ? t('canvas.topBar.autoSaveTitleSlotFull')
    : t('canvas.topBar.autoSaveTitleSave')
  return `${status} — ${hint}`
})

// Diagram type from store (when loaded) or route query (for new diagrams)
const diagramTypeForName = computed(
  () => (diagramStore.type as string) || (route.query.type as string) || null
)

/**
 * Generate default diagram name (simple, no timestamp)
 * Format: "新圆圈图" / "New Circle Map"
 */
function generateDefaultName(): string {
  return getDefaultDiagramName(diagramTypeForName.value, currentLanguage.value)
}

// File name editing state (UI only)
const isFileNameEditing = ref(false)
const fileNameInputRef = ref<InstanceType<typeof ElInput> | null>(null)

// Use Pinia store for title (synced with diagram state)
// Priority: topic > user-edited title > simple default (no timestamp)
const fileName = computed({
  get: () => {
    const topicText = diagramStore.getTopicNodeText()
    if (topicText) {
      return topicText
    }
    return diagramStore.effectiveTitle || generateDefaultName()
  },
  set: (value: string) => diagramStore.setTitle(value, true),
})

const showSlotFullModal = ref(false)

// Cleanup watcher on unmount
onUnmounted(() => {
  topBarResizeObserver?.disconnect()
  topBarResizeObserver = null
  eventBus.removeAllListenersForOwner('CanvasTopBar')
})

onMounted(() => {
  eventBus.onWithOwner(
    'canvas:show_slot_full_modal',
    () => {
      showSlotFullModal.value = true
    },
    'CanvasTopBar'
  )
  // Initialize title if not already set (new diagram)
  if (!diagramStore.title) {
    const topicText = diagramStore.getTopicNodeText()
    if (topicText) {
      diagramStore.initTitle(topicText)
    } else {
      diagramStore.initTitle(generateDefaultName())
    }
  }
  // Fetch diagrams to get current slot count
  savedDiagramsStore.fetchDiagrams()

  const root = topBarRootRef.value
  if (root) {
    topBarResizeObserver = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0
      updateCompactFromTopBarWidth(w)
    })
    updateCompactFromTopBarWidth(root.getBoundingClientRect().width)
    topBarResizeObserver.observe(root)
  }
})

// Watch for topic node text changes and auto-update title
// Only if user hasn't manually edited the name
watch(
  () => diagramStore.getTopicNodeText(),
  (newTopicText) => {
    // Don't auto-update if user has manually edited the title
    if (!diagramStore.shouldAutoUpdateTitle()) return
    // Don't auto-update if currently editing the name
    if (isFileNameEditing.value) return

    if (newTopicText) {
      diagramStore.initTitle(newTopicText)
    }
  }
)

function handleBack() {
  const entry = sessionStorage.getItem(CANVAS_ENTRY_PATH_KEY)
  if (
    entry &&
    isMindGraphLandingPath(entry) &&
    typeof window !== 'undefined' &&
    window.history.length > 1
  ) {
    router.back()
    return
  }
  router.replace({ name: 'MindGraph' })
}

function handleFileNameClick() {
  isFileNameEditing.value = true
  nextTick(() => {
    fileNameInputRef.value?.select()
  })
}

function handleFileNameBlur() {
  isFileNameEditing.value = false
  const currentValue = diagramStore.title?.trim()
  if (!currentValue) {
    // Reset to default if empty (and allow auto-updates again)
    diagramStore.initTitle(generateDefaultName())
  }
  // If there's a value, isUserEditedTitle is already set by the computed setter
}

function handleFileNameKeyPress(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    handleFileNameBlur()
  }
}

function handleAutoSaveStatusClick() {
  if (props.slotFullAndNewDiagram) {
    showSlotFullModal.value = true
  } else {
    emit('saveRequested')
  }
}

/** Get diagram spec for saving (includes llm_results when 2+ models) */
const getDiagramSpec = useDiagramSpecForSave()

// Handle slot full modal success
function handleSlotModalSuccess(_diagramId: string): void {
  showSlotFullModal.value = false
  // The diagram is now saved and activeDiagramId is set in the store
}

// Handle slot full modal cancel
function handleSlotModalCancel(): void {
  showSlotFullModal.value = false
}

// Export menu actions - emit event for DiagramCanvas to handle
function handleExportCommand(command: string) {
  eventBus.emit('toolbar:export_requested', { format: command })
}

function handleOpenMindmate() {
  panelsStore.openMindmate()
}

/**
 * Reset canvas to default template: clears diagram, node palette, and saved state.
 * Nothing is persisted. Shows confirmation modal first.
 */
async function handleReset() {
  const diagramType = diagramStore.type as DiagramType | null
  if (!diagramType) {
    notify.warning(t('canvas.reset.warnSelectType'))
    return
  }

  try {
    await ElMessageBox.confirm(t('canvas.reset.confirmBody'), t('canvas.reset.confirmTitle'), {
      confirmButtonText: t('canvas.reset.confirmButton'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }

  savedDiagramsStore.clearActiveDiagram()
  router.replace({ path: '/canvas', query: { type: diagramType } })
  showSlotFullModal.value = false
  useLLMResultsStore().reset()
  panelsStore.reset()
  diagramStore.clearHistory()
  diagramStore.loadDefaultTemplate(diagramType)
  diagramStore.initTitle(generateDefaultName())
  if (diagramType !== 'concept_map') {
    eventBus.emit('view:fit_to_canvas_requested', { animate: true })
  }
  notify.success(t('notification.resetDefaultTemplate'))
}
</script>

<template>
  <div
    ref="topBarRootRef"
    class="canvas-top-bar relative w-full min-h-12 px-2 sm:px-3 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-x-1 sm:gap-x-2 shrink-0 border-b border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md"
  >
    <!-- Col 1: back + title + auto-save -->
    <div
      class="flex items-center gap-1 min-w-0 z-10"
      :style="{ maxWidth: CANVAS_TOP_BAR.LEFT_CLUSTER_MAX_WIDTH }"
    >
      <ElTooltip
        :content="t('canvas.topBar.back')"
        placement="bottom"
      >
        <ElButton
          text
          circle
          size="small"
          @click="handleBack"
        >
          <ArrowLeft class="w-[18px] h-[18px] mg-icon-flip-rtl" />
        </ElButton>
      </ElTooltip>

      <div class="h-5 border-r border-gray-200 dark:border-gray-600 mx-1 shrink-0" />

      <div class="flex items-center gap-1.5 sm:gap-2 ml-1 min-w-0 flex-1 overflow-hidden">
        <ElInput
          v-if="isFileNameEditing"
          ref="fileNameInputRef"
          v-model="fileName"
          size="small"
          class="file-name-input"
          :style="{ maxWidth: CANVAS_TOP_BAR.FILE_NAME_INPUT_MAX_WIDTH }"
          @blur="handleFileNameBlur"
          @keypress="handleFileNameKeyPress"
        />
        <ElTooltip
          v-else
          :content="fileName"
          placement="bottom"
        >
          <span
            class="file-name-label text-xs font-medium text-gray-700 dark:text-gray-200 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors px-1.5 sm:px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 truncate"
            :style="{ maxWidth: CANVAS_TOP_BAR.FILENAME_DISPLAY_MAX_WIDTH }"
            @click="handleFileNameClick"
          >
            {{ fileName }}
          </span>
        </ElTooltip>

        <span
          v-if="props.autoSavedStatus && !props.isViewer"
          class="auto-saved-status text-xs shrink-0 min-w-0 cursor-pointer transition-colors truncate"
          :style="{ maxWidth: CANVAS_TOP_BAR.AUTOSAVE_STATUS_MAX_WIDTH }"
          :title="autoSaveHoverTitle"
          :class="[
            props.isSaving
              ? 'text-blue-500 dark:text-blue-400'
              : props.isDirty
                ? 'text-amber-500 dark:text-amber-400'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
          ]"
          @click="handleAutoSaveStatusClick"
        >
          {{ props.autoSavedStatus }}
        </span>
      </div>
    </div>

    <!-- Col 2: editing toolbar (hidden for viewers) -->
    <div class="min-w-0 flex justify-center items-center self-center overflow-x-auto px-0.5 z-[5]">
      <span
        v-if="props.isViewer"
        class="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 rounded-full px-2.5 py-1 select-none"
      >
        👁 {{ t('canvas.topBar.viewOnly') }}
      </span>
      <CanvasToolbar
        v-else
        embedded
        :compact-toolbar="compactCanvasToolbar"
      />
    </div>

    <!-- Col 3: snapshots + workshop participants + actions -->
    <div
      class="flex w-full min-w-0 items-center justify-end gap-1.5 sm:gap-2 md:gap-3 z-10 flex-wrap sm:flex-nowrap"
    >
      <div
        v-if="props.snapshots?.length && !props.isViewer"
        class="flex items-center gap-1.5 shrink-0"
      >
        <ElTooltip
          v-for="snap in props.snapshots"
          :key="snap.version_number"
          :content="t('canvas.topBar.snapshotBadgeTooltip', { n: snap.version_number })"
          placement="bottom"
        >
          <span
            class="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0 transition-colors select-none"
            :class="[
              props.isCollabGuest ? 'cursor-default opacity-50' : 'cursor-pointer',
              snap.version_number === props.activeSnapshotVersion
                ? 'bg-blue-500 text-white ring-2 ring-blue-300 ring-offset-1'
                : 'bg-blue-100 text-blue-600 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-800/50',
            ]"
            @click="
              props.isCollabGuest
                ? undefined
                : (e: MouseEvent) =>
                    e.ctrlKey || e.metaKey
                      ? emit('snapshotDelete', snap.version_number)
                      : emit('snapshotRecall', snap.version_number)
            "
          >
            {{ snap.version_number }}
          </span>
        </ElTooltip>
      </div>

      <div class="flex items-center gap-1.5 sm:gap-2 shrink-0">
        <ElTooltip
          :content="t('canvas.topBar.teachingDesign')"
          placement="bottom"
          :disabled="!compactTopBarActions"
        >
          <ElButton
            class="mindmate-button"
            size="small"
            :icon="ChatDotRound"
            :aria-label="t('canvas.topBar.teachingDesign')"
            @click="handleOpenMindmate"
          >
            <span v-if="!compactTopBarActions">{{ t('canvas.topBar.teachingDesign') }}</span>
          </ElButton>
        </ElTooltip>

        <ElTooltip
          :content="t('canvas.topBar.resetTemplate')"
          placement="bottom"
          :disabled="!compactTopBarActions"
        >
          <ElButton
            class="reset-button"
            size="small"
            :icon="RotateCcw"
            :aria-label="t('canvas.topBar.reset')"
            @click="handleReset"
          >
            <span v-if="!compactTopBarActions">{{ t('canvas.topBar.reset') }}</span>
          </ElButton>
        </ElTooltip>

        <ElTooltip
          :content="t('canvas.topBar.export')"
          placement="bottom"
          :disabled="!compactTopBarActions"
        >
          <span class="inline-flex">
            <ElDropdown
              trigger="click"
              @command="handleExportCommand"
            >
              <ElButton
                class="export-button"
                size="small"
                :icon="Download"
                :aria-label="t('canvas.topBar.export')"
              >
                <span v-if="!compactTopBarActions">{{ t('canvas.topBar.export') }}</span>
              </ElButton>
              <template #dropdown>
                <ElDropdownMenu>
                  <ElDropdownItem command="png">
                    <ImageDown class="w-4 h-4 mr-2 text-emerald-500" />
                    {{ t('canvas.topBar.exportPng') }}
                  </ElDropdownItem>
                  <ElDropdownItem command="svg">
                    <FileImage class="w-4 h-4 mr-2 text-violet-500" />
                    {{ t('canvas.topBar.exportSvg') }}
                  </ElDropdownItem>
                  <ElDropdownItem command="pdf">
                    <FileText class="w-4 h-4 mr-2 text-red-500" />
                    {{ t('canvas.topBar.exportPdf') }}
                  </ElDropdownItem>
                  <ElDropdownItem
                    divided
                    command="mg"
                  >
                    <FileJson class="w-4 h-4 mr-2 text-amber-500" />
                    {{ t('canvas.topBar.exportJson') }}
                  </ElDropdownItem>
                  <ElDropdownItem
                    v-if="featureCommunity && authStore.isAuthenticated"
                    divided
                    command="community"
                  >
                    <Share2 class="w-4 h-4 mr-2 text-rose-500" />
                    {{ t('canvas.topBar.shareCommunity') }}
                  </ElDropdownItem>
                </ElDropdownMenu>
              </template>
            </ElDropdown>
          </span>
        </ElTooltip>
      </div>
    </div>

    <DiagramSlotFullModal
      v-model:visible="showSlotFullModal"
      :pending-title="fileName"
      :pending-diagram-type="diagramStore.type || ''"
      :pending-spec="getDiagramSpec() || {}"
      :pending-language="promptLanguage"
      @success="handleSlotModalSuccess"
      @cancel="handleSlotModalCancel"
    />
  </div>
</template>

<style scoped>
.canvas-top-bar {
  z-index: 100;
}

.participant-emoji {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  cursor: pointer;
  transition: transform 0.2s;
  border: 2px solid rgba(255, 255, 255, 0.3);
}

.participant-emoji:hover {
  transform: scale(1.1);
}

.participant-emoji-small {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.participant-more {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  background-color: rgba(0, 0, 0, 0.1);
  color: #666;
  cursor: pointer;
  transition: background-color 0.2s;
}

.participant-more:hover {
  background-color: rgba(0, 0, 0, 0.2);
}

.file-name-input {
  min-width: 0;
  width: 100%;
}

/* maxWidth from CANVAS_TOP_BAR.FILENAME_DISPLAY_MAX_WIDTH (inline) */
.file-name-label {
  min-width: 0;
  display: inline-block;
}

.file-name-input :deep(.el-input__inner) {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-color-primary);
}

/* Make dropdown items flex for shortcut alignment */
:deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  min-width: 180px;
}

.export-button {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

/* MindMate AI top-bar button - Swiss Design style */
.mindmate-button {
  --el-button-bg-color: #dbeafe;
  --el-button-border-color: #93c5fd;
  --el-button-hover-bg-color: #bfdbfe;
  --el-button-hover-border-color: #60a5fa;
  --el-button-active-bg-color: #93c5fd;
  --el-button-active-border-color: #3b82f6;
  --el-button-text-color: #1e40af;
  font-weight: 500;
  border-radius: 9999px;
}

/* Reset button - subtle warning tone */
.reset-button {
  --el-button-bg-color: #fef3c7;
  --el-button-border-color: #fcd34d;
  --el-button-hover-bg-color: #fde68a;
  --el-button-hover-border-color: #f59e0b;
  --el-button-active-bg-color: #fcd34d;
  --el-button-active-border-color: #d97706;
  --el-button-text-color: #92400e;
  font-weight: 500;
  border-radius: 9999px;
}
</style>
