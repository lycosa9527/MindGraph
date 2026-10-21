<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ElButton, ElIcon, ElInput } from 'element-plus'

import { Close, VideoPause } from '@element-plus/icons-vue'

import { ArrowRight, Mic, Paperclip, Send } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import UserAvatarGlyph from '@/components/common/UserAvatarGlyph.vue'
import MindmateSeminarBriefForm from '@/components/mindmate/MindmateSeminarBriefForm.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  seminarComposerAttachments,
  seminarComposerCitations,
} from '@/composables/mindmate/mindmateSeminarChrome'
import type { MindMateFile } from '@/composables/mindmate/useMindMate'
import { useMindmateMentionPicker } from '@/composables/mindmate/useMindmateMentionPicker'
import { useAuthStore } from '@/stores/auth'
import {
  MINDMATE_COMPOSER_FILE_ACCEPT,
  isMindmateComposerUploadableFile,
} from '@/utils/mindmateComposerUpload'
import type { MindmateMentionCandidate } from '@/utils/mindmateMention'
import type { SeminarBrief } from '@/utils/mindmateSeminarBrief'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

import SuggestionBubbles from '../../common/SuggestionBubbles.vue'

const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
    inputText?: string
    isLoading?: boolean
    isStreaming?: boolean
    isUploading?: boolean
    pendingFiles?: MindMateFile[]
    showSuggestions?: boolean
    /** Home screen mode. Seminar replaces starter prompts with room actions. */
    homeMode?: 'dialogue' | 'seminar'
    /** When false, hide file upload button (e.g. canvas mini-mindmate) */
    showFileUpload?: boolean
    /** Custom placeholder (default: question prompt) */
    placeholder?: string
    /** Max length for input (e.g. 1000 for comments) */
    maxlength?: number
    /** Seminar composer: @MindMate and org contacts. */
    enableMentions?: boolean
    mentionCandidates?: MindmateMentionCandidate[]
    /** Group seminar: chips sit under the field, send stays on the right. */
    seminarComposer?: boolean
    /** @MindMate tag shown inside the seminar field. */
    seminarMindmateTag?: boolean
    /** @mindgraph tag shown inside the seminar field. */
    seminarMindgraphTag?: boolean
    seminarAgentName?: string
    seminarVoiceRecording?: boolean
  }>(),
  {
    mode: 'panel',
    inputText: '',
    isLoading: false,
    isStreaming: false,
    isUploading: false,
    pendingFiles: () => [],
    showSuggestions: false,
    homeMode: 'dialogue',
    showFileUpload: true,
    placeholder: '',
    maxlength: undefined,
    enableMentions: false,
    mentionCandidates: () => [],
    seminarComposer: false,
    seminarMindmateTag: false,
    seminarMindgraphTag: false,
    seminarAgentName: 'MindMate',
    seminarVoiceRecording: false,
  }
)

