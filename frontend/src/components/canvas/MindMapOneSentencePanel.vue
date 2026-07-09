<script setup lang="ts">
/**
 * Mind map one-sentence panel — Kitty chat (text-only).
 */
import { computed } from 'vue'

import { ElAvatar } from 'element-plus'

import { Send } from '@lucide/vue'

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
  connecting,
  isInputBlocked,
  inputBlockReason,
  kittyAgentState,
  sendDraft,
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
            }"
          >
            {{ msg.text }}
          </div>
        </div>
      </div>
    </div>

    <footer class="one-sentence-footer shrink-0 bg-white px-3 pb-3 pt-2">
      <p
        v-if="inputBlockReason"
        class="one-sentence-block-banner mb-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs leading-snug text-amber-900"
        role="status"
      >
        {{ inputBlockReason }}
      </p>
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
            :placeholder="t('canvas.mindMapOneSentence.inputPlaceholder')"
            rows="1"
            :disabled="inputDisabled"
            @keydown="handleInputKeydown"
          />
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
  white-space: pre-wrap;
  word-break: break-word;
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
  align-items: flex-end;
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
  flex: 1;
  min-width: 0;
  min-height: 24px;
  max-height: 5.5rem;
  padding: 5px 0;
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

.one-sentence-input-send {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin-bottom: 1px;
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
