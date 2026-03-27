<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import {
  Bold,
  ChevronRight,
  Code,
  CodeSquare,
  Italic,
  Link2,
  Paperclip,
  SendHorizonal,
  Smile,
  Strikethrough,
  X,
} from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'
import { apiUpload } from '@/utils/apiClient'

import EmojiPicker from './EmojiPicker.vue'

const { t } = useLanguage()
const store = useWorkshopChatStore()

const DRAFT_PREFIX = 'workshopChatDraft:'

const props = withDefaults(
  defineProps<{
    channelName?: string
    channelColor?: string
    topicName?: string
    dmPartnerName?: string
    mode?: 'channel' | 'topic' | 'dm'
    /** When false, show read-only hint (e.g. global announce topics for non-admins). */
    allowSend?: boolean
    /** localStorage key segment for autosave (narrow-scoped). */
    draftKey?: string
  }>(),
  { mode: 'channel', allowSend: true }
)

const emit = defineEmits<{
  send: [content: string]
  typing: []
  newConversation: []
  newDM: []
}>()

const content = ref('')
const isExpanded = ref(false)
const textareaRef = ref<HTMLTextAreaElement>()
const showEmojiPicker = ref(false)
const uploading = ref(false)
const fileInputRef = ref<HTMLInputElement>()
const showMentionPicker = ref(false)
const mentionQuery = ref('')

let draftSaveTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.draftKey,
  (key) => {
    if (!key) {
      content.value = ''
      return
    }
    const raw = localStorage.getItem(DRAFT_PREFIX + key)
    content.value = raw ?? ''
  },
  { immediate: true }
)

watch(content, () => {
  const key = props.draftKey
  if (!key) return
  if (draftSaveTimer != null) clearTimeout(draftSaveTimer)
  draftSaveTimer = setTimeout(() => {
    draftSaveTimer = null
    const trimmed = content.value.trim()
    if (trimmed) {
      localStorage.setItem(DRAFT_PREFIX + key, content.value)
    } else {
      localStorage.removeItem(DRAFT_PREFIX + key)
    }
  }, 400)
})

const mentionPickerResults = ref<OrgMember[]>([])
let mentionFetchTimer: ReturnType<typeof setTimeout> | null = null

function localMentionMatches(): OrgMember[] {
  const q = mentionQuery.value.trim().toLowerCase()
  return store.orgMembers
    .filter((m) => {
      const label = (m.name || `User ${m.id}`).toLowerCase()
      return label.includes(q)
    })
    .slice(0, 8)
}

watch(
  [mentionQuery, showMentionPicker],
  () => {
    if (!showMentionPicker.value) {
      mentionPickerResults.value = []
      return
    }
    if (mentionFetchTimer != null) {
      clearTimeout(mentionFetchTimer)
    }
    const raw = mentionQuery.value.trim()
    if (!raw) {
      mentionPickerResults.value = localMentionMatches()
      return
    }
    mentionFetchTimer = setTimeout(async () => {
      mentionFetchTimer = null
      mentionPickerResults.value = await store.searchOrgMembers(raw, 12)
    }, 200)
  },
  { flush: 'post' }
)

watch(
  () => store.orgMembers.length,
  () => {
    if (showMentionPicker.value && !mentionQuery.value.trim()) {
      mentionPickerResults.value = localMentionMatches()
    }
  }
)

const replyLabel = computed<string>(() => {
  if (props.mode === 'dm' && props.dmPartnerName) {
    return `${t('workshop.composeMessageTo')} ${props.dmPartnerName}`
  }
  if (props.mode === 'topic' && props.channelName && props.topicName) {
    return `${t('workshop.composeMessageTo')} #${props.channelName} > ${props.topicName}`
  }
  if (props.channelName) {
    return `${t('workshop.composeMessageTo')} #${props.channelName}`
  }
  return t('workshop.composeMessage')
})

const placeholderText = computed<string>(() => {
  if (props.mode === 'dm' && props.dmPartnerName) {
    return `${t('workshop.composeMessageTo')} ${props.dmPartnerName}…`
  }
  if (props.mode === 'topic' && props.channelName && props.topicName) {
    return `${t('workshop.composeMessageTo')} #${props.channelName} > ${props.topicName}…`
  }
  if (props.channelName) {
    return `${t('workshop.composeMessageTo')} #${props.channelName}…`
  }
  return t('workshop.typeMessagePlaceholder')
})

