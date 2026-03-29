<script setup lang="ts">
/**
 * InternationalLanding - Google-homepage-inspired MindGraph landing page.
 * Centered prompt bar + large diagram cards. Avatar menu in top-right corner.
 */
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  ElAvatar,
  ElButton,
  ElDialog,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
} from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { KeyRound, Languages, LogIn, LogOut, Upload, UserRound } from 'lucide-vue-next'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import mindmateAvatar from '@/assets/mindmate-avatar-md.png'
import { AccountInfoModal, ChangePasswordModal } from '@/components/auth'
import LanguageSettingsModal from '@/components/settings/LanguageSettingsModal.vue'
import { useDiagramImport, useLanguage, useNotifications } from '@/composables'
import { useAuthStore, useDiagramStore, useLLMResultsStore, useUIStore } from '@/stores'
import type { SavedDiagram } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'

import DiagramPreviewSvg from './DiagramPreviewSvg.vue'
import IntlDiagramDropdown from './IntlDiagramDropdown.vue'
import IntlModuleGrid from './IntlModuleGrid.vue'

const MAX_PROMPT_LENGTH = 10000
const LANDING_LLM_MODELS = ['qwen', 'deepseek', 'kimi', 'doubao'] as const

const route = useRoute()
const router = useRouter()
const { t, promptLanguage } = useLanguage()
const { triggerImport } = useDiagramImport()
const authStore = useAuthStore()
const uiStore = useUIStore()
const diagramStore = useDiagramStore()
const notify = useNotifications()

const userAvatar = computed(() => {
  const raw = authStore.user?.avatar || '🐈‍⬛'
  return raw.startsWith('avatar_') ? '🐈‍⬛' : raw
})

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

const allDiagramTypes: Array<{
  titleKey: string
  descKey: string
  type: DiagramType
}> = [
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

onMounted(() => {
  document.addEventListener('mousedown', handleClickOutside)
})

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

function handleMindMateClick() {
  router.push('/mindmate')
}

function handleCardClick(item: { type: DiagramType }) {
  const zhName = TYPE_TO_ZH_NAME[item.type]
  if (zhName) uiStore.setSelectedChartType(zhName)
  router.push({ path: '/canvas', query: { type: item.type } })
}

// ── Collaboration dialogs ──

const showLanguageSettingsModal = ref(false)
const showAccountModal = ref(false)
const showPasswordModal = ref(false)
const showOrgSessionsDialog = ref(false)
const showSharedCodeDialog = ref(false)
const orgSessionsLoading = ref(false)
const orgSessions = ref<
  Array<{ diagram_id: string; title: string; owner_username: string; participant_count: number }>
>([])
const joinCode = ref(['', '', '', '', '', ''])
const isJoining = ref(false)
const codeInputRefs = ref<(HTMLInputElement | null)[]>([])

function handleDigitInput(index: number, event: Event) {
  const target = event.target as HTMLInputElement
  const value = target.value.replace(/\D/g, '')
  if (value.length > 0) {
    joinCode.value[index] = value[value.length - 1]
    if (index < 5 && codeInputRefs.value[index + 1]) {
      codeInputRefs.value[index + 1]?.focus()
    }
  } else {
    joinCode.value[index] = ''
  }
}

function handleKeyDown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace' && !joinCode.value[index] && index > 0) {
    codeInputRefs.value[index - 1]?.focus()
  }
}

function handlePaste(event: ClipboardEvent) {
  event.preventDefault()
  const digits = (event.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 6)
  digits.split('').forEach((digit, i) => {
    if (i < 6) joinCode.value[i] = digit
  })
  const nextIdx = digits.length < 6 ? digits.length : 5
  codeInputRefs.value[nextIdx]?.focus()
}

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
      showSharedCodeDialog.value = false
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

async function openOrgSessionsDialog() {
  showOrgSessionsDialog.value = true
  orgSessionsLoading.value = true
  orgSessions.value = []
  try {
    const response = await authFetch('/api/workshop/organization/sessions', { method: 'GET' })
    if (response.ok) {
      orgSessions.value = (await response.json()).sessions || []
    } else {
      notify.error(t('mindgraphLanding.loadOrgSessionsFailed'))
    }
  } catch {
    notify.error(t('mindgraphLanding.networkError'))
  } finally {
    orgSessionsLoading.value = false
  }
}

