<script setup lang="ts">
/**
 * Draggable tabbed remote for the new canvas. Teachers on a 110" IFP can
 * keep common tools next to where they stand instead of reaching the ribbon.
 */
import { type Component, computed, ref } from 'vue'

import {
  BookMarked,
  Bot,
  Download,
  FileText,
  Folder,
  GitBranch,
  GraduationCap,
  Hand,
  LayoutGrid,
  Lightbulb,
  Maximize2,
  MessageSquare,
  Minus,
  MonitorPlay,
  Move,
  Paintbrush,
  Palette,
  Plus,
  RotateCcw,
  RotateCw,
  Save,
  School,
  Sparkles,
  Trash2,
  Upload,
  X,
} from '@lucide/vue'

import MindMapClassroomRemoteTopics from '@/canvas-ribbon/MindMapClassroomRemoteTopics.vue'
import MindMapRibbonAiMark from '@/canvas-ribbon/MindMapRibbonAiMark.vue'
import {
  CLASSROOM_REMOTE_TABS,
  CLASSROOM_REMOTE_TAB_LABEL_KEYS,
  type ClassroomRemoteTabId,
} from '@/canvas-ribbon/mindMapClassroomRemoteTypes'
import { useMindMapRibbonActions } from '@/canvas-ribbon/useMindMapRibbonActions'
import MindMapInsertNodeIcon from '@/components/canvas/MindMapInsertNodeIcon.vue'
import I18nText from '@/components/common/I18nText.vue'
import {
  useClassroomRemotePosition,
  useClassroomRemoteVisibility,
} from '@/composables/canvas/useClassroomRemotePosition'
import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar/useCanvasToolbarFormatting'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useCollabGuestAiGate } from '@/composables/collab/useCollabGuestAiGate'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSourceLock } from '@/composables/mindMap/useDiagramSourceLock'
import { docSummaryLiteIntent } from '@/composables/mindMap/useDocSummaryLiteSaveAndGenerate'
import { DOC_SUMMARY_LITE_UI } from '@/config/docSummaryLite'
import { useMindClassroomStore } from '@/stores'

import './mindMapClassroomRemote.css'

type RemoteInsertKind = 'child' | 'sibling'

type RemoteTool = {
  id: string
  labelKey: string
  testid?: string
  insertKind?: RemoteInsertKind
  icon?: Component
  active?: boolean
  dimmed?: boolean
  disabled?: boolean
  danger?: boolean
  run: () => void
}

const props = withDefaults(
  defineProps<{
    zoom?: number | null
    handToolActive?: boolean
  }>(),
  {
    zoom: null,
    handToolActive: false,
  }
)

const { t } = useLanguage()
const notify = useNotifications()
const ribbon = useMindMapRibbonActions()
const classroomStore = useMindClassroomStore()
const { aiBlockedByCollab, notifyCollabGuestAiBlocked } = useCollabGuestAiGate()
const { formatBrushActive, formatBrushLocked, handleFormatBrush } = useCanvasToolbarFormatting()
const { activeTool, handleToolSelect, openTool } = useMindMapSideToolbarState()
const sourceLock = useDiagramSourceLock()
const panelRef = ref<HTMLElement | null>(null)
const position = useClassroomRemotePosition(panelRef)
const { setHidden: setClassroomRemoteHidden } = useClassroomRemoteVisibility()

const zoomPercent = computed(() => (props.zoom != null ? Math.round(props.zoom * 100) : 100))

const TAB_ICONS: Record<Exclude<ClassroomRemoteTabId, 'ai'>, Component> = {
  view: Move,
  topics: BookMarked,
  edit: Palette,
  teaching: GraduationCap,
  file: Folder,
}

function requireSelection(run: () => void): void {
  if (ribbon.hasSelection) {
    run()
    return
  }
  notify.warning(t('canvas.toolbar.selectNodesFirst'))
}