const emit = defineEmits<{
  (e: 'update:inputText', value: string): void
  (e: 'send'): void
  (e: 'stop'): void
  (e: 'upload', files: FileList): void
  (e: 'removeFile', fileId: string): void
  (e: 'suggestionSelect', suggestion: string): void
  (e: 'seminarStart', brief: SeminarBrief): void
  (e: 'clearSeminarTag', tag: 'mindmate' | 'mindgraph'): void
  (e: 'seminarVoicePress'): void
  (e: 'seminarVoiceRelease', send: boolean): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const router = useRouter()
const isFullpageMode = computed(() => props.mode === 'fullpage')
const showSeminarHome = computed(() => props.showSuggestions && props.homeMode === 'seminar')
const fileInputRef = ref<HTMLInputElement | null>(null)
const chatInputRef = ref<InstanceType<typeof ElInput> | null>(null)

function nativeTextarea(): HTMLTextAreaElement | null {
  const root = chatInputRef.value?.$el
  if (!(root instanceof HTMLElement)) {
    return null
  }
  return root.querySelector('textarea')
}

const {
  showMentionPicker,
  mentionPickerResults,
  syncMentionPicker,
  insertMention,
  dismissMentionPicker,
} = useMindmateMentionPicker({
  text: () => props.inputText,
  setText: (value) => emit('update:inputText', value),
  textarea: nativeTextarea,
  candidates: () => props.mentionCandidates,
})

/** Grow with newlines without Element Plus autosize (avoids unmount nextTick race). */
const composeExpanded = ref(false)

const useWelcomeComposeHeight = computed(
  () => isFullpageMode.value && props.showSuggestions && props.homeMode === 'dialogue'
)

const textareaRows = computed(() => (useWelcomeComposeHeight.value ? 2 : 1))

function fitComposerToText(): void {
  const ta = nativeTextarea()
  if (!ta || isWelcomeCompose()) {
    return
  }
  const style = getComputedStyle(ta)
  const parsedLine = Number.parseFloat(style.lineHeight)
  const line = Number.isFinite(parsedLine) ? parsedLine : 22.5
  const pad =
    (Number.parseFloat(style.paddingTop) || 0) + (Number.parseFloat(style.paddingBottom) || 0)
  const maxHeight = line * 4 + pad
  ta.style.height = 'auto'
  const needed = ta.scrollHeight
  const next = Math.min(Math.max(needed, line + pad), maxHeight)
  ta.style.height = `${next}px`
  ta.style.maxHeight = `${maxHeight}px`
  ta.style.overflowY = needed > maxHeight + 1 ? 'auto' : 'hidden'
}

function isWelcomeCompose(): boolean {
  if (useWelcomeComposeHeight.value) {
    return true
  }
  const ta = nativeTextarea()
  return Boolean(ta?.closest('.mindmate-stage--welcome'))
}

function clearTextareaFillHeight(): void {
  const ta = nativeTextarea()
  if (!ta) {
    return
  }
  ta.style.height = ''
  ta.style.maxHeight = ''
  ta.style.minHeight = ''
  ta.style.overflowY = ''
}

function syncTextareaFillHeight(): void {
  const ta = nativeTextarea()
  if (!ta || !isWelcomeCompose()) {
    return
  }
  const field = ta.closest('.input-field-fullpage')
  if (!(field instanceof HTMLElement)) {
    return
  }
  const height = field.clientHeight
  if (height <= 0) {
    return
  }
  ta.style.height = `${height}px`
  ta.style.maxHeight = `${height}px`
  ta.style.minHeight = `${height}px`
  ta.style.overflowY = 'auto'
}

async function syncComposeExpand(): Promise<void> {
  await nextTick()
  if (!isWelcomeCompose()) {
    clearTextareaFillHeight()
    composeExpanded.value = false
    fitComposerToText()
    return
  }
  if (!isFullpageMode.value) {
    return
  }
  syncTextareaFillHeight()
  const ta = nativeTextarea()
  if (!ta) {
    return
  }
  if (!props.inputText.trim()) {
    if (composeExpanded.value) {
      composeExpanded.value = false
      await nextTick()
      syncTextareaFillHeight()
    }
    return
  }
  if (composeExpanded.value) {
    syncTextareaFillHeight()
    return
  }
  if (ta.scrollHeight > ta.clientHeight + 2) {
    composeExpanded.value = true
    await nextTick()
    requestAnimationFrame(() => {
      syncTextareaFillHeight()
    })
  }
}

watch(
  () => props.inputText,
  () => {
    void syncComposeExpand()
  }
)

watch(useWelcomeComposeHeight, () => {
  void syncComposeExpand()
})

watch(composeExpanded, async () => {
  await nextTick()
  syncTextareaFillHeight()
})

function onComposerResize(): void {
  if (!isWelcomeCompose()) {
    fitComposerToText()
  }
}

onMounted(() => {
  void syncComposeExpand()
  window.addEventListener('resize', onComposerResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onComposerResize)
})

// Computed for send button disabled state
const seminarVoiceSlot = computed(
  () =>
    props.seminarComposer &&
    !props.seminarVoiceRecording &&
    !props.inputText.trim() &&
    seminarComposerCitations.value.length === 0 &&
    seminarComposerAttachments.value.length === 0
)

const isSendDisabled = computed(() => {
  const hasCitations = props.seminarComposer && seminarComposerCitations.value.length > 0
  const hasConversationFiles = props.seminarComposer && seminarComposerAttachments.value.length > 0
  const hasContent =
    props.inputText.trim() ||
    hasCitations ||
    hasConversationFiles ||
    (props.showFileUpload && props.pendingFiles.length > 0)
  return !hasContent || props.isLoading || !authStore.isAuthenticated
})

// Get file icon based on type
function getFileIcon(type: string): string {
  switch (type) {
    case 'image':
      return '🖼️'
    case 'audio':
      return '🎵'
    case 'video':
      return '🎬'
    case 'document':
      return '📄'
    default:
      return '📎'
  }
}

// Trigger file input
function triggerFileUpload() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  fileInputRef.value?.click()
}