async function joinOrgSession(session: { diagram_id: string }) {
  isJoining.value = true
  try {
    const response = await authFetch('/api/workshop/join-organization', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diagram_id: session.diagram_id }),
    })
    if (response.ok) {
      const data = await response.json()
      const enc = encodeURIComponent(data.workshop.code as string)
      notify.success(t('mindgraphLanding.joinedCollab', { title: data.workshop.title }))
      showOrgSessionsDialog.value = false
      window.location.href = `/canvas?diagramId=${encodeURIComponent(data.workshop.diagram_id)}&join_workshop=${enc}`
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(error.detail || t('mindgraphLanding.joinFailed'))
    }
  } catch {
    notify.error(t('mindgraphLanding.networkError'))
  } finally {
    isJoining.value = false
  }
}

// ── Avatar menu commands ──

function handleAvatarCommand(cmd: string) {
  if (cmd === 'import') triggerImport()
  else if (cmd === 'language') showLanguageSettingsModal.value = true
  else if (cmd === 'account') showAccountModal.value = true
  else if (cmd === 'password') showPasswordModal.value = true
  else if (cmd === 'collab-org') openOrgSessionsDialog()
  else if (cmd === 'collab-shared') {
    showSharedCodeDialog.value = true
  } else if (cmd === 'logout') authStore.logout()
}

// ── Auto-join from QR query ──

