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

// Using Lucide icons for a more modern, cute look
import {
  ArrowLeft,
  Check,
  CircleSlash,
  FileImage,
  FileJson,
  FileText,
  ImageDown,
  Loader2,
  RotateCcw,
  Share2,
  Users,
} from 'lucide-vue-next'

import { DiagramSlotFullModal } from '@/components/canvas'
import OnlineCollabModal from '@/components/canvas/OnlineCollabModal.vue'
import { useFeatureFlags } from '@/composables'
import {
  eventBus,
  getDefaultDiagramName,
  useDiagramSpecForSave,
  useNotifications,
  useWorkshop,
} from '@/composables'
import type { SnapshotMetadata } from '@/composables'
import { useLanguage } from '@/composables'
import { FOCUS_MODELS, type FocusModel } from '@/composables/editor/conceptMapFocusQuestionApi'
import { getLLMColor } from '@/config/llmModelColors'
import {
  useAuthStore,
  useConceptMapFocusReviewStore,
  useDiagramStore,
  useLLMResultsStore,
  usePanelsStore,
} from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'
import type { DiagramType } from '@/types'

const notify = useNotifications()

const props = defineProps<{
  autoSavedStatus?: string | null
  slotFullAndNewDiagram?: boolean
  isDirty?: boolean
  isSaving?: boolean
  /** Concept map: focus question (standard mode), shown centered in the bar */
  focusQuestion?: string | null
  /** Snapshot badges to display next to the filename */
  snapshots?: SnapshotMetadata[]
  /** Currently active (recalled) snapshot version */
  activeSnapshotVersion?: number | null
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

const focusQuestionCenterTitle = computed(() => {
  if (!props.focusQuestion) return ''
  const prefix = t('canvas.topBar.focusQuestionLabel')
  return `${prefix} ${props.focusQuestion}`
})
const savedDiagramsStore = useSavedDiagramsStore()
const authStore = useAuthStore()
const focusReviewStore = useConceptMapFocusReviewStore()
const uiStore = useUIStore()
const panelsStore = usePanelsStore()

const FOCUS_MODEL_LABELS: Record<FocusModel, string> = {
  qwen: 'Qwen',
  deepseek: 'DeepSeek',
  doubao: 'Doubao',
}

/**
 * Three LLM focus-question validation chips: only while the topic node alone is selected.
 * Clicking the canvas (clearing selection) or selecting another node hides them — validation is “done” for this focus.
 */
const showFocusValidationChips = computed(() => {
  if (diagramStore.type !== 'concept_map' || !props.focusQuestion) return false
  const nodes = diagramStore.selectedNodes
  return nodes.length === 1 && nodes[0] === 'topic'
})

function focusVState(m: FocusModel) {
  return (
    focusReviewStore.validationByModel[m] ?? {
      valid: null,
      reason: '',
      error: null,
      loading: false,
    }
  )
}

function focusChipSurface(m: FocusModel): Record<string, string> {
  const c = getLLMColor(m, uiStore.isDark)
  if (!c) return {}
  return { backgroundColor: c.bg, borderColor: c.border }
}

function focusChipLabelStyle(m: FocusModel): Record<string, string> {
  const c = getLLMColor(m, uiStore.isDark)
  if (!c) return {}
  return { color: c.text }
}

function focusChipTooltip(m: FocusModel): string {
  if (!authStore.isAuthenticated) {
    return t('canvas.topBar.focusChipSignIn')
  }
  const v = focusVState(m)
  const label = FOCUS_MODEL_LABELS[m]
  if (v.loading) return t('canvas.topBar.focusChipValidating', { label })
  if (v.error) return `${label} · ${v.error}`
  if (v.valid === true) {
    return `${label} · ${v.reason || t('canvas.topBar.focusChipPass')}`
  }
  if (v.valid === false) {
    return `${label} · ${v.reason || t('canvas.topBar.focusChipWeak')}`
  }
  return t('canvas.topBar.focusChipHint', { label })
}

const { featureCommunity } = useFeatureFlags()

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

// Diagram presentation mode (shared code) — not Workshop Chat
const showOnlineCollabModal = ref(false)
const collabMode = ref<'organization' | 'network'>('organization')
const currentDiagramId = computed(() => {
  // Priority 1: Use activeDiagramId from store (set when diagram is saved)
  if (savedDiagramsStore.activeDiagramId) {
    return savedDiagramsStore.activeDiagramId
  }
  // Priority 2: Route query (diagramId or legacy diagram_id)
  const raw = route.query.diagramId ?? route.query.diagram_id
  if (raw && typeof raw === 'string') {
    return raw
  }
  return null
})
const workshopCode = ref<string | null>(null)

// Presentation-mode composable for participant tracking
const { participantsWithNames, disconnect, watchCode } = useWorkshop(workshopCode, currentDiagramId)

// User colors and emojis (must match backend)
const USER_COLORS = [
  '#FF6B6B', // Red
  '#4ECDC4', // Teal
  '#45B7D1', // Blue
  '#FFA07A', // Light Salmon
  '#98D8C8', // Mint
  '#F7DC6F', // Yellow
  '#BB8FCE', // Purple
  '#85C1E2', // Sky Blue
]

const USER_EMOJIS = ['✏️', '🖊️', '✒️', '🖋️', '📝', '✍️', '🖍️', '🖌️']

// Get user emoji and color
function getUserEmoji(userId: number): string {
  return USER_EMOJIS[userId % USER_EMOJIS.length]
}

function getUserColor(userId: number): string {
  return USER_COLORS[userId % USER_COLORS.length]
}

// Computed: visible participants (first 10) and dropdown (rest)
const visibleParticipants = computed(() => {
  return participantsWithNames.value.slice(0, 10)
})

const dropdownParticipants = computed(() => {
  return participantsWithNames.value.slice(10)
})

// Watch for presentation code changes
watch(
  () => workshopCode.value,
  (code) => {
    if (code) {
      watchCode()
    } else {
      disconnect()
    }
  },
  { immediate: false }
)

// Cleanup watcher on unmount
onUnmounted(() => {
  disconnect()
  eventBus.removeAllListenersForOwner('CanvasTopBar')
})

onMounted(() => {
  eventBus.onWithOwner(
    'workshop:code-changed',
    (data) => {
      if (data.code !== undefined) {
        workshopCode.value = data.code as string | null
      }
    },
    'CanvasTopBar'
  )
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
  // Use browser history to go back to where user came from
  // (could be /mindgraph or /mindmate depending on navigation path)
  // Fallback to /mindgraph if no history (e.g., direct URL access)
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/mindgraph')
  }
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

function handleCollabCommand(cmd: string) {
  if (cmd === 'organization' || cmd === 'network') {
    collabMode.value = cmd
    showOnlineCollabModal.value = true
  }
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
  showOnlineCollabModal.value = false
  useLLMResultsStore().reset()
  panelsStore.reset()
  diagramStore.clearHistory()
  diagramStore.loadDefaultTemplate(diagramType)
  diagramStore.initTitle(generateDefaultName())
  eventBus.emit('view:fit_to_canvas_requested', { animate: true })
  notify.success(t('notification.resetDefaultTemplate'))
}
</script>

<template>
  <div
    class="canvas-top-bar absolute top-0 left-0 right-0 z-30 w-full h-12 px-3 flex items-center shadow-sm border-b border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md"
  >
    <!-- Left section: Back + filename + save status -->
    <div class="flex items-center gap-1 shrink-0 min-w-0 z-10">
      <!-- Back button -->
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
          <ArrowLeft class="w-[18px] h-[18px]" />
        </ElButton>
      </ElTooltip>

      <div class="h-5 border-r border-gray-200 dark:border-gray-600 mx-1" />

      <!-- File name (editable) + auto-save status -->
      <div class="flex items-center gap-2 ml-2 min-w-0">
        <ElInput
          v-if="isFileNameEditing"
          ref="fileNameInputRef"
          v-model="fileName"
          size="small"
          class="file-name-input"
          @blur="handleFileNameBlur"
          @keypress="handleFileNameKeyPress"
        />
        <ElTooltip
          v-else
          :content="fileName"
          placement="bottom"
        >
          <span
            class="file-name-label text-xs font-medium text-gray-700 dark:text-gray-200 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 truncate"
            @click="handleFileNameClick"
          >
            {{ fileName.length > 15 ? fileName.slice(0, 15) + '…' : fileName }}
          </span>
        </ElTooltip>

        <span
          v-if="props.autoSavedStatus"
          class="auto-saved-status text-xs shrink-0 cursor-pointer transition-colors whitespace-nowrap"
          :class="[
            props.isSaving
              ? 'text-blue-500 dark:text-blue-400'
              : props.isDirty
                ? 'text-amber-500 dark:text-amber-400'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
          ]"
          :title="
            props.slotFullAndNewDiagram
              ? t('canvas.topBar.autoSaveTitleSlotFull')
              : t('canvas.topBar.autoSaveTitleSave')
          "
          @click="handleAutoSaveStatusClick"
        >
          {{ props.autoSavedStatus }}
        </span>
      </div>
    </div>

    <!-- Spacer pushes snapshot badges toward the right -->
    <div class="flex-1 min-w-0" />

    <!-- Snapshot version badges: adaptive, pushed right -->
    <div
      v-if="props.snapshots?.length"
      class="flex items-center gap-1.5 shrink-0 z-10 mr-3"
    >
      <ElTooltip
        v-for="snap in props.snapshots"
        :key="snap.version_number"
        :content="t('canvas.topBar.snapshotBadgeTooltip', { n: snap.version_number })"
        placement="bottom"
      >
        <span
          class="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0 cursor-pointer transition-colors select-none"
          :class="
            snap.version_number === props.activeSnapshotVersion
              ? 'bg-blue-500 text-white ring-2 ring-blue-300 ring-offset-1'
              : 'bg-blue-100 text-blue-600 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-800/50'
          "
          @click="
            (e: MouseEvent) =>
              e.ctrlKey || e.metaKey
                ? emit('snapshotDelete', snap.version_number)
                : emit('snapshotRecall', snap.version_number)
          "
        >
          {{ snap.version_number }}
        </span>
      </ElTooltip>
    </div>

    <!-- Center: focus question + 3-LLM validation (concept map) -->
    <div
      v-if="props.focusQuestion"
      class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 max-w-[min(92vw,980px)] px-2 z-[5] flex flex-row items-center gap-2 pointer-events-auto"
    >
      <p
        class="text-xs text-gray-600 dark:text-gray-300 min-w-0 flex-1 truncate text-left"
        :title="focusQuestionCenterTitle"
      >
        <span class="text-gray-400 dark:text-gray-500">{{
          t('canvas.topBar.focusQuestionLabel')
        }}</span>
        <span class="ml-1">{{ props.focusQuestion }}</span>
      </p>
      <div
        v-if="showFocusValidationChips"
        class="flex shrink-0 items-center flex-nowrap gap-1.5 max-w-[min(44vw,380px)]"
      >
        <div
          v-for="m in FOCUS_MODELS"
          :key="m"
          class="flex items-center gap-1 rounded-lg border border-solid px-2 py-1"
          :class="{ 'opacity-60': !authStore.isAuthenticated }"
          :style="focusChipSurface(m)"
        >
          <ElTooltip
            :content="focusChipTooltip(m)"
            placement="bottom"
          >
            <span class="inline-flex items-center gap-1">
              <span
                class="text-[10px] font-semibold"
                :style="focusChipLabelStyle(m)"
                >{{ FOCUS_MODEL_LABELS[m] }}</span
              >
              <Loader2
                v-if="focusVState(m).loading"
                class="w-3.5 h-3.5 animate-spin text-blue-500 shrink-0"
              />
              <template v-else-if="focusVState(m).error">
                <CircleSlash class="w-3.5 h-3.5 text-amber-600 shrink-0" />
              </template>
              <template v-else-if="focusVState(m).valid === true">
                <Check class="w-3.5 h-3.5 text-emerald-600 shrink-0" />
              </template>
              <template v-else-if="focusVState(m).valid === false">
                <CircleSlash class="w-3.5 h-3.5 text-red-600 shrink-0" />
              </template>
            </span>
          </ElTooltip>
        </div>
      </div>
    </div>

    <!-- Right section: Online collaboration + participants + teaching design + export -->
    <div class="flex items-center gap-4 shrink-0 z-10">
      <ElTooltip
        :content="t('canvas.topBar.collabTooltip')"
        placement="bottom"
      >
        <ElDropdown
          trigger="click"
          :disabled="!currentDiagramId"
          @command="handleCollabCommand"
        >
          <ElButton
            class="workshop-button"
            size="small"
            :disabled="!currentDiagramId"
          >
            <Users class="w-4 h-4 mr-1" />
            {{ t('canvas.topBar.collab') }}
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="organization">
                {{ t('canvas.topBar.schoolCollab') }}
              </ElDropdownItem>
              <ElDropdownItem command="network">
                {{ t('canvas.topBar.sharedCollab') }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </ElTooltip>

      <!-- Participant bar (only when collaboration session has a join code) -->
      <div
        v-if="workshopCode && participantsWithNames && participantsWithNames.length > 0"
        class="flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700"
      >
        <!-- Visible participants (first 10) -->
        <template
          v-for="participant in visibleParticipants"
          :key="participant.user_id"
        >
          <ElTooltip
            :content="participant.username"
            placement="bottom"
          >
            <div class="flex items-center gap-1 max-w-[140px]">
              <div
                class="participant-emoji shrink-0"
                :style="{ backgroundColor: getUserColor(participant.user_id) }"
              >
                {{ getUserEmoji(participant.user_id) }}
              </div>
              <span
                class="text-xs font-medium text-gray-700 dark:text-gray-200 truncate"
                :title="participant.username"
              >
                {{ participant.username }}
              </span>
            </div>
          </ElTooltip>
        </template>

        <!-- Dropdown for additional participants -->
        <ElDropdown
          v-if="dropdownParticipants.length > 0"
          trigger="hover"
          placement="bottom-end"
        >
          <div class="participant-more">+{{ dropdownParticipants.length }}</div>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem
                v-for="participant in dropdownParticipants"
                :key="participant.user_id"
                disabled
              >
                <div class="flex items-center gap-2">
                  <div
                    class="participant-emoji-small"
                    :style="{ backgroundColor: getUserColor(participant.user_id) }"
                  >
                    {{ getUserEmoji(participant.user_id) }}
                  </div>
                  <span>{{ participant.username }}</span>
                </div>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>

      <!-- Action buttons: 教学设计, Reset, Export (even spacing) -->
      <div class="flex items-center gap-2">
        <ElTooltip
          :content="t('canvas.topBar.teachingDesign')"
          placement="bottom"
        >
          <ElButton
            class="mindmate-button"
            size="small"
            :icon="ChatDotRound"
            @click="handleOpenMindmate"
          >
            {{ t('canvas.topBar.teachingDesign') }}
          </ElButton>
        </ElTooltip>

        <ElTooltip
          :content="t('canvas.topBar.resetTemplate')"
          placement="bottom"
        >
          <ElButton
            class="reset-button"
            size="small"
            :icon="RotateCcw"
            @click="handleReset"
          >
            {{ t('canvas.topBar.reset') }}
          </ElButton>
        </ElTooltip>

        <ElDropdown
          trigger="click"
          @command="handleExportCommand"
        >
          <ElButton
            class="export-button"
            size="small"
            :icon="Download"
          >
            {{ t('canvas.topBar.export') }}
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
                command="json"
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
      </div>
    </div>

    <!-- Diagram slot full modal -->
    <DiagramSlotFullModal
      v-model:visible="showSlotFullModal"
      :pending-title="fileName"
      :pending-diagram-type="diagramStore.type || ''"
      :pending-spec="getDiagramSpec() || {}"
      :pending-language="promptLanguage"
      @success="handleSlotModalSuccess"
      @cancel="handleSlotModalCancel"
    />

    <OnlineCollabModal
      v-model:visible="showOnlineCollabModal"
      :diagram-id="currentDiagramId"
      :mode="collabMode"
      @collab-code-changed="
        (code) => {
          workshopCode = code
          eventBus.emit('workshop:code-changed', { code })
        }
      "
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

.menu-button {
  font-weight: 500;
  color: var(--el-text-color-regular);
  padding: 4px 10px;
}

.menu-button:hover {
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
}

.file-name-input {
  width: 180px;
}

.file-name-label {
  max-width: 15ch;
  display: inline-block;
}

.file-name-input :deep(.el-input__inner) {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-color-primary);
}

/* Keyboard shortcut styling */
.shortcut {
  margin-left: auto;
  padding-left: 24px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: ui-monospace, monospace;
}

/* Make dropdown items flex for shortcut alignment */
:deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  min-width: 180px;
}

/* Presentation / export buttons - Swiss Design style (matching MindMate) */
.workshop-button {
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

/* 教学设计 button - Swiss Design style (matches MindMate) */
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
