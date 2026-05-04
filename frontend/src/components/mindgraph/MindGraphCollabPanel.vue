<script setup lang="ts">
/**
 * MindGraphCollabPanel — inline collaboration UI for MindGraph landing.
 *
 * Pill trigger opens an Element dropdown: 校内协同 / 加入图示編輯 (i18n).
 * Choosing an item opens a popover: org sessions list or passkey entry.
 *
 * Exposes ``prefillAndAutoJoin(rawCode)`` for QR-code join from URL query.
 */
import { onUnmounted, ref } from 'vue'

import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElPopover,
  ElTooltip,
} from 'element-plus'

import { ArrowLeft, ChevronDown, Loader2, RefreshCw, Users } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { authFetch } from '@/utils/api'

const ORG_REFRESH_INTERVAL_MS = 30_000

const { t } = useLanguage()
const notify = useNotifications()

// ── Popover state ─────────────────────────────────────────────────────────
const collabPopoverVisible = ref(false)
const collabPanelMode = ref<'organization' | 'network'>('network')

// ── Org sessions ──────────────────────────────────────────────────────────
let orgRefreshTimer: ReturnType<typeof setInterval> | null = null
const orgSessionsLoading = ref(false)
const orgSessions = ref<
  Array<{
    diagram_id: string
    title: string
    owner_name: string | null
    participant_count: number
  }>
>([])

// ── Network code input ────────────────────────────────────────────────────
// Safe charset: alphanumeric, uppercase only.
// Excluded: 0 (≈O), 1 (≈I/l), I (≈1/l), L (≈1/i), O (≈0)
const CODE_SAFE_RE = /[^2-9A-HJ-KM-NP-Z]/g

const joinCode = ref(['', '', '', '', '', ''])
const isJoining = ref(false)
const codeInputRefs = ref<(HTMLInputElement | null)[]>([])
let autoJoinTimeout: ReturnType<typeof setTimeout> | null = null

function sanitizeChar(raw: string): string {
  return raw.toUpperCase().replace(CODE_SAFE_RE, '')
}

function handleCharInput(index: number, event: Event) {
  const target = event.target as HTMLInputElement
  const cleaned = sanitizeChar(target.value)
  if (cleaned.length > 0) {
    joinCode.value[index] = cleaned[cleaned.length - 1]
    if (index < 5 && codeInputRefs.value[index + 1]) {
      codeInputRefs.value[index + 1]?.focus()
    }
  } else {
    joinCode.value[index] = ''
  }
  target.value = joinCode.value[index]
}

function handleKeyDown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace' && !joinCode.value[index] && index > 0) {
    codeInputRefs.value[index - 1]?.focus()
  }
}

function handlePaste(event: ClipboardEvent) {
  event.preventDefault()
  const pasted = event.clipboardData?.getData('text') || ''
  const chars = sanitizeChar(pasted).slice(0, 6)
  chars.split('').forEach((ch, index) => {
    if (index < 6) joinCode.value[index] = ch
  })
  const nextEmptyIndex = chars.length < 6 ? chars.length : 5
  codeInputRefs.value[nextEmptyIndex]?.focus()
}

function getFormattedCode(): string {
  const code = joinCode.value.join('')
  return code.length === 6 ? `${code.slice(0, 3)}-${code.slice(3, 6)}` : code
}

