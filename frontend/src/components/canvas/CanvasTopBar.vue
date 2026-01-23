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
import { computed, nextTick, onMounted, ref, watch } from 'vue'
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
  Check,
  ClipboardCopy,
  ClipboardPaste,
  Download,
  Eye,
  FileImage,
  FileJson,
  FilePlus2,
  FileText,
  FolderHeart,
  ImageDown,
  Loader2,
  Maximize,
  Redo2,
  Save,
  Trash2,
  Undo2,
  Upload,
  ZoomIn,
  ZoomOut,
} from 'lucide-vue-next'

import { DiagramSlotFullModal } from '@/components/canvas'
import { useNotifications } from '@/composables'
import { useLanguage } from '@/composables'
import { useDiagramStore, useSavedDiagramsStore } from '@/stores'

const notify = useNotifications()

const route = useRoute()
const router = useRouter()
const { isZh } = useLanguage()
const diagramStore = useDiagramStore()
const savedDiagramsStore = useSavedDiagramsStore()

// Get chart type from route query
const chartType = computed(() => (route.query.type as string) || '复流程图')

/**
 * Generate default diagram name (simple, no timestamp)
 * Format: "新圆圈图" / "New Circle Map"
 */
function generateDefaultName(): string {
  return isZh.value ? `新${chartType.value}` : `New ${chartType.value}`
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

// Get current diagram spec for saving
function getDiagramSpec(): Record<string, unknown> | null {
  if (!diagramStore.data) return null

  return {
    type: diagramStore.type,
    nodes: diagramStore.data.nodes,
    connections: diagramStore.data.connections,
    _customPositions: diagramStore.data._customPositions,
    _node_styles: diagramStore.data._node_styles,
  }
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

// File menu actions
function handleFileCommand(command: string) {
  switch (command) {
    case 'new':
      notify.info(isZh.value ? '新建画布功能开发中' : 'New canvas feature in development')
      break
    case 'save-as':
      notify.info(isZh.value ? '另存为功能开发中' : 'Save as feature in development')
      break
    case 'save-gallery':
      saveToGallery()
      break
    case 'import':
      notify.info(isZh.value ? '从文件中导入功能开发中' : 'Import from file feature in development')
      break
  }
}

// Edit menu actions
function handleEditCommand(command: string) {
  switch (command) {
    case 'undo':
      notify.info(isZh.value ? '撤销' : 'Undo')
      break
    case 'redo':
      notify.info(isZh.value ? '重做' : 'Redo')
      break
    case 'copy':
      notify.info(isZh.value ? '复制功能开发中' : 'Copy feature in development')
      break
    case 'paste':
      notify.info(isZh.value ? '粘贴功能开发中' : 'Paste feature in development')
      break
    case 'delete':
      notify.info(isZh.value ? '删除功能开发中' : 'Delete feature in development')
      break
  }
}

// View menu actions
function handleViewCommand(command: string) {
  switch (command) {
    case 'zoom-in':
      notify.info(isZh.value ? '放大' : 'Zoom In')
      break
    case 'zoom-out':
      notify.info(isZh.value ? '缩小' : 'Zoom Out')
      break
    case 'fit-view':
      notify.info(isZh.value ? '适应画布' : 'Fit to View')
      break
    case 'fullscreen':
      notify.info(isZh.value ? '全屏功能开发中' : 'Fullscreen feature in development')
      break
  }
}

// Export menu actions
function handleExportCommand(command: string) {
  switch (command) {
    case 'png':
      notify.success(isZh.value ? 'PNG图片导出成功' : 'PNG exported successfully')
      break
    case 'svg':
      notify.info(isZh.value ? 'SVG导出功能开发中' : 'SVG export in development')
      break
    case 'pdf':
      notify.info(isZh.value ? 'PDF导出功能开发中' : 'PDF export in development')
      break
    case 'json':
      notify.info(isZh.value ? 'JSON导出功能开发中' : 'JSON export in development')
      break
  }
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

      <!-- File menu -->
      <ElDropdown
        trigger="click"
        @command="handleFileCommand"
      >
        <ElButton
          text
          size="small"
          class="menu-button"
        >
          {{ isZh ? '文件' : 'File' }}
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="new">
              <FilePlus2 class="w-4 h-4 mr-2 text-blue-500" />
              {{ isZh ? '新建画布' : 'New Canvas' }}
            </ElDropdownItem>
            <ElDropdownItem command="save-as">
              <Save class="w-4 h-4 mr-2 text-green-500" />
              {{ isZh ? '另存为' : 'Save As' }}
            </ElDropdownItem>
            <ElDropdownItem command="save-gallery">
              <Loader2
                v-if="isSaving"
                class="w-4 h-4 mr-2 text-pink-500 animate-spin"
              />
              <Check
                v-else-if="isAlreadySaved"
                class="w-4 h-4 mr-2 text-green-500"
              />
              <FolderHeart
                v-else
                class="w-4 h-4 mr-2 text-pink-500"
              />
              {{
                isAlreadySaved
                  ? isZh
                    ? '已保存到图库'
                    : 'Saved to Gallery'
                  : isZh
                    ? '保存到我的图库'
                    : 'Save to Gallery'
              }}
            </ElDropdownItem>
            <ElDropdownItem
              divided
              command="import"
            >
              <Upload class="w-4 h-4 mr-2 text-purple-500" />
              {{ isZh ? '从文件中导入' : 'Import from File' }}
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>

      <!-- Edit menu -->
      <ElDropdown
        trigger="click"
        @command="handleEditCommand"
      >
        <ElButton
          text
          size="small"
          class="menu-button"
        >
          {{ isZh ? '编辑' : 'Edit' }}
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="undo">
              <Undo2 class="w-4 h-4 mr-2 text-orange-500" />
              {{ isZh ? '撤销' : 'Undo' }}
              <span class="shortcut">Ctrl+Z</span>
            </ElDropdownItem>
            <ElDropdownItem command="redo">
              <Redo2 class="w-4 h-4 mr-2 text-orange-500" />
              {{ isZh ? '重做' : 'Redo' }}
              <span class="shortcut">Ctrl+Y</span>
            </ElDropdownItem>
            <ElDropdownItem
              divided
              command="copy"
            >
              <ClipboardCopy class="w-4 h-4 mr-2 text-cyan-500" />
              {{ isZh ? '复制' : 'Copy' }}
              <span class="shortcut">Ctrl+C</span>
            </ElDropdownItem>
            <ElDropdownItem command="paste">
              <ClipboardPaste class="w-4 h-4 mr-2 text-cyan-500" />
              {{ isZh ? '粘贴' : 'Paste' }}
              <span class="shortcut">Ctrl+V</span>
            </ElDropdownItem>
            <ElDropdownItem
              divided
              command="delete"
            >
              <Trash2 class="w-4 h-4 mr-2 text-red-400" />
              {{ isZh ? '删除' : 'Delete' }}
              <span class="shortcut">Del</span>
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>

      <!-- View menu -->
      <ElDropdown
        trigger="click"
        @command="handleViewCommand"
      >
        <ElButton
          text
          size="small"
          class="menu-button"
        >
          {{ isZh ? '视图' : 'View' }}
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="zoom-in">
              <ZoomIn class="w-4 h-4 mr-2 text-indigo-500" />
              {{ isZh ? '放大' : 'Zoom In' }}
              <span class="shortcut">Ctrl++</span>
            </ElDropdownItem>
            <ElDropdownItem command="zoom-out">
              <ZoomOut class="w-4 h-4 mr-2 text-indigo-500" />
              {{ isZh ? '缩小' : 'Zoom Out' }}
              <span class="shortcut">Ctrl+-</span>
            </ElDropdownItem>
            <ElDropdownItem command="fit-view">
              <Eye class="w-4 h-4 mr-2 text-teal-500" />
              {{ isZh ? '适应画布' : 'Fit to View' }}
              <span class="shortcut">Ctrl+0</span>
            </ElDropdownItem>
            <ElDropdownItem
              divided
              command="fullscreen"
            >
              <Maximize class="w-4 h-4 mr-2 text-gray-500" />
              {{ isZh ? '全屏' : 'Fullscreen' }}
              <span class="shortcut">F11</span>
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>

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

    <!-- Right section: Export button -->
    <div class="flex items-center gap-2">
      <!-- Export dropdown -->
      <ElDropdown
        trigger="click"
        @command="handleExportCommand"
      >
        <ElButton
          size="small"
          type="primary"
          class="export-button"
        >
          <Download class="w-4 h-4 mr-1" />
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
  </div>
</template>

<style scoped>
.canvas-top-bar {
  z-index: 100;
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

/* Export button with gradient */
.export-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  font-weight: 500;
}

.export-button:hover {
  background: linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}
</style>