// Handle file selection — images, Word, PDF, and PowerPoint
function handleFileSelect(event: Event) {
  // Check authentication before allowing file upload
  if (!authStore.isAuthenticated) {
    const input = event.target as HTMLInputElement
    input.value = ''
    authStore.handleTokenExpired(undefined, undefined)
    return
  }

  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  const selected = Array.from(files)
  const allowedFiles = selected.filter((file) => isMindmateComposerUploadableFile(file))

  if (allowedFiles.length < selected.length) {
    notify.errorKey('mindmate.input.unsupportedFile')
  }

  if (allowedFiles.length === 0) {
    input.value = ''
    return
  }

  const dataTransfer = new DataTransfer()
  allowedFiles.forEach((file) => dataTransfer.items.add(file))

  emit('upload', dataTransfer.files)
  input.value = ''
}

// Handle keyboard
function handleKeydown(event: Event | KeyboardEvent) {
  // Type guard for KeyboardEvent
  if (!('key' in event)) return

  // Check authentication before allowing input
  if (!authStore.isAuthenticated) {
    event.preventDefault()
    authStore.handleTokenExpired(undefined, undefined)
    return
  }

  if (props.enableMentions && showMentionPicker.value) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      const first = mentionPickerResults.value[0]
      if (first) {
        insertMention(first)
      }
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      dismissMentionPicker()
      return
    }
  }

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

function handleInputUpdate(value: string) {
  emit('update:inputText', value)
  if (!props.enableMentions) {
    return
  }
  void nextTick(() => {
    syncMentionPicker()
  })
}

// Handle input focus - show login modal if not authenticated
function handleInputFocus() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
  }
}

// Handle send button click
function handleSend() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  emit('send')
}

const voiceHolding = ref(false)
const voiceWillCancel = ref(false)
let voicePointerId = -1

function onVoicePointerDown(event: PointerEvent): void {
  if (props.isLoading) {
    return
  }
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  const target = event.currentTarget
  if (!(target instanceof HTMLElement)) {
    return
  }
  voiceHolding.value = true
  voiceWillCancel.value = false
  voicePointerId = event.pointerId
  target.setPointerCapture(event.pointerId)
  emit('seminarVoicePress')
}

function onVoicePointerMove(event: PointerEvent): void {
  if (!voiceHolding.value || event.pointerId !== voicePointerId) {
    return
  }
  const target = event.currentTarget
  if (!(target instanceof HTMLElement)) {
    return
  }
  const rect = target.getBoundingClientRect()
  voiceWillCancel.value =
    event.clientY < rect.top - 36 ||
    event.clientX < rect.left - 28 ||
    event.clientX > rect.right + 28
}

function finishVoicePointer(send: boolean): void {
  if (!voiceHolding.value) {
    return
  }
  voiceHolding.value = false
  voiceWillCancel.value = false
  voicePointerId = -1
  emit('seminarVoiceRelease', send)
}

function onVoicePointerUp(event: PointerEvent): void {
  if (event.pointerId !== voicePointerId) {
    return
  }
  finishVoicePointer(!voiceWillCancel.value)
}

function onVoicePointerCancel(event: PointerEvent): void {
  if (event.pointerId !== voicePointerId) {
    return
  }
  finishVoicePointer(false)
}

// Handle suggestion bubble click
function handleSuggestionSelect(suggestion: string) {
  emit('update:inputText', suggestion)
  emit('suggestionSelect', suggestion)
}

function openPluginDownload(): void {
  void router.push('/browser-plugin')
}

function focusComposer(place?: 'end'): void {
  const input = chatInputRef.value
  input?.focus()
  if (place !== 'end' || !input) {
    return
  }
  const root = input.$el as HTMLElement | undefined
  const field = root?.querySelector('textarea')
  if (!(field instanceof HTMLTextAreaElement)) {
    return
  }
  const end = field.value.length
  field.setSelectionRange(end, end)
}

