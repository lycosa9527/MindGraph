<script setup lang="ts">
/**
 * Editor Page - Main diagram editor interface
 * Integrates DiagramGallery, EditorToolbar, EditorCanvas, and panels
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

// Components
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import DiagramGallery from '@/components/editor/DiagramGallery.vue'
import EditorStatusBar from '@/components/editor/EditorStatusBar.vue'
import EditorToolbar from '@/components/editor/EditorToolbar.vue'
import MindmatePanel from '@/components/panels/MindmatePanel.vue'
import NodePalettePanel from '@/components/panels/NodePalettePanel.vue'
import PropertyPanel from '@/components/panels/PropertyPanel.vue'
import {
  getDiagramOperations,
  getPanelCoordinator,
  useKeyboard,
  useLanguage,
  useNotifications,
} from '@/composables'
import { useAuthStore, useDiagramStore, usePanelsStore } from '@/stores'
import type { DiagramType } from '@/types'

// Initialize global singletons to ensure voice agent events are handled
const _diagramOperations = getDiagramOperations()
const _panelCoordinator = getPanelCoordinator()

const diagramStore = useDiagramStore()
const panelsStore = usePanelsStore()
const authStore = useAuthStore()
const { t } = useLanguage()
const notify = useNotifications()

// View state
const showGallery = ref(true)
const isGenerating = ref(false)
const promptText = ref('')

// Computed (prefixed with _ for future use)
const _hasActiveDiagram = computed(() => diagramStore.data !== null)
const _userName = computed(() => authStore.user?.username || '')

// Handle diagram type selection from gallery
function handleDiagramSelect(type: DiagramType) {
  diagramStore.setDiagramType(type)
  showGallery.value = false
}

// Handle prompt submission
async function handlePromptSubmit(prompt: string) {
  if (!prompt.trim()) return

  isGenerating.value = true
  promptText.value = prompt

  try {
    // TODO: Call API to generate diagram
    notify.success(t('common.success'))
    showGallery.value = false
  } catch {
    notify.error(t('common.error'))
  } finally {
    isGenerating.value = false
  }
}

// Return to gallery
function backToGallery() {
  showGallery.value = true
  diagramStore.reset()
}

// Keyboard shortcuts
useKeyboard([
  { key: 'z', ctrl: true, handler: () => diagramStore.undo() },
  { key: 'y', ctrl: true, handler: () => diagramStore.redo() },
  { key: 'z', ctrl: true, shift: true, handler: () => diagramStore.redo() },
  {
    key: 'Escape',
    handler: () => {
      if (panelsStore.isAnyPanelOpen) {
        panelsStore.closeAllPanels()
      } else {
        diagramStore.clearSelection()
      }
    },
  },
])

onMounted(() => {
  // Initialize editor
  console.log('Editor page mounted')
})

onUnmounted(() => {
  // Cleanup
  diagramStore.reset()
})
</script>

<template>
  <div class="editor-page h-full flex flex-col">
    <!-- Gallery View -->
    <template v-if="showGallery">
      <DiagramGallery
        :is-generating="isGenerating"
        @select="handleDiagramSelect"
        @submit-prompt="handlePromptSubmit"
      />
    </template>

    <!-- Editor View -->
    <template v-else>
      <!-- Toolbar -->
      <EditorToolbar
        @back="backToGallery"
        @toggle-mindmate="panelsStore.toggleMindmatePanel"
        @toggle-palette="panelsStore.toggleNodePalettePanel"
        @toggle-properties="panelsStore.togglePropertyPanel"
      />

      <!-- Main Editor Area -->
      <div class="editor-main flex-1 relative overflow-hidden">
        <!-- Canvas -->
        <DiagramCanvas class="w-full h-full" />

        <!-- Left Panel: Node Palette -->
        <transition name="slide-left">
          <NodePalettePanel
            v-if="panelsStore.nodePalettePanel.isOpen"
            class="absolute left-0 top-0 bottom-0 w-72"
            @close="panelsStore.closeNodePalettePanel"
          />
        </transition>

        <!-- Right Panel: Property Panel -->
        <transition name="slide-right">
          <PropertyPanel
            v-if="panelsStore.propertyPanel.isOpen && diagramStore.hasSelection"
            class="absolute right-0 top-0 bottom-0 w-80"
            @close="panelsStore.closePropertyPanel"
          />
        </transition>

        <!-- Right Panel: MindMate AI -->
        <transition name="slide-right">
          <MindmatePanel
            v-if="panelsStore.mindmatePanel.isOpen"
            class="absolute right-0 top-0 bottom-0 w-96"
            @close="panelsStore.closeMindmatePanel"
          />
        </transition>
      </div>

      <!-- Status Bar -->
      <EditorStatusBar />
    </template>
  </div>
</template>

<style scoped>
.editor-page {
  background: var(--mg-bg-secondary);
}

.editor-main {
  background: var(--mg-bg-tertiary);
}

/* Panel transitions */
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.3s ease;
}

.slide-left-enter-from,
.slide-left-leave-to {
  transform: translateX(-100%);
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}
</style>
