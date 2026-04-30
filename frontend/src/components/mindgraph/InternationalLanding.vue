<script setup lang="ts">
/**
 * InternationalLanding - Google-homepage-inspired MindGraph landing page.
 * Centered prompt bar + large diagram cards. Account actions live in the app sidebar.
 */
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElAvatar, ElButton, ElIcon, ElTooltip } from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { Check, Globe, PanelLeftOpen } from 'lucide-vue-next'

import { storeToRefs } from 'pinia'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore, useDiagramStore, useLLMResultsStore, useUIStore } from '@/stores'
import { useLiveTranslationStore } from '@/stores/liveTranslation'
import type { SavedDiagram } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'
import { TRANSLATE_LANGUAGES } from '@/utils/translateLanguages'

import DiagramPreviewSvg from './DiagramPreviewSvg.vue'
import IntlDiagramDropdown from './IntlDiagramDropdown.vue'
import MindGraphLanguageSwitcher from './MindGraphLanguageSwitcher.vue'

const MAX_PROMPT_LENGTH = 10000
const LANDING_LLM_MODELS = ['qwen', 'deepseek', 'kimi', 'doubao'] as const

const route = useRoute()
const router = useRouter()
const { t, promptLanguage } = useLanguage()
const authStore = useAuthStore()
const uiStore = useUIStore()
const diagramStore = useDiagramStore()
const notify = useNotifications()
const liveTranslationStore = useLiveTranslationStore()
const {
  enabled: translationOn,
  connecting: translationConnecting,
  targetLanguage: translationTargetLang,
} = storeToRefs(liveTranslationStore)

function handleTranslateCommand(command: string): void {
  if (command === '__toggle__') {
    liveTranslationStore.toggle()
  } else {
    liveTranslationStore.setTargetLanguage(command)
  }
}

const TYPE_TO_ZH_NAME: Record<DiagramType, string> = {
  circle_map: '圆圈图',
  bubble_map: '气泡图',
  double_bubble_map: '双气泡图',
  tree_map: '树形图',
  brace_map: '括号图',
  flow_map: '流程图',
  multi_flow_map: '复流程图',
  bridge_map: '桥形图',
  mindmap: '思维导图',
  mind_map: '思维导图',
  concept_map: '概念图',
  diagram: '图表',
}

type LandingDiagramCard = {
  titleKey: string
  descKey: string
  type: DiagramType
}

/** Thinking Maps®–style eight (circle through bridge); not mind map / concept map. */
const eightThinkingMapCards: LandingDiagramCard[] = [
  {
    titleKey: 'landing.diagramGrid.circle_map.title',
    descKey: 'landing.diagramGrid.circle_map.desc',
    type: 'circle_map',
  },
  {
    titleKey: 'landing.diagramGrid.bubble_map.title',
    descKey: 'landing.diagramGrid.bubble_map.desc',
    type: 'bubble_map',
  },
  {
    titleKey: 'landing.diagramGrid.double_bubble_map.title',
    descKey: 'landing.diagramGrid.double_bubble_map.desc',
    type: 'double_bubble_map',
  },
  {
    titleKey: 'landing.diagramGrid.tree_map.title',
    descKey: 'landing.diagramGrid.tree_map.desc',
    type: 'tree_map',
  },
  {
    titleKey: 'landing.diagramGrid.brace_map.title',
    descKey: 'landing.diagramGrid.brace_map.desc',
    type: 'brace_map',
  },
  {
    titleKey: 'landing.diagramGrid.flow_map.title',
    descKey: 'landing.diagramGrid.flow_map.desc',
    type: 'flow_map',
  },
  {
    titleKey: 'landing.diagramGrid.multi_flow_map.title',
    descKey: 'landing.diagramGrid.multi_flow_map.desc',
    type: 'multi_flow_map',
  },
  {
    titleKey: 'landing.diagramGrid.bridge_map.title',
    descKey: 'landing.diagramGrid.bridge_map.desc',
    type: 'bridge_map',
  },
]

const advancedDiagramCards: LandingDiagramCard[] = [
  {
    titleKey: 'landing.diagramGrid.mindmap.title',
    descKey: 'landing.diagramGrid.mindmap.desc',
    type: 'mindmap',
  },
  {
    titleKey: 'landing.diagramGrid.concept_map.title',
    descKey: 'landing.diagramGrid.concept_map.desc',
    type: 'concept_map',
  },
]