defineExpose({ focus: focusComposer })
</script>

<template>
  <div
    class="shrink-0"
    :class="{ 'mm-seminar-brief-host': showSeminarHome }"
  >
    <MindmateSeminarBriefForm
      v-if="showSeminarHome"
      @start="emit('seminarStart', $event)"
    />
    <!-- Suggestion Bubbles - Above Input (Panel Mode) -->
    <div
      v-if="showSuggestions && !isFullpageMode && !showSeminarHome"
      class="suggestions-above-input-panel"
    >
      <SuggestionBubbles @select="handleSuggestionSelect" />
    </div>

    <!-- Input Area - Same design for fullpage and panel (MindMate module style) -->
    <div
      v-if="!showSeminarHome"
      class="input-area-fullpage"
    >
      <!-- Hidden file input -->
      <input
        id="mindmate-file-input"
        ref="fileInputRef"
        type="file"
        class="hidden"
        name="mindmate-file-input"
        :accept="MINDMATE_COMPOSER_FILE_ACCEPT"
        multiple
        :aria-label="t('mindmate.input.attachFile')"
        @change="handleFileSelect"
      />

      <!-- Pending Files Preview -->
      <div
        v-if="showFileUpload && pendingFiles.length > 0"
        class="pending-files-fullpage"
      >
        <div
          v-for="file in pendingFiles"
          :key="file.id"
          class="file-chip"
        >
          <img
            v-if="file.preview_url"
            :src="file.preview_url"
            :alt="file.name"
            class="w-5 h-5 object-cover rounded"
          />
          <span v-else>{{ getFileIcon(file.type) }}</span>
          <span class="file-name">{{ file.name }}</span>
          <ElButton
            text
            circle
            size="small"
            class="file-remove-btn"
            @click="emit('removeFile', file.id)"
          >
            <ElIcon :size="12"><Close /></ElIcon>
          </ElButton>
        </div>
      </div>

      <!-- Input Container -->
      <div
        class="input-container-fullpage mindmate-input-compose"
        :class="{
          'mindmate-input-compose--seminar': seminarComposer,
          'mindmate-input-compose--expanded': composeExpanded,
        }"
      >
        <div
          v-if="enableMentions && showMentionPicker"
          class="mindmate-mention-picker"
          role="listbox"
        >
          <button
            v-for="row in mentionPickerResults"
            :key="row.id"
            type="button"
            class="mindmate-mention-picker__item"
            role="option"
            @mousedown.prevent="insertMention(row)"
          >
            <span
              class="mindmate-mention-picker__avatar"
              :class="{ 'is-agent': row.kind === 'agent' }"
              :style="
                row.kind === 'agent'
                  ? undefined
                  : {
                      background: seminarAvatarTone(row.id).background,
                      color: seminarAvatarTone(row.id).color,
                    }
              "
            >
              <UserAvatarGlyph
                v-if="row.kind === 'agent'"
                :value="row.avatar"
              />
              <template v-else>{{ seminarAvatarSurname(row.name) }}</template>
            </span>
            <span class="mindmate-mention-picker__name">{{ row.name }}</span>
          </button>
        </div>
        <!-- Text Input -->
        <div class="input-field-fullpage">
          <div
            v-if="seminarComposer && (seminarMindmateTag || seminarMindgraphTag)"
            class="mm-seminar-field-tags"
          >
            <button
              v-if="seminarMindmateTag"
              type="button"
              class="mm-seminar-field-tag"
              :title="t('mindmate.composer.mindmateTagHint')"
              :aria-label="t('mindmate.composer.mindmateTagHint')"
              @click="emit('clearSeminarTag', 'mindmate')"
            >
              <span>@{{ seminarAgentName }}</span>
              <span class="mm-seminar-field-tag__x">×</span>
            </button>
            <button
              v-if="seminarMindgraphTag"
              type="button"
              class="mm-seminar-field-tag"
              :title="t('mindmate.composer.mindgraphHint')"
              :aria-label="t('mindmate.composer.mindgraphHint')"
              @click="emit('clearSeminarTag', 'mindgraph')"
            >
              <span>@mindgraph</span>
              <span class="mm-seminar-field-tag__x">×</span>
            </button>
          </div>
          <div
            v-if="seminarComposer && (seminarVoiceRecording || voiceHolding)"
            class="mm-voice-live"
            :class="{ 'is-cancel': voiceWillCancel }"
          >
            <span class="mm-voice-live__dot" />
            <span>{{
              voiceWillCancel
                ? t('mindmate.composer.voiceHoldCancel')
                : t('mindmate.composer.voiceHoldSend')
            }}</span>
          </div>
          <ElInput
            id="mindmate-chat-input"
            ref="chatInputRef"
            :model-value="inputText"
            type="textarea"
            name="mindmate-chat-input"
            :rows="textareaRows"
            :placeholder="placeholder || t('mindmate.input.placeholder')"
            :disabled="isLoading || !authStore.isAuthenticated"
            :maxlength="maxlength"
            :show-word-limit="maxlength != null"
            class="fullpage-textarea"
            :aria-label="placeholder || t('mindmate.input.placeholder')"
            @update:model-value="handleInputUpdate"
            @keydown="handleKeydown"
            @focus="handleInputFocus"
          />
        </div>

        <div
          class="input-bottom"
          :class="{ 'input-bottom--seminar': seminarComposer }"
        >
          <div
            v-if="seminarComposer"
            class="mm-seminar-toolslot"
          >
            <slot name="seminarTools" />
          </div>
          <!-- Action buttons (right side) -->
          <div class="input-actions-fullpage">
            <!-- Upload Button (Paperclip) - hidden when showFileUpload is false -->
            <I18nTooltip
              v-if="showFileUpload"
              k="mindmate.input.attachFile"
            >
              <ElButton
                text
                class="attach-btn-fullpage"
                :disabled="isLoading || isUploading || !authStore.isAuthenticated"
                @click="triggerFileUpload"
              >
                <Paperclip
                  v-if="!isUploading"
                  :size="20"
                />
                <span
                  v-else
                  class="loading-dot"
                />
              </ElButton>
            </I18nTooltip>

            <!-- Send/Stop Button -->
            <ElButton
              v-if="isStreaming"
              type="danger"
              class="send-btn-fullpage stop"
              @click="emit('stop')"
            >
              <ElIcon><VideoPause /></ElIcon>
            </ElButton>
            <button
              v-else-if="seminarVoiceSlot || voiceHolding || seminarVoiceRecording"
              type="button"
              class="mm-voice-hold"
              :class="{
                'is-holding': (voiceHolding || seminarVoiceRecording) && !voiceWillCancel,
                'is-cancel': voiceWillCancel,
              }"
              :disabled="isLoading"
              :aria-label="t('mindmate.composer.voiceMessage')"
              :title="t('mindmate.composer.voiceMessage')"
              @pointerdown.prevent="onVoicePointerDown"
              @pointermove="onVoicePointerMove"
              @pointerup="onVoicePointerUp"
              @pointercancel="onVoicePointerCancel"
              @contextmenu.prevent
            >
              <Mic :size="18" />
            </button>
            <ElButton
              v-else
              type="primary"
              class="send-btn-fullpage"
              :disabled="isSendDisabled"
              @click="handleSend"
            >
              <Send :size="18" />
            </ElButton>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="showSuggestions && isFullpageMode && !showSeminarHome"
      class="suggestions-above-input"
    >
      <SuggestionBubbles
        flow
        :flow-rows="[3, 4]"
        @select="handleSuggestionSelect"
      />
      <button
        type="button"
        class="mm-plugin-download"
        @click="openPluginDownload"
      >
        <span class="mm-plugin-download__badge">
          <I18nText
            k="mindmate.pluginDownloadBadge"
            dense
            primary-only
          />
        </span>
        <span class="mm-plugin-download__label">
          <I18nText
            k="mindmate.pluginDownload"
            dense
          />
        </span>
        <ArrowRight
          class="mm-plugin-download__arrow"
          :size="16"
          :stroke-width="2"
        />
      </button>
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';