function runGuestAi(run: () => void): void {
  if (aiBlockedByCollab.value) {
    notifyCollabGuestAiBlocked()
    return
  }
  run()
}

function onFormatPainter(): void {
  if (formatBrushActive.value) {
    handleFormatBrush()
    return
  }
  requireSelection(handleFormatBrush)
}

function openDocGenerate(): void {
  if (aiBlockedByCollab.value) {
    notifyCollabGuestAiBlocked()
    return
  }
  if (sourceLock.isLocked('doc')) {
    sourceLock.notifyLocked()
    return
  }
  docSummaryLiteIntent.value = 'doc'
  openTool('document_summary')
  eventBus.emit('mindmap:doc_summary_tab', { tab: DOC_SUMMARY_LITE_UI ? 'file' : 'document' })
}

const viewTools = computed<RemoteTool[]>(() => [
  {
    id: 'hand',
    labelKey: 'canvas.zoomControls.hand',
    testid: 'mindmap-classroom-remote-hand-tool',
    icon: Hand,
    active: props.handToolActive,
    run: () => ribbon.toggleHand(!props.handToolActive),
  },
  {
    id: 'zoom-out',
    labelKey: 'editor.zoomOut',
    testid: 'mindmap-classroom-remote-zoom-out',
    icon: Minus,
    run: () => ribbon.zoomOut(),
  },
  {
    id: 'zoom-in',
    labelKey: 'editor.zoomIn',
    testid: 'mindmap-classroom-remote-zoom-in',
    icon: Plus,
    run: () => ribbon.zoomIn(),
  },
  {
    id: 'fit',
    labelKey: 'canvas.zoomControls.fitCanvas',
    testid: 'mindmap-classroom-remote-fit-view',
    icon: Maximize2,
    run: () => ribbon.fitToScreen(),
  },
  {
    id: 'present',
    labelKey: 'canvas.zoomControls.presentationMode',
    testid: 'mindmap-classroom-remote-presentation',
    icon: MonitorPlay,
    run: () => ribbon.startPresentation(),
  },
])

const editTools = computed<RemoteTool[]>(() => [
  {
    id: 'undo',
    labelKey: 'canvas.toolbar.undo',
    icon: RotateCcw,
    disabled: !ribbon.canUndo,
    run: () => ribbon.undo(),
  },
  {
    id: 'redo',
    labelKey: 'canvas.toolbar.redo',
    icon: RotateCw,
    disabled: !ribbon.canRedo,
    run: () => ribbon.redo(),
  },
  {
    id: 'child',
    labelKey: 'canvas.toolbar.addChildNode',
    insertKind: 'child',
    dimmed: !ribbon.hasSelection,
    run: () => ribbon.handleAddChildClick(),
  },
  {
    id: 'sibling',
    labelKey: 'canvas.toolbar.addSiblingNode',
    insertKind: 'sibling',
    dimmed: !ribbon.hasSelection,
    run: () => requireSelection(() => ribbon.handleAddSibling()),
  },
  {
    id: 'delete',
    labelKey: 'canvas.toolbar.deleteNode',
    icon: Trash2,
    dimmed: !ribbon.hasSelection,
    danger: true,
    run: () => requireSelection(() => ribbon.handleDeleteNode()),
  },
  {
    id: 'painter',
    labelKey: 'canvas.classroomRemote.formatPainter',
    icon: Paintbrush,
    active: formatBrushActive.value,
    dimmed: !ribbon.hasSelection && !formatBrushActive.value,
    run: onFormatPainter,
  },
])

