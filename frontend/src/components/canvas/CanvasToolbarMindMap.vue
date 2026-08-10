<script setup lang="ts">
/**
 * Mind-map dedicated toolbar — single-row horizontal flow, lightweight UI.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'

import { storeToRefs } from 'pinia'

import { ElDropdown, ElPopover, ElTooltip } from 'element-plus'

import {
  Award,
  BookOpen,
  Briefcase,
  Check,
  ChevronDown,
  Download,
  GitBranchPlus,
  GraduationCap,
  Landmark,
  Plus,
  RotateCcw,
  RotateCw,
  School,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
  X,
} from '@lucide/vue'

import MindMapAppearanceDropdown from '@/components/canvas/MindMapAppearanceDropdown.vue'
import MindMapExportOptionsPanel from '@/components/canvas/MindMapExportOptionsPanel.vue'

import {
  AI_CONTENT_LEVEL_COLORS,
  AI_CONTENT_LEVEL_IDS,
  DEFAULT_AI_CONTENT_LEVEL,
  type AiContentLevelId,
} from '@/config/aiContentLevels'

const AI_CONTENT_LEVEL_ICONS: Record<AiContentLevelId, Component> = {
  general: Sparkles,
  primary: School,
  junior: BookOpen,
  senior: GraduationCap,
  university: Landmark,
  adult: Briefcase,
  expert: Award,
}

import {
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar'
import { useFeatureFlags } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import { CANVAS_MINDMAP_EXPORT_MENU_ITEMS, CANVAS_COMMUNITY_EXPORT_MENU_ITEM, CANVAS_WORKSHEET_TEXT_MENU_ITEM, CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM } from '@/config/canvasExportMenu'
import {
  useAiContentLevelStore,
  useAuthStore,
  useCanvasExportStore,
  useDiagramStore,
  useSavedDiagramsStore,
} from '@/stores'

import MindMapStructureIcon from './MindMapStructureIcon.vue'

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const authStore = useAuthStore()
const { featureCommunity, featureZhihui } = useFeatureFlags()
const { triggerImportInPlace } = useDiagramImport()

const showCommunityExport = computed(
  () => featureCommunity.value && authStore.isAuthenticated
)

const showZhihuiDiagramExport = computed(
  () => featureZhihui.value && authStore.isAuthenticated && authStore.canAccessZhihui
)

const { handleAddChild, handleAddSibling, handleDeleteNode, handleAddBranch } = useNodeActions({
  registerEventBusListeners: false,
})

const { isAIGenerating, handleAIGenerate } = useCanvasToolbarApps()

const canvasExportStore = useCanvasExportStore()
const { exportOptions, mergedExportOptions } = storeToRefs(canvasExportStore)

const aiContentLevelStore = useAiContentLevelStore()
const savedDiagramsStore = useSavedDiagramsStore()
const { level: proContentLevel, userSet: proContentUserSet, showFirstRunGuide } =
  storeToRefs(aiContentLevelStore)
const proContentPanelOpen = ref(false)
const proContentGuideReady = ref(false)
const proContentAnchorRect = ref<DOMRect | null>(null)

const proContentLevelOptions = computed(() =>
  AI_CONTENT_LEVEL_IDS.map((id) => ({
    id,
    title: t(`canvas.toolbar.professionalContent.level.${id}.title`),
    description: t(`canvas.toolbar.professionalContent.level.${id}.description`),
    color: AI_CONTENT_LEVEL_COLORS[id],
    icon: AI_CONTENT_LEVEL_ICONS[id],
  }))
)

const proContentActiveOption = computed(
  () =>
    proContentLevelOptions.value.find((option) => option.id === proContentLevel.value) ??
    proContentLevelOptions.value[0]
)

/** First-time hint: show「专业内容」until the user has picked a level once. */
const showProContentHintLabel = computed(
  () => !props.compact && !proContentUserSet.value
)

const proContentButtonTitle = computed(
  () =>
    `${t('canvas.toolbar.professionalContent.label')} · ${proContentActiveOption.value.title}`
)

const showProContentGuide = computed(
  () =>
    showFirstRunGuide.value &&
    proContentGuideReady.value &&
    !diagramStore.collabSessionActive &&
    !proContentPanelOpen.value
)

const proContentGuideStyle = computed(() => {
  const rect = proContentAnchorRect.value
  if (!rect) {
    return {
      top: '56px',
      left: '50%',
      transform: 'translateX(-50%)',
    }
  }
  return {
    top: `${rect.bottom + 10}px`,
    left: `${rect.left + rect.width / 2}px`,
    transform: 'translateX(-50%)',
  }
})

let proContentGuideTimer: number | undefined
let proContentGuideRaf = 0

function findProContentAnchor(): HTMLElement | null {
  const el = document.querySelector('[data-pro-content-anchor]')
  return el instanceof HTMLElement ? el : null
}