const showNewConversationBtn = computed<boolean>(() => props.mode !== 'dm')

function expand(): void {
  isExpanded.value = true
  setTimeout(() => textareaRef.value?.focus(), 50)
}

function collapse(): void {
  isExpanded.value = false
  showMentionPicker.value = false
}

function handleSend(): void {
  const trimmed = content.value.trim()
  if (!trimmed) return
  emit('send', trimmed)
  content.value = ''
  if (props.draftKey) {
    localStorage.removeItem(DRAFT_PREFIX + props.draftKey)
  }
}

function syncMentionPicker(): void {
  const el = textareaRef.value
  if (!el) return
  const pos = el.selectionStart ?? 0
  const text = content.value
  let at = pos - 1
  while (at >= 0 && text.charAt(at) !== '@') {
    if (/\s/.test(text.charAt(at))) {
      showMentionPicker.value = false
      return
    }
    at -= 1
  }
  if (at < 0 || text.charAt(at) !== '@') {
    showMentionPicker.value = false
    return
  }
  if (at > 0 && !/\s/.test(text.charAt(at - 1))) {
    showMentionPicker.value = false
    return
  }
  mentionQuery.value = text.slice(at + 1, pos)
  showMentionPicker.value = true
}

function insertMentionUser(member: OrgMember): void {
  const el = textareaRef.value
  if (!el) return
  const pos = el.selectionStart ?? content.value.length
  const text = content.value
  let at = pos - 1
  while (at >= 0 && text.charAt(at) !== '@') {
    if (/\s/.test(text.charAt(at))) return
    at -= 1
  }
  if (at < 0 || text.charAt(at) !== '@') return
  if (at > 0 && !/\s/.test(text.charAt(at - 1))) return
  const rawName = member.name || `User ${member.id}`
  const safeName = rawName.replace(/\*/g, '').trim() || `User ${member.id}`
  const insert = `@**${safeName}**`
  content.value = text.slice(0, at) + insert + text.slice(pos)
  showMentionPicker.value = false
  nextTick(() => {
    el.focus()
    const caret = at + insert.length
    el.setSelectionRange(caret, caret)
  })
}

function onTextareaInput(): void {
  handleInput()
  syncMentionPicker()
}

function handleKeydown(event: KeyboardEvent): void {
  if (showMentionPicker.value && mentionPickerResults.value.length > 0) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      insertMentionUser(mentionPickerResults.value[0])
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      showMentionPicker.value = false
      return
    }
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
  if (event.key === 'Escape') {
    collapse()
  }
}

let typingTimeout: ReturnType<typeof setTimeout> | null = null
function handleInput(): void {
  if (typingTimeout) clearTimeout(typingTimeout)
  typingTimeout = setTimeout(() => emit('typing'), 500)
}

function wrapSelection(before: string, after: string): void {
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  const text = content.value
  const selected = text.slice(start, end)
  const replacement = `${before}${selected || 'text'}${after}`
  content.value = text.slice(0, start) + replacement + text.slice(end)
  setTimeout(() => {
    el.focus()
    const newStart = start + before.length
    const newEnd = newStart + (selected ? selected.length : 4)
    el.setSelectionRange(newStart, newEnd)
  }, 10)
}

function insertBold(): void {
  wrapSelection('**', '**')
}
function insertItalic(): void {
  wrapSelection('*', '*')
}
function insertStrikethrough(): void {
  wrapSelection('~~', '~~')
}
function insertInlineCode(): void {
  wrapSelection('`', '`')
}

function insertCodeBlock(): void {
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart
  const text = content.value
  const block = '\n```\n\n```\n'
  content.value = text.slice(0, start) + block + text.slice(start)
  setTimeout(() => {
    el.focus()
    el.setSelectionRange(start + 5, start + 5)
  }, 10)
}

function insertLink(): void {
  wrapSelection('[', '](url)')
}

function handleEmojiSelect(_name: string, code: string): void {
  showEmojiPicker.value = false
  const el = textareaRef.value
  if (!el) return
  const start = el.selectionStart
  const text = content.value
  content.value = text.slice(0, start) + code + text.slice(start)
  setTimeout(() => {
    el.focus()
    el.setSelectionRange(start + code.length, start + code.length)
  }, 10)
}