.mm-seminar-brief-host {
  box-sizing: border-box;
  width: 100%;
  padding: 4px 16px 28px;
}

.mm-plugin-download {
  display: flex;
  align-items: center;
  gap: 12px;
  width: fit-content;
  max-width: 100%;
  min-height: 44px;
  margin: 18px auto 0;
  padding: 5px 16px 5px 5px;
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.38);
  color: #1c1917;
  font-size: 15px;
  font-weight: 500;
  line-height: 1;
  letter-spacing: 0.01em;
  cursor: pointer;
  backdrop-filter: blur(16px) saturate(1.35);
  -webkit-backdrop-filter: blur(16px) saturate(1.35);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.85),
    0 8px 24px rgba(28, 25, 23, 0.06);
  transition:
    transform 0.18s ease,
    background 0.18s ease,
    box-shadow 0.18s ease;
}

.mm-plugin-download:hover {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.55);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 12px 28px rgba(28, 25, 23, 0.08);
}

.mm-plugin-download:active {
  transform: translateY(0);
}

.mm-plugin-download:focus-visible {
  outline: 2px solid rgba(28, 25, 23, 0.28);
  outline-offset: 3px;
}

.mm-plugin-download__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #7c3aed;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.06);
}

.mm-plugin-download__label {
  min-width: 0;
  color: #1c1917;
}