function updateProContentAnchorRect(): void {
  proContentAnchorRect.value = findProContentAnchor()?.getBoundingClientRect() ?? null
}

function scheduleProContentAnchorUpdate(): void {
  cancelAnimationFrame(proContentGuideRaf)
  proContentGuideRaf = requestAnimationFrame(updateProContentAnchorRect)
}

function bindProContentGuideListeners(): void {
  window.addEventListener('resize', scheduleProContentAnchorUpdate)
  window.addEventListener('scroll', scheduleProContentAnchorUpdate, true)
}

function unbindProContentGuideListeners(): void {
  window.removeEventListener('resize', scheduleProContentAnchorUpdate)
  window.removeEventListener('scroll', scheduleProContentAnchorUpdate, true)
  cancelAnimationFrame(proContentGuideRaf)
}

function dismissProContentGuide(): void {
  aiContentLevelStore.dismissGuide()
  proContentGuideReady.value = false
}

function openProContentFromGuide(): void {
  updateProContentAnchorRect()
  dismissProContentGuide()
  void nextTick(() => {
    proContentPanelOpen.value = true
  })
}

watch(showProContentGuide, (visible) => {
  if (visible) {
    bindProContentGuideListeners()
    scheduleProContentAnchorUpdate()
    return
  }
  unbindProContentGuideListeners()
})

watch(proContentPanelOpen, (open) => {
  if (open && showFirstRunGuide.value) {
    aiContentLevelStore.dismissGuide()
  }
})

onMounted(() => {
  if (!showFirstRunGuide.value || diagramStore.collabSessionActive) return
  proContentGuideTimer = window.setTimeout(() => {
    updateProContentAnchorRect()
    if (findProContentAnchor()) {
      proContentGuideReady.value = true
    }
  }, 700)
})

onBeforeUnmount(() => {
  if (proContentGuideTimer !== undefined) window.clearTimeout(proContentGuideTimer)
  unbindProContentGuideListeners()
})

function proContentDiagramKey(): string {
  return savedDiagramsStore.activeDiagramId || 'unsaved'
}

function proContentLevelTitle(id: AiContentLevelId): string {
  return t(`canvas.toolbar.professionalContent.level.${id}.title`)
}

function handleProContentPick(id: AiContentLevelId): void {
  if (id === proContentLevel.value && aiContentLevelStore.userSet) {
    proContentPanelOpen.value = false
    return
  }

  const diagramKey = proContentDiagramKey()
  const generatedAt = aiContentLevelStore.getGeneratedLevel(diagramKey)
  aiContentLevelStore.setLevel(id)
  proContentPanelOpen.value = false

  if (generatedAt && generatedAt !== id) {
    notify.info(
      t('canvas.toolbar.professionalContent.notify.afterGenerated', {
        current: proContentLevelTitle(generatedAt),
        next: proContentLevelTitle(id),
      })
    )
    return
  }

  if (id === DEFAULT_AI_CONTENT_LEVEL) {
    notify.info(t('canvas.toolbar.professionalContent.notify.preferenceGeneral'))
    return
  }

  notify.info(
    t('canvas.toolbar.professionalContent.notify.preference', {
      level: proContentLevelTitle(id),
    })
  )
}

const structureDropdownOpen = ref(false)
const exportDropdownOpen = ref(false)

const structureMode = computed(() => {
  void diagramStore.data?.nodes?.length
  void diagramStore.data?.connections?.length
  return diagramStore.getMindMapStructureMode()
})

const structureLabel = computed(() =>
  structureMode.value === 'right'
    ? t('canvas.toolbar.mindMapStructureRight')
    : t('canvas.toolbar.mindMapStructureBalanced')
)

function handleUndo() {
  tryCollabGuardedUndo()
}

function handleRedo() {
  tryCollabGuardedRedo()
}

function handleStructurePick(mode: 'balanced' | 'right') {
  structureDropdownOpen.value = false
  if (diagramStore.setMindMapStructureMode(mode)) {
    notify.success(t('canvas.toolbar.mindMapStructureApplied'))
  }
}

function handleExportCommand(format: string) {
  exportDropdownOpen.value = false
  eventBus.emit('toolbar:export_requested', {
    format,
    options: { ...mergedExportOptions.value },
  })
}

function handleZhihuiDiagramMenuClick() {
  exportDropdownOpen.value = false
  eventBus.emit('toolbar:zhihui_diagram_requested', {})
}

function handleWorksheetTextMenuClick() {
  exportDropdownOpen.value = false
  eventBus.emit('toolbar:worksheet_text_requested', {})
}

function handleAddChildClick() {
  const selectedId = diagramStore.selectedNodes[0]
  if (!selectedId || selectedId === 'topic') {
    handleAddBranch()
    return
  }
  handleAddChild()
}
</script>

