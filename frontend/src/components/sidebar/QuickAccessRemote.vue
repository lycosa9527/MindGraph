<script setup lang="ts">
/**
 * Draggable tabbed remote opened from the account menu.
 * Diagrams open a blank canvas; prompts run the landing generator.
 */
import { type ComponentPublicInstance, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { LayoutGrid, Lightbulb, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import DiagramPreviewSvg from '@/components/mindgraph/DiagramPreviewSvg.vue'
import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import {
  isNewCanvasTypeQuery,
  loadBlankCanvasForType,
  resolveDiagramTypeFromQuery,
} from '@/composables/canvasPage/newCanvasBootstrap'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useCanvasSessionDirty } from '@/composables/editor/canvasSessionDirty'
import { executeLandingPrompt } from '@/composables/mindgraph/runLandingPromptGeneration'
import { useLandingGenerateGraph } from '@/composables/mindgraph/useLandingGenerateGraph'
import {
  QUICK_ACCESS_REMOTE_TABS,
  quickAccessReplaceNeedsConfirm,
  resolveQuickAccessDiagramOpen,
  resolveQuickAccessPromptText,
} from '@/composables/sidebar/quickAccessRemoteModel'
import {
  commitQuickAccessPromptEdit,
  hideQuickAccessRemote,
  quickAccessPromptBusy,
  quickAccessPromptOverrides,
  setQuickAccessRemoteTab,
  useQuickAccessRemoteChrome,
} from '@/composables/sidebar/useQuickAccessRemote'
import {
  LANDING_PROMPT_EXAMPLE_KEYS,
  LANDING_PROMPT_MAX_LENGTH,
  type LandingPromptExampleKey,
  quickAccessDiagramCards,
} from '@/config/landingQuickAccess'
import { useAuthStore, useDiagramStore, useSavedDiagramsStore, useUIStore } from '@/stores'
import type { DiagramType } from '@/types'

import './quickAccessRemote.css'

const route = useRoute()
const router = useRouter()
const { t, promptLanguage } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const diagramStore = useDiagramStore()
const savedDiagramsStore = useSavedDiagramsStore()
const uiStore = useUIStore()
const canvasDirty = useCanvasSessionDirty()
const generation = useLandingGenerateGraph({ t, notify })
const chrome = useQuickAccessRemoteChrome()
const editingKey = ref<LandingPromptExampleKey | null>(null)
const editDraft = ref('')
const runningPromptKey = ref<LandingPromptExampleKey | null>(null)
let promptRun = 0

function clearPromptRun(): void {
  promptRun += 1
  quickAccessPromptBusy.value = false
  runningPromptKey.value = null
}

const TAB_LABELS = {
  diagrams: 'sidebar.quickAccessRemote.tabDiagrams',
  prompts: 'sidebar.quickAccessRemote.tabPrompts',
} as const

function reloadBlankCanvas(diagramType: DiagramType): void {
  loadBlankCanvasForType({
    diagramType,
    force: true,
    setDiagramType: (type) => diagramStore.setDiagramType(type),
    clearActiveDiagram: () => {
      savedDiagramsStore.clearActiveDiagram()
    },
    loadDefaultTemplate: (type) => diagramStore.loadDefaultTemplate(type),
    setSelectedChartType: (name) => uiStore.setSelectedChartType(name),
    hasDiagramData: Boolean(diagramStore.data),
  })
}

async function openDiagram(diagramType: DiagramType): Promise<void> {
  const onCanvas = route.path === '/canvas'
  if (quickAccessReplaceNeedsConfirm(onCanvas, canvasDirty.value)) {
    if (!window.confirm(t('editor.unsavedChanges'))) {
      return
    }
  }
  generation.cancelInFlightGeneration()
  clearPromptRun()
  const blankTypeQuery = isNewCanvasTypeQuery(route.query)
    ? resolveDiagramTypeFromQuery(route.query)
    : null
  const action = resolveQuickAccessDiagramOpen({
    onCanvas,
    blankTypeQuery,
    targetType: diagramType,
  })
  if (action === 'reload') {
    reloadBlankCanvas(diagramType)
    return
  }
  const location = { path: '/canvas', query: { type: diagramType } }
  if (action === 'push') {
    await router.push(location).catch(() => undefined)
    return
  }
  await router.replace(location).catch(() => undefined)
}

function promptLabel(key: LandingPromptExampleKey): string {
  return resolveQuickAccessPromptText(key, t(key), quickAccessPromptOverrides.value)
}

function beginPromptEdit(key: LandingPromptExampleKey, event: MouseEvent): void {
  event.preventDefault()
  if (quickAccessPromptBusy.value || generation.isGenerating.value) {
    return
  }
  editingKey.value = key
  editDraft.value = promptLabel(key)
}

function focusPromptEditor(el: Element | ComponentPublicInstance | null): void {
  if (!(el instanceof HTMLTextAreaElement)) {
    return
  }
  el.focus()
  el.select()
}

function finishPromptEdit(key: LandingPromptExampleKey): void {
  if (editingKey.value !== key) {
    return
  }
  commitQuickAccessPromptEdit(key, editDraft.value, t(key))
  editingKey.value = null
}

function cancelPromptEdit(): void {
  editingKey.value = null
}

async function runPreset(key: LandingPromptExampleKey): Promise<void> {
  if (editingKey.value === key || quickAccessPromptBusy.value || generation.isGenerating.value) {
    return
  }
  const runId = ++promptRun
  runningPromptKey.value = key
  quickAccessPromptBusy.value = true
  try {
    await executeLandingPrompt({
      text: promptLabel(key),
      language: promptLanguage.value,
      t,
      notify,
      router,
      isAuthenticated: authStore.isAuthenticated,
      canApply: () => authStore.isAuthenticated,
      onAuthRequired: () => {
        authStore.handleTokenExpired(undefined, undefined)
      },
      generation,
    })
  } finally {
    if (promptRun === runId) {
      quickAccessPromptBusy.value = false
      runningPromptKey.value = null
    }
  }
}

onUnmounted(() => {
  clearPromptRun()
})
</script>

<template>
  <aside
    class="qa-remote"
    :class="{ 'is-dragging': chrome.dragging.value, 'is-resizing': chrome.resizing.value }"
    data-testid="quick-access-remote"
    role="dialog"
    :aria-label="t('sidebar.quickAccessRemote.ariaLabel')"
    :style="{
      left: `${chrome.left.value}px`,
      top: `${chrome.top.value}px`,
      width: `${chrome.width.value}px`,
      height: `${chrome.height.value}px`,
    }"
  >
    <div
      class="qa-remote__handle"
      @pointerdown="chrome.onHandlePointerDown"
      @pointermove="chrome.onHandlePointerMove"
      @pointerup="chrome.onHandlePointerUp"
      @pointercancel="chrome.onHandlePointerUp"
    >
      <span
        class="qa-remote__grip"
        aria-hidden="true"
      >
        <span /><span /><span /><span />
      </span>
      <span class="qa-remote__title">
        <I18nText
          k="sidebar.quickAccessRemote.ariaLabel"
          dense
        />
      </span>
      <button
        type="button"
        class="qa-remote__close"
        data-testid="quick-access-remote-close"
        :title="t('common.close')"
        :aria-label="t('common.close')"
        @pointerdown.stop
        @click.stop="hideQuickAccessRemote"
      >
        <X
          class="h-4 w-4"
          :stroke-width="2.2"
        />
      </button>
    </div>

    <div
      class="qa-remote__tabs"
      role="tablist"
    >
      <button
        v-for="tab in QUICK_ACCESS_REMOTE_TABS"
        :key="tab"
        type="button"
        class="qa-remote__tab"
        role="tab"
        :class="{ 'is-active': chrome.activeTab.value === tab }"
        :aria-selected="chrome.activeTab.value === tab"
        :data-testid="`quick-access-remote-tab-${tab}`"
        @click="setQuickAccessRemoteTab(tab)"
      >
        <LayoutGrid
          v-if="tab === 'diagrams'"
          class="mr-1 h-3.5 w-3.5"
          :stroke-width="2.2"
        />
        <Lightbulb
          v-else
          class="mr-1 h-3.5 w-3.5"
          :stroke-width="2.2"
        />
        <I18nText
          :k="TAB_LABELS[tab]"
          dense
        />
      </button>
    </div>

    <div class="qa-remote__body">
      <div
        v-if="chrome.activeTab.value === 'diagrams'"
        class="qa-remote__grid"
        role="group"
      >
        <button
          v-for="card in quickAccessDiagramCards"
          :key="card.type"
          type="button"
          class="qa-remote__tool"
          :data-testid="`quick-access-diagram-${card.type}`"
          @click="openDiagram(card.type)"
        >
          <span
            class="qa-remote__icon"
            aria-hidden="true"
          >
            <DiagramPreviewSvg :type="card.type" />
          </span>
          <span class="qa-remote__label">
            <I18nText
              :k="card.titleKey"
              dense
            />
          </span>
        </button>
      </div>
      <div
        v-else
        class="qa-remote__prompts"
      >
        <template
          v-for="key in LANDING_PROMPT_EXAMPLE_KEYS"
          :key="key"
        >
          <textarea
            v-if="editingKey === key"
            :ref="focusPromptEditor"
            v-model="editDraft"
            class="qa-remote__prompt qa-remote__prompt--edit"
            :maxlength="LANDING_PROMPT_MAX_LENGTH"
            :aria-label="t('sidebar.quickAccessRemote.editPrompt')"
            :data-testid="`quick-access-prompt-edit-${key}`"
            @blur="finishPromptEdit(key)"
            @keydown.esc.prevent="cancelPromptEdit"
            @contextmenu.prevent
          />
          <LlmPhaseRing
            v-else
            class="qa-remote__prompt-ring"
            :phase="generation.loadPhase.value"
            :active="runningPromptKey === key"
            border-radius="10px"
            streaming-variant="qwen"
            ring-padding="2px"
          >
            <button
              type="button"
              class="qa-remote__prompt"
              :class="{ 'is-running': runningPromptKey === key }"
              :disabled="quickAccessPromptBusy || generation.isGenerating.value"
              :title="t('sidebar.quickAccessRemote.editPrompt')"
              :data-testid="`quick-access-prompt-${key}`"
              @click="runPreset(key)"
              @contextmenu="beginPromptEdit(key, $event)"
            >
              {{ promptLabel(key) }}
            </button>
          </LlmPhaseRing>
        </template>
      </div>
    </div>

    <button
      type="button"
      class="qa-remote__resize"
      data-testid="quick-access-remote-resize"
      :aria-label="t('sidebar.quickAccessRemote.resize')"
      @pointerdown="chrome.onResizePointerDown"
      @pointermove="chrome.onResizePointerMove"
      @pointerup="chrome.onResizePointerUp"
      @pointercancel="chrome.onResizePointerUp"
    />
  </aside>
</template>