function triggerFileUpload(): void {
  fileInputRef.value?.click()
}

async function handleFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await apiUpload('/api/chat/upload', formData)
    if (res.ok) {
      const data = await res.json()
      const isImage = file.type.startsWith('image/')
      const mdLink = isImage
        ? `![${data.filename}](${data.file_path})`
        : `[${data.filename}](${data.file_path})`

      const el = textareaRef.value
      const start = el?.selectionStart ?? content.value.length
      const text = content.value
      content.value = text.slice(0, start) + mdLink + text.slice(start)
    }
  } catch (err) {
    console.error('[ChatComposeBox] upload failed:', err)
  } finally {
    uploading.value = false
  }
}

const toolbarButtons = [
  { key: 'bold', icon: Bold, action: insertBold, titleKey: 'workshop.bold' },
  { key: 'italic', icon: Italic, action: insertItalic, titleKey: 'workshop.italic' },
  {
    key: 'strike',
    icon: Strikethrough,
    action: insertStrikethrough,
    titleKey: 'workshop.strikethrough',
  },
  { key: 'code', icon: Code, action: insertInlineCode, titleKey: 'workshop.code' },
  { key: 'codeBlock', icon: CodeSquare, action: insertCodeBlock, titleKey: 'workshop.codeBlock' },
  { key: 'link', icon: Link2, action: insertLink, titleKey: 'workshop.insertLink' },
]
</script>

<template>
  <div
    v-if="!allowSend"
    class="compose compose--readonly"
  >
    <div class="compose__read-only">
      {{ t('workshop.announceReadOnlyHint') }}
    </div>
  </div>
  <div
    v-else
    class="compose"
  >
    <div
      class="compose__box"
      :class="{ 'compose__box--open': isExpanded }"
    >
      <!-- Collapsed state — Zulip-style three-part bar -->
      <div
        v-if="!isExpanded"
        class="compose__collapsed"
      >
        <div class="compose__reply-container">
          <button
            class="compose__reply-btn"
            @click="expand"
          >
            {{ replyLabel }}
          </button>
          <button
            v-if="showNewConversationBtn"
            class="compose__new-conv-btn"
            @click="emit('newConversation')"
          >
            {{ t('workshop.startNewConversation') }}
          </button>
        </div>
        <button
          class="compose__new-dm-btn"
          @click="emit('newDM')"
        >
          {{ t('workshop.newDirectMessage') }}
        </button>
      </div>

      <!-- Expanded state -->
      <div
        v-else
        class="compose__expanded"
      >
        <!-- Recipient header row -->
        <div class="compose__recipient">
          <div class="compose__recipient-info">
            <template v-if="mode === 'dm'">
              <span class="compose__recipient-dm-label">{{ t('workshop.directMessage') }}:</span>
              <span class="compose__recipient-dm-name">{{ dmPartnerName }}</span>
            </template>
            <template v-else>
              <span
                class="compose__recipient-channel"
                :style="channelColor ? { color: channelColor } : undefined"
              >
                #
              </span>
              <span class="compose__recipient-channel-name">{{ channelName }}</span>
              <ChevronRight
                :size="12"
                class="compose__recipient-sep"
              />
              <span class="compose__recipient-topic">
                {{ topicName || t('workshop.generalChat') }}
              </span>
            </template>
          </div>
          <button
            class="compose__close-btn"
            :title="t('workshop.dismiss')"
            @click="collapse"
          >
            <X :size="14" />
          </button>
        </div>

        <div
          v-if="showMentionPicker && mentionPickerResults.length > 0"
          class="mention-picker"
        >
          <button
            v-for="m in mentionPickerResults"
            :key="m.id"
            type="button"
            class="mention-picker__item"
            @mousedown.prevent="insertMentionUser(m)"
          >
            <span class="mention-picker__avatar">{{ m.avatar || '👤' }}</span>
            <span class="mention-picker__name">{{ m.name || `User ${m.id}` }}</span>
          </button>
        </div>

        <textarea
          ref="textareaRef"
          v-model="content"
          class="compose__textarea"
          rows="3"
          :placeholder="placeholderText"
          @keydown="handleKeydown"
          @input="onTextareaInput"
          @keyup="syncMentionPicker"
          @click="syncMentionPicker"
        />

        <!-- Toolbar + send -->
        <div class="compose__toolbar">
          <div class="compose__fmt-group">
            <button
              v-for="btn in toolbarButtons"
              :key="btn.key"
              class="compose__tool-btn"
              :title="t(btn.titleKey)"
              @click="btn.action"
            >
              <component
                :is="btn.icon"
                :size="15"
              />
            </button>

            <span class="compose__divider" />

            <!-- File upload -->
            <button
              class="compose__tool-btn"
              :class="{ 'compose__tool-btn--uploading': uploading }"
              :title="t('workshop.uploadFile')"
              :disabled="uploading"
              @click="triggerFileUpload"
            >
              <Paperclip :size="15" />
            </button>
            <input
              ref="fileInputRef"
              type="file"
              class="compose__file-input"
              accept="image/*,.pdf,.doc,.docx,.txt"
              @change="handleFileChange"
            />

            <!-- Emoji -->
            <el-popover
              :visible="showEmojiPicker"
              placement="top-end"
              :width="260"
              trigger="click"
              :show-arrow="false"
              @update:visible="showEmojiPicker = $event"
            >
              <template #reference>
                <button
                  class="compose__tool-btn"
                  :title="t('workshop.emoji')"
                  @click="showEmojiPicker = !showEmojiPicker"
                >
                  <Smile :size="15" />
                </button>
              </template>
              <EmojiPicker @select="handleEmojiSelect" />
            </el-popover>
          </div>

          <button
            class="compose__send-btn"
            :disabled="!content.trim()"
            @click="handleSend"
          >
            <SendHorizonal :size="16" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.compose {
  flex-shrink: 0;
  padding: 0 0 8px;
}

