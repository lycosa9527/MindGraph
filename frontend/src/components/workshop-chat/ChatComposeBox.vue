<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { ChevronRight, X } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useRenderedMarkdown } from '@/composables/core/useRenderedMarkdown'
import { type OrgMember, useWorkshopChatStore } from '@/stores/workshopChat'
import { apiUpload } from '@/utils/apiClient'
import { stripMindmateDiagramIdComments } from '@/utils/mindmateDiagramMeta'
import {
  type ComposeFormatType,
  applyComposeFormat,
  insertTextAtCursor,
} from '@/utils/workshopComposeFormat'

import './ChatComposeBox.css'
import WorkshopComposeToolbar from './WorkshopComposeToolbar.vue'
import WorkshopDiagramPicker from './WorkshopDiagramPicker.vue'

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
    allowSend?: boolean
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
const isPreview = ref(false)
const textareaRef = ref<HTMLTextAreaElement>()
const showEmojiPicker = ref(false)
const showDiagramPicker = ref(false)
const uploading = ref(false)
const fileInputRef = ref<HTMLInputElement>()
const showMentionPicker = ref(false)
const mentionQuery = ref('')

const { html: previewHtml } = useRenderedMarkdown(() =>
  stripMindmateDiagramIdComments(content.value)
)

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
  isPreview.value = false
  showMentionPicker.value = false
  showEmojiPicker.value = false
}

function handleSend(): void {
  const trimmed = content.value.trim()
  if (!trimmed) return
  emit('send', trimmed)
  content.value = ''
  isPreview.value = false
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

function applyToTextarea(result: { text: string; start: number; end: number }): void {
  content.value = result.text
  nextTick(() => {
    const el = textareaRef.value
    if (!el) return
    el.focus()
    el.setSelectionRange(result.start, result.end)
  })
}

function handleFormat(type: ComposeFormatType): void {
  if (isPreview.value) return
  const el = textareaRef.value
  const start = el?.selectionStart ?? content.value.length
  const end = el?.selectionEnd ?? start
  applyToTextarea(applyComposeFormat(content.value, start, end, type))
}

function handleEmojiSelect(_name: string, code: string): void {
  showEmojiPicker.value = false
  const el = textareaRef.value
  const start = el?.selectionStart ?? content.value.length
  const end = el?.selectionEnd ?? start
  applyToTextarea(insertTextAtCursor(content.value, start, end, code))
}

function handleDiagramInsert(markdown: string): void {
  const el = textareaRef.value
  const start = el?.selectionStart ?? content.value.length
  const end = el?.selectionEnd ?? start
  const prefix = start > 0 && content.value.charAt(start - 1) !== '\n' ? '\n' : ''
  applyToTextarea(insertTextAtCursor(content.value, start, end, `${prefix}${markdown}\n`))
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
      const data = (await res.json()) as { filename?: string; file_path?: string }
      if (!data.file_path) return
      const isImage = file.type.startsWith('image/')
      const mdLink = isImage
        ? `![${data.filename || file.name}](${data.file_path})`
        : `[${data.filename || file.name}](${data.file_path})`
      const el = textareaRef.value
      const start = el?.selectionStart ?? content.value.length
      const end = el?.selectionEnd ?? start
      applyToTextarea(insertTextAtCursor(content.value, start, end, mdLink))
    }
  } catch (err) {
    console.error('[ChatComposeBox] upload failed:', err)
  } finally {
    uploading.value = false
  }
}
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

      <div
        v-else
        class="compose__expanded"
      >
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

        <div
          v-if="isPreview"
          class="compose__preview"
        >
          <p
            v-if="!content.trim()"
            class="compose__preview-empty"
          >
            {{ t('workshop.previewEmpty') }}
          </p>
          <div
            v-else
            v-html="previewHtml"
          />
        </div>
        <textarea
          v-else
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

        <input
          ref="fileInputRef"
          type="file"
          class="compose__file-input"
          accept="image/*,.pdf,.doc,.docx,.txt"
          @change="handleFileChange"
        />

        <WorkshopComposeToolbar
          :can-send="Boolean(content.trim())"
          :preview-on="isPreview"
          :format-disabled="isPreview"
          :uploading="uploading"
          :show-emoji-picker="showEmojiPicker"
          @format="handleFormat"
          @toggle-preview="isPreview = !isPreview"
          @upload="triggerFileUpload"
          @update:show-emoji-picker="showEmojiPicker = $event"
          @emoji="handleEmojiSelect"
          @open-diagram="showDiagramPicker = true"
          @send="handleSend"
        />
      </div>
    </div>
    <WorkshopDiagramPicker
      :visible="showDiagramPicker"
      @update:visible="showDiagramPicker = $event"
      @insert="handleDiagramInsert"
    />
  </div>
</template>
