<script setup lang="ts">
/**
 * Draggable tabbed remote opened from the account menu.
 * Diagrams open a blank canvas; prompts run the landing generator.
 */
import { type ComponentPublicInstance, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Home, LayoutGrid, Lightbulb, X } from '@lucide/vue'

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
  quickAccessReplaceNeedsConfirm,
  resolveQuickAccessDiagramOpen,
  resolveQuickAccessPromptText,
} from '@/composables/sidebar/quickAccessRemoteModel'
import {
  rememberQuickAccessSpec,
  resolveQuickAccessSpec,
} from '@/composables/sidebar/quickAccessSpecSync'
import {
  commitQuickAccessPromptEdit,
  hideQuickAccessRemote,
  playQuickAccessSpecReplay,
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
import {
  useAuthStore,
  useDiagramStore,
  useLLMResultsStore,
  useSavedDiagramsStore,
  useUIStore,
} from '@/stores'
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
const promptEditor = ref<HTMLTextAreaElement | null>(null)
const runningPromptKey = ref<LandingPromptExampleKey | null>(null)
const preloadingPromptKey = ref<LandingPromptExampleKey | null>(null)
let editBlurReadyAt = 0
let promptRun = 0

function clearPromptRun(): void {
  promptRun += 1
  quickAccessPromptBusy.value = false
  runningPromptKey.value = null
  preloadingPromptKey.value = null
}

function promptIsLocked(key: LandingPromptExampleKey): boolean {
  const preloading = preloadingPromptKey.value
  if (preloading != null) {
    return preloading !== key
  }
  return quickAccessPromptBusy.value || generation.isGenerating.value
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

async function goGallery(): Promise<void> {
  generation.cancelInFlightGeneration()
  clearPromptRun()
  if (route.path === '/mindgraph') {
    return
  }
  await router.push('/mindgraph').catch(() => undefined)
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
  if (quickAccessPromptBusy.value || generation.isGenerating.value || preloadingPromptKey.value) {
    return
  }
  editBlurReadyAt = Date.now() + 400
  editingKey.value = key
  editDraft.value = promptLabel(key)
}

function focusPromptEditor(el: Element | ComponentPublicInstance | null): void {
  if (!(el instanceof HTMLTextAreaElement)) {
    promptEditor.value = null
    return
  }
  promptEditor.value = el
  el.focus()
  el.select()
}

function keepPromptEditorOpen(key: LandingPromptExampleKey): void {
  const editor = promptEditor.value
  if (editor == null || editingKey.value !== key) {
    return
  }
  editor.focus()
}

function startPromptPreload(key: LandingPromptExampleKey): void {
  preloadingPromptKey.value = key
  void runPreset(key).finally(() => {
    if (preloadingPromptKey.value === key) {
      preloadingPromptKey.value = null
    }
  })
}

function finishPromptEdit(key: LandingPromptExampleKey): void {
  if (editingKey.value !== key) {
    return
  }
  if (Date.now() < editBlurReadyAt) {
    keepPromptEditorOpen(key)
    return
  }
  const fallback = t(key)
  const draft = editDraft.value
  commitQuickAccessPromptEdit(key, draft, fallback)
  editingKey.value = null
  promptEditor.value = null
  const text = promptLabel(key)
  if (text === fallback || resolveQuickAccessSpec(key, text, fallback)) {
    return
  }
  startPromptPreload(key)
}

function onPromptEditKeydown(key: LandingPromptExampleKey, event: KeyboardEvent): void {
  if (event.isComposing) {
    return
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    cancelPromptEdit()
    return
  }
  if (event.key !== 'Enter' || event.shiftKey) {
    return
  }
  event.preventDefault()
  editBlurReadyAt = 0
  finishPromptEdit(key)
}

function cancelPromptEdit(): void {
  editingKey.value = null
  promptEditor.value = null
}

async function replaySavedSpec(key: LandingPromptExampleKey, text: string): Promise<boolean> {
  const saved = resolveQuickAccessSpec(key, text, t(key))
  if (!saved) {
    return false
  }
  const run = generation.beginGeneration()
  try {
    const played = await playQuickAccessSpecReplay(
      (phase) => generation.setLoadPhase(phase),
      run.signal
    )
    if (!played || !generation.isCurrentRun(run.runId) || !authStore.isAuthenticated) {
      return true
    }
    generation.releaseRun(run)
    const diagramStore = useDiagramStore()
    diagramStore.clearHistory()
    const loaded = diagramStore.loadFromSpec(saved.spec, saved.diagramType)
    if (!loaded) {
      notify.error(t('diagramTemplate.generationFailed'))
      return true
    }
    useLLMResultsStore().reset()
    if (!generation.isCurrentRun(run.runId)) {
      return true
    }
    await router.push({ path: '/canvas' }).catch(() => undefined)
    return true
  } finally {
    generation.endGeneration(run)
  }
}

async function runPreset(key: LandingPromptExampleKey): Promise<void> {
  if (editingKey.value === key || quickAccessPromptBusy.value || generation.isGenerating.value) {
    return
  }
  const runId = ++promptRun
  runningPromptKey.value = key
  quickAccessPromptBusy.value = true
  const text = promptLabel(key)
  try {
    if (await replaySavedSpec(key, text)) {
      return
    }
    await executeLandingPrompt({
      text,
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
      onApplied: (applied) => {
        if (text !== t(key)) {
          void rememberQuickAccessSpec(key, { text, ...applied })
        }
      },
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
      <div
        class="qa-remote__tab-group"
        :class="{ 'is-active': chrome.activeTab.value === 'diagrams' }"
      >
        <button
          type="button"
          class="qa-remote__tab"
          role="tab"
          :aria-selected="chrome.activeTab.value === 'diagrams'"
          data-testid="quick-access-remote-tab-diagrams"
          @click="setQuickAccessRemoteTab('diagrams')"
        >
          <LayoutGrid
            class="mr-1 h-3.5 w-3.5"
            :stroke-width="2.2"
          />
          <I18nText
            :k="TAB_LABELS.diagrams"
            dense
          />
        </button>
        <button
          v-show="chrome.activeTab.value === 'diagrams'"
          type="button"
          class="qa-remote__home"
          data-testid="quick-access-remote-home"
          :title="t('canvas.ribbon.backToGallery')"
          :aria-label="t('canvas.ribbon.backToGallery')"
          @click="goGallery"
        >
          <Home
            class="h-3.5 w-3.5"
            :stroke-width="2.2"
          />
        </button>
      </div>
      <button
        type="button"
        class="qa-remote__tab"
        role="tab"
        :class="{ 'is-active': chrome.activeTab.value === 'prompts' }"
        :aria-selected="chrome.activeTab.value === 'prompts'"
        data-testid="quick-access-remote-tab-prompts"
        @click="setQuickAccessRemoteTab('prompts')"
      >
        <Lightbulb
          class="mr-1 h-3.5 w-3.5"
          :stroke-width="2.2"
        />
        <I18nText
          :k="TAB_LABELS.prompts"
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
            @keydown="onPromptEditKeydown(key, $event)"
            @contextmenu.prevent
          />
          <LlmPhaseRing
            v-else
            class="qa-remote__prompt-ring"
            :class="{ 'is-locked': promptIsLocked(key) }"
            :phase="generation.loadPhase.value"
            :active="runningPromptKey === key"
            border-radius="10px"
            streaming-variant="qwen"
            ring-padding="2px"
          >
            <button
              type="button"
              class="qa-remote__prompt"
              :class="{
                'is-running': runningPromptKey === key,
                'is-preloading': preloadingPromptKey === key,
              }"
              :disabled="promptIsLocked(key) || preloadingPromptKey === key"
              :aria-busy="preloadingPromptKey === key"
              :title="t('sidebar.quickAccessRemote.editPrompt')"
              :data-testid="`quick-access-prompt-${key}`"
              @click="runPreset(key)"
              @contextmenu="beginPromptEdit(key, $event)"
            >
              <span class="qa-remote__prompt-text">{{ promptLabel(key) }}</span>
              <span
                v-if="preloadingPromptKey === key"
                class="qa-remote__preload"
                data-testid="quick-access-prompt-preloading"
              >
                <I18nText k="sidebar.quickAccessRemote.preloadingSpec" />
              </span>
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