<template>
  <div class="mm-toolbar">
    <div class="mm-toolbar__track">
      <!-- Structure mode -->
      <ElTooltip
        :content="structureLabel"
        placement="bottom"
      >
        <span class="inline-flex shrink-0">
          <ElDropdown
            v-model:visible="structureDropdownOpen"
            trigger="hover"
            :show-timeout="150"
            :hide-timeout="200"
            placement="bottom-start"
            popper-class="mm-toolbar-popper mm-toolbar-popper--structure"
          >
            <button
              type="button"
              class="mm-btn mm-btn--structure"
              :aria-label="structureLabel"
            >
              <MindMapStructureIcon
                class="mm-btn__structure-preview"
                :mode="structureMode"
              />
            </button>
        <template #dropdown>
          <div class="mm-panel mm-panel--structure">
            <button
              type="button"
              class="mm-structure-card"
              :class="{ 'is-active': structureMode === 'balanced' }"
              @click="handleStructurePick('balanced')"
            >
              <MindMapStructureIcon mode="balanced" />
              <span class="mm-structure-card__label">{{
                t('canvas.toolbar.mindMapStructureBalanced')
              }}</span>
            </button>
            <div class="mm-panel__divider-v" />
            <button
              type="button"
              class="mm-structure-card"
              :class="{ 'is-active': structureMode === 'right' }"
              @click="handleStructurePick('right')"
            >
              <MindMapStructureIcon mode="right" />
              <span class="mm-structure-card__label">{{
                t('canvas.toolbar.mindMapStructureRight')
              }}</span>
            </button>
          </div>
        </template>
          </ElDropdown>
        </span>
      </ElTooltip>

      <span class="mm-sep" />

      <!-- Undo / Redo -->
      <div
        class="mm-history-group"
        role="group"
        :aria-label="t('canvas.toolbar.historyGroup')"
      >
        <ElTooltip
          placement="bottom"
          :show-arrow="true"
          popper-class="mm-shortcut-tooltip"
        >
          <template #content>
            <div class="mm-shortcut-tooltip__row">
              <span>{{ t('canvas.toolbar.undo') }}</span>
              <kbd class="mm-shortcut-tooltip__kbd">{{ t('canvas.toolbar.undoShortcut') }}</kbd>
            </div>
          </template>
          <button
            type="button"
            class="mm-history-btn"
            :disabled="!diagramStore.canUndo"
            :aria-label="t('canvas.toolbar.undo')"
            @click="handleUndo"
          >
            <RotateCcw class="mm-history-btn__icon" />
          </button>
        </ElTooltip>
        <ElTooltip
          placement="bottom"
          :show-arrow="true"
          popper-class="mm-shortcut-tooltip"
        >
          <template #content>
            <div class="mm-shortcut-tooltip__row">
              <span>{{ t('canvas.toolbar.redo') }}</span>
              <kbd class="mm-shortcut-tooltip__kbd">{{ t('canvas.toolbar.redoShortcut') }}</kbd>
            </div>
          </template>
          <button
            type="button"
            class="mm-history-btn"
            :disabled="!diagramStore.canRedo"
            :aria-label="t('canvas.toolbar.redo')"
            @click="handleRedo"
          >
            <RotateCw class="mm-history-btn__icon" />
          </button>
        </ElTooltip>
      </div>

      <span class="mm-sep" />

      <!-- Node editing -->
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('canvas.toolbar.addChildNode')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.addChildNode')"
            @click="handleAddChildClick"
          >
            <Plus class="w-4 h-4 text-blue-500" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
            >{{ t('canvas.toolbar.addChildNode') }}</span>
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.addSiblingNode')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.addSiblingNode')"
            @click="handleAddSibling"
          >
            <GitBranchPlus class="w-4 h-4 text-emerald-600" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
            >{{ t('canvas.toolbar.addSiblingNode') }}</span>
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.deleteNode')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn mm-btn--danger"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.deleteNode')"
            @click="handleDeleteNode"
          >
            <Trash2 class="w-4 h-4" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
            >{{ t('canvas.toolbar.deleteNode') }}</span>
          </button>
        </ElTooltip>
      </div>

      <span class="mm-sep" />

      <!-- Appearance: diagram style + theme color -->
      <MindMapAppearanceDropdown :compact="props.compact" />

      <span class="mm-sep" />

      <!-- Audience level picker — before AI generate so users set audience first -->
      <ElPopover
        v-if="!diagramStore.collabSessionActive"
        v-model:visible="proContentPanelOpen"
        placement="bottom-start"
        :width="280"
        trigger="click"
        popper-class="mm-toolbar-popper mm-toolbar-popper--pro-content"
      >
        <template #reference>
          <button
            type="button"
            class="mm-btn mm-btn--pro-content"
            data-pro-content-anchor
            :class="{
              'mm-btn--icon': props.compact,
              'mm-btn--pro-content-compact': !showProContentHintLabel && !props.compact,
              'mm-btn--pro-content-guide': showProContentGuide,
              'is-open': proContentPanelOpen,
            }"
            :title="proContentButtonTitle"
            :aria-label="proContentButtonTitle"
            :aria-expanded="proContentPanelOpen"
          >
            <span
              class="mm-pro-icon"
              :style="{
                color: proContentActiveOption.color,
                backgroundColor: `color-mix(in srgb, ${proContentActiveOption.color} 16%, transparent)`,
              }"
              aria-hidden="true"
            >
              <component
                :is="proContentActiveOption.icon"
                class="mm-pro-icon__svg"
              />
            </span>
            <span
              v-if="showProContentHintLabel"
              class="mm-btn__label"
            >{{ t('canvas.toolbar.professionalContent.label') }}</span>
            <span
              v-if="!props.compact"
              class="mm-pro-level-tag"
              :style="{ color: proContentActiveOption.color }"
            >{{ proContentActiveOption.title }}</span>
            <ChevronDown
              class="mm-btn__chevron"
              :class="{ 'mm-btn__chevron--open': proContentPanelOpen }"
            />
          </button>
        </template>

        <div
          class="mm-pro-panel"
          role="listbox"
          :aria-label="t('canvas.toolbar.professionalContent.panelTitle')"
        >
          <div class="mm-pro-panel__eyebrow">
            {{ t('canvas.toolbar.professionalContent.panelTitle') }}
          </div>
          <div class="mm-pro-panel__list">
            <button
              v-for="option in proContentLevelOptions"
              :key="option.id"
              type="button"
              class="mm-pro-level"
              :class="{ 'is-active': option.id === proContentLevel }"
              role="option"
              :aria-selected="option.id === proContentLevel"
              @click="handleProContentPick(option.id)"
            >
              <span
                class="mm-pro-icon"
                :style="{
                  color: option.color,
                  backgroundColor: `color-mix(in srgb, ${option.color} 16%, transparent)`,
                }"
                aria-hidden="true"
              >
                <component
                  :is="option.icon"
                  class="mm-pro-icon__svg"
                />
              </span>
              <span class="mm-pro-level__title">{{ option.title }}</span>
              <span class="mm-pro-level__hint">{{ option.description }}</span>
              <Check
                v-if="option.id === proContentLevel"
                class="mm-pro-level__check"
                aria-hidden="true"
              />
            </button>
          </div>
        </div>
      </ElPopover>

      <Teleport to="body">
        <Transition name="mm-pro-guide">
          <div
            v-if="showProContentGuide"
            class="mm-pro-guide"
            role="dialog"
            :aria-label="t('canvas.toolbar.professionalContent.guideTitle')"
            :style="proContentGuideStyle"
          >
            <div
              class="mm-pro-guide__arrow"
              aria-hidden="true"
            />
            <div class="mm-pro-guide__card">
              <button
                type="button"
                class="mm-pro-guide__close"
                :aria-label="t('canvas.toolbar.professionalContent.guideDismiss')"
                @click="dismissProContentGuide"
              >
                <X
                  class="h-3.5 w-3.5"
                  :stroke-width="2.5"
                />
              </button>
              <p class="mm-pro-guide__title">
                {{ t('canvas.toolbar.professionalContent.guideTitle') }}
              </p>
              <p class="mm-pro-guide__body">
                {{ t('canvas.toolbar.professionalContent.guideBody') }}
              </p>
              <div class="mm-pro-guide__actions">
                <button
                  type="button"
                  class="mm-pro-guide__dismiss"
                  @click="dismissProContentGuide"
                >
                  {{ t('canvas.toolbar.professionalContent.guideDismiss') }}
                </button>
                <button
                  type="button"
                  class="mm-pro-guide__action"
                  @click="openProContentFromGuide"
                >
                  {{ t('canvas.toolbar.professionalContent.guideAction') }}
                </button>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- AI generate -->
      <ElTooltip
        v-if="!diagramStore.collabSessionActive"
        :content="
          isAIGenerating
            ? t('canvas.toolbar.aiGenerating')
            : t('canvas.toolbar.aiGenerateTooltip')
        "
        placement="bottom"
        :disabled="!props.compact"
      >
        <button
          type="button"
          class="mm-btn mm-btn--ai"
          :class="{ 'mm-btn--icon': props.compact }"
          :disabled="isAIGenerating"
          :aria-label="
            isAIGenerating ? t('canvas.toolbar.aiGenerating') : t('canvas.toolbar.aiGenerate')
          "
          @click="() => handleAIGenerate()"
        >
          <Wand2 class="h-4 w-4 shrink-0 text-white" />
          <span
            v-if="!props.compact"
            class="mm-btn__label"
          >{{
            isAIGenerating ? t('canvas.toolbar.aiGenerating') : t('canvas.toolbar.aiGenerate')
          }}</span>
        </button>
      </ElTooltip>

      <span
        v-if="!diagramStore.collabSessionActive"
        class="mm-sep"
      />

      <!-- Import / Export -->
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('canvas.toolbar.import')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.import')"
            @click="() => triggerImportInPlace()"
          >
            <Upload class="w-4 h-4 text-gray-500" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
            >{{ t('canvas.toolbar.import') }}</span>
          </button>
        </ElTooltip>

        <div class="mm-export-anchor">
          <ElTooltip
            :content="t('canvas.toolbar.export')"
            placement="bottom"
            :disabled="!props.compact"
          >
            <span class="inline-flex">
              <ElDropdown
                v-model:visible="exportDropdownOpen"
                trigger="click"
                placement="bottom-end"
                popper-class="mm-toolbar-popper mm-toolbar-popper--export"
              >
                <button
                  type="button"
                  class="mm-btn mm-btn--export"
                  :class="{ 'mm-btn--icon': props.compact }"
                  data-learning-sheet-export-anchor
                  data-canvas-export-anchor
                  :aria-label="t('canvas.toolbar.export')"
                >
                  <Download class="w-4 h-4 text-amber-300" />
                  <span
                    v-if="!props.compact"
                    class="mm-btn__label"
                  >{{ t('canvas.toolbar.export') }}</span>
                  <ChevronDown
                    v-if="!props.compact"
                    class="mm-btn__chevron mm-btn__chevron--on-dark"
                  />
                </button>
            <template #dropdown>
              <div class="mm-panel mm-panel--export">
                <MindMapExportOptionsPanel v-model="exportOptions" />
                <div class="mm-panel mm-panel--list mm-panel--export-formats">
                  <button
                    type="button"
                    class="mm-list-item"
                    :class="{ 'mm-list-item--divided': CANVAS_WORKSHEET_TEXT_MENU_ITEM.divided }"
                    @click="handleWorksheetTextMenuClick"
                  >
                    {{ t(CANVAS_WORKSHEET_TEXT_MENU_ITEM.labelKey) }}
                  </button>
                  <button
                    v-for="item in CANVAS_MINDMAP_EXPORT_MENU_ITEMS"
                    :key="item.command"
                    type="button"
                    class="mm-list-item"
                    :class="{ 'mm-list-item--divided': item.divided }"
                    @click="handleExportCommand(item.command)"
                  >
                    {{ t(item.labelKey) }}
                  </button>
                  <button
                    v-if="showZhihuiDiagramExport"
                    type="button"
                    class="mm-list-item"
                    :class="{ 'mm-list-item--divided': CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM.divided }"
                    @click="handleZhihuiDiagramMenuClick"
                  >
                    {{ t(CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM.labelKey) }}
                  </button>
                  <button
                    v-if="showCommunityExport"
                    type="button"
                    class="mm-list-item"
                    :class="{ 'mm-list-item--divided': CANVAS_COMMUNITY_EXPORT_MENU_ITEM.divided }"
                    @click="handleExportCommand(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.command)"
                  >
                    {{ t(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.labelKey) }}
                  </button>
                </div>
              </div>
            </template>
              </ElDropdown>
            </span>
          </ElTooltip>
        </div>
      </div>
    </div>
  </div>

