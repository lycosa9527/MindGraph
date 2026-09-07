<script setup lang="ts">
/**
 * Zulip-style in-row message editor: textarea + compose toolbar + Save/Cancel.
 */
import { computed, onMounted, ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useWorkshopComposeDraft } from '@/composables/workshop/useWorkshopComposeDraft'
import { resolveMessageEditKeydown } from '@/utils/workshopMessageEditKeys'

import WorkshopComposeToolbar from './WorkshopComposeToolbar.vue'
import WorkshopDiagramPicker from './WorkshopDiagramPicker.vue'

const props = defineProps<{
  initialContent: string
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [content: string]
  cancel: []
}>()

const { t } = useLanguage()
const {
  content,
  isPreview,
  previewHtml,
  textareaRef,
  fileInputRef,
  uploading,
  showEmojiPicker,
  showRolePicker,
  showDiagramPicker,
  showMentionPicker,
  mentionPickerResults,
  syncMentionPicker,
  insertMentionUser,
  handleFormat,
  handleEmojiSelect,
  handleDiagramInsert,
  handleRolePick,
  onEmojiPickerVisible,
  onRolePickerVisible,
  openDiagramPicker,
  triggerFileUpload,
  handleFileChange,
  onTextareaInput,
  focusTextarea,
} = useWorkshopComposeDraft()
const saveError = ref(false)

const textareaRows = computed(() => {
  const lines = content.value.split('\n').length
  return Math.min(16, Math.max(3, lines))
})

const canSave = computed(() => Boolean(content.value.trim()) && !props.saving)

onMounted(() => {
  content.value = props.initialContent
  focusTextarea()
})

function submitSave(): void {
  const trimmed = content.value.trim()
  if (!trimmed || props.saving) return
  saveError.value = false
  emit('save', trimmed)
}

function handleKeydown(event: KeyboardEvent): void {
  const mentionOpen = showMentionPicker.value && mentionPickerResults.value.length > 0
  const action = resolveMessageEditKeydown(event, mentionOpen)
  if (action === 'insert-mention') {
    event.preventDefault()
    insertMentionUser(mentionPickerResults.value[0])
    return
  }
  if (action === 'dismiss-mention') {
    event.preventDefault()
    showMentionPicker.value = false
    return
  }
  if (action === 'cancel') {
    event.preventDefault()
    emit('cancel')
    return
  }
  if (action === 'save') {
    event.preventDefault()
    submitSave()
  }
}

function togglePreview(): void {
  isPreview.value = !isPreview.value
}

function markSaveFailed(): void {
  saveError.value = true
}

defineExpose({ markSaveFailed })
</script>

<template>
  <div class="msg-edit">
    <div
      v-if="showMentionPicker && mentionPickerResults.length > 0"
      class="msg-edit__mentions"
    >
      <button
        v-for="member in mentionPickerResults"
        :key="member.id"
        type="button"
        class="msg-edit__mention"
        @mousedown.prevent="insertMentionUser(member)"
      >
        <span class="msg-edit__mention-avatar">{{ member.avatar || '👤' }}</span>
        <span class="msg-edit__mention-name">{{ member.name || `User ${member.id}` }}</span>
      </button>
    </div>

    <div
      v-if="isPreview"
      class="msg-edit__preview"
    >
      <p
        v-if="!content.trim()"
        class="msg-edit__preview-empty"
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
      class="msg-edit__textarea"
      :rows="textareaRows"
      :placeholder="t('workshop.editMessagePrompt')"
      :disabled="saving"
      @keydown="handleKeydown"
      @input="onTextareaInput"
      @keyup="syncMentionPicker"
      @click="syncMentionPicker"
    />

    <input
      ref="fileInputRef"
      type="file"
      class="msg-edit__file"
      accept="image/*,.pdf,.doc,.docx,.txt"
      @change="handleFileChange"
    />

    <WorkshopComposeToolbar
      :can-send="canSave"
      :preview-on="isPreview"
      :format-disabled="isPreview || Boolean(saving)"
      :uploading="uploading"
      :show-emoji-picker="showEmojiPicker"
      :show-role-picker="showRolePicker"
      :show-send="false"
      @format="handleFormat"
      @toggle-preview="togglePreview"
      @upload="triggerFileUpload"
      @update:show-emoji-picker="onEmojiPickerVisible"
      @update:show-role-picker="onRolePickerVisible"
      @emoji="handleEmojiSelect"
      @pick-role="handleRolePick"
      @open-diagram="openDiagramPicker"
    />

    <div class="msg-edit__actions">
      <button
        type="button"
        class="msg-edit__save"
        :disabled="!canSave"
        @click="submitSave"
      >
        {{ t('common.save') }}
      </button>
      <button
        type="button"
        class="msg-edit__cancel"
        :disabled="saving"
        @click="emit('cancel')"
      >
        {{ t('common.cancel') }}
      </button>
      <span
        v-if="saveError"
        class="msg-edit__error"
      >
        {{ t('workshop.editMessageFailed') }}
      </span>
    </div>

    <WorkshopDiagramPicker
      :visible="showDiagramPicker"
      @update:visible="showDiagramPicker = $event"
      @insert="handleDiagramInsert"
    />
  </div>
