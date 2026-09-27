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

import { ElButton, ElInput, ElTooltip } from 'element-plus'

import { ArrowLeft } from '@lucide/vue'

import MindMapRibbonTabs from '@/canvas-ribbon/MindMapRibbonTabs.vue'
import { MIND_MAP_RIBBON_TOOLS_ID } from '@/canvas-ribbon/mindMapRibbonTypes'
import { useMindMapRibbonState } from '@/canvas-ribbon/useMindMapRibbonState'
import CanvasOnlineCollabMenu from '@/components/canvas/CanvasOnlineCollabMenu.vue'
import CanvasToolbar from '@/components/canvas/CanvasToolbar.vue'
import DiagramSlotFullModal from '@/components/canvas/DiagramSlotFullModal.vue'
import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import { eventBus, getDefaultDiagramName, useDiagramSpecForSave } from '@/composables'
import type { SnapshotMetadata } from '@/composables'
import { useLanguage } from '@/composables'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { studentHomeworkDiagramTitle } from '@/composables/learningSpace/lsHelpers'
import { useCanvasRibbonChrome } from '@/composables/mindMap/useCanvasRibbonChrome'
import { CANVAS_TOP_BAR } from '@/config/uiConfig'
import { useAuthStore } from '@/stores'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'
import { navigateBackFromCanvas } from '@/utils/canvasBackNavigation'

const topBarRootRef = ref<HTMLElement | null>(null)
/** Icon-only editing toolbar labels (second tier — narrower breakpoint). */
const compactCanvasToolbar = ref(false)

let topBarResizeObserver: ResizeObserver | null = null

function updateCompactFromTopBarWidth(width: number): void {
  const w = width > 0 ? width : 0
  compactCanvasToolbar.value = w > 0 && w < CANVAS_TOP_BAR.COMPACT_TOOLBAR_BREAKPOINT_PX
}