const aiTools = computed<RemoteTool[]>(() => [
  {
    id: 'topic',
    labelKey: 'canvas.ribbon.topicGenerate',
    icon: Sparkles,
    dimmed: aiBlockedByCollab.value,
    run: () => runGuestAi(() => ribbon.handleAIGenerate()),
  },
  {
    id: 'doc',
    labelKey: 'canvas.ribbon.docGenerate',
    icon: FileText,
    dimmed: aiBlockedByCollab.value || sourceLock.isLocked('doc'),
    active: activeTool.value === 'document_summary',
    run: openDocGenerate,
  },
  {
    id: 'waterfall',
    labelKey: 'canvas.mindMapSideToolbar.waterfall',
    icon: LayoutGrid,
    dimmed: aiBlockedByCollab.value,
    active: activeTool.value === 'waterfall',
    run: () => runGuestAi(() => handleToolSelect('waterfall')),
  },
  {
    id: 'one-sentence',
    labelKey: 'canvas.mindMapSideToolbar.oneSentence',
    icon: MessageSquare,
    dimmed: aiBlockedByCollab.value,
    active: activeTool.value === 'one_sentence',
    run: () => runGuestAi(() => ribbon.openSideTool('one_sentence')),
  },
  {
    id: 'subgraph',
    labelKey: 'canvas.floatingToolbar.aiSubgraph',
    icon: GitBranch,
    dimmed: aiBlockedByCollab.value || !ribbon.hasSelection,
    run: () => runGuestAi(() => requireSelection(() => ribbon.requestAiSubgraph())),
  },
])

const teachingTools = computed<RemoteTool[]>(() => [
  {
    id: 'learning-sheet',
    labelKey: 'canvas.mindMapSideToolbar.learningSheet',
    icon: GraduationCap,
    dimmed: aiBlockedByCollab.value,
    active:
      activeTool.value === 'learning_sheet' ||
      ribbon.learningSheet.isPickActive ||
      ribbon.learningSheet.isLearningSheetActive,
    run: () => ribbon.openSideTool('learning_sheet'),
  },
  {
    id: 'worksheet',
    labelKey: 'canvas.ribbon.makeLearningSheet',
    icon: FileText,
    run: () => ribbon.requestWorksheetText(true),
  },
  {
    id: 'explain',
    labelKey: 'canvas.floatingToolbar.explain',
    icon: Lightbulb,
    dimmed: aiBlockedByCollab.value || !ribbon.hasSelection,
    run: () => runGuestAi(() => requireSelection(() => ribbon.requestExplainNode())),
  },
  {
    id: 'classroom',
    labelKey: 'canvas.mindMapSideToolbar.mindClassroom',
    icon: School,
    run: () => classroomStore.openModal(),
  },
  {
    id: 'mindmate',
    labelKey: 'canvas.ribbon.mindMate',
    icon: Bot,
    active: ribbon.isMindmateOpen,
    run: () => ribbon.toggleMindmate(),
  },
])

const fileTools = computed<RemoteTool[]>(() => [
  {
    id: 'save',
    labelKey: 'common.save',
    icon: Save,
    run: () => ribbon.requestSave(),
  },
  {
    id: 'import',
    labelKey: 'canvas.toolbar.import',
    icon: Upload,
    run: () => ribbon.importMg(),
  },
  {
    id: 'export',
    labelKey: 'canvas.toolbar.export',
    icon: Download,
    run: () => ribbon.exportPng(),
  },
  {
    id: 'reset',
    labelKey: 'canvas.topBar.resetCanvas',
    icon: RotateCcw,
    run: () => {
      void ribbon.resetTemplate()
    },
  },
])

const activeTools = computed(() => {
  switch (position.activeTab.value) {
    case 'edit':
      return editTools.value
    case 'ai':
      return aiTools.value
    case 'teaching':
      return teachingTools.value
    case 'file':
      return fileTools.value
    default:
      return viewTools.value
  }
})

function tabIcon(tab: ClassroomRemoteTabId): Component | undefined {
  return tab === 'ai' ? undefined : TAB_ICONS[tab]
}

function runTool(tool: RemoteTool): void {
  if (tool.disabled) {
    return
  }
  tool.run()
}

function onSelectTab(tab: ClassroomRemoteTabId): void {
  position.setActiveTab(tab)
}

function onClose(): void {
  setClassroomRemoteHidden(true)
}
</script>