</template>

<style scoped>
.msg-edit {
  position: relative;
  margin: 2px 0 8px;
  border: 1px solid hsl(0deg 0% 0% / 12%);
  border-radius: 6px;
  background: hsl(0deg 0% 100%);
}

.msg-edit:focus-within {
  border-color: hsl(228deg 40% 68%);
  box-shadow: 0 0 0 2px hsl(228deg 56% 58% / 8%);
}

.msg-edit__mentions {
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

.msg-edit__mention {
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

.msg-edit__mention:hover {
  background: hsl(228deg 40% 96%);
}

.msg-edit__mention-avatar {
  flex-shrink: 0;
  font-size: 16px;
  line-height: 1;
}

.msg-edit__mention-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.msg-edit__textarea,
.msg-edit__preview {
  display: block;
  width: 100%;
  min-height: 52px;
  max-height: 320px;
  padding: 8px 10px 6px;
  font-size: 14px;
  line-height: 1.55;
  color: hsl(0deg 0% 12%);
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
  box-sizing: border-box;
}

.msg-edit__textarea {
  resize: vertical;
}

.msg-edit__preview {
  overflow-y: auto;
}

.msg-edit__preview-empty {
  color: hsl(0deg 0% 52%);
  margin: 0;
}

.msg-edit__preview :deep(p) {
  margin: 0 0 6px;
}

.msg-edit__preview :deep(p:last-child) {
  margin-bottom: 0;
}

.msg-edit__preview :deep(ul),
.msg-edit__preview :deep(ol) {
  margin: 4px 0;
  padding-left: 22px;
}

.msg-edit__preview :deep(img) {
  max-width: 100%;
  max-height: 240px;
  border-radius: 6px;
}

.msg-edit__preview :deep(img[src*='/api/training/assets/roles/']) {
  display: inline-block;
  width: 140px;
  height: 140px;
  max-width: 140px;
  max-height: 140px;
  margin: 0 0.2em;
  vertical-align: bottom;
  object-fit: contain;
  border: none;
  background: transparent;
}

.msg-edit__preview :deep(blockquote) {
  margin: 6px 0;
  padding: 6px 12px;
  border-left: 3px solid hsl(228deg 40% 76%);
  background: hsl(228deg 20% 97%);
}

.msg-edit__file {
  display: none;
}

.msg-edit__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px 8px;
}

.msg-edit__save,
.msg-edit__cancel {
  height: 28px;
  padding: 0 12px;
  border: none;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  line-height: 28px;
}

.msg-edit__save {
  background: hsl(228deg 56% 58%);
  color: hsl(0deg 0% 100%);
}

.msg-edit__save:hover:not(:disabled) {
  background: hsl(228deg 48% 48%);
}

.msg-edit__save:disabled {
  opacity: 0.4;
  cursor: default;
}

.msg-edit__cancel {
  background: hsl(0deg 0% 0% / 6%);
  color: hsl(0deg 0% 28%);
}

.msg-edit__cancel:hover:not(:disabled) {
  background: hsl(0deg 0% 0% / 10%);
}

.msg-edit__cancel:disabled {
  opacity: 0.45;
  cursor: default;
}

.msg-edit__error {
  font-size: 12px;
  color: hsl(0deg 65% 42%);
}
</style>
