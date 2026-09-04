<script setup lang="ts">
/**
 * V3 chrome — collapsed pill bar, or expanded Word ribbon.
 */
import { computed, nextTick, ref } from 'vue'

import { ChevronDown } from '@lucide/vue'

import CanvasVirtualKeyboardPanel from '@/components/canvas/CanvasVirtualKeyboardPanel.vue'
import { getDefaultDiagramName } from '@/composables'
import { canvasVirtualKeyboardOpen } from '@/composables/canvasToolbar/useCanvasVirtualKeyboardOpen'
import { useLanguage } from '@/composables/core/useLanguage'
import type { SnapshotMetadata } from '@/composables/editor/useSnapshotHistory'
import { useDiagramStore } from '@/stores'

import V3CollapsedPills from './V3CollapsedPills.vue'
import V3Ribbon from './V3Ribbon.vue'
import { useV3RibbonActions } from './useV3RibbonActions'
import { useV3RibbonState } from './useV3RibbonState'
import './v3Chrome.css'
import './v3Ribbon.css'

const props = withDefaults(
  defineProps<{
    autoSavedStatus?: string | null
    isDirty?: boolean
    isSaving?: boolean
    snapshots?: SnapshotMetadata[]
    activeSnapshotVersion?: number | null
    recallingSnapshotVersion?: number | null
    workshopCode?: string | null
    isCollabGuest?: boolean
    isViewer?: boolean
  }>(),
  {
    autoSavedStatus: null,
    isDirty: false,
    isSaving: false,
    snapshots: () => [],
    activeSnapshotVersion: null,
    recallingSnapshotVersion: null,
    workshopCode: null,
    isCollabGuest: false,
    isViewer: false,
  }
)

const { t, currentLanguage } = useLanguage()
const diagramStore = useDiagramStore()
const actions = useV3RibbonActions()
const { classic, activeTab, setActiveTab, toggleClassic } = useV3RibbonState()
const editingTitle = ref(false)
const titleInput = ref<HTMLInputElement | null>(null)

const fileName = computed({
  get: () =>
    diagramStore.effectiveTitle || getDefaultDiagramName(diagramStore.type, currentLanguage.value),
  set: (value: string) => diagramStore.setTitle(value, true),
})

function startRename(): void {
  if (props.isViewer) return
  editingTitle.value = true
  nextTick(() => titleInput.value?.select())
}

function finishRename(): void {
  editingTitle.value = false
  if (!diagramStore.title?.trim()) {
    diagramStore.initTitle(getDefaultDiagramName(diagramStore.type, currentLanguage.value))
  }
}
</script>

<template>
  <div data-testid="mindmap-v3-top-toolbar">
    <div
      v-if="!classic"
      class="v3-toolbar"
    >
      <V3CollapsedPills :disabled="isViewer" />
      <button
        type="button"
        class="v3-ribbon__chevron-btn"
        data-testid="mindmap-v3-ribbon-chevron"
        :aria-expanded="false"
        :aria-label="t('canvas.v3.ribbon.expand')"
        @click="toggleClassic"
      >
        <ChevronDown
          :size="16"
          :stroke-width="2.25"
        />
      </button>
    </div>
    <div
      v-else
      class="v3-chrome"
    >
      <div class="v3-qat">
        <button
          type="button"
          class="v3-tool-btn v3-tool-btn--back"
          @click="actions.goBack"
        >
          {{ t('canvas.v3.backToGallery') }}
        </button>
        <div class="v3-qat__title">
          <input
            v-if="editingTitle"
            ref="titleInput"
            v-model="fileName"
            class="v3-qat__title-input"
            @blur="finishRename"
            @keydown.enter="finishRename"
          />
          <button
            v-else
            type="button"
            class="v3-qat__title-btn"
            :title="fileName"
            @click="startRename"
          >
            {{ fileName }}
          </button>
        </div>
        <button
          type="button"
          class="v3-ribbon-cmd"
          :disabled="isViewer"
          :title="`${t('common.save')} (${t('canvas.toolbar.saveShortcut')})`"
          @click="actions.requestSave"
        >
          {{ t('common.save') }}
        </button>
        <button
          type="button"
          class="v3-ribbon-cmd"
          :disabled="!actions.canUndo || isViewer"
          :title="`${t('canvas.toolbar.undo')} (${t('canvas.toolbar.undoShortcut')})`"
          @click="actions.undo"
        >
          {{ t('canvas.toolbar.undo') }}
        </button>
        <button
          type="button"
          class="v3-ribbon-cmd"
          :disabled="!actions.canRedo || isViewer"
          :title="`${t('canvas.toolbar.redo')} (${t('canvas.toolbar.redoShortcut')})`"
          @click="actions.redo"
        >
          {{ t('canvas.toolbar.redo') }}
        </button>
        <span
          v-if="autoSavedStatus && !isViewer"
          class="v3-qat__autosave"
          :title="autoSavedStatus"
          >{{ autoSavedStatus }}</span
        >
        <div class="v3-qat__end">
          <button
            type="button"
            class="v3-mindmate-btn"
            :class="{ 'is-active': actions.isMindmateOpen }"
            :disabled="isViewer"
            @click="actions.toggleMindmate"
          >
            {{ t('canvas.v3.mindMate') }}
          </button>
        </div>
      </div>
      <V3Ribbon
        :active-tab="activeTab"
        :disabled="isViewer"
        :snapshots="snapshots"
        :active-snapshot-version="activeSnapshotVersion"
        :recalling-snapshot-version="recallingSnapshotVersion"
        :is-collab-guest="isCollabGuest"
        :workshop-code="workshopCode"
        @update:active-tab="setActiveTab"
        @toggle-classic="toggleClassic"
      />
    </div>
    <CanvasVirtualKeyboardPanel v-model="canvasVirtualKeyboardOpen" />
  </div>
</template>