// ── Join handlers ─────────────────────────────────────────────────────────
async function joinWorkshop() {
  const code = getFormattedCode()
  if (code.length !== 7) {
    notify.warning(t('mindgraphLanding.codeIncomplete'))
    return
  }
  if (!/^[2-9A-HJ-KM-NP-Z]{3}-[2-9A-HJ-KM-NP-Z]{3}$/i.test(code)) {
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

async function fetchOrgSessions(showLoadingSpinner = true) {
  if (showLoadingSpinner) orgSessionsLoading.value = true
  try {
    const response = await authFetch('/api/workshop/organization/sessions', { method: 'GET' })
    if (response.ok) {
      const data = await response.json()
      orgSessions.value = data.sessions || []
    } else {
      notify.error(t('mindgraphLanding.loadOrgSessionsFailed'))
    }
  } catch {
    notify.error(t('mindgraphLanding.networkError'))
  } finally {
    if (showLoadingSpinner) orgSessionsLoading.value = false
  }
}

function stopOrgRefresh() {
  if (orgRefreshTimer !== null) {
    clearInterval(orgRefreshTimer)
    orgRefreshTimer = null
  }
}

async function openOrgPanel() {
  collabPanelMode.value = 'organization'
  orgSessions.value = []
  await fetchOrgSessions(true)
  stopOrgRefresh()
  orgRefreshTimer = setInterval(() => {
    void fetchOrgSessions(false)
  }, ORG_REFRESH_INTERVAL_MS)
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
      const code = data.workshop.code as string
      const enc = encodeURIComponent(code)
      notify.success(t('mindgraphLanding.joinedCollab', { title: data.workshop.title }))
      collabPopoverVisible.value = false
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

function onCollabDropdownCommand(command: string) {
  if (command !== 'organization' && command !== 'network') {
    return
  }
  collabPanelMode.value = command
  collabPopoverVisible.value = true
  if (command === 'organization') {
    void openOrgPanel()
  }
}

function closeCollabPopover() {
  collabPopoverVisible.value = false
  stopOrgRefresh()
}

/**
 * Pre-fill the network code input from ``rawCode`` and schedule an auto-join.
 * Called by MindGraphContainer when a ``join_workshop`` query param is present.
 */
function prefillAndAutoJoin(rawCode: string) {
  const chars = sanitizeChar(rawCode).slice(0, 6)
  chars.split('').forEach((ch, index) => {
    if (index < 6) joinCode.value[index] = ch
  })
  autoJoinTimeout = setTimeout(() => {
    autoJoinTimeout = null
    void joinWorkshop()
  }, 500)
}

onUnmounted(() => {
  if (autoJoinTimeout !== null) {
    clearTimeout(autoJoinTimeout)
    autoJoinTimeout = null
  }
  stopOrgRefresh()
})

defineExpose({ prefillAndAutoJoin })
</script>

<template>
  <ElPopover
    v-model:visible="collabPopoverVisible"
    :trigger="'manual' as 'click'"
    placement="bottom-end"
    width="min(360px, calc(100vw - 48px))"
    popper-class="collab-panel-popper"
    :hide-after="0"
    @click-outside="closeCollabPopover"
  >
    <template #reference>
      <div class="collab-trigger-wrap inline-flex">
        <ElDropdown
          trigger="click"
          placement="bottom-end"
          popper-class="collab-trigger-dropdown-popper"
          @command="onCollabDropdownCommand"
        >
          <span class="inline-flex">
            <ElTooltip
              :content="t('mindgraphLanding.collaborate')"
              placement="bottom"
            >
              <ElButton
                type="default"
                class="join-workshop-btn join-workshop-btn--pill"
                size="small"
                :aria-haspopup="true"
                :aria-label="t('mindgraphLanding.collaborate')"
              >
                <Users class="collab-trigger-icon-users" />
                <ChevronDown
                  class="collab-trigger-icon-chevron"
                  aria-hidden="true"
                />
              </ElButton>
            </ElTooltip>
          </span>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="organization">
                {{ t('mindgraphLanding.schoolCollab') }}
              </ElDropdownItem>
              <ElDropdownItem command="network">
                {{ t('mindgraphLanding.joinDiagramEdit') }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </template>

    <!-- Panel: within-org sessions list -->
    <div
      v-if="collabPanelMode === 'organization'"
      class="sw-panel"
    >
      <div class="sw-panel__header">
        <button
          type="button"
          class="sw-panel__back"
          @click="closeCollabPopover"
        >
          <ArrowLeft
            class="sw-panel__back-icon"
            aria-hidden="true"
          />
          {{ t('mindgraphLanding.dialogSchoolTitle') }}
        </button>
        <button
          type="button"
          class="sw-panel__refresh"
          :disabled="orgSessionsLoading"
          :aria-label="t('common.refresh')"
          @click="fetchOrgSessions(true)"
        >
          <RefreshCw
            class="sw-panel__refresh-icon"
            :class="{ 'sw-panel__refresh-icon--spinning': orgSessionsLoading }"
            aria-hidden="true"
          />
        </button>
      </div>

      <!-- Loading -->
      <div
        v-if="orgSessionsLoading"
        class="sw-panel__loading"
      >
        <Loader2
          class="sw-panel__loading-icon"
          aria-hidden="true"
        />
        <span>{{ t('common.loading') }}</span>
      </div>

      <!-- Empty state -->
      <p
        v-else-if="orgSessions.length === 0"
        class="sw-panel__empty"
      >
        {{ t('mindgraphLanding.orgSessionsEmpty') }}
      </p>

      <!-- Sessions list -->
      <ul
        v-else
        class="sw-sessions"
      >
        <li
          v-for="s in orgSessions"
          :key="s.diagram_id"
          class="sw-session-row"
        >
          <div class="sw-session-body">
            <div
              v-if="s.owner_name"
              class="sw-session-title"
            >
              {{ s.owner_name }}
            </div>
            <div :class="s.owner_name ? 'sw-session-owner' : 'sw-session-title'">{{ s.title }}</div>
          </div>
          <button
            type="button"
            class="sw-session-join"
            :disabled="isJoining"
            @click="joinOrgSession(s)"
          >
            <Loader2
              v-if="isJoining"
              class="sw-session-join__spinner"
              aria-hidden="true"
            />
            {{ t('mindgraphLanding.join') }}
          </button>
        </li>
      </ul>
    </div>

    <!-- Panel: cross-org passkey input -->
    <div
      v-else
      class="sw-panel sw-panel--join-code"
    >
      <div class="sw-panel__header">
        <button
          type="button"
          class="sw-panel__back"
          @click="closeCollabPopover"
        >
          <ArrowLeft
            class="sw-panel__back-icon"
            aria-hidden="true"
          />
          {{ t('mindgraphLanding.dialogSharedTitle') }}
        </button>
      </div>
      <p class="sw-panel__hint">{{ t('mindgraphLanding.sharedCodeHint') }}</p>
      <div class="code-input-container">
        <div class="code-input-boxes">
          <input
            v-for="(digit, index) in joinCode.slice(0, 3)"
            :id="`join-workshop-code-${index}`"
            :key="index"
            :ref="
              (el) => {
                codeInputRefs[index] = el as HTMLInputElement | null
              }
            "
            v-model="joinCode[index]"
            type="text"
            :name="`join-workshop-code-${index}`"
            :aria-label="`${index + 1} / 6`"
            inputmode="text"
            autocomplete="off"
            maxlength="1"
            class="code-input-box"
            @input="handleCharInput(index, $event)"
            @keydown="handleKeyDown(index, $event)"
            @paste="handlePaste"
          />
          <span class="code-dash">-</span>
          <input
            v-for="(digit, index) in joinCode.slice(3, 6)"
            :id="`join-workshop-code-${index + 3}`"
            :key="index + 3"
            :ref="
              (el) => {
                codeInputRefs[index + 3] = el as HTMLInputElement | null
              }
            "
            v-model="joinCode[index + 3]"
            type="text"
            :name="`join-workshop-code-${index + 3}`"
            :aria-label="`${index + 4} / 6`"
            inputmode="text"
            autocomplete="off"
            maxlength="1"
            class="code-input-box"
            @input="handleCharInput(index + 3, $event)"
            @keydown="handleKeyDown(index + 3, $event)"
            @paste="handlePaste"
          />
        </div>
      </div>
      <button
        type="button"
        class="sw-join-btn"
        :disabled="isJoining"
        @click="joinWorkshop"
      >
        <Loader2
          v-if="isJoining"
          class="sw-join-btn__spinner"
          aria-hidden="true"
        />
        {{ t('mindgraphLanding.join') }}
      </button>
    </div>
  </ElPopover>
</template>

<style scoped>
/* ── Pill trigger button ───────────────────────────────────────────────── */
.join-workshop-btn.join-workshop-btn--pill {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
  padding-left: 12px;
  padding-right: 12px;
  gap: 6px;
  display: inline-flex;
  align-items: center;
}

.collab-trigger-icon-users {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.collab-trigger-icon-chevron {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  opacity: 0.72;
}

.collab-trigger-wrap {
  vertical-align: middle;
}

/* ── Swiss panel shell ────────────────────────────────────────────────── */
.sw-panel {
  padding: 4px 0 2px;
}

.sw-panel__header {
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid #e7e5e4;
}

.sw-panel__back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #57534e;
  line-height: 1.25;
  transition: color 0.15s;
}

.sw-panel__back:hover {
  color: #1c1917;
}

.sw-panel__back-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

.sw-panel__refresh {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 4px;
  color: #a8a29e;
  transition:
    color 0.15s,
    background 0.15s;
}

.sw-panel__refresh:hover:not(:disabled) {
  color: #44403c;
  background: #f5f5f4;
}

.sw-panel__refresh:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.sw-panel__refresh-icon {
  width: 13px;
  height: 13px;
}

.sw-panel__refresh-icon--spinning {
  animation: spin 0.8s linear infinite;
}

.sw-panel__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 0;
  font-size: 13px;
  color: #a8a29e;
}

.sw-panel__loading-icon {
  width: 15px;
  height: 15px;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.sw-panel__empty {
  font-size: 12px;
  color: #a8a29e;
  text-align: center;
  padding: 20px 0 12px;
  margin: 0;
  line-height: 1.5;
}

.sw-panel__hint {
  font-size: 12px;
  color: #78716c;
  margin: 0 0 16px;
  line-height: 1.5;
}

.sw-panel--join-code {
  container-type: inline-size;
  container-name: collab-join-panel;
}

/* ── Org sessions list ────────────────────────────────────────────────── */
.sw-sessions {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 260px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sw-sessions::-webkit-scrollbar {
  width: 4px;
}

.sw-sessions::-webkit-scrollbar-thumb {
  background: #e7e5e4;
  border-radius: 2px;
}

.sw-session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f5f4;
  transition: background 0.15s;
}

.sw-session-row:hover {
  background: #e7e5e4;
}

.sw-session-body {
  min-width: 0;
  flex: 1;
}

.sw-session-title {
  font-size: 13px;
  font-weight: 500;
  color: #1c1917;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.sw-session-owner {
  font-size: 11px;
  font-weight: 400;
  color: #78716c;
  margin-top: 2px;
  letter-spacing: 0.01em;
}

.sw-session-join {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: #1c1917;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  line-height: 1.4;
}

.sw-session-join:hover:not(:disabled) {
  background: #292524;
}

.sw-session-join:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sw-session-join__spinner {
  width: 12px;
  height: 12px;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

/* ── Passkey join button ──────────────────────────────────────────────── */
.sw-join-btn {
  width: 100%;
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  background: #1c1917;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.sw-join-btn:hover:not(:disabled) {
  background: #292524;
}

.sw-join-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sw-join-btn__spinner {
  width: 14px;
  height: 14px;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

.code-input-container {
  width: 100%;
  min-width: 0;
  margin-block: 16px;
}

.code-input-boxes {
  display: grid;
  width: 100%;
  min-width: 0;
  align-items: center;
  justify-items: stretch;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.code-input-box {
  min-width: 0;
  width: 100%;
  aspect-ratio: 1;
  height: auto;
  padding: 0;
  box-sizing: border-box;
  text-align: center;
  font-weight: 600;
  line-height: 1;
  font-size: clamp(13px, 4vmin, 18px);
  border: 2px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #1f2937;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
  outline: none;
}

.code-input-box:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  background: #f9fafb;
}

.code-dash {
  display: flex;
  align-self: stretch;
  align-items: center;
  justify-content: center;
  margin: 0;
  justify-self: center;
  line-height: 1;
  font-size: clamp(12px, 3.5vmin, 17px);
  font-weight: 600;
  color: #6b7280;
  user-select: none;
}

@supports (container-type: inline-size) {
  .sw-panel--join-code .code-input-container {
    margin-block: clamp(12px, 4cqi, 22px);
  }

  .sw-panel--join-code .code-input-boxes {
    gap: clamp(4px, 2cqi, 10px);
  }

  .sw-panel--join-code .code-input-box {
    font-size: clamp(13px, 7cqi, 24px);
    border-radius: clamp(6px, 2.25cqi, 10px);
  }

  .sw-panel--join-code .code-input-box:focus {
    box-shadow: 0 0 0 clamp(2px, 1cqi, 4px) rgba(59, 130, 246, 0.14);
  }

  .sw-panel--join-code .code-dash {
    font-size: clamp(12px, 6cqi, 20px);
  }
}
</style>

<style>
/* Global: popper wrapper padding (teleported outside component scope) */
.collab-panel-popper.el-popper {
  padding: 12px !important;
  box-sizing: border-box;
  max-width: calc(100vw - 24px);
}

/* ── Swiss-style trigger dropdown (teleported) ────────────────────────── */
.collab-trigger-dropdown-popper.el-popper {
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden;
}

.collab-trigger-dropdown-popper .el-dropdown-menu {
  padding: 0;
  border: none;
  background: transparent;
}

.collab-trigger-dropdown-popper .el-dropdown-menu__item {
  display: flex;
  align-items: center;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  border-radius: 6px;
  line-height: 1.4;
  letter-spacing: 0.01em;
  transition:
    background 0.12s,
    color 0.12s;
}

.collab-trigger-dropdown-popper .el-dropdown-menu__item:hover,
.collab-trigger-dropdown-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4;
  color: #1c1917;
}

.collab-trigger-dropdown-popper .el-dropdown-menu__item:active {
  background: #e7e5e4;
}
</style>