onMounted(() => {
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
    <!-- Top-right module grid + avatar / login -->
    <div class="intl-top-right">
      <IntlModuleGrid />
      <template v-if="authStore.isAuthenticated">
        <ElDropdown
          trigger="click"
          placement="bottom-end"
          @command="handleAvatarCommand"
        >
          <ElAvatar
            :size="40"
            class="intl-avatar"
          >
            {{ userAvatar }}
          </ElAvatar>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="import">
                <Upload class="w-4 h-4 mr-2" />
                {{ t('mindgraphLanding.import') }}
              </ElDropdownItem>
              <ElDropdownItem
                command="language"
                divided
              >
                <Languages class="w-4 h-4 mr-2" />
                {{ t('sidebar.languageSettings') }}
              </ElDropdownItem>
              <ElDropdownItem command="account">
                <UserRound class="w-4 h-4 mr-2" />
                {{ t('auth.accountInfo') }}
              </ElDropdownItem>
              <ElDropdownItem command="password">
                <KeyRound class="w-4 h-4 mr-2" />
                {{ t('auth.changePassword') }}
              </ElDropdownItem>
              <ElDropdownItem
                command="logout"
                divided
              >
                <LogOut class="w-4 h-4 mr-2" />
                {{ t('auth.logout') }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </template>
      <template v-else>
        <ElButton
          type="primary"
          round
          @click="authStore.handleTokenExpired(undefined, undefined)"
        >
          <LogIn class="w-4 h-4 mr-1" />
          {{ t('auth.loginRegister') }}
        </ElButton>
      </template>
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
            v-for="item in allDiagramTypes"
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

          <!-- MindMate card -->
          <div
            class="intl-card intl-card--mindmate"
            @click="handleMindMateClick"
          >
            <div class="intl-card-preview intl-card-preview--avatar">
              <ElAvatar
                :src="mindmateAvatar"
                :size="80"
                shape="square"
                class="intl-mindmate-logo"
              />
            </div>
            <h3 class="intl-card-title">MindMate</h3>
            <p class="intl-card-desc">虚拟教研伙伴</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Org sessions dialog -->
    <ElDialog
      v-model="showOrgSessionsDialog"
      :title="t('mindgraphLanding.dialogSchoolTitle')"
      width="480px"
    >
      <div
        v-loading="orgSessionsLoading"
        class="min-h-[120px]"
      >
        <p
          v-if="!orgSessionsLoading && orgSessions.length === 0"
          class="text-gray-500 text-sm"
        >
          {{ t('mindgraphLanding.orgSessionsEmpty') }}
        </p>
        <ul
          v-else
          class="space-y-2 max-h-[360px] overflow-y-auto"
        >
          <li
            v-for="s in orgSessions"
            :key="s.diagram_id"
            class="flex items-center justify-between gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50/80"
          >
            <div class="min-w-0 flex-1">
              <div class="font-medium text-gray-900 truncate">{{ s.title }}</div>
              <div class="text-xs text-gray-500">
                {{ s.owner_username }} ·
                {{ t('mindgraphLanding.participantsOnline', { n: s.participant_count }) }}
              </div>
            </div>
            <ElButton
              type="primary"
              size="small"
              :loading="isJoining"
              @click="joinOrgSession(s)"
            >
              {{ t('mindgraphLanding.join') }}
            </ElButton>
          </li>
        </ul>
      </div>
    </ElDialog>

    <!-- Shared code dialog -->
    <ElDialog
      v-model="showSharedCodeDialog"
      :title="t('mindgraphLanding.dialogSharedTitle')"
      width="400px"
    >
      <div>
        <p class="mb-4 text-gray-600">{{ t('mindgraphLanding.sharedCodeHint') }}</p>
        <div class="flex justify-center my-5">
          <div class="flex items-center gap-2">
            <input
              v-for="(_digit, index) in joinCode.slice(0, 3)"
              :key="index"
              :ref="
                (el) => {
                  codeInputRefs[index] = el as HTMLInputElement | null
                }
              "
              v-model="joinCode[index]"
              type="text"
              inputmode="numeric"
              maxlength="1"
              class="code-box"
              @input="handleDigitInput(index, $event)"
              @keydown="handleKeyDown(index, $event)"
              @paste="handlePaste"
            />
            <span class="text-2xl font-semibold text-gray-500 select-none mx-1">-</span>
            <input
              v-for="(_digit, index) in joinCode.slice(3, 6)"
              :key="index + 3"
              :ref="
                (el) => {
                  codeInputRefs[index + 3] = el as HTMLInputElement | null
                }
              "
              v-model="joinCode[index + 3]"
              type="text"
              inputmode="numeric"
              maxlength="1"
              class="code-box"
              @input="handleDigitInput(index + 3, $event)"
              @keydown="handleKeyDown(index + 3, $event)"
              @paste="handlePaste"
            />
          </div>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <ElButton @click="showSharedCodeDialog = false">
            {{ t('mindgraphLanding.cancel') }}
          </ElButton>
          <ElButton
            type="primary"
            :loading="isJoining"
            @click="joinWorkshop"
          >
            {{ t('mindgraphLanding.join') }}
          </ElButton>
        </div>
      </div>
    </ElDialog>

    <LanguageSettingsModal v-model="showLanguageSettingsModal" />
    <AccountInfoModal
      v-model:visible="showAccountModal"
      @success="authStore.checkAuth()"
    />
    <ChangePasswordModal v-model:visible="showPasswordModal" />
  </div>
</template>

<style scoped>
.intl-landing {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color, #fff);
}

.intl-top-right {
  position: absolute;
  top: 16px;
  right: 20px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
}

.intl-avatar {
  cursor: pointer;
  background: #e7e5e4;
  font-size: 1.5rem;
  transition: box-shadow 0.2s;
}

.intl-avatar:hover {
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.25);
}

/* ── Scrollable content ── */

.intl-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 20px 60px;
}

/* ── Hero ── */

.intl-hero {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding-top: 48px;
  margin-bottom: 32px;
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
  margin: 0 auto 48px;
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

/* ── Gallery — same grey as /auth international (AuthLayout .auth-layout--minimal-intl) ── */

.intl-gallery {
  width: calc(100% + 40px);
  margin-left: -20px;
  margin-right: -20px;
  margin-top: 0;
  padding: 32px 30px 48px;
  box-sizing: border-box;
  background-color: rgb(249 250 251);
  color-scheme: light;
}

.intl-gallery .intl-section-title {
  max-width: 1400px;
  margin-left: auto;
  margin-right: auto;
  margin-bottom: 24px;
  padding-left: 10px;
  padding-right: 10px;
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

.intl-card-preview--avatar {
  background: var(--el-fill-color-lighter, #f8f9fa);
}

.intl-mindmate-logo {
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.intl-mindmate-logo :deep(img) {
  object-fit: cover;
}

.intl-card--mindmate:hover .intl-mindmate-logo {
  transform: scale(1.06);
  transition: transform 0.3s ease;
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

/* ── Code input boxes ── */

.code-box {
  width: 48px;
  height: 48px;
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  border: 2px solid #d1d5db;
  border-radius: 8px;
  background: var(--el-bg-color, #fff);
  color: var(--el-text-color-primary, #1f2937);
  outline: none;
  transition: all 0.2s;
}

.code-box:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15);
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

.dark .code-box {
  background: #1f2937;
  border-color: #4b5563;
  color: #f9fafb;
}

.dark .code-box:focus {
  border-color: #667eea;
  background: #111827;
}
</style>