.compose--readonly {
  padding: 0 14px 10px;
}

.compose__read-only {
  font-size: 13px;
  line-height: 1.45;
  color: hsl(0deg 0% 45%);
  padding: 10px 12px;
  border-radius: 8px;
  background: hsl(0deg 0% 0% / 4%);
  border: 1px solid hsl(0deg 0% 0% / 8%);
}

.compose__box {
  margin: 0 14px;
  border: 1px solid hsl(0deg 0% 0% / 12%);
  border-radius: 6px;
  background: hsl(0deg 0% 100%);
  transition:
    border-color 150ms ease,
    box-shadow 150ms ease;
}

.compose__box--open:focus-within {
  border-color: hsl(228deg 40% 68%);
  box-shadow: 0 0 0 2px hsl(228deg 56% 58% / 8%);
}

/* ── Collapsed ── */
.compose__collapsed {
  display: flex;
  align-items: stretch;
  gap: 4px;
  padding: 4px;
}

.compose__reply-container {
  display: flex;
  flex: 1;
  min-width: 0;
  border-radius: 4px;
  background: hsl(228deg 24% 96%);
  border: 1px solid hsl(228deg 18% 88%);
  transition:
    background 120ms ease,
    border-color 120ms ease;
}

.compose__reply-container:hover {
  background: hsl(228deg 20% 93%);
  border-color: hsl(228deg 18% 82%);
}

.compose__reply-btn {
  flex: 1;
  min-width: 0;
  padding: 5px 10px;
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  text-align: left;
  color: hsl(0deg 0% 28%);
  border: none;
  background: none;
  border-radius: 3px;
  cursor: pointer;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  line-height: 20px;
}

.compose__new-conv-btn {
  flex-shrink: 0;
  padding: 0 10px;
  margin: 1px;
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  color: hsl(0deg 0% 42%);
  border: none;
  background: none;
  border-radius: 3px;
  cursor: pointer;
  white-space: nowrap;
  line-height: 20px;
  transition:
    background 100ms ease,
    color 100ms ease;
}

.compose__new-conv-btn:hover {
  background: hsl(0deg 0% 0% / 6%);
  color: hsl(0deg 0% 15%);
}

.compose__new-dm-btn {
  flex-shrink: 0;
  padding: 5px 10px;
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  color: hsl(0deg 0% 28%);
  background: hsl(0deg 0% 96%);
  border: 1px solid hsl(0deg 0% 0% / 10%);
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  line-height: 20px;
  transition:
    background 100ms ease,
    border-color 100ms ease;
}