.mm-plugin-download__arrow {
  flex: 0 0 auto;
  color: #44403c;
}

:global(.dark) .mm-plugin-download {
  border-color: rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.08);
  color: #f5f5f4;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.12),
    0 8px 24px rgba(0, 0, 0, 0.28);
}

:global(.dark) .mm-plugin-download__badge {
  background: rgba(255, 255, 255, 0.92);
  color: #7c3aed;
}

:global(.dark) .mm-plugin-download__label,
:global(.dark) .mm-plugin-download__arrow {
  color: #f5f5f4;
}

.mindmate-input-compose {
  position: relative;
}

.mindmate-input-compose .input-field-fullpage {
  flex: 1 1 auto;
  min-height: 0;
}

.mindmate-input-compose--seminar .input-field-fullpage {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.mindmate-input-compose--seminar .fullpage-textarea {
  flex: 1 1 auto;
  min-width: 0;
}

.mm-seminar-field-tags {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  height: 26px;
  margin-top: 6px;
}

.mm-seminar-field-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid #ddd6fe;
  border-radius: 999px;
  background: #f5f3ff;
  color: #6d28d9;
  font-size: 12px;
  cursor: pointer;
}

.mm-seminar-field-tag__x {
  opacity: 0;
  font-size: 14px;
  line-height: 1;
}

.mm-seminar-field-tag:hover {
  background: #ede9fe;
}

.mm-seminar-field-tag:hover .mm-seminar-field-tag__x {
  opacity: 1;
}

.mm-voice-live {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 26px;
  margin-top: 6px;
  color: #44403c;
  font-size: 13px;
}

.mm-voice-live.is-cancel {
  color: #b91c1c;
}

.mm-voice-live__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #ef4444;
}

.mm-voice-hold {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: none;
  border-radius: 10px;
  background: #f3f4f6;
  color: #6b7280;
  cursor: pointer;
  touch-action: none;
  user-select: none;
}

.mm-voice-hold:hover,
.mm-voice-hold.is-holding {
  background: #e5e7eb;
  color: #374151;
}

.mm-voice-hold.is-cancel {
  background: #fee2e2;
  color: #b91c1c;
}

.mm-voice-hold:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mindmate-input-compose--expanded .fullpage-textarea {
  height: 100%;
}

.mindmate-input-compose .fullpage-textarea :deep(.el-textarea__inner) {
  overflow-y: hidden;
}

.mindmate-mention-picker {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 6px);
  max-height: 200px;
  overflow-y: auto;
  z-index: 20;
  border-radius: 10px;
  border: 1px solid #e7e5e4;
  background: #fff;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.1);
  padding: 4px;
}

.mindmate-mention-picker__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border: none;
  border-radius: 8px;
  background: none;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  color: #1c1917;
}

.mindmate-mention-picker__item:hover {
  background: #f5f5f4;
}

.mindmate-mention-picker__avatar {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 650;
  line-height: 1;
  overflow: hidden;
}

.mindmate-mention-picker__avatar.is-agent {
  background: linear-gradient(145deg, #a78bfa 0%, #6d5efc 100%);
}

.mindmate-mention-picker__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