</template>

<style src="./mindMapToolbarButtons.css"></style>

<style scoped>
.mm-toolbar {
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

.mm-toolbar__track {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  min-width: min-content;
  max-width: 100%;
  padding: 2px 4px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.mm-toolbar__track::-webkit-scrollbar {
  display: none;
}

.mm-sep {
  flex-shrink: 0;
  width: 1px;
  height: 20px;
  margin: 0 2px;
  background: #e5e7eb;
}

:global(.dark) .mm-sep {
  background: #4b5563;
}

.mm-btn-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.mm-export-anchor {
  position: relative;
  flex-shrink: 0;
}

.mm-history-group {
  flex-shrink: 0;
  display: inline-flex;
  align-items: stretch;
  height: 32px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}

:global(.dark) .mm-history-group {
  background: #1f2937;
  border-color: #374151;
  box-shadow: none;
}

.mm-history-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 100%;
  padding: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.mm-history-btn + .mm-history-btn {
  border-left: 1px solid #e5e7eb;
}

:global(.dark) .mm-history-btn + .mm-history-btn {
  border-left-color: #374151;
}

.mm-history-btn:hover:not(:disabled) {
  background: #f9fafb;
  color: #6b7280;
}

:global(.dark) .mm-history-btn:hover:not(:disabled) {
  background: #374151;
  color: #d1d5db;
}

.mm-history-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.mm-history-btn__icon {
  width: 16px;
  height: 16px;
}

.mm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}

:global(.dark) .mm-btn {
  background: #1f2937;
  border-color: #374151;
  color: #e5e7eb;
  box-shadow: none;
}

.mm-btn:hover:not(:disabled) {
  background: #f9fafb;
  border-color: #d1d5db;
}

.mm-btn:focus {
  outline: none;
}

.mm-btn:focus-visible {
  box-shadow:
    0 1px 2px rgb(0 0 0 / 0.04),
    inset 0 0 0 2px #3b82f6;
}

:global(.dark) .mm-btn:focus-visible {
  box-shadow: inset 0 0 0 2px #60a5fa;
}

.mm-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.mm-btn--icon {
  width: 32px;
  padding: 0;
}

.mm-btn--structure {
  width: auto;
  max-width: none;
  padding: 0 6px;
}

.mm-btn--select {
  max-width: 168px;
}

.mm-btn--danger {
  color: #dc2626;
  border-color: #fecaca;
}

.mm-btn--danger:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #fca5a5;
}