<template>
  <aside
    ref="panelRef"
    class="mm-remote"
    :class="{ 'is-dragging': position.dragging.value }"
    :style="{ left: `${position.left.value}px`, top: `${position.top.value}px` }"
    role="toolbar"
    :aria-label="t('canvas.classroomRemote.ariaLabel')"
    data-testid="mindmap-classroom-remote"
    @pointerdown.stop
  >
    <div
      class="mm-remote__handle"
      :title="t('canvas.classroomRemote.resetPosition')"
      data-testid="mindmap-classroom-remote-handle"
      @pointerdown="position.onHandlePointerDown"
      @pointermove="position.onHandlePointerMove"
      @pointerup="position.onHandlePointerUp"
      @pointercancel="position.onHandlePointerUp"
      @dblclick="position.resetToDefault"
    >
      <span
        class="mm-remote__grip"
        aria-hidden="true"
      >
        <span /><span /><span /><span />
      </span>
      <span class="mm-remote__title">
        <I18nText
          k="canvas.classroomRemote.ariaLabel"
          dense
        />
      </span>
      <button
        type="button"
        class="mm-remote__close"
        data-testid="mindmap-classroom-remote-close"
        :title="t('common.close')"
        :aria-label="t('common.close')"
        @pointerdown.stop
        @click.stop="onClose"
      >
        <X
          class="h-4 w-4"
          :stroke-width="2.2"
        />
      </button>
    </div>

    <div
      class="mm-remote__tabs"
      role="tablist"
    >
      <button
        v-for="tab in CLASSROOM_REMOTE_TABS"
        :key="tab"
        type="button"
        class="mm-remote__tab"
        role="tab"
        :class="{ 'is-active': position.activeTab.value === tab }"
        :aria-selected="position.activeTab.value === tab"
        :data-testid="`mindmap-classroom-remote-tab-${tab}`"
        :title="t(CLASSROOM_REMOTE_TAB_LABEL_KEYS[tab])"
        @click="onSelectTab(tab)"
      >
        <MindMapRibbonAiMark v-if="tab === 'ai'" />
        <component
          :is="tabIcon(tab)"
          v-else
          class="h-3.5 w-3.5"
          :stroke-width="2.2"
        />
        <span class="mm-remote__tab-label">
          <I18nText
            :k="CLASSROOM_REMOTE_TAB_LABEL_KEYS[tab]"
            dense
          />
        </span>
      </button>
    </div>

    <div class="mm-remote__body">
      <MindMapClassroomRemoteTopics v-if="position.activeTab.value === 'topics'" />
      <div
        v-if="position.activeTab.value === 'view'"
        class="mm-remote__zoom"
        data-testid="mindmap-classroom-remote-zoom-percent"
      >
        {{ zoomPercent }}%
      </div>
      <div
        v-if="position.activeTab.value !== 'topics'"
        class="mm-remote__grid"
        role="group"
      >
        <button
          v-for="tool in activeTools"
          :key="tool.id"
          type="button"
          class="mm-remote__tool"
          :class="{
            'is-active': tool.active,
            'is-dimmed': tool.dimmed,
            'is-danger': tool.danger,
            'is-locked': tool.id === 'painter' && formatBrushLocked,
          }"
          :disabled="tool.disabled"
          :data-testid="tool.testid"
          :aria-label="t(tool.labelKey)"
          :aria-pressed="tool.active"
          @click="runTool(tool)"
        >
          <MindMapInsertNodeIcon
            v-if="tool.insertKind"
            class="mm-remote__glyph"
            :kind="tool.insertKind"
          />
          <component
            :is="tool.icon"
            v-else-if="tool.icon"
            class="mm-remote__glyph"
            :stroke-width="2"
          />
          <span class="mm-remote__label">
            <I18nText
              :k="tool.labelKey"
              dense
            />
          </span>
        </button>
      </div>
    </div>
  </aside>
</template>