// ── Prompt generation ──

const promptText = ref('')
const isGenerating = ref(false)
const landingAbortControllers = ref<AbortController[]>([])

async function handlePromptSubmit() {
  const text = promptText.value.trim()
  if (!text) return
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  if (text.length > MAX_PROMPT_LENGTH) {
    notify.error(
      t('diagramTemplate.promptTooLong', { length: text.length, max: MAX_PROMPT_LENGTH })
    )
    return
  }

  landingAbortControllers.value = LANDING_LLM_MODELS.map(() => new AbortController())

  async function fetchWithModel(model: string, index: number) {
    const response = await authFetch('/api/generate_graph', {
      method: 'POST',
      body: JSON.stringify({ prompt: text, language: promptLanguage.value, llm: model }),
      signal: landingAbortControllers.value[index].signal,
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(err.detail || `HTTP ${response.status}`)
    }
    const result = await response.json()
    if (result.success && result.spec) {
      landingAbortControllers.value.forEach((c, j) => j !== index && c.abort())
      return { model, result }
    }
    throw new Error(result.error || 'Generation failed')
  }

  isGenerating.value = true
  try {
    const promises = LANDING_LLM_MODELS.map((model, i) => fetchWithModel(model, i))
    const { model: winningModel, result } = await Promise.any(promises)
    const finalType = result.diagram_type as DiagramType | undefined
    if (!finalType) throw new Error('No diagram type specified')

    diagramStore.clearHistory()
    const loaded = diagramStore.loadFromSpec(result.spec, finalType)
    if (loaded) {
      useLLMResultsStore().reset()
      notify.success(t('diagramTemplate.generated', { model: winningModel }))
      router.push({ path: '/canvas' })
    } else {
      throw new Error('Failed to load diagram data')
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AggregateError') {
      notify.error(t('diagramTemplate.allModelsFailed'))
    } else {
      const msg = error instanceof Error ? error.message : t('diagramTemplate.generationFailed')
      notify.error(msg)
    }
  } finally {
    isGenerating.value = false
  }
}

function handlePromptKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handlePromptSubmit()
  }
}

// ── Diagram dropdown ──

const showDropdown = ref(false)
const promptSectionRef = ref<HTMLElement | null>(null)

function handlePromptFocus() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  showDropdown.value = true
}

function handleClickOutside(event: MouseEvent) {
  if (!promptSectionRef.value) return
  if (!promptSectionRef.value.contains(event.target as Node)) {
    showDropdown.value = false
  }
}

function handleDiagramSelect(diagram: SavedDiagram) {
  showDropdown.value = false
  nextTick(() => {
    router.push({
      path: '/canvas',
      query: { diagramId: diagram.id.toString() },
    })
  })
}

onUnmounted(() => {
  document.removeEventListener('mousedown', handleClickOutside)
  landingAbortControllers.value.forEach((c) => c.abort())
  landingAbortControllers.value = []
})

// ── Card click ──

function handleCardClick(item: { type: DiagramType }) {
  const zhName = TYPE_TO_ZH_NAME[item.type]
  if (zhName) uiStore.setSelectedChartType(zhName)
  router.push({ path: '/canvas', query: { type: item.type } })
}

// ── Auto-join workshop from QR query ──

const joinCode = ref(['', '', '', '', '', ''])
const isJoining = ref(false)

function getFormattedCode(): string {
  const code = joinCode.value.join('')
  return code.length === 6 ? `${code.slice(0, 3)}-${code.slice(3, 6)}` : code
}

async function joinWorkshop() {
  const code = getFormattedCode()
  if (code.length !== 7) {
    notify.warning(t('mindgraphLanding.codeIncomplete'))
    return
  }
  if (!/^\d{3}-\d{3}$/.test(code)) {
    notify.warning(t('mindgraphLanding.codeFormatInvalid'))
    return
  }
  isJoining.value = true
  try {
    const response = await authFetch(`/api/workshop/join?code=${code}`, { method: 'POST' })
    if (response.ok) {
      const data = await response.json()
      notify.success(t('mindgraphLanding.joinedPresentation', { title: data.workshop.title }))
      const enc = encodeURIComponent(code)
      window.location.href = `/canvas?diagramId=${encodeURIComponent(data.workshop.diagram_id)}&join_workshop=${enc}`
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(error.detail || t('mindgraphLanding.joinPresentationFailed'))
    }
  } catch {
    notify.error(t('mindgraphLanding.networkErrorJoin'))
  } finally {
    isJoining.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside)
  const joinWorkshopCode = route.query.join_workshop as string | undefined
  if (joinWorkshopCode) {
    const digits = joinWorkshopCode.replace(/\D/g, '').slice(0, 6)
    digits.split('').forEach((digit, i) => {
      if (i < 6) joinCode.value[i] = digit
    })
    const newQuery = { ...route.query }
    delete newQuery.join_workshop
    router.replace({ query: newQuery })
    setTimeout(() => {
      joinWorkshop()
    }, 500)
  }
})
</script>