.mm-btn--ai {
  border: none;
  color: #fff;
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  box-shadow:
    0 1px 3px rgb(37 99 235 / 0.35),
    inset 0 1px 0 rgb(255 255 255 / 0.2);
}

.mm-btn--ai:hover:not(:disabled) {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
  border-color: transparent;
  box-shadow:
    0 2px 8px rgb(37 99 235 / 0.4),
    inset 0 1px 0 rgb(255 255 255 / 0.2);
}

.mm-btn--ai .mm-btn__label {
  color: #fff;
}

.mm-pro-level-tag {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  max-width: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-btn--pro-content {
  border-color: #3b82f6;
}

.mm-btn--pro-content:hover:not(:disabled) {
  border-color: #2563eb;
  background: #eff6ff;
}

.mm-btn--pro-content.is-open {
  border-color: #2563eb;
  background: #eff6ff;
}

:global(.dark) .mm-btn--pro-content {
  border-color: #60a5fa;
}

:global(.dark) .mm-btn--pro-content:hover:not(:disabled),
:global(.dark) .mm-btn--pro-content.is-open {
  border-color: #93c5fd;
  background: rgb(59 130 246 / 0.12);
}

.mm-btn--pro-content-compact .mm-pro-level-tag {
  max-width: 3em;
}

.mm-btn--pro-content-guide {
  border-color: #2563eb;
  box-shadow:
    0 0 0 2px rgb(59 130 246 / 0.35),
    0 2px 8px rgb(37 99 235 / 0.28),
    inset 0 1px 0 rgb(255 255 255 / 0.2);
  animation: mm-pro-guide-pulse 1.6s ease-in-out infinite;
}

@keyframes mm-pro-guide-pulse {
  0%,
  100% {
    box-shadow:
      0 0 0 2px rgb(59 130 246 / 0.35),
      0 2px 8px rgb(37 99 235 / 0.28),
      inset 0 1px 0 rgb(255 255 255 / 0.2);
  }
  50% {
    box-shadow:
      0 0 0 3px rgb(59 130 246 / 0.5),
      0 4px 14px rgb(37 99 235 / 0.4),
      inset 0 1px 0 rgb(255 255 255 / 0.2);
  }
}

.mm-pro-guide {
  position: fixed;
  z-index: 4100;
  width: min(280px, calc(100vw - 24px));
  pointer-events: auto;
}

.mm-pro-guide__arrow {
  position: absolute;
  top: -5px;
  left: 50%;
  width: 10px;
  height: 10px;
  background: #fff;
  border-left: 1px solid rgb(191 219 254 / 0.95);
  border-top: 1px solid rgb(191 219 254 / 0.95);
  transform: translateX(-50%) rotate(45deg);
}

.mm-pro-guide__card {
  position: relative;
  padding: 14px 14px 12px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid rgb(191 219 254 / 0.95);
  box-shadow:
    0 12px 32px rgb(15 23 42 / 0.12),
    0 2px 8px rgb(37 99 235 / 0.12);
}

.mm-pro-guide__close {
  position: absolute;
  top: 8px;
  right: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
}

.mm-pro-guide__close:hover {
  background: #f8fafc;
  color: #475569;
}

.mm-pro-guide__title {
  margin: 0 24px 6px 0;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.35;
}

.mm-pro-guide__body {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.mm-pro-guide__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.mm-pro-guide__dismiss {
  padding: 5px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.mm-pro-guide__dismiss:hover {
  color: #334155;
  background: #f1f5f9;
}

.mm-pro-guide__action {
  padding: 5px 12px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 1px 3px rgb(37 99 235 / 0.35);
}

.mm-pro-guide__action:hover {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
}

.mm-pro-guide-enter-active,
.mm-pro-guide-leave-active {
  transition: opacity 0.2s ease;
}

.mm-pro-guide-enter-from,
.mm-pro-guide-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .mm-btn--pro-content-guide {
    animation: none;
  }
}

.mm-btn--pro-content.is-open .mm-btn__chevron--open {
  transform: rotate(180deg);
}

.mm-btn__chevron {
  transition: transform 0.15s ease;
}

.mm-pro-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  flex-shrink: 0;
}

.mm-pro-icon__svg {
  width: 13px;
  height: 13px;
}

.mm-pro-panel__eyebrow {
  padding: 2px 8px 8px;
  font-size: 12px;
  font-weight: 500;
  color: #9ca3af;
}

.mm-pro-panel__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mm-pro-level {
  display: grid;
  grid-template-columns: 22px minmax(0, auto) minmax(0, 1fr) 16px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 36px;
  padding: 8px 10px;
  border: none;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.mm-pro-level:hover {
  background: #f3f4f6;
}

.mm-pro-level.is-active {
  background: #f8fafc;
}

.mm-pro-level__title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  white-space: nowrap;
}

.mm-pro-level__hint {
  font-size: 12px;
  color: #9ca3af;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mm-pro-level__check {
  width: 16px;
  height: 16px;
  color: #2563eb;
  justify-self: end;
}

:global(.dark) .mm-pro-level-tag {
  color: #94a3b8;
}

:global(.dark) .mm-pro-panel__eyebrow {
  color: #6b7280;
}

:global(.dark) .mm-pro-level:hover,
:global(.dark) .mm-pro-level.is-active {
  background: #1f2937;
}

:global(.dark) .mm-pro-level__title {
  color: #f9fafb;
}

:global(.dark) .mm-pro-level__hint {
  color: #6b7280;
}

:global(.dark) .mm-btn--ai {
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  border: none;
  color: #fff;
}

:global(.dark) .mm-btn--ai:hover:not(:disabled) {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
}

.mm-btn--export {
  background: #1e293b;
  border-color: #1e293b;
  color: #fff;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.25);
}

.mm-btn--export:hover:not(:disabled) {
  background: #0f172a;
  border-color: #0f172a;
}

.mm-btn__label--truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 96px;
}