const props = defineProps<{
  autoSavedStatus?: string | null
  slotFullAndNewDiagram?: boolean
  isDirty?: boolean
  isSaving?: boolean
  previewLock?: boolean
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

const route = useRoute()
const router = useRouter()
const { promptLanguage, t, currentLanguage } = useLanguage()
const diagramStore = useDiagramSession()

const authStore = useAuthStore()
const lsCanvas = useLearningAssignmentCanvasStore()
const isHomeworkCanvas = computed(() => lsCanvas.isActive)

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

const ribbonChrome = useCanvasRibbonChrome()
const { activeTab, classic, selectTab } = useMindMapRibbonState()

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

function lockHomeworkFileName(): void {
  if (!isHomeworkCanvas.value || isFileNameEditing.value) return
  if (!lsCanvas.draftHydrated) return
  const locked = studentHomeworkDiagramTitle(
    authStore.user?.username,
    authStore.user?.id,
    lsCanvas.assignment?.title
  )
  if (diagramStore.title !== locked) {
    diagramStore.setTitle(locked, true)
  }
}

onMounted(() => {
  eventBus.onWithOwner(
    'canvas:show_slot_full_modal',
    () => {
      showSlotFullModal.value = true
    },
    'CanvasTopBar'
  )
  // Initialize title if not already set (new diagram)
  if (isHomeworkCanvas.value) {
    lockHomeworkFileName()
  } else if (!diagramStore.title) {
    const topicText = diagramStore.getTopicNodeText()
    if (topicText) {
      diagramStore.initTitle(topicText)
    } else {
      diagramStore.initTitle(generateDefaultName())
    }
  }

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
    if (isHomeworkCanvas.value) return
    // Don't auto-update if user has manually edited the title
    if (!diagramStore.shouldAutoUpdateTitle()) return
    // Don't auto-update if currently editing the name
    if (isFileNameEditing.value) return

    if (newTopicText) {
      diagramStore.initTitle(newTopicText)
    }
  }
)

watch(
  () =>
    [
      isHomeworkCanvas.value,
      lsCanvas.draftHydrated,
      lsCanvas.assignment?.title,
      authStore.user?.username,
    ] as const,
  () => {
    lockHomeworkFileName()
  }
)

function handleBack() {
  if (props.previewLock) return
  if (lsCanvas.isActive) {
    void router.push('/learning-space')
    return
  }
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

/** Pure read — never stamp from the template (that freezes AutoComplete). */
const getDiagramSpec = useDiagramSpecForSave()
/** Snapshot at modal open so template does not re-evaluate on every render. */
const pendingSpecForSlotModal = ref<Record<string, unknown>>({})

watch(showSlotFullModal, (open) => {
  if (open) {
    pendingSpecForSlotModal.value = getDiagramSpec() || {}
  }
})

// Handle slot full modal success
function handleSlotModalSuccess(_diagramId: string): void {
  showSlotFullModal.value = false
  // The diagram is now saved and activeDiagramId is set in the store
}

// Handle slot full modal cancel
function handleSlotModalCancel(): void {
  showSlotFullModal.value = false
}
</script>

<template>
  <div
    ref="topBarRootRef"
    class="canvas-top-bar relative w-full min-h-12 shrink-0"
    :class="
      ribbonChrome
        ? {
            'canvas-top-bar--mindmap': true,
            'canvas-top-bar--collapsed': !classic,
            'canvas-top-bar--collab-flush': Boolean(workshopCode),
          }
        : 'px-2 sm:px-3 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-x-1 sm:gap-x-2 border-b border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md'
    "
  >
    <div
      class="canvas-top-bar__title-row"
      :class="{ 'canvas-top-bar__title-row--mindmap': ribbonChrome }"
    >
      <div
        class="flex items-center gap-1 min-w-0 z-10"
        :class="{ 'canvas-top-bar__doc': ribbonChrome }"
        :style="ribbonChrome ? undefined : { maxWidth: CANVAS_TOP_BAR.LEFT_CLUSTER_MAX_WIDTH }"
      >
        <I18nTooltip
          :k="isHomeworkCanvas ? 'learningSpace.backToLearningSpace' : 'canvas.topBar.back'"
          placement="bottom"
        >
          <ElButton
            text
            circle
            size="small"
            @click="handleBack"
          >
            <ArrowLeft class="w-4.5 h-4.5 mg-icon-flip-rtl" />
          </ElButton>
        </I18nTooltip>

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
              class="file-name-label text-xs font-medium cursor-pointer transition-colors px-1.5 sm:px-2 py-1 rounded truncate"
              :class="
                ribbonChrome
                  ? 'text-gray-800 hover:text-blue-600 hover:bg-white/70'
                  : 'text-gray-700 dark:text-gray-200 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700'
              "
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
                ? ribbonChrome
                  ? 'text-blue-500'
                  : 'text-blue-500 dark:text-blue-400'
                : props.isDirty
                  ? ribbonChrome
                    ? 'text-amber-500'
                    : 'text-amber-500 dark:text-amber-400'
                  : ribbonChrome
                    ? 'text-gray-500 hover:text-gray-700'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
            ]"
            @click="handleAutoSaveStatusClick"
          >
            {{ props.autoSavedStatus }}
          </span>
        </div>
      </div>
      <div
        v-if="ribbonChrome"
        class="canvas-top-bar__tabs"
      >
        <MindMapRibbonTabs
          :active-tab="activeTab"
          :expanded="classic"
          @update:active-tab="selectTab"
        />
      </div>
      <div
        v-if="ribbonChrome"
        class="canvas-top-bar__global"
      >
        <CanvasOnlineCollabMenu
          :workshop-code="workshopCode"
          :is-collab-guest="isCollabGuest"
          :is-viewer="isViewer"
        />
      </div>
    </div>

    <!-- Col 2: editing toolbar (hidden for viewers) -->
    <div
      :id="ribbonChrome ? MIND_MAP_RIBBON_TOOLS_ID : undefined"
      class="min-w-0 flex justify-center items-center self-center overflow-x-auto px-0.5 z-5"
      :class="{
        'canvas-top-bar__tools-row': ribbonChrome,
        'canvas-top-bar__tools-row--collapsed': ribbonChrome && !classic,
      }"
      :aria-hidden="ribbonChrome && !classic"
    >
      <span
        v-if="props.isViewer"
        class="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 rounded-full px-2.5 py-1 select-none"
      >
        👁 <I18nText k="canvas.topBar.viewOnly" />
      </span>
      <CanvasToolbar
        v-else
        embedded
        :compact-toolbar="compactCanvasToolbar"
        :ribbon-tab="ribbonChrome ? activeTab : undefined"
      />
    </div>

    <DiagramSlotFullModal
      v-model:visible="showSlotFullModal"
      :pending-title="fileName"
      :pending-diagram-type="diagramStore.type || ''"
      :pending-spec="pendingSpecForSlotModal"
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

.canvas-top-bar__title-row {
  display: contents;
}

.canvas-top-bar__title-row--mindmap {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: flex-end;
  gap: 8px;
  width: 100%;
  min-height: 2.25rem;
  padding: 0 12px 0 8px;
  overflow: visible;
  border: none;
  background: transparent;
  box-shadow: none;
  transition: padding 0.18s ease;
}

