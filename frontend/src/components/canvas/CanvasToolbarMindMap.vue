<script setup lang="ts">
/**
 * Mind-map dedicated toolbar — single-row horizontal flow, lightweight UI.
 */
import { type Component, computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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
  X,
} from '@lucide/vue'

import CanvasToolbarAiGenerateSplit from '@/components/canvas/CanvasToolbarAiGenerateSplit.vue'
import MindMapAppearanceDropdown from '@/components/canvas/MindMapAppearanceDropdown.vue'
import MindMapExportOptionsPanel from '@/components/canvas/MindMapExportOptionsPanel.vue'
import { useFeatureFlags } from '@/composables'
import {
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import {
  AI_CONTENT_LEVEL_COLORS,
  AI_CONTENT_LEVEL_IDS,
  type AiContentLevelId,
  DEFAULT_AI_CONTENT_LEVEL,
} from '@/config/aiContentLevels'
import {
  CANVAS_COMMUNITY_EXPORT_MENU_ITEM,
  CANVAS_MINDMAP_EXPORT_MENU_ITEMS,
  CANVAS_WORKSHEET_TEXT_MENU_ITEM,
  CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM,
} from '@/config/canvasExportMenu'
import {
  useAiContentLevelStore,
  useAuthStore,
  useCanvasExportStore,
  useDiagramStore,
  useSavedDiagramsStore,
} from '@/stores'

import MindMapStructureIcon from './MindMapStructureIcon.vue'

const AI_CONTENT_LEVEL_ICONS: Record<AiContentLevelId, Component> = {
  general: Sparkles,
  primary: School,
  junior: BookOpen,
  senior: GraduationCap,
  university: Landmark,
  adult: Briefcase,
  expert: Award,
}

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const authStore = useAuthStore()
const { featureCommunity, featureZhihui } = useFeatureFlags()
const { triggerImportInPlace } = useDiagramImport()

const showCommunityExport = computed(() => featureCommunity.value && authStore.isAuthenticated)

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
const {
  level: proContentLevel,
  userSet: proContentUserSet,
  showFirstRunGuide,
} = storeToRefs(aiContentLevelStore)
const proContentPanelOpen = ref(false)
const proContentGuideReady = ref(false)
const proContentAnchor = ref<HTMLElement | null>(null)
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
const showProContentHintLabel = computed(() => !props.compact && !proContentUserSet.value)

const proContentButtonTitle = computed(
  () => `${t('canvas.toolbar.professionalContent.label')} · ${proContentActiveOption.value.title}`
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
  const viewportWidth = typeof window === 'undefined' ? 304 : window.innerWidth
  const guideWidth = Math.min(280, viewportWidth - 24)
  const halfWidth = guideWidth / 2
  const anchorCenter = rect.left + rect.width / 2
  const clampedCenter = Math.max(
    halfWidth + 12,
    Math.min(viewportWidth - halfWidth - 12, anchorCenter)
  )
  return {
    top: `${rect.bottom + 10}px`,
    left: `${clampedCenter}px`,
    transform: 'translateX(-50%)',
  }
})

let proContentGuideTimer: number | undefined
let proContentGuideRaf = 0

function updateProContentAnchorRect(): void {
  proContentAnchorRect.value = proContentAnchor.value?.getBoundingClientRect() ?? null
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
    if (proContentAnchor.value) {
      proContentGuideReady.value = true
    }
  }, 700)
})

onBeforeUnmount(() => {
  if (proContentGuideTimer !== undefined) window.clearTimeout(proContentGuideTimer)
  unbindProContentGuideListeners()
})

function proContentDiagramKey(): string {
  return aiContentLevelStore.diagramKey(savedDiagramsStore.activeDiagramId)
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

function handleProContentKeydown(event: KeyboardEvent, id: AiContentLevelId): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    proContentPanelOpen.value = false
    proContentAnchor.value?.focus()
    return
  }
  const currentIndex = AI_CONTENT_LEVEL_IDS.indexOf(id)
  let nextIndex: number | null = null
  if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
    nextIndex = (currentIndex + 1) % AI_CONTENT_LEVEL_IDS.length
  } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
    nextIndex = (currentIndex - 1 + AI_CONTENT_LEVEL_IDS.length) % AI_CONTENT_LEVEL_IDS.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = AI_CONTENT_LEVEL_IDS.length - 1
  }
  if (nextIndex === null) return
  event.preventDefault()
  const listbox = (event.currentTarget as HTMLElement).closest('[role="listbox"]')
  listbox?.querySelectorAll<HTMLElement>('[role="option"]')[nextIndex]?.focus()
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
              >{{ t('canvas.toolbar.addChildNode') }}</span
            >
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
              >{{ t('canvas.toolbar.addSiblingNode') }}</span
            >
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
              >{{ t('canvas.toolbar.deleteNode') }}</span
            >
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
            ref="proContentAnchor"
            type="button"
            class="mm-btn mm-btn--pro-content"
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
              >{{ t('canvas.toolbar.professionalContent.label') }}</span
            >
            <span
              v-if="!props.compact"
              class="mm-pro-level-tag"
              :style="{ color: proContentActiveOption.color }"
              >{{ proContentActiveOption.title }}</span
            >
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
              :tabindex="option.id === proContentLevel ? 0 : -1"
              @click="handleProContentPick(option.id)"
              @keydown="handleProContentKeydown($event, option.id)"
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
      <CanvasToolbarAiGenerateSplit
        v-if="!diagramStore.collabSessionActive"
        variant="mindmap"
        :compact="props.compact"
        :is-a-i-generating="isAIGenerating"
        :ai-generate-label="t('canvas.toolbar.aiGenerate')"
        :ai-generating-label="t('canvas.toolbar.aiGenerating')"
        @ai-generate="() => handleAIGenerate()"
      />

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
              >{{ t('canvas.toolbar.import') }}</span
            >
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
                    >{{ t('canvas.toolbar.export') }}</span
                  >
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
                        :class="{
                          'mm-list-item--divided': CANVAS_WORKSHEET_TEXT_MENU_ITEM.divided,
                        }"
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
                        :class="{
                          'mm-list-item--divided': CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM.divided,
                        }"
                        @click="handleZhihuiDiagramMenuClick"
                      >
                        {{ t(CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM.labelKey) }}
                      </button>
                      <button
                        v-if="showCommunityExport"
                        type="button"
                        class="mm-list-item"
                        :class="{
                          'mm-list-item--divided': CANVAS_COMMUNITY_EXPORT_MENU_ITEM.divided,
                        }"
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
<style scoped src="./canvasToolbarMindMap.css"></style>
<style src="./canvasToolbarMindMapPopper.css"></style>
