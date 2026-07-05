<script setup lang="ts">
/**
 * MindmateCollabPanel — shared AI chatroom entry (org browse + invite code).
 * Swiss-style trigger dropdown aligned with MindGraphCollabPanel.
 */
import { onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElPopover,
  ElTooltip,
} from 'element-plus'

import { ArrowLeft, ChevronDown, Loader2, RefreshCw, Users } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { applyThinkingCoinMutation, extractThinkingCoinsFooter } from '@/composables/auth/useThinkingCoinSync'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import type { MindmateCollabMessage } from '@/composables/mindmate/useMindmateCollab'
import { authFetch } from '@/utils/api'
import {
  formatMindmateCollabCode,
  trackLocalMindmateCollabSession,
} from '@/utils/mindmateCollabSessions'

const props = withDefaults(
  defineProps<{
    inConversation?: boolean
    conversationTitle?: string
    embedInPanel?: boolean
    getSeedMessages?: () => MindmateCollabMessage[]
  }>(),
  {
    inConversation: false,
    conversationTitle: '',
    embedInPanel: false,
    getSeedMessages: undefined,
  },
)

const emit = defineEmits<{
  (e: 'session-started', payload: {
    code: string
    visibility?: 'organization' | 'network'
    ownerUserId?: number
  }): void
}>()

const ORG_REFRESH_INTERVAL_MS = 30_000
const CODE_SAFE_RE = /[^2-9A-HJ-KM-NP-Z]/g

const { t } = useLanguage()
const notify = useNotifications()
const router = useRouter()
const { canUseOnlineCollab } = useSchoolTierFeatures()

const collabPopoverVisible = ref(false)
const collabPanelMode = ref<'organization' | 'network'>('network')
const orgSessionsLoading = ref(false)
const orgSessions = ref<
  Array<{
    session_id: string
    code: string
    title: string
    owner_name: string | null
    participant_count: number
  }>
>([])
const joinCode = ref(['', '', '', '', '', ''])
const isJoining = ref(false)
const codeInputRefs = ref<(HTMLInputElement | null)[]>([])
let orgRefreshTimer: ReturnType<typeof setInterval> | null = null
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

function navigateToRoom(code: string, sessionMeta?: Record<string, unknown>) {
  collabPopoverVisible.value = false
  stopOrgRefresh()
  const formatted = formatMindmateCollabCode(code)
  if (props.embedInPanel) {
    if (sessionMeta) {
      trackLocalMindmateCollabSession({
        session_id: String(sessionMeta.session_id || ''),
        code: String(sessionMeta.code || formatted),
        title: String(sessionMeta.title || props.conversationTitle || t('mindmate.collabPill')),
        owner_user_id: Number(sessionMeta.owner_user_id || 0),
        participant_count: Number(sessionMeta.participant_count || 1),
        visibility: String(sessionMeta.visibility || 'organization'),
        expires_at: (sessionMeta.expires_at as string | null) ?? null,
      })
    }
    emit('session-started', {
      code: formatted,
      visibility: (sessionMeta?.visibility as 'organization' | 'network') || 'organization',
      ownerUserId: Number(sessionMeta?.owner_user_id || 0) || undefined,
    })
    return
  }
  void router.push({ path: '/mindmate/collab', query: { code: formatted } })
}

async function joinByCode() {
  const code = getFormattedCode()
  if (code.length !== 7) {
    notify.warning(t('mindgraphLanding.codeIncomplete'))
    return
  }
  if (!/^[2-9A-HJ-KM-NP-Z]{3}-[2-9A-HJ-KM-NP-Z]{3}$/i.test(code)) {
    notify.warning(t('mindgraphLanding.codeFormatInvalid'))
    return
  }
  navigateToRoom(code)
}

