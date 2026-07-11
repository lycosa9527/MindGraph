<script setup lang="ts">
/**
 * Mind map one-sentence panel — Kitty chat (text-only).
 */
import { computed } from 'vue'

import { ElAvatar } from 'element-plus'

import { Mic, Send } from '@lucide/vue'

import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'
import OneSentenceKittyAvatar from '@/components/canvas/OneSentenceKittyAvatar.vue'
import KittyBlackCatMascot from '@/components/kitty/KittyBlackCatMascot.vue'

import { useLanguage } from '@/composables'
import { useMindMapOneSentenceChat } from '@/composables/canvasToolbar/useMindMapOneSentenceChat'
import { useAuthStore } from '@/stores'
import { resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const authStore = useAuthStore()

const {
  draft,
  messages,
  isInputBlocked,
  kittyAgentState,
  asrListening,
  sendDraft,
  selectClarifyChoice,
  toggleMic,
  bindChatScroll,
} = useMindMapOneSentenceChat()

const userAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))

function setChatScrollEl(el: unknown): void {
  const node = el instanceof HTMLElement ? el : null
  bindChatScroll(node)
}

const inputDisabled = computed(
  () => isInputBlocked.value
)

const sendDisabled = computed(() => inputDisabled.value || !draft.value.trim())

function handleClose(): void {
  emit('close')
}

function handleSend(): void {
  void sendDraft()
}

function handleMic(): void {
  void toggleMic()
}

function handleInputKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    event.stopPropagation()
    if (!sendDisabled.value) {
      handleSend()
    }
  }
}
</script>

