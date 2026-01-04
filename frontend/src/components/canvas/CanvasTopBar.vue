<script setup lang="ts">
/**
 * CanvasTopBar - Top navigation bar for canvas page
 * Migrated from prototype MindGraphCanvasPage top bar
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElMessage } from 'element-plus'

import {
  ChevronDown,
  ChevronLeft,
  Download,
  FileText,
  Image as ImageIcon,
  Plus,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

// Get chart type from route query
const chartType = computed(() => (route.query.type as string) || '复流程图')

// File name state
const fileName = ref('')
const isFileNameEditing = ref(false)
const fileNameInputRef = ref<HTMLInputElement | null>(null)
const isFileMenuOpen = ref(false)

onMounted(() => {
  fileName.value = `未命名${chartType.value}`
})

function handleBack() {
  router.push('/')
}

function handleFileNameClick() {
  isFileNameEditing.value = true
  setTimeout(() => {
    fileNameInputRef.value?.select()
  }, 0)
}

function handleFileNameBlur() {
  isFileNameEditing.value = false
  if (!fileName.value.trim()) {
    fileName.value = `未命名${chartType.value}`
  }
}

function handleFileNameKeyPress(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    handleFileNameBlur()
  }
}

function handleNewCanvas() {
  ElMessage.info('新建画布功能开发中')
  isFileMenuOpen.value = false
}

function handleSaveAs() {
  ElMessage.info('另存为功能开发中')
  isFileMenuOpen.value = false
}

function handleSaveToGallery() {
  ElMessage.info('保存到我的图库功能开发中')
  isFileMenuOpen.value = false
}

function handleImportFromFile() {
  ElMessage.info('从文件中导入功能开发中')
  isFileMenuOpen.value = false
}

function handleExportImage() {
  ElMessage.success('图片导出成功')
}
</script>

<template>
  <div class="canvas-top-bar w-full bg-white p-2 flex items-center justify-between shadow-sm">
    <div class="flex items-center space-x-3">
      <!-- Back button -->
      <button
        class="p-1.5 rounded-md hover:bg-gray-100 transition-colors"
        title="返回"
        @click="handleBack"
      >
        <ChevronLeft class="w-5 h-5 text-gray-600" />
      </button>

      <!-- File menu dropdown -->
      <div class="relative">
        <button
          class="flex items-center space-x-1 px-2 py-1.5 rounded-md hover:bg-gray-100 transition-colors"
          title="文件操作"
          @click="isFileMenuOpen = !isFileMenuOpen"
        >
          <span class="text-sm font-medium text-gray-800">文件</span>
          <ChevronDown class="w-4 h-4 text-gray-600" />
        </button>

        <!-- Dropdown content -->
        <div
          v-if="isFileMenuOpen"
          class="absolute left-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-10"
        >
          <button
            class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center"
            @click="handleNewCanvas"
          >
            <Plus class="w-3.5 h-3.5 mr-2 text-gray-500" />
            新建画布
          </button>
          <button
            class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center"
            @click="handleSaveAs"
          >
            <FileText class="w-3.5 h-3.5 mr-2 text-gray-500" />
            另存为
          </button>
          <button
            class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center"
            @click="handleSaveToGallery"
          >
            <ImageIcon class="w-3.5 h-3.5 mr-2 text-gray-500" />
            保存到我的图库
          </button>
          <div class="border-t border-gray-200 my-1" />
          <button
            class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center"
            @click="handleImportFromFile"
          >
            <Download class="w-3.5 h-3.5 mr-2 text-gray-500" />
            从文件中导入
          </button>
        </div>
      </div>

      <!-- File name -->
      <div class="flex items-center space-x-2">
        <input
          v-if="isFileNameEditing"
          ref="fileNameInputRef"
          v-model="fileName"
          type="text"
          class="text-sm font-medium text-blue-600 bg-transparent border-none outline-none w-40"
          autofocus
          @blur="handleFileNameBlur"
          @keypress="handleFileNameKeyPress"
        />
        <span
          v-else
          class="text-sm font-medium text-gray-800 cursor-pointer hover:text-blue-600 transition-colors"
          title="点击编辑文件名"
          @click="handleFileNameClick"
        >
          {{ fileName }}
        </span>

        <!-- Export button -->
        <button
          class="p-1.5 rounded-md hover:bg-gray-100 transition-colors"
          title="导出图片"
          @click="handleExportImage"
        >
          <Download class="w-4.5 h-4.5 text-gray-600" />
        </button>
      </div>
    </div>
  </div>
</template>
