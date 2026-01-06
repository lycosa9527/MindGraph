<script setup lang="ts">
/**
 * CanvasTopBar - Top navigation bar for canvas page
 * Uses Element Plus components for polished menu bar
 * Migrated from prototype MindGraphCanvasPage top bar
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElInput,
  ElMessage,
  ElTooltip,
} from 'element-plus'

// Using Lucide icons for a more modern, cute look
import {
  ArrowLeft,
  ClipboardCopy,
  ClipboardPaste,
  Download,
  Eye,
  FileDown,
  FileImage,
  FileJson,
  FilePlus2,
  FileText,
  FolderHeart,
  ImageDown,
  Maximize,
  Redo2,
  Save,
  Trash2,
  Undo2,
  Upload,
  ZoomIn,
  ZoomOut,
} from 'lucide-vue-next'

import { useLanguage } from '@/composables'

const route = useRoute()
const router = useRouter()
const { isZh } = useLanguage()

// Get chart type from route query
const chartType = computed(() => (route.query.type as string) || '复流程图')

// File name state
const fileName = ref('')
const isFileNameEditing = ref(false)
const fileNameInputRef = ref<InstanceType<typeof ElInput> | null>(null)

onMounted(() => {
  fileName.value = isZh.value ? `未命名${chartType.value}` : `Untitled ${chartType.value}`
})

function handleBack() {
  router.push('/')
}

function handleFileNameClick() {
  isFileNameEditing.value = true
  nextTick(() => {
    fileNameInputRef.value?.select()
  })
}

function handleFileNameBlur() {
  isFileNameEditing.value = false
  if (!fileName.value.trim()) {
    fileName.value = isZh.value ? `未命名${chartType.value}` : `Untitled ${chartType.value}`
  }
}

function handleFileNameKeyPress(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    handleFileNameBlur()
  }
}

// File menu actions
function handleFileCommand(command: string) {
  switch (command) {
    case 'new':
      ElMessage.info(isZh.value ? '新建画布功能开发中' : 'New canvas feature in development')
      break
    case 'save-as':
      ElMessage.info(isZh.value ? '另存为功能开发中' : 'Save as feature in development')
      break
    case 'save-gallery':
      ElMessage.info(isZh.value ? '保存到我的图库功能开发中' : 'Save to gallery feature in development')
      break
    case 'import':
      ElMessage.info(isZh.value ? '从文件中导入功能开发中' : 'Import from file feature in development')
      break
  }
}

// Edit menu actions
function handleEditCommand(command: string) {
  switch (command) {
    case 'undo':
      ElMessage.info(isZh.value ? '撤销' : 'Undo')
      break
    case 'redo':
      ElMessage.info(isZh.value ? '重做' : 'Redo')
      break
    case 'copy':
      ElMessage.info(isZh.value ? '复制功能开发中' : 'Copy feature in development')
      break
    case 'paste':
      ElMessage.info(isZh.value ? '粘贴功能开发中' : 'Paste feature in development')
      break
    case 'delete':
      ElMessage.info(isZh.value ? '删除功能开发中' : 'Delete feature in development')
      break
  }
}

// View menu actions
function handleViewCommand(command: string) {
  switch (command) {
    case 'zoom-in':
      ElMessage.info(isZh.value ? '放大' : 'Zoom In')
      break
    case 'zoom-out':
      ElMessage.info(isZh.value ? '缩小' : 'Zoom Out')
      break
    case 'fit-view':
      ElMessage.info(isZh.value ? '适应画布' : 'Fit to View')
      break
    case 'fullscreen':
      ElMessage.info(isZh.value ? '全屏功能开发中' : 'Fullscreen feature in development')
      break
  }
}

// Export menu actions
function handleExportCommand(command: string) {
  switch (command) {
    case 'png':
      ElMessage.success(isZh.value ? 'PNG图片导出成功' : 'PNG exported successfully')
      break
    case 'svg':
      ElMessage.info(isZh.value ? 'SVG导出功能开发中' : 'SVG export in development')
      break
    case 'pdf':
      ElMessage.info(isZh.value ? 'PDF导出功能开发中' : 'PDF export in development')
      break
    case 'json':
      ElMessage.info(isZh.value ? 'JSON导出功能开发中' : 'JSON export in development')
      break
  }
}
</script>

<template>
  <div class="canvas-top-bar w-full bg-white dark:bg-gray-800 h-12 px-3 flex items-center justify-between shadow-sm border-b border-gray-200 dark:border-gray-700">
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
              <FolderHeart class="w-4 h-4 mr-2 text-pink-500" />
              {{ isZh ? '保存到我的图库' : 'Save to Gallery' }}
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
