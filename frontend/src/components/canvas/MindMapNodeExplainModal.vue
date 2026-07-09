<script setup lang="ts">
/**
 * Mind map node explain modal — Kitty chatroom-style helper.
 */
import { computed, watch } from 'vue'

import { ElDialog } from 'element-plus'

import { Send } from '@lucide/vue'

import OneSentenceKittyAvatar from '@/components/canvas/OneSentenceKittyAvatar.vue'
import KittyBlackCatMascot from '@/components/kitty/KittyBlackCatMascot.vue'

import { useLanguage } from '@/composables'
import type { KittyAgentState } from '@/composables/kitty/useKittyAgent'
import type { MindMapNodeExplainMessage } from '@/composables/mindMap/useMindMapNodeExplain'

const visible = defineModel<boolean>('visible', { required: true })
const draft = defineModel<string>('draft', { required: true })

const props = defineProps<{
  messages: MindMapNodeExplainMessage[]
  loading: boolean
  errorMessage: string | null
  kittyAgentState: KittyAgentState
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'send'): void
}>()

const { t } = useLanguage()

const inputDisabled = computed(() => props.loading)

const sendDisabled = computed(() => inputDisabled.value || !draft.value.trim())

const lastKittyMessageId = computed(() => {
  const kittyMessages = props.messages.filter((msg) => msg.role === 'kitty')
  return kittyMessages[kittyMessages.length - 1]?.id ?? null
})

function displayText(message: MindMapNodeExplainMessage): string {
  if (message.role === 'kitty' && message.streaming && !message.text) {
    return t('canvas.mindMapNodeExplain.thinking')
  }
  if (
    message.role === 'kitty' &&
    message.id === lastKittyMessageId.value &&
    props.errorMessage &&
    !message.text
  ) {
    return props.errorMessage
  }
  return message.text
}

watch(
  () => visible.value,
  (open) => {
    if (!open) {
      emit('close')
    }
  }
)

function handleClose(): void {
  visible.value = false
}

function handleSend(): void {
  if (sendDisabled.value) return
  emit('send')
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
  <ElDialog
    v-model="visible"
    :title="t('canvas.mindMapNodeExplain.title')"
    width="460px"
    append-to-body
    destroy-on-close
    class="mind-map-node-explain-modal"
    @close="handleClose"
  >
    <div
      class="mind-map-node-explain-chat flex max-h-[min(50vh,360px)] min-h-[180px] flex-col gap-3 overflow-y-auto px-0.5 py-1"
      role="log"
      :aria-label="t('canvas.mindMapNodeExplain.title')"
    >
      <div
        v-for="message in messages"
        :key="message.id"
        class="one-sentence-chat-row"
        :class="
          message.role === 'user' ? 'one-sentence-chat-row--user' : 'one-sentence-chat-row--kitty'
        "
      >
        <div
          class="one-sentence-chat-message flex items-start gap-2"
          :class="message.role === 'user' ? 'flex-row-reverse' : ''"
        >
          <OneSentenceKittyAvatar
            v-if="message.role === 'kitty'"
            :size="32"
          />
          <div
            class="one-sentence-chat-bubble"
            :class="{
              'one-sentence-chat-bubble--user': message.role === 'user',
              'one-sentence-chat-bubble--kitty': message.role === 'kitty',
              'one-sentence-chat-bubble--streaming': message.streaming,
              'one-sentence-chat-bubble--error':
                message.role === 'kitty' &&
                message.id === lastKittyMessageId &&
                !!errorMessage &&
                !message.text,
            }"
          >
            {{ displayText(message) }}
          </div>
        </div>
      </div>
    </div>

    <footer class="mind-map-node-explain-footer mt-3 shrink-0">
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
            :placeholder="t('canvas.mindMapNodeExplain.inputPlaceholder')"
            rows="1"
            :disabled="inputDisabled"
            @keydown="handleInputKeydown"
          />
          <button
            type="button"
            class="one-sentence-input-send"
            :disabled="sendDisabled"
            :aria-label="t('canvas.mindMapNodeExplain.sendButton')"
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
  </ElDialog>
</template>

<style scoped>
.mind-map-node-explain-footer {
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

.one-sentence-chat-row--user {
  display: flex;
  justify-content: flex-end;
}

.one-sentence-chat-row--kitty {
  display: flex;
  justify-content: flex-start;
}

.one-sentence-chat-row--user .one-sentence-chat-message {
  max-width: 88%;
}

.one-sentence-chat-row--kitty .one-sentence-chat-message {
  max-width: 92%;
}

.one-sentence-chat-bubble {
  max-width: 100%;
  border-radius: 14px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.one-sentence-chat-bubble--user {
  background: #eef2ff;
  color: #1e293b;
}

.one-sentence-chat-bubble--kitty {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.one-sentence-chat-bubble--streaming {
  border-color: #c7d2fe;
}

.one-sentence-chat-bubble--error {
  background: #fff7ed;
  border-color: #fdba74;
  color: #9a3412;
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

.dark .one-sentence-chat-bubble--user {
  background: #312e81;
  color: #e2e8f0;
}

.dark .one-sentence-chat-bubble--kitty {
  background: #1e293b;
  border-color: #334155;
  color: #e2e8f0;
}

.dark .one-sentence-chat-bubble--error {
  background: #431407;
  border-color: #9a3412;
  color: #fed7aa;
}
</style>