.compose__new-dm-btn:hover {
  background: hsl(0deg 0% 93%);
  border-color: hsl(0deg 0% 0% / 16%);
}

/* ── Expanded ── */
.compose__expanded {
  display: flex;
  flex-direction: column;
  position: relative;
}

.mention-picker {
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 100%;
  margin-bottom: 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 20;
  border-radius: 8px;
  border: 1px solid hsl(0deg 0% 0% / 12%);
  background: hsl(0deg 0% 100%);
  box-shadow: 0 4px 18px hsl(0deg 0% 0% / 12%);
  padding: 4px;
}

.mention-picker__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: none;
  border-radius: 6px;
  background: none;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  color: hsl(0deg 0% 20%);
}

.mention-picker__item:hover {
  background: hsl(228deg 40% 96%);
}

.mention-picker__avatar {
  flex-shrink: 0;
  font-size: 16px;
  line-height: 1;
}

.mention-picker__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Recipient header row */
.compose__recipient {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 5px 8px 4px 10px;
  border-bottom: 1px solid hsl(0deg 0% 0% / 6%);
  background: hsl(0deg 0% 98.5%);
  border-radius: 6px 6px 0 0;
}

.compose__recipient-info {
  display: flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  font-size: 13px;
  line-height: 20px;
  overflow: hidden;
}

.compose__recipient-channel {
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
}

.compose__recipient-channel-name {
  font-weight: 600;
  color: hsl(0deg 0% 22%);
  flex-shrink: 0;
}

.compose__recipient-sep {
  color: hsl(0deg 0% 55%);
  flex-shrink: 0;
  margin: 0 1px;
}

.compose__recipient-topic {
  color: hsl(0deg 0% 38%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compose__recipient-dm-label {
  font-weight: 600;
  color: hsl(0deg 0% 38%);
  flex-shrink: 0;
}

.compose__recipient-dm-name {
  font-weight: 600;
  color: hsl(0deg 0% 22%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compose__close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  background: none;
  border-radius: 3px;
  cursor: pointer;
  color: hsl(0deg 0% 48%);
  flex-shrink: 0;
  transition:
    background 100ms ease,
    color 100ms ease;
}

.compose__close-btn:hover {
  background: hsl(0deg 0% 0% / 8%);
  color: hsl(0deg 0% 15%);
}

.compose__textarea {
  display: block;
  width: 100%;
  min-height: 54px;
  max-height: 320px;
  padding: 10px 12px 6px;
  font-size: 14px;
  line-height: 1.55;
  color: hsl(0deg 0% 12%);
  border: none;
  outline: none;
  resize: vertical;
  background: transparent;
  font-family: inherit;
}

.compose__textarea::placeholder {
  color: hsl(0deg 0% 52%);
}

/* Toolbar */
.compose__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 5px;
  border-top: 1px solid hsl(0deg 0% 0% / 6%);
}

.compose__fmt-group {
  display: flex;
  align-items: center;
  gap: 1px;
}

.compose__tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  color: hsl(0deg 0% 42%);
  transition: all 100ms ease;
}

.compose__tool-btn:hover {
  background: hsl(0deg 0% 0% / 6%);
  color: hsl(0deg 0% 15%);
}

.compose__tool-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.compose__tool-btn--uploading {
  animation: compose-pulse 1.5s infinite;
}

@keyframes compose-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.compose__divider {
  width: 1px;
  height: 16px;
  background: hsl(0deg 0% 0% / 10%);
  margin: 0 5px;
}

.compose__file-input {
  display: none;
}

/* Send button */
.compose__send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 30px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  background: hsl(228deg 56% 58%);
  color: hsl(0deg 0% 100%);
  transition: all 120ms ease;
  box-shadow: 0 1px 2px hsl(228deg 56% 58% / 25%);
}

.compose__send-btn:hover:not(:disabled) {
  background: hsl(228deg 48% 48%);
  box-shadow: 0 2px 4px hsl(228deg 56% 58% / 30%);
}

.compose__send-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.compose__send-btn:disabled {
  opacity: 0.35;
  cursor: default;
  box-shadow: none;
}
</style>