<template>
  <aside
    class="mind-map-one-sentence-panel pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-[22rem] flex-col rounded-2xl border border-slate-200/90 bg-white shadow-sm"
    :aria-label="t('canvas.mindMapSideToolbar.oneSentence')"
  >
    <header class="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-3 py-3">
      <h3 class="truncate text-sm font-semibold text-slate-800">
        {{ t('canvas.mindMapSideToolbar.oneSentence') }}
      </h3>
      <MindMapSidePanelCloseButton @close="handleClose" />
    </header>

    <div
      :ref="setChatScrollEl"
      class="one-sentence-chat-scroll flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 py-3"
    >
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="one-sentence-chat-row"
        :class="msg.role === 'user' ? 'one-sentence-chat-row--user' : 'one-sentence-chat-row--kitty'"
      >
        <div
          class="one-sentence-chat-message flex items-start gap-2"
          :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
        >
          <OneSentenceKittyAvatar
            v-if="msg.role === 'kitty'"
            :size="32"
          />
          <ElAvatar
            v-else
            :size="32"
            class="one-sentence-user-avatar shrink-0"
          >
            {{ userAvatar }}
          </ElAvatar>

          <div
            class="one-sentence-chat-bubble"
            :class="{
              'one-sentence-chat-bubble--user': msg.role === 'user',
              'one-sentence-chat-bubble--kitty': msg.role === 'kitty',
              'one-sentence-chat-bubble--streaming': msg.streaming,
              'one-sentence-chat-bubble--queued': msg.status === 'queued',
              'one-sentence-chat-bubble--failed': msg.status === 'failed',
            }"
            :data-request-status="msg.status || undefined"
          >
            <p class="one-sentence-chat-text">{{ msg.text }}</p>
            <p
              v-if="msg.role === 'user' && msg.status === 'queued'"
              class="one-sentence-chat-status"
            >
              {{ t('canvas.mindMapOneSentence.requestQueued') }}
            </p>
            <p
              v-else-if="msg.role === 'user' && msg.status === 'failed'"
              class="one-sentence-chat-status one-sentence-chat-status--failed"
            >
              {{ t('canvas.mindMapOneSentence.requestFailed') }}
            </p>
            <div
              v-if="msg.choices?.length && !msg.choicesConsumed"
              class="one-sentence-choices"
              role="group"
              :aria-label="t('canvas.mindMapOneSentence.clarifyChoices')"
            >
              <button
                v-for="choice in msg.choices"
                :key="`${msg.id}-${choice.index}`"
                type="button"
                class="one-sentence-choice"
                :class="`one-sentence-choice--${((choice.index - 1) % 3) + 1}`"
                :disabled="inputDisabled"
                @click="selectClarifyChoice(choice)"
              >
                <span class="one-sentence-choice-index">{{ choice.index }}</span>
                <span class="one-sentence-choice-label">{{ choice.label }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <footer class="one-sentence-footer shrink-0 bg-white px-3 pb-3 pt-2">
      <div class="one-sentence-input-stack">
        <div
          class="one-sentence-input-container"
          :class="{ 'one-sentence-input-container--disabled': inputDisabled }"
        >
          <KittyBlackCatMascot
            class="one-sentence-input-kitty"
            :agent-state="kittyAgentState"
          />

          <textarea
            v-model="draft"
            class="one-sentence-input-field"
            :placeholder="
              asrListening
                ? t('canvas.mindMapOneSentence.listeningPlaceholder')
                : t('canvas.mindMapOneSentence.inputPlaceholder')
            "
            rows="2"
            :disabled="inputDisabled"
            @keydown="handleInputKeydown"
          />
          <div class="one-sentence-input-actions">
            <button
              type="button"
              class="one-sentence-input-icon"
              :class="{ 'one-sentence-input-icon--recording': asrListening }"
              :aria-label="t('canvas.mindMapOneSentence.micButton')"
              :disabled="inputDisabled"
              @click="handleMic"
            >
              <Mic
                class="h-[18px] w-[18px]"
                :stroke-width="2"
              />
            </button>
            <button
              type="button"
              class="one-sentence-input-send"
              :disabled="sendDisabled"
              :aria-label="t('canvas.mindMapOneSentence.sendButton')"
              @click="handleSend"
            >
              <Send
                class="h-[18px] w-[18px]"
                :stroke-width="2"
              />
            </button>
          </div>
        </div>
      </div>
    </footer>
  </aside>
</template>

<style scoped>
.mind-map-one-sentence-panel {
  max-height: calc(100% - 1.5rem);
  overflow: hidden;
}

.one-sentence-footer {
  overflow: visible;
}

.one-sentence-input-stack {
  position: relative;
  padding-top: 1.5rem;
}

.one-sentence-input-kitty {
  position: absolute;
  left: 6px;
  bottom: calc(100% - 6px);
  z-index: 3;
  width: 2.75rem;
  max-height: 3.5rem;
  aspect-ratio: 272 / 344;
  margin: 0;
  pointer-events: none;
}

.one-sentence-input-kitty:deep(.black-cat-container) {
  width: 100%;
  height: 100%;
}

.one-sentence-input-kitty:deep(.black-cat-container .kitty-svg) {
  width: 100%;
  height: 100%;
  overflow: visible;
  filter: drop-shadow(0 2px 4px rgb(15 23 42 / 0.12));
}

.one-sentence-chat-row {
  width: 100%;
}

.one-sentence-chat-row--user {
  display: flex;
  justify-content: flex-end;
}

.one-sentence-chat-row--kitty {
  display: flex;
  justify-content: flex-start;
}

.one-sentence-chat-message {
  max-width: 100%;
}

.one-sentence-chat-row--user .one-sentence-chat-message {
  max-width: 88%;
}

.one-sentence-chat-row--kitty .one-sentence-chat-message {
  max-width: 92%;
}

.one-sentence-user-avatar {
  --el-avatar-bg-color: #fafafa;
  border: 2px solid #303133;
  font-size: 14px;
}

.one-sentence-chat-bubble {
  min-width: 0;
  padding: 8px 11px;
  border-radius: 14px;
  font-size: 12px;
  line-height: 1.55;
  word-break: break-word;
}

.one-sentence-chat-text {
  margin: 0;
  white-space: pre-wrap;
}

.one-sentence-chat-status {
  margin: 4px 0 0;
  font-size: 10px;
  line-height: 1.3;
  color: #64748b;
}

.one-sentence-chat-status--failed {
  color: #b45309;
}

.one-sentence-chat-bubble--queued {
  opacity: 0.92;
}

.one-sentence-chat-bubble--failed {
  box-shadow: inset 0 0 0 1px rgba(180, 83, 9, 0.25);
}

.one-sentence-choices {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.one-sentence-choice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    transform 0.15s ease;
}

.one-sentence-choice:hover:not(:disabled) {
  transform: translateY(-1px);
}

.one-sentence-choice:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.one-sentence-choice-index {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  min-width: 1.25rem;
  height: 1.25rem;
  padding: 0 4px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 650;
  line-height: 1;
}

.one-sentence-choice-label {
  min-width: 0;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Option 1 — teal */
.one-sentence-choice--1 {
  background: rgb(240 253 250);
  border-color: rgb(153 246 228);
  color: rgb(19 78 74);
}

.one-sentence-choice--1 .one-sentence-choice-index {
  background: rgb(45 212 191);
  color: rgb(19 78 74);
}

.one-sentence-choice--1:hover:not(:disabled) {
  background: rgb(204 251 241);
  border-color: rgb(94 234 212);
}

/* Option 2 — amber */
.one-sentence-choice--2 {
  background: rgb(255 251 235);
  border-color: rgb(253 230 138);
  color: rgb(120 53 15);
}

.one-sentence-choice--2 .one-sentence-choice-index {
  background: rgb(251 191 36);
  color: rgb(120 53 15);
}

.one-sentence-choice--2:hover:not(:disabled) {
  background: rgb(254 243 199);
  border-color: rgb(252 211 77);
}

/* Option 3 — rose */
.one-sentence-choice--3 {
  background: rgb(255 241 242);
  border-color: rgb(254 205 211);
  color: rgb(136 19 55);
}

.one-sentence-choice--3 .one-sentence-choice-index {
  background: rgb(251 113 133);
  color: rgb(136 19 55);
}

.one-sentence-choice--3:hover:not(:disabled) {
  background: rgb(255 228 230);
  border-color: rgb(253 164 175);
}

.one-sentence-chat-bubble--user {
  border-bottom-right-radius: 4px;
  background: #606266;
  color: white;
}

.one-sentence-chat-bubble--kitty {
  border-bottom-left-radius: 4px;
  border: 1px solid rgb(241 245 249);
  background: rgb(248 250 252);
  color: rgb(51 65 85);
}

.one-sentence-chat-bubble--streaming::after {
  content: '…';
  display: inline-block;
  margin-left: 2px;
  animation: one-sentence-stream-pulse 1s ease-in-out infinite;
}

.one-sentence-input-container {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 11px 12px;
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 16px;
  overflow: visible;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.one-sentence-input-container:focus-within {
  border-color: rgb(124 58 237);
  box-shadow: 0 0 0 3px rgb(124 58 237 / 0.12);
}

.one-sentence-input-container--disabled {
  opacity: 0.65;
}

.one-sentence-input-field {
  width: 100%;
  min-width: 0;
  min-height: 2.625rem;
  max-height: 5.5rem;
  padding: 2px 0;
  border: none;
  background: transparent;
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  color: rgb(30 41 59);
  outline: none;
  text-align: left;
}

.one-sentence-input-field::placeholder {
  color: #9ca3af;
}

.one-sentence-input-field:disabled {
  cursor: not-allowed;
}

.one-sentence-input-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.one-sentence-input-icon {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.one-sentence-input-icon:hover:not(:disabled) {
  color: #334155;
  background: #f1f5f9;
}

.one-sentence-input-icon--recording {
  color: #dc2626;
  background: #fef2f2;
}

.one-sentence-input-icon--active {
  color: #94a3b8;
}

.one-sentence-input-icon:disabled {
  color: #cbd5e1;
  cursor: not-allowed;
}

.one-sentence-input-send {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, rgb(124 58 237) 0%, rgb(79 70 229) 100%);
  color: white;
  cursor: pointer;
  transition:
    opacity 0.15s ease,
    transform 0.15s ease,
    background 0.15s ease;
}

.one-sentence-input-send:hover:not(:disabled) {
  transform: translateY(-1px);
}

.one-sentence-input-send:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
  transform: none;
}

@keyframes one-sentence-stream-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}
</style>
