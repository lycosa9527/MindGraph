<script setup lang="ts">
/**
 * Editor Toolbar - File operations, node management, view controls
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { useDiagramStore, usePanelsStore, useUIStore } from '@/stores'

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'toggleMindmate'): void
  (e: 'togglePalette'): void
  (e: 'toggleProperties'): void
}>()

const diagramStore = useDiagramStore()
const panelsStore = usePanelsStore()
const uiStore = useUIStore()
const { t, isZh } = useLanguage()

// Computed
const canUndo = computed(() => diagramStore.canUndo)
const canRedo = computed(() => diagramStore.canRedo)
const hasSelection = computed(() => diagramStore.hasSelection)

// Handlers
function handleExport() {
  // TODO: Implement export to PNG
  console.log('Export diagram')
}

function handleSave() {
  // TODO: Implement save to .mg file
  console.log('Save diagram')
}

function handleImport() {
  // TODO: Implement import from .mg file
  console.log('Import diagram')
}

function handleUndo() {
  diagramStore.undo()
}

function handleRedo() {
  diagramStore.redo()
}

function handleZoomIn() {
  // TODO: Implement zoom in
  console.log('Zoom in')
}

function handleZoomOut() {
  // TODO: Implement zoom out
  console.log('Zoom out')
}

function handleFitToScreen() {
  // TODO: Implement fit to screen
  console.log('Fit to screen')
}

function handleResetView() {
  // TODO: Implement reset view
  console.log('Reset view')
}
</script>

<template>
  <div
    class="editor-toolbar h-12 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 flex items-center justify-between"
  >
    <!-- Left Section: Navigation & File Operations -->
    <div class="toolbar-left flex items-center gap-3">
      <!-- Back Button -->
      <el-button
        size="small"
        @click="emit('back')"
      >
        <el-icon class="mr-1"><ArrowLeft /></el-icon>
        {{ isZh ? '返回' : 'Back' }}
      </el-button>

      <el-divider direction="vertical" />

      <!-- File Operations -->
      <div class="flex items-center gap-1">
        <el-tooltip
          :content="isZh ? '导出PNG' : 'Export PNG'"
          placement="bottom"
        >
          <el-button
            size="small"
            @click="handleExport"
          >
            <el-icon><Download /></el-icon>
          </el-button>
        </el-tooltip>

        <el-tooltip
          :content="isZh ? '保存' : 'Save'"
          placement="bottom"
        >
          <el-button
            size="small"
            @click="handleSave"
          >
            <el-icon><Folder /></el-icon>
          </el-button>
        </el-tooltip>

        <el-tooltip
          :content="isZh ? '导入' : 'Import'"
          placement="bottom"
        >
          <el-button
            size="small"
            @click="handleImport"
          >
            <el-icon><Upload /></el-icon>
          </el-button>
        </el-tooltip>
      </div>

      <el-divider direction="vertical" />

      <!-- Undo/Redo -->
      <div class="flex items-center gap-1">
        <el-tooltip
          :content="t('editor.undo') + ' (Ctrl+Z)'"
          placement="bottom"
        >
          <el-button
            size="small"
            :disabled="!canUndo"
            @click="handleUndo"
          >
            <el-icon><RefreshLeft /></el-icon>
          </el-button>
        </el-tooltip>

        <el-tooltip
          :content="t('editor.redo') + ' (Ctrl+Y)'"
          placement="bottom"
        >
          <el-button
            size="small"
            :disabled="!canRedo"
            @click="handleRedo"
          >
            <el-icon><RefreshRight /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- Center Section: View Controls -->
    <div class="toolbar-center flex items-center gap-1">
      <el-tooltip
        :content="t('editor.zoomIn')"
        placement="bottom"
      >
        <el-button
          size="small"
          @click="handleZoomIn"
        >
          <el-icon><ZoomIn /></el-icon>
        </el-button>
      </el-tooltip>

      <el-tooltip
        :content="t('editor.zoomOut')"
        placement="bottom"
      >
        <el-button
          size="small"
          @click="handleZoomOut"
        >
          <el-icon><ZoomOut /></el-icon>
        </el-button>
      </el-tooltip>

      <el-tooltip
        :content="t('editor.fitToScreen')"
        placement="bottom"
      >
        <el-button
          size="small"
          @click="handleFitToScreen"
        >
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </el-tooltip>

      <el-tooltip
        :content="isZh ? '重置视图' : 'Reset View'"
        placement="bottom"
      >
        <el-button
          size="small"
          @click="handleResetView"
        >
          <el-icon><Refresh /></el-icon>
        </el-button>
      </el-tooltip>
    </div>

    <!-- Right Section: Panel Toggles -->
    <div class="toolbar-right flex items-center gap-2">
      <!-- Node Palette Toggle -->
      <el-tooltip
        :content="t('panel.nodePalette')"
        placement="bottom"
      >
        <el-button
          size="small"
          :type="panelsStore.nodePalettePanel.isOpen ? 'primary' : 'default'"
          @click="emit('togglePalette')"
        >
          <el-icon><Grid /></el-icon>
        </el-button>
      </el-tooltip>

      <!-- Property Panel Toggle -->
      <el-tooltip
        :content="t('panel.properties')"
        placement="bottom"
      >
        <el-button
          size="small"
          :type="panelsStore.propertyPanel.isOpen ? 'primary' : 'default'"
          :disabled="!hasSelection"
          @click="emit('toggleProperties')"
        >
          <el-icon><Setting /></el-icon>
        </el-button>
      </el-tooltip>

      <!-- MindMate AI Toggle -->
      <el-tooltip
        :content="t('panel.mindmate')"
        placement="bottom"
      >
        <el-button
          size="small"
          :type="panelsStore.mindmatePanel.isOpen ? 'primary' : 'default'"
          @click="emit('toggleMindmate')"
        >
          <el-icon><ChatDotRound /></el-icon>
        </el-button>
      </el-tooltip>

      <el-divider direction="vertical" />

      <!-- Theme Toggle -->
      <el-button
        size="small"
        circle
        @click="uiStore.toggleTheme"
      >
        <el-icon>
          <Sunny v-if="uiStore.isDark" />
          <Moon v-else />
        </el-icon>
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.editor-toolbar {
  flex-shrink: 0;
}
</style>
