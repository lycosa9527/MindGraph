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
  ElTooltip,
} from 'element-plus'

import { ChatDotRound, Download } from '@element-plus/icons-vue'

import { ArrowLeft, FileImage, FileJson, FileText, ImageDown, RotateCcw, Share2 } from '@lucide/vue'

import CanvasToolbar from '@/components/canvas/CanvasToolbar.vue'
import DiagramSlotFullModal from '@/components/canvas/DiagramSlotFullModal.vue'
import { useFeatureFlags } from '@/composables'
import { useCanvasReset } from '@/composables/canvasPage/useCanvasReset'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import {
  eventBus,
  getDefaultDiagramName,
  useDiagramSpecForSave,
  useNotifications,
} from '@/composables'
import type { SnapshotMetadata } from '@/composables'
import { useLanguage } from '@/composables'
import { CANVAS_TOP_BAR } from '@/config/uiConfig'
import { CANVAS_STANDARD_EXPORT_MENU_ITEMS, CANVAS_COMMUNITY_EXPORT_MENU_ITEM } from '@/config/canvasExportMenu'
import { isPdfExportCommand } from '@/utils/diagramPdfExport'
import { useAuthStore, useDiagramStore, usePanelsStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { navigateBackFromCanvas } from '@/utils/canvasBackNavigation'

const { resetToDefaultTemplate } = useCanvasReset()

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
  /** Snapshot version being restored (shows loading animation on that badge) */
  recallingSnapshotVersion?: number | null
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

function onSnapshotBadgeClick(event: MouseEvent, versionNumber: number): void {
  if (props.isCollabGuest || props.recallingSnapshotVersion != null) {
    return
  }
  event.stopPropagation()
  if (event.ctrlKey || event.metaKey) {
    emit('snapshotDelete', versionNumber)
    return
  }
  emit('snapshotRecall', versionNumber)
}

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

const isMindMapEditor = useMindMapV2Chrome()

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

// Use Pinia store for title (synced with diagram state via effectiveTitle)
const fileName = computed({
  get: () => diagramStore.effectiveTitle || generateDefaultName(),
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
  navigateBackFromCanvas(router, route.path)
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
  await resetToDefaultTemplate()
  showSlotFullModal.value = false
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
    <div
      class="min-w-0 flex justify-center items-center self-center overflow-x-auto px-0.5 z-[5]"
    >
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
        v-if="props.snapshots?.length && !props.isViewer && !props.isCollabGuest"
        class="flex items-center gap-1.5 shrink-0"
      >
        <ElTooltip
          v-for="snap in props.snapshots"
          :key="snap.version_number"
          trigger="hover"
          :content="
            snap.version_number === props.recallingSnapshotVersion
              ? t('canvas.topBar.snapshotRecallingTooltip', { n: snap.version_number })
              : t('canvas.topBar.snapshotBadgeTooltip', { n: snap.version_number })
          "
          placement="bottom"
        >
          <span
            class="snapshot-version-badge inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0 transition-colors select-none"
            :class="[
              props.isCollabGuest ? 'cursor-default opacity-50' : 'cursor-pointer',
              snap.version_number === props.recallingSnapshotVersion
                ? 'snapshot-version-badge--loading'
                : props.recallingSnapshotVersion != null
                  ? 'opacity-50 pointer-events-none'
                  : '',
              snap.version_number === props.activeSnapshotVersion &&
              snap.version_number !== props.recallingSnapshotVersion
                ? 'bg-blue-500 text-white ring-2 ring-blue-300 ring-offset-1'
                : snap.version_number !== props.recallingSnapshotVersion
                  ? 'bg-blue-100 text-blue-600 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-800/50'
                  : 'bg-blue-500 text-white',
            ]"
            :aria-busy="snap.version_number === props.recallingSnapshotVersion"
            role="button"
            tabindex="0"
            @click.stop="onSnapshotBadgeClick($event, snap.version_number)"
            @keydown.enter.stop="
              onSnapshotBadgeClick($event as unknown as MouseEvent, snap.version_number)
            "
            @keydown.space.prevent.stop="
              onSnapshotBadgeClick($event as unknown as MouseEvent, snap.version_number)
            "
          >
            {{ snap.version_number }}
          </span>
        </ElTooltip>
      </div>

      <div class="flex items-center gap-1.5 sm:gap-2 shrink-0">
        <ElTooltip
          v-if="isMindMapEditor && !props.isViewer"
          :content="t('canvas.topBar.resetTemplate')"
          placement="bottom"
          :disabled="!compactTopBarActions"
        >
          <button
            type="button"
            class="mm-btn"
            :class="{ 'mm-btn--icon': compactTopBarActions }"
            :aria-label="t('canvas.topBar.resetCanvas')"
            @click="handleReset"
          >
            <RotateCcw class="w-4 h-4" />
            <span
              v-if="!compactTopBarActions"
              class="mm-btn__label"
            >{{ t('canvas.topBar.resetCanvas') }}</span>
          </button>
        </ElTooltip>

        <ElTooltip
          v-if="!isMindMapEditor"
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
          v-if="!isMindMapEditor"
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
          v-if="!isMindMapEditor"
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
                  <ElDropdownItem
                    v-for="item in CANVAS_STANDARD_EXPORT_MENU_ITEMS"
                    :key="item.command"
                    :command="item.command"
                    :divided="item.divided"
                  >
                    <ImageDown
                      v-if="item.command === 'png'"
                      class="w-4 h-4 mr-2 text-emerald-500"
                    />
                    <FileImage
                      v-else-if="item.command === 'svg'"
                      class="w-4 h-4 mr-2 text-violet-500"
                    />
                    <FileText
                      v-else-if="isPdfExportCommand(item.command)"
                      class="w-4 h-4 mr-2 text-red-500"
                    />
                    <FileJson
                      v-else-if="item.command === 'mg'"
                      class="w-4 h-4 mr-2 text-amber-500"
                    />
                    {{ t(item.labelKey) }}
                  </ElDropdownItem>
                  <ElDropdownItem
                    v-if="featureCommunity && authStore.isAuthenticated"
                    :divided="CANVAS_COMMUNITY_EXPORT_MENU_ITEM.divided"
                    :command="CANVAS_COMMUNITY_EXPORT_MENU_ITEM.command"
                  >
                    <Share2 class="w-4 h-4 mr-2 text-rose-500" />
                    {{ t(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.labelKey) }}
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

<style src="./mindMapToolbarButtons.css"></style>

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

/* Snapshot version badge — spinning ring while recall is in progress */
.snapshot-version-badge {
  position: relative;
}

.snapshot-version-badge--loading {
  pointer-events: none;
}

.snapshot-version-badge--loading::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 2px solid rgb(147 197 253 / 0.35);
  border-top-color: rgb(255 255 255 / 0.95);
  animation: snapshot-version-badge-spin 0.65s linear infinite;
}

@keyframes snapshot-version-badge-spin {
  to {
    transform: rotate(360deg);
  }
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