.canvas-top-bar--collapsed .canvas-top-bar__title-row--mindmap {
  padding-bottom: 2px;
}

.canvas-top-bar--mindmap {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  padding: 0 0 10px;
  border-bottom: none;
  background-color: transparent;
  background-image: linear-gradient(
    90deg,
    rgb(214 232 252 / 0.8) 0%,
    rgb(226 224 248 / 0.72) 48%,
    rgb(236 222 250 / 0.84) 100%
  );
  backdrop-filter: blur(18px) saturate(1.12);
  -webkit-backdrop-filter: blur(18px) saturate(1.12);
  box-shadow: 0 8px 22px rgb(168 176 228 / 0.14);
  transition: padding 0.18s ease;
}

.canvas-top-bar--mindmap.canvas-top-bar--collapsed {
  padding-bottom: 6px;
}

/* Live session banner sits in the next flex row — drop the card-shadow inset. */
.canvas-top-bar--mindmap.canvas-top-bar--collab-flush {
  padding-bottom: 0;
  box-shadow: none;
}

.canvas-top-bar__doc {
  justify-self: start;
  align-self: end;
  display: flex;
  align-items: center;
  box-sizing: border-box;
  height: 36px;
  max-width: min(46vw, 22rem);
}

.canvas-top-bar__tabs {
  grid-column: 2;
  justify-self: center;
  display: flex;
  justify-content: center;
}

.canvas-top-bar__global {
  grid-column: 3;
  justify-self: end;
  align-self: end;
  display: flex;
  align-items: center;
  height: 36px;
}

.canvas-top-bar__doc :deep(.el-button) {
  color: #4b5563;
}

.canvas-top-bar__doc :deep(.el-button:hover) {
  background: rgb(255 255 255 / 0.72);
  color: #1f2937;
}

.canvas-top-bar__doc .file-name-label {
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  padding-top: 0;
  padding-bottom: 0;
}

.canvas-top-bar__doc .file-name-label:hover {
  color: #2563eb;
  background: rgb(255 255 255 / 0.72);
}

.canvas-top-bar__doc .auto-saved-status {
  color: #6b7280;
  font-size: 13px;
  line-height: 1;
}

.canvas-top-bar__doc .border-r {
  border-color: #d1d5db;
}

.canvas-top-bar__tools-row {
  box-sizing: border-box;
  width: calc(100% - 24px);
  max-width: calc(100% - 24px);
  min-height: 50px;
  height: auto;
  flex-shrink: 0;
  align-self: center;
  justify-content: center;
  margin: 0 auto;
  padding: 5px 10px;
  overflow-x: auto;
  overflow-y: hidden;
  border: none;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 10px 18px -8px rgb(15 23 42 / 0.12);
  transition:
    height 0.18s ease,
    min-height 0.18s ease,
    padding 0.18s ease,
    margin 0.18s ease,
    opacity 0.16s ease;
}

.canvas-top-bar__tools-row--collapsed {
  height: 0;
  min-height: 0;
  max-height: 0;
  margin: 0 auto;
  padding: 0 10px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
  box-shadow: none;
}

.canvas-top-bar__tools-row :deep(.canvas-toolbar),
.canvas-top-bar__tools-row :deep(.mm-toolbar) {
  width: 100%;
  max-width: 100%;
  height: 100%;
}

.canvas-top-bar__tools-row :deep(.canvas-toolbar > div) {
  width: 100%;
  max-width: 100%;
}

:global(.dark) .canvas-top-bar__tools-row {
  background: #1f2937;
  box-shadow: 0 10px 18px -8px rgb(0 0 0 / 0.35);
}

:global(.dark) .canvas-top-bar--mindmap {
  background-color: transparent;
  background-image: linear-gradient(
    90deg,
    rgb(36 62 102 / 0.78) 0%,
    rgb(52 48 92 / 0.72) 48%,
    rgb(72 44 102 / 0.82) 100%
  );
  box-shadow: 0 8px 22px rgb(0 0 0 / 0.18);
}

:global(.dark) .canvas-top-bar--mindmap.canvas-top-bar--collab-flush {
  box-shadow: none;
}

:global(.dark) .canvas-top-bar__doc :deep(.el-button) {
  color: #d1d5db;
}

:global(.dark) .canvas-top-bar__doc .file-name-label {
  color: #e5e7eb;
}

:global(.dark) .canvas-top-bar__doc .file-name-label:hover {
  color: #93c5fd;
}

:global(.dark) .canvas-top-bar__doc .auto-saved-status {
  color: #9ca3af;
}

:global(.dark) .canvas-top-bar__doc .border-r {
  border-color: #4b5563;
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