.mm-btn__structure-preview {
  width: 36px !important;
  height: 22px !important;
}

.mm-btn__chevron {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: #9ca3af;
}

.mm-btn__chevron--on-dark {
  color: rgb(255 255 255 / 0.65);
}
</style>

<!-- Teleported dropdown panels — isolated from global Element Plus styles -->
<style>
.mm-toolbar-popper.el-popper {
  padding: 0 !important;
  border: 1px solid #e5e7eb !important;
  border-radius: 12px !important;
  background: #fff !important;
  box-shadow:
    0 4px 16px rgb(15 23 42 / 0.08),
    0 1px 4px rgb(15 23 42 / 0.04) !important;
  overflow: hidden !important;
}

.mm-toolbar-popper--pro-content.el-popper {
  padding: 10px !important;
}

/* Export dropdown — Swiss stone panel (matches AdminSwissSegmented / collab menus). */
.mm-toolbar-popper--export.el-popper {
  border: 1px solid var(--swiss-border-strong, #d6d3d1) !important;
  border-radius: 6px !important;
  background: var(--swiss-surface, #ffffff) !important;
  box-shadow:
    0 4px 6px -1px rgb(0 0 0 / 0.07),
    0 2px 4px -2px rgb(0 0 0 / 0.05) !important;
}

.mm-toolbar-popper--export.el-popper .el-popper__arrow::before {
  border-color: var(--swiss-border-strong, #d6d3d1) !important;
  background: var(--swiss-surface, #ffffff) !important;
}

.dark .mm-toolbar-popper--export.el-popper {
  border-color: #57534e !important;
  background: #292524 !important;
  box-shadow:
    0 4px 6px -1px rgb(0 0 0 / 0.35),
    0 2px 4px -2px rgb(0 0 0 / 0.25) !important;
}

.dark .mm-toolbar-popper--export.el-popper .el-popper__arrow::before {
  border-color: #57534e !important;
  background: #292524 !important;
}

.mm-toolbar-popper.el-popper .el-popper__arrow::before {
  border-color: #e5e7eb !important;
  background: #fff !important;
}

.dark .mm-toolbar-popper.el-popper {
  border-color: #374151 !important;
  background: #1f2937 !important;
  box-shadow:
    0 4px 16px rgb(0 0 0 / 0.35),
    0 1px 4px rgb(0 0 0 / 0.2) !important;
}

.dark .mm-toolbar-popper.el-popper .el-popper__arrow::before {
  border-color: #374151 !important;
  background: #1f2937 !important;
}

.mm-panel {
  box-sizing: border-box;
}

.mm-panel--structure {
  display: flex;
  align-items: stretch;
  padding: 10px;
  gap: 0;
}

.mm-panel__divider-v {
  width: 1px;
  margin: 4px 6px;
  background: #e5e7eb;
  flex-shrink: 0;
}

.dark .mm-panel__divider-v {
  background: #374151;
}

.mm-structure-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 108px;
  padding: 10px 12px 8px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  outline: none;
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.mm-structure-card:hover {
  background: #f3f4f6;
  box-shadow: inset 0 0 0 2px #93c5fd;
}

.mm-structure-card.is-active {
  background: #eff6ff;
  box-shadow: inset 0 0 0 2px #3b82f6;
}

.mm-structure-card.is-active:hover {
  background: #dbeafe;
  box-shadow: inset 0 0 0 2px #2563eb;
}

.mm-structure-card:focus-visible {
  box-shadow: inset 0 0 0 2px #2563eb;
}

.dark .mm-structure-card:hover {
  background: #374151;
  box-shadow: inset 0 0 0 2px #60a5fa;
}

.dark .mm-structure-card.is-active {
  background: #1e3a5f;
  box-shadow: inset 0 0 0 2px #3b82f6;
}

.dark .mm-structure-card.is-active:hover {
  background: #1e40af;
  box-shadow: inset 0 0 0 2px #60a5fa;
}

.dark .mm-structure-card:focus-visible {
  box-shadow: inset 0 0 0 2px #60a5fa;
}

.mm-structure-card__label {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
  text-align: center;
  line-height: 1.3;
  white-space: nowrap;
}

.dark .mm-structure-card__label {
  color: #e5e7eb;
}

.mm-panel--list {
  display: flex;
  flex-direction: column;
  padding: 4px;
  min-width: 0;
  width: 100%;
}

.mm-panel--export {
  width: max-content;
  min-width: min(100%, 168px);
  max-width: min(320px, calc(100vw - 24px));
}

.mm-panel--export-formats {
  padding: 4px 6px 6px;
}

.mm-panel--export-formats .mm-list-item {
  padding: 7px 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--swiss-body, #44403c);
}

.mm-panel--export-formats .mm-list-item:hover {
  background: var(--swiss-hover, #f5f5f4);
  color: var(--swiss-ink, #1c1917);
}

.mm-panel--export-formats .mm-list-item.is-active {
  background: transparent;
  color: var(--swiss-body, #44403c);
}

.mm-panel--export-formats .mm-list-item--divided {
  margin-top: 4px;
  padding-top: 9px;
  border-top: 1px solid var(--swiss-border, #e7e5e4);
}

.dark .mm-panel--export-formats .mm-list-item {
  color: #e7e5e4;
}

.dark .mm-panel--export-formats .mm-list-item:hover {
  background: #44403c;
  color: #fafaf9;
}

.dark .mm-panel--export-formats .mm-list-item--divided {
  border-top-color: #57534e;
}

.mm-panel--scrollable {
  max-height: min(420px, 70vh);
  overflow-y: auto;
}

.mm-list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #374151;
  font-size: 12px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.mm-list-item:hover {
  background: #f3f4f6;
}

.mm-list-item.is-active {
  background: #eff6ff;
  color: #2563eb;
}

.mm-list-item--divided {
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid #f3f4f6;
}

.dark .mm-list-item {
  color: #e5e7eb;
}

.dark .mm-list-item:hover {
  background: #374151;
}

.dark .mm-list-item.is-active {
  background: #1e3a5f;
  color: #93c5fd;
}

.mm-theme-swatch {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1px solid rgb(0 0 0 / 0.08);
  flex-shrink: 0;
}

.mm-list-item__label {
  flex: 1;
  min-width: 0;
}

.mm-toolbar-popper--apps {
  width: min(300px, calc(100vw - 24px)) !important;
}

.mm-panel--apps {
  display: flex;
  flex-direction: column;
  padding: 4px;
  max-height: min(420px, 70vh);
  overflow-y: auto;
}

.mm-app-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.mm-app-item:hover {
  background: #f3f4f6;
}

.dark .mm-app-item:hover {
  background: #374151;
}

.mm-app-item__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.mm-app-item__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.mm-app-item__title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.dark .mm-app-item__title {
  color: #f9fafb;
}

.mm-app-item__tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 9999px;
  background: #f3f4f6;
  color: #6b7280;
}

.mm-app-item__desc {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.35;
}

.dark .mm-app-item__desc {
  color: #9ca3af;
}

.mm-shortcut-tooltip.el-popper {
  padding: 6px 10px !important;
  border: none !important;
  border-radius: 8px !important;
  background: #1e1e20 !important;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.28) !important;
}

.mm-shortcut-tooltip.el-popper .el-popper__arrow::before {
  border-color: #1e1e20 !important;
  background: #1e1e20 !important;
}

.mm-shortcut-tooltip__row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
  color: #fff;
  white-space: nowrap;
}

.mm-shortcut-tooltip__kbd {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border: none;
  border-radius: 6px;
  background: #3e3e42;
  color: #fff;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}
</style>