async function startSeminar(visibility: 'organization' | 'network') {
  if (!props.inConversation) {
    return
  }
  isJoining.value = true
  try {
    const seedMessages = (props.getSeedMessages?.() ?? []).map((message) => ({
      role: message.role,
      content: message.content,
    }))
    const response = await authFetch('/api/mindmate/collab/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        visibility,
        title: props.conversationTitle || undefined,
        seed_messages: seedMessages,
      }),
    })
    if (response.ok) {
      const data = (await response.json()) as Record<string, unknown>
      applyThinkingCoinMutation(extractThinkingCoinsFooter(data))
      notify.success(t('mindmate.collabStarted'))
      navigateToRoom(String(data.code || ''), data)
    } else {
      const err = await response.json().catch(() => ({}))
      notify.error((err as { detail?: string }).detail || t('mindmate.collabStartFailed'))
    }
  } catch {
    notify.error(t('mindmate.collabStartFailed'))
  } finally {
    isJoining.value = false
  }
}

async function fetchOrgSessions(showSpinner = true) {
  if (showSpinner) orgSessionsLoading.value = true
  try {
    const response = await authFetch('/api/mindmate/collab/organization/sessions')
    if (response.ok) {
      const data = await response.json()
      orgSessions.value = data.sessions || []
    } else {
      notify.error(t('mindgraphLanding.loadOrgSessionsFailed'))
    }
  } catch {
    notify.error(t('mindgraphLanding.networkError'))
  } finally {
    if (showSpinner) orgSessionsLoading.value = false
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
  orgRefreshTimer = setInterval(() => void fetchOrgSessions(false), ORG_REFRESH_INTERVAL_MS)
}

function joinOrgSession(session: {
  session_id: string
  code: string
  title?: string
  owner_user_id?: number
  participant_count?: number
  visibility?: string
}) {
  navigateToRoom(session.code, {
    session_id: session.session_id,
    code: session.code,
    title: session.title,
    owner_user_id: session.owner_user_id,
    participant_count: session.participant_count,
    visibility: session.visibility || 'organization',
  })
}

function onCollabDropdownCommand(command: string) {
  if (command === 'launch-org') {
    void startSeminar('organization')
    return
  }
  if (command === 'launch-network') {
    void startSeminar('network')
    return
  }
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

function prefillAndAutoJoin(rawCode: string) {
  const chars = sanitizeChar(rawCode).slice(0, 6)
  if (props.inConversation && props.embedInPanel && chars.length === 6) {
    emit('session-started', { code: formatMindmateCollabCode(chars) })
    return
  }
  chars.split('').forEach((ch, index) => {
    if (index < 6) joinCode.value[index] = ch
  })
  collabPanelMode.value = 'network'
  collabPopoverVisible.value = true
  autoJoinTimeout = setTimeout(() => {
    autoJoinTimeout = null
    void joinByCode()
  }, 500)
}

onUnmounted(() => {
  stopOrgRefresh()
  if (autoJoinTimeout !== null) {
    clearTimeout(autoJoinTimeout)
    autoJoinTimeout = null
  }
})

defineExpose({ prefillAndAutoJoin })
</script>

<template>
  <ElPopover
    v-if="canUseOnlineCollab"
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
              :content="inConversation ? t('mindmate.collabLaunchTooltip') : t('mindgraphLanding.collaborate')"
              placement="bottom"
            >
              <ElButton
                type="default"
                class="join-workshop-btn join-workshop-btn--pill"
                size="small"
                :aria-haspopup="true"
                :aria-label="inConversation ? t('mindmate.collabLaunchTooltip') : t('mindgraphLanding.collaborate')"
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
              <template v-if="inConversation">
                <ElDropdownItem command="launch-org">
                  {{ t('mindmate.collabLaunchOrg') }}
                </ElDropdownItem>
                <ElDropdownItem command="launch-network">
                  {{ t('mindmate.collabLaunchNetwork') }}
                </ElDropdownItem>
                <ElDropdownItem
                  divided
                  command="organization"
                >
                  {{ t('mindmate.collabJoinOrgSeminar') }}
                </ElDropdownItem>
                <ElDropdownItem command="network">
                  {{ t('mindmate.collabJoinPublicSeminar') }}
                </ElDropdownItem>
              </template>
              <template v-else>
                <ElDropdownItem command="organization">
                  {{ t('mindmate.collabJoinOrgSeminar') }}
                </ElDropdownItem>
                <ElDropdownItem command="network">
                  {{ t('mindmate.collabJoinPublicSeminar') }}
                </ElDropdownItem>
              </template>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </template>

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

      <p
        v-else-if="orgSessions.length === 0"
        class="sw-panel__empty"
      >
        {{ t('mindmate.collabNoOrgSessions') }}
      </p>

      <ul
        v-else
        class="sw-sessions"
      >
        <li
          v-for="session in orgSessions"
          :key="session.session_id"
          class="sw-session-row"
        >
          <div class="sw-session-body">
            <div
              v-if="session.owner_name"
              class="sw-session-title"
            >
              {{ session.owner_name }}
            </div>
            <div :class="session.owner_name ? 'sw-session-owner' : 'sw-session-title'">
              {{ session.title }}
              <template v-if="session.owner_name">
                · {{ session.participant_count }} {{ t('mindmate.collabParticipants') }}
              </template>
            </div>
          </div>
          <button
            type="button"
            class="sw-session-join"
            :disabled="isJoining"
            @click="joinOrgSession(session)"
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
          {{ t('mindmate.collabSharedPanelTitle') }}
        </button>
      </div>

      <p class="sw-panel__hint">{{ t('mindmate.collabSharedCodeHint') }}</p>

      <div class="code-input-container">
        <div class="code-input-boxes">
          <input
            v-for="(_, index) in joinCode.slice(0, 3)"
            :id="`mindmate-collab-code-${index}`"
            :key="index"
            :ref="
              (el) => {
                codeInputRefs[index] = el as HTMLInputElement | null
              }
            "
            v-model="joinCode[index]"
            type="text"
            :name="`mindmate-collab-code-${index}`"
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
            v-for="(_, index) in joinCode.slice(3, 6)"
            :id="`mindmate-collab-code-${index + 3}`"
            :key="index + 3"
            :ref="
              (el) => {
                codeInputRefs[index + 3] = el as HTMLInputElement | null
              }
            "
            v-model="joinCode[index + 3]"
            type="text"
            :name="`mindmate-collab-code-${index + 3}`"
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
        @click="joinByCode"
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

.sw-panel {
  padding: 4px 0 2px;
}

.sw-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
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
  animation: mmc-collab-spin 0.8s linear infinite;
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
  animation: mmc-collab-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes mmc-collab-spin {
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
  margin: 0 0 12px;
  line-height: 1.5;
}

.sw-panel--join-code {
  container-type: inline-size;
  container-name: collab-join-panel;
}

.sw-start-btn {
  width: 100%;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  background: #fafaf9;
  color: #44403c;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.sw-start-btn:hover:not(:disabled) {
  background: #f5f5f4;
  border-color: #d6d3d1;
}

.sw-start-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sw-start-btn__spinner {
  width: 13px;
  height: 13px;
  animation: mmc-collab-spin 0.8s linear infinite;
  flex-shrink: 0;
}

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
  animation: mmc-collab-spin 0.8s linear infinite;
  flex-shrink: 0;
}

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
  animation: mmc-collab-spin 0.8s linear infinite;
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
.collab-panel-popper.el-popper {
  padding: 12px !important;
  box-sizing: border-box;
  max-width: calc(100vw - 24px);
}

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
  min-width: 100%;
}

.collab-trigger-dropdown-popper .el-dropdown-menu__item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  box-sizing: border-box;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  border-radius: 6px;
  line-height: 1.4;
  letter-spacing: 0.01em;
  text-align: center;
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
