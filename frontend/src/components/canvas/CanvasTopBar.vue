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

// Using Lucide icons for a more modern, cute look
import {
  ArrowLeft,
  FileImage,
  FileJson,
  FileText,
  ImageDown,
} from 'lucide-vue-next'

import {
  Download,
  Connection,
} from '@element-plus/icons-vue'

import { DiagramSlotFullModal } from '@/components/canvas'
import { WorkshopModal } from '@/components/workshop'
import { eventBus, getDefaultDiagramName, useNotifications, useWorkshop } from '@/composables'
import { useLanguage } from '@/composables'
import { useAuthStore, useDiagramStore, useSavedDiagramsStore } from '@/stores'

const notify = useNotifications()

const route = useRoute()
const router = useRouter()
const { isZh } = useLanguage()
const diagramStore = useDiagramStore()
const savedDiagramsStore = useSavedDiagramsStore()
const authStore = useAuthStore()

// Diagram type from store (when loaded) or route query (for new diagrams)
const diagramTypeForName = computed(
  () => (diagramStore.type as string) || (route.query.type as string) || null
)

/**
 * Generate default diagram name (simple, no timestamp)
 * Format: "新圆圈图" / "New Circle Map"
 */
function generateDefaultName(): string {
  return getDefaultDiagramName(diagramTypeForName.value, isZh.value)
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

// Save to gallery state
const isSaving = ref(false)
const showSlotFullModal = ref(false)

// Workshop state
const showWorkshopModal = ref(false)
const currentDiagramId = computed(() => {
  // Priority 1: Use activeDiagramId from store (set when diagram is saved)
  if (savedDiagramsStore.activeDiagramId) {
    return savedDiagramsStore.activeDiagramId
  }
  // Priority 2: Check route query parameter (for saved diagrams loaded from URL)
  const diagramIdFromRoute = route.query.diagramId
  if (diagramIdFromRoute && typeof diagramIdFromRoute === 'string') {
    return diagramIdFromRoute
  }
  return null
})
const workshopCode = ref<string | null>(null)

// Workshop composable for participant tracking
const { participantsWithNames, activeEditors, connect, disconnect, watchCode } = useWorkshop(
  workshopCode,
  currentDiagramId
)

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

// Watch for workshop code changes
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
})

// Computed for save button state
const isAlreadySaved = computed(() => savedDiagramsStore.isActiveDiagramSaved)