<template>
  <div class="intl-landing">
    <el-button
      v-if="uiStore.sidebarCollapsed"
      text
      circle
      size="small"
      class="intl-sidebar-toggle intl-sidebar-toggle--floating"
      :title="t('sidebar.expandSidebar')"
      :aria-label="t('sidebar.expandSidebar')"
      @click="uiStore.toggleSidebar()"
    >
      <PanelLeftOpen class="w-[18px] h-[18px]" />
    </el-button>
    <div class="intl-landing-chrome">
      <MindGraphLanguageSwitcher variant="floating" />
      <ElDropdown
        v-if="authStore.isAdmin"
        trigger="click"
        placement="bottom-end"
        popper-class="mindgraph-translate-popper"
        class="intl-translate-btn"
        @command="handleTranslateCommand"
      >
        <ElButton
          size="small"
          circle
          :loading="translationConnecting"
          :type="translationOn ? 'primary' : 'default'"
          :aria-pressed="translationOn"
          :aria-label="t('canvas.translation.aria')"
          class="intl-translate-btn__trigger"
        >
          <Globe class="w-[17px] h-[17px]" />
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu class="max-h-[min(420px,70vh)] overflow-y-auto">
            <ElDropdownItem command="__toggle__">
              <span class="translate-lang-row">
                <span class="translate-lang-label">
                  {{ translationOn ? t('canvas.translation.stop') : t('canvas.translation.start') }}
                </span>
              </span>
            </ElDropdownItem>
            <ElDivider style="margin: 4px 0;" />
            <ElDropdownItem
              v-for="lang in TRANSLATE_LANGUAGES"
              :key="lang.code"
              :command="lang.code"
            >
              <span class="translate-lang-row">
                <span class="translate-lang-label" dir="auto">{{ lang.label }}</span>
                <Check
                  v-if="translationTargetLang === lang.code"
                  class="translate-lang-check w-4 h-4 shrink-0 opacity-70"
                  aria-hidden="true"
                />
              </span>
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>
    <!-- Scrollable content -->
    <div class="intl-scroll">
      <!-- Hero: logo left, title + slogan right -->
      <div class="intl-hero">
        <div class="intl-logo-wrapper">
          <div class="intl-logo-inner">
            <ElAvatar
              :src="mindgraphLogo"
              alt="MindGraph"
              :size="96"
              shape="square"
              class="intl-logo"
            />
          </div>
        </div>
        <div class="intl-hero-text">
          <h1 class="intl-title">MindGraph</h1>
          <p class="intl-subtitle">{{ t('landing.international.subtitle') }}</p>
        </div>
      </div>

      <!-- Pill-shaped prompt bar + dropdown -->
      <div
        ref="promptSectionRef"
        class="intl-prompt-section"
      >
        <div
          class="intl-prompt-wrapper"
          :class="{ 'intl-prompt-generating': isGenerating }"
        >
          <input
            v-model="promptText"
            type="text"
            class="intl-prompt-input"
            :placeholder="t('landing.international.promptPlaceholder')"
            :disabled="isGenerating"
            @keydown="handlePromptKeydown"
            @focus="handlePromptFocus"
          />
          <button
            class="intl-prompt-send"
            :disabled="!promptText.trim() || isGenerating || !authStore.isAuthenticated"
            @click="handlePromptSubmit"
          >
            <ElIcon
              v-if="isGenerating"
              class="is-loading"
            >
              <Loading />
            </ElIcon>
            <svg
              v-else
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line
                x1="22"
                y1="2"
                x2="11"
                y2="13"
              />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>

        <!-- Saved-diagram dropdown -->
        <transition name="intl-dd-fade">
          <IntlDiagramDropdown
            v-if="showDropdown && authStore.isAuthenticated"
            class="intl-prompt-dropdown"
            @select="handleDiagramSelect"
          />
        </transition>
      </div>

      <!-- Diagram cards -->
      <div class="intl-gallery">
        <h2 class="intl-section-title">{{ t('landing.international.sectionTitle') }}</h2>
        <div class="intl-grid">
          <div
            v-for="item in eightThinkingMapCards"
            :key="item.type"
            class="intl-card"
            @click="handleCardClick(item)"
          >
            <div class="intl-card-preview">
              <DiagramPreviewSvg :type="item.type" />
            </div>
            <h3 class="intl-card-title">{{ t(item.titleKey) }}</h3>
            <p class="intl-card-desc">{{ t(item.descKey) }}</p>
          </div>
        </div>
        <h2 class="intl-section-title intl-section-title--secondary">
          {{ t('landing.international.advancedDiagramsTitle') }}
        </h2>
        <div class="intl-grid">
          <div
            v-for="item in advancedDiagramCards"
            :key="item.type"
            class="intl-card"
            @click="handleCardClick(item)"
          >
            <div class="intl-card-preview">
              <DiagramPreviewSvg :type="item.type" />
            </div>
            <h3 class="intl-card-title">{{ t(item.titleKey) }}</h3>
            <p class="intl-card-desc">{{ t(item.descKey) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.intl-sidebar-toggle {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
}

.intl-sidebar-toggle--floating {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 20;
}

.intl-landing-chrome {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 21;
  display: flex;
  align-items: center;
  gap: 8px;
}

.intl-landing-chrome :deep(.mindgraph-lang-switcher-root--floating) {
  position: static;
  top: auto;
  right: auto;
}

/* Translate button — white floating style when inactive */
.intl-translate-btn__trigger.el-button--default {
  --el-button-bg-color: #ffffff;
  --el-button-border-color: #e7e5e4;
  --el-button-hover-bg-color: #f5f5f4;
  --el-button-hover-border-color: #d6d3d1;
  --el-button-text-color: #44403c;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

/* Centered label with checkmark in the gutter */
.translate-lang-row {
  position: relative;
  display: block;
  box-sizing: border-box;
  width: 100%;
  padding: 5px 20px;
  min-height: 1.35em;
}

.translate-lang-label {
  display: block;
  width: 100%;
  text-align: center;
}

.translate-lang-check {
  position: absolute;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
}

.intl-landing {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  /* Cool neutral canvas — aligns with card preview (#f8f9fa) + Swiss clarity */
  background-color: rgb(248 250 252);
  color-scheme: light;
  /* Flow animation lives on the full viewport layer (not on .intl-scroll — see below) */
  background-image: linear-gradient(
    97deg,
    transparent 0%,
    transparent 32%,
    rgba(148, 163, 184, 0.32) 38%,
    rgba(255, 255, 255, 0.98) 46%,
    rgba(102, 126, 234, 0.26) 49.5%,
    rgba(237, 233, 254, 0.75) 50%,
    rgba(118, 75, 162, 0.12) 50.8%,
    rgba(248, 250, 252, 0.95) 53%,
    rgba(100, 116, 139, 0.28) 61%,
    transparent 72%,
    transparent 100%
  );
  background-size: 300% 100%;
  background-position: 0% 50%;
  background-repeat: no-repeat;
  /* Linear + negative delay: avoid slow ease at loop join and first paint */
  animation: intlScrollSheen 19s linear infinite;
  animation-delay: -6s;
}

.intl-landing::before,
.intl-landing::after {
  content: '';
  position: absolute;
  pointer-events: none;
  z-index: 0;
}

.intl-landing::before {
  top: -32%;
  left: -52%;
  width: 205%;
  height: 195%;
  background: linear-gradient(
    104deg,
    transparent 0%,
    transparent 26%,
    rgba(148, 163, 184, 0.14) 38%,
    rgba(102, 126, 234, 0.12) 50%,
    rgba(226, 232, 240, 0.78) 51%,
    rgba(118, 75, 162, 0.1) 52%,
    rgba(148, 163, 184, 0.16) 62%,
    transparent 100%
  );
  filter: blur(11px);
  transform: translateX(-6%) rotate(1.25deg);
  animation: intlScrollWindPrimary 28s linear infinite;
  animation-delay: -10s;
}

.intl-landing::after {
  top: -20%;
  right: -72%;
  width: 190%;
  height: 180%;
  background: linear-gradient(
    -68deg,
    transparent 0%,
    rgba(241, 245, 249, 0.95) 40%,
    rgba(255, 255, 255, 0.75) 49%,
    rgba(102, 126, 234, 0.1) 51%,
    rgba(100, 116, 139, 0.16) 58%,
    transparent 100%
  );
  filter: blur(9px);
  opacity: 1;
  animation: intlScrollWindSecondary 36s linear infinite;
  animation-delay: -18s;
}

.intl-scroll {
  position: relative;
  z-index: 1;
  flex: 1 1 0;
  width: 100%;
  min-height: 0;
  box-sizing: border-box;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0 20px 20px;
}

@keyframes intlScrollSheen {
  0%,
  100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

@keyframes intlScrollWindPrimary {
  0%,
  100% {
    transform: translateX(-6%) translateY(0) rotate(1.25deg);
  }
  50% {
    transform: translateX(38%) translateY(4%) rotate(0.9deg);
  }
}

@keyframes intlScrollWindSecondary {
  0%,
  100% {
    transform: translateX(8%) translateY(-5%);
  }
  50% {
    transform: translateX(-32%) translateY(7%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .intl-landing {
    animation: none;
    background-position: 50% 50%;
  }

  .intl-landing::before,
  .intl-landing::after {
    animation: none;
  }
}

/* ── Hero ── */

.intl-hero {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding-top: 48px;
  margin-bottom: 24px;
}

.intl-hero-text {
  display: flex;
  flex-direction: column;
}

@property --rainbow-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.intl-logo-wrapper {
  position: relative;
  width: 104px;
  height: 104px;
  border-radius: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.intl-logo-wrapper::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 20px;
  padding: 4px;
  --rainbow-angle: 0deg;
  background: conic-gradient(
    from var(--rainbow-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 45deg,
    #a8a29e 90deg,
    #667eea 135deg,
    #764ba2 180deg,
    #667eea 225deg,
    #78716c 270deg,
    #d6d3d1 315deg,
    #e7e5e4 360deg
  );
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: intl-rainbow 2.5s linear infinite;
}

@keyframes intl-rainbow {
  to {
    --rainbow-angle: 360deg;
  }
}

.intl-logo-inner {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--el-bg-color, #fff);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.intl-logo {
  border-radius: 16px;
}

.intl-logo :deep(img) {
  object-fit: cover;
}

.intl-title {
  font-size: 48px;
  font-weight: 700;
  color: var(--el-text-color-primary, #1c1917);
  margin: 0 0 4px;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

.intl-subtitle {
  font-size: 16px;
  color: var(--el-text-color-secondary, #78716c);
  margin: 0;
}

/* ── Prompt bar ── */

.intl-prompt-section {
  max-width: 680px;
  margin: 0 auto;
  padding: 0 20px;
  position: relative;
}

.intl-prompt-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 20px;
  right: 20px;
  z-index: 50;
}

/* Dropdown fade transition */
.intl-dd-fade-enter-active {
  transition: all 0.2s ease-out;
}

.intl-dd-fade-leave-active {
  transition: all 0.15s ease-in;
}

.intl-dd-fade-enter-from {
  opacity: 0;
  transform: translateY(-6px);
}

.intl-dd-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.intl-prompt-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--el-bg-color, #fff);
  border-radius: 50px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  transition: all 0.3s ease;
}

.intl-prompt-wrapper:focus-within {
  box-shadow: 0 12px 40px rgba(102, 126, 234, 0.25);
  transform: translateY(-2px);
}

.intl-prompt-generating {
  box-shadow:
    0 0 0 3px rgba(102, 126, 234, 0.4),
    0 8px 30px rgba(0, 0, 0, 0.12);
}

.intl-prompt-input {
  flex: 1;
  border: none;
  outline: none;
  padding: 18px 28px;
  font-size: 16px;
  font-family: inherit;
  background: transparent;
  color: var(--el-text-color-primary, #333);
  border-radius: 50px;
}

.intl-prompt-input::placeholder {
  color: var(--el-text-color-placeholder, #999);
}

.intl-prompt-send {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-right: 6px;
  color: #fff;
  flex-shrink: 0;
  transition: opacity 0.2s;
}

.intl-prompt-send:hover:not(:disabled) {
  opacity: 0.85;
}
.intl-prompt-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Gallery (background + wind live on .intl-scroll + .intl-landing) ── */

.intl-gallery {
  width: 100%;
  margin-top: 0;
  padding: 20px 10px 16px;
  box-sizing: border-box;
}

.intl-gallery .intl-section-title {
  max-width: 1400px;
  margin-left: auto;
  margin-right: auto;
  margin-bottom: 20px;
  padding-left: 10px;
  padding-right: 10px;
}

.intl-gallery .intl-section-title--secondary {
  margin-top: 40px;
}

.intl-gallery .intl-grid {
  max-width: 1400px;
  margin-left: auto;
  margin-right: auto;
}

.intl-section-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary, #333);
  margin: 0 0 24px 10px;
}

.intl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
  padding: 0 10px;
}

.intl-card {
  background: var(--el-bg-color, #fff);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  user-select: none;
  border: 2px solid transparent;
}

.intl-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
  border-color: #667eea;
}

.intl-card:active {
  transform: translateY(-4px);
}

.intl-card-preview {
  width: 100%;
  height: 150px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-lighter, #f8f9fa);
  border-radius: 8px;
  overflow: hidden;
}

.intl-card-preview :deep(.diagram-preview) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.intl-card-preview :deep(svg) {
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.intl-card-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary, #333);
  margin: 0 0 8px;
  text-align: center;
}

.intl-card-desc {
  font-size: 14px;
  color: var(--el-text-color-secondary, #666);
  text-align: center;
  margin: 0;
}

/* Hover animation on SVG previews — staggered pulse matching old gallery */
.intl-card:hover :deep(.diagram-svg .anim-node) {
  transform-origin: center;
  animation: intlNodePulse 2s ease-in-out infinite;
}

.intl-card:hover :deep(.anim-node:nth-child(1 of .anim-node)) {
  animation-delay: 0s;
}
.intl-card:hover :deep(.anim-node:nth-child(2 of .anim-node)) {
  animation-delay: 0.2s;
}
.intl-card:hover :deep(.anim-node:nth-child(3 of .anim-node)) {
  animation-delay: 0.3s;
}
.intl-card:hover :deep(.anim-node:nth-child(4 of .anim-node)) {
  animation-delay: 0.4s;
}
.intl-card:hover :deep(.anim-node:nth-child(5 of .anim-node)) {
  animation-delay: 0.5s;
}
.intl-card:hover :deep(.anim-node:nth-child(6 of .anim-node)) {
  animation-delay: 0.6s;
}
.intl-card:hover :deep(.anim-node:nth-child(7 of .anim-node)) {
  animation-delay: 0.7s;
}
.intl-card:hover :deep(.anim-node:nth-child(8 of .anim-node)) {
  animation-delay: 0.8s;
}

@keyframes intlNodePulse {
  0%,
  20%,
  100% {
    transform: scale(1);
  }
  10% {
    transform: scale(1.3);
  }
}

/* ── Mobile ── */

@media (max-width: 768px) {
  .intl-hero {
    padding-top: 64px;
    gap: 16px;
  }
  .intl-title {
    font-size: 28px;
  }
  .intl-subtitle {
    font-size: 13px;
  }
  .intl-logo-wrapper {
    width: 72px;
    height: 72px;
  }
  .intl-logo-inner {
    width: 64px;
    height: 64px;
  }
  .intl-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    padding: 0 8px;
  }
  .intl-card {
    padding: 16px 12px;
  }
  .intl-card-preview {
    height: 100px;
    margin-bottom: 12px;
  }
  .intl-card-title {
    font-size: 16px;
    margin-bottom: 4px;
  }
  .intl-card-desc {
    font-size: 12px;
  }
  .intl-section-title {
    font-size: 20px;
  }
}

/* ── Dark mode ── */

.dark .intl-prompt-wrapper {
  background: var(--el-bg-color, #1c1917);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
}

.dark .intl-card {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.dark .intl-card:hover {
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.45);
}
</style>

<!-- Teleported translate dropdown — width lives on popper, not scoped subtree -->
<style>
.mindgraph-translate-popper.el-popper {
  max-width: min(210px, calc(100vw - 24px));
}

.mindgraph-translate-popper .el-dropdown-menu {
  width: min(210px, calc(100vw - 24px));
  padding: 4px 0;
}

.mindgraph-translate-popper .el-dropdown-menu__item {
  padding: 6px 8px;
}
</style>