onMounted(() => {
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

/** Get diagram spec for saving (uses recalculated positions for bubble map) */
function getDiagramSpec(): Record<string, unknown> | null {
  return diagramStore.getSpecForSave()
}

// Save to gallery
async function saveToGallery(): Promise<void> {
  if (!diagramStore.type || !diagramStore.data) {
    notify.warning(isZh.value ? '没有可保存的图示' : 'No diagram to save')
    return
  }

  const spec = getDiagramSpec()
  if (!spec) {
    notify.warning(isZh.value ? '图示数据无效' : 'Invalid diagram data')
    return
  }

  isSaving.value = true

  try {
    const result = await savedDiagramsStore.manualSaveDiagram(
      fileName.value,
      diagramStore.type,
      spec,
      isZh.value ? 'zh' : 'en',
      null // TODO: Generate thumbnail
    )

    if (result.success) {
      notify.success(
        result.action === 'updated'
          ? isZh.value
            ? '图示已更新'
            : 'Diagram updated'
          : isZh.value
            ? '图示已保存到图库'
            : 'Diagram saved to gallery'
      )
    } else if (result.needsSlotClear) {
      // Show modal to let user delete a diagram
      showSlotFullModal.value = true
    } else {
      notify.error(result.error || (isZh.value ? '保存失败' : 'Save failed'))
    }
  } catch (error) {
    console.error('Save to gallery error:', error)
    notify.error(isZh.value ? '网络错误，保存失败' : 'Network error, save failed')
  } finally {
    isSaving.value = false
  }
}

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
</script>

<template>
  <div
    class="canvas-top-bar w-full bg-white dark:bg-gray-800 h-12 px-3 flex items-center justify-between shadow-sm border-b border-gray-200 dark:border-gray-700"
  >
    <!-- Left section: Back + Menu bar -->
    <div class="flex items-center gap-1">
      <!-- Back button -->
      <ElTooltip
        :content="isZh ? '返回' : 'Back'"
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

      <!-- File name (editable) -->
      <div class="flex items-center gap-2 ml-2">
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
          :content="isZh ? '点击编辑文件名' : 'Click to edit filename'"
          placement="bottom"
        >
          <span
            class="text-sm font-medium text-gray-700 dark:text-gray-200 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            @click="handleFileNameClick"
          >
            {{ fileName }}
          </span>
        </ElTooltip>
      </div>
    </div>

    <!-- Right section: Participants + Workshop + Export buttons -->
    <div class="flex items-center gap-2">
      <!-- Participant bar (only show when workshop is active) -->
      <div
        v-if="workshopCode && participantsWithNames && participantsWithNames.length > 0"
        class="flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700"
      >
        <!-- Visible participants (first 10) -->
        <template v-for="participant in visibleParticipants" :key="participant.user_id">
          <ElTooltip
            :content="participant.username"
            placement="bottom"
          >
            <div
              class="participant-emoji"
              :style="{ backgroundColor: getUserColor(participant.user_id) }"
            >
              {{ getUserEmoji(participant.user_id) }}
            </div>
          </ElTooltip>
        </template>

        <!-- Dropdown for additional participants -->
        <ElDropdown
          v-if="dropdownParticipants.length > 0"
          trigger="hover"
          placement="bottom-end"
        >
          <div class="participant-more">
            +{{ dropdownParticipants.length }}
          </div>
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

      <!-- Workshop button -->
      <ElTooltip
        :content="isZh ? '工作坊协作' : 'Workshop Collaboration'"
        placement="bottom"
      >
        <ElButton
          class="workshop-button"
          size="small"
          :icon="Connection"
          @click="showWorkshopModal = true"
        >
          {{ isZh ? '工作坊' : 'Workshop' }}
        </ElButton>
      </ElTooltip>

      <!-- Export dropdown -->
      <ElDropdown
        trigger="click"
        @command="handleExportCommand"
      >
        <ElButton
          class="export-button"
          size="small"
          :icon="Download"
        >
          {{ isZh ? '导出' : 'Export' }}
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="png">
              <ImageDown class="w-4 h-4 mr-2 text-emerald-500" />
              {{ isZh ? '导出为 PNG' : 'Export as PNG' }}
            </ElDropdownItem>
            <ElDropdownItem command="svg">
              <FileImage class="w-4 h-4 mr-2 text-violet-500" />
              {{ isZh ? '导出为 SVG' : 'Export as SVG' }}
            </ElDropdownItem>
            <ElDropdownItem command="pdf">
              <FileText class="w-4 h-4 mr-2 text-red-500" />
              {{ isZh ? '导出为 PDF' : 'Export as PDF' }}
            </ElDropdownItem>
            <ElDropdownItem
              divided
              command="json"
            >
              <FileJson class="w-4 h-4 mr-2 text-amber-500" />
              {{ isZh ? '导出为 JSON' : 'Export as JSON' }}
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>

    <!-- Diagram slot full modal -->
    <DiagramSlotFullModal
      v-model:visible="showSlotFullModal"
      :pending-title="fileName"
      :pending-diagram-type="diagramStore.type || ''"
      :pending-spec="getDiagramSpec() || {}"
      :pending-language="isZh ? 'zh' : 'en'"
      @success="handleSlotModalSuccess"
      @cancel="handleSlotModalCancel"
    />

    <!-- Workshop modal -->
    <WorkshopModal
      v-model:visible="showWorkshopModal"
      :diagram-id="currentDiagramId"
      @workshopCodeChanged="(code) => { 
        workshopCode = code
        // Emit event for CanvasPage to sync
        eventBus.emit('workshop:code-changed', { code })
      }"
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

.file-name-input :deep(.el-input__inner) {
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

/* Workshop and Export buttons - Swiss Design style (matching MindMate) */
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
</style>
