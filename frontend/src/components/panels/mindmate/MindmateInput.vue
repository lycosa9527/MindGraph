<script setup lang="ts">
import { computed, ref } from 'vue'

import { ElButton, ElIcon, ElInput, ElTooltip } from 'element-plus'

import { Close, VideoPause } from '@element-plus/icons-vue'

import { Paperclip, Send } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import type { MindMateFile } from '@/composables/mindmate/useMindMate'
import { useAuthStore } from '@/stores/auth'

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
    /** When false, hide file upload button (e.g. canvas mini-mindmate) */
    showFileUpload?: boolean
    /** Custom placeholder (default: question prompt) */
    placeholder?: string
    /** Max length for input (e.g. 1000 for comments) */
    maxlength?: number
  }>(),
  {
    mode: 'panel',
    inputText: '',
    isLoading: false,
    isStreaming: false,
    isUploading: false,
    pendingFiles: () => [],
    showSuggestions: false,
    showFileUpload: true,
    placeholder: '',
    maxlength: undefined,
  }
)

const emit = defineEmits<{
  (e: 'update:inputText', value: string): void
  (e: 'send'): void
  (e: 'stop'): void
  (e: 'upload', files: FileList): void
  (e: 'removeFile', fileId: string): void
  (e: 'suggestionSelect', suggestion: string): void
}>()

const { t } = useLanguage()
const authStore = useAuthStore()
const isFullpageMode = computed(() => props.mode === 'fullpage')
const fileInputRef = ref<HTMLInputElement | null>(null)

// Computed for send button disabled state
const isSendDisabled = computed(() => {
  const hasContent =
    props.inputText.trim() || (props.showFileUpload && props.pendingFiles.length > 0)
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

// Handle file selection - only images allowed
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

  // Filter to only image files
  const imageFiles = Array.from(files).filter((file) => file.type.startsWith('image/'))

  if (imageFiles.length === 0) {
    // No valid images selected
    console.warn('Only image files are allowed')
    input.value = ''
    return
  }

  // Create a new FileList-like object with only images
  const dataTransfer = new DataTransfer()
  imageFiles.forEach((file) => dataTransfer.items.add(file))

  emit('upload', dataTransfer.files)
  // Reset input
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

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
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

// Handle suggestion bubble click
function handleSuggestionSelect(suggestion: string) {
  emit('update:inputText', suggestion)
  emit('suggestionSelect', suggestion)
}
</script>

<template>
  <div class="shrink-0">
    <!-- Suggestion Bubbles - Above Input (Fullpage Mode) -->
    <div
      v-if="showSuggestions && isFullpageMode"
      class="suggestions-above-input"
    >
      <SuggestionBubbles @select="handleSuggestionSelect" />
    </div>

    <!-- Suggestion Bubbles - Above Input (Panel Mode) -->
    <div
      v-if="showSuggestions && !isFullpageMode"
      class="suggestions-above-input-panel"
    >
      <SuggestionBubbles @select="handleSuggestionSelect" />
    </div>

    <!-- Input Area - Same design for fullpage and panel (MindMate module style) -->
    <div class="input-area-fullpage">
      <!-- Hidden file input -->
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        accept="image/*"
        multiple
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
      <div class="input-container-fullpage">
        <!-- Text Input -->
        <div class="input-field-fullpage">
          <ElInput
            :model-value="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="placeholder || t('mindmate.input.placeholder')"
            :disabled="isLoading || !authStore.isAuthenticated"
            :maxlength="maxlength"
            :show-word-limit="maxlength != null"
            class="fullpage-textarea"
            @update:model-value="emit('update:inputText', $event)"
            @keydown="handleKeydown"
            @focus="handleInputFocus"
          />
        </div>

        <!-- Action buttons (right side) -->
        <div class="input-actions-fullpage">
          <!-- Upload Button (Paperclip) - hidden when showFileUpload is false -->
          <ElTooltip
            v-if="showFileUpload"
            :content="t('mindmate.input.attachFile')"
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
          </ElTooltip>

          <!-- Send/Stop Button -->
          <ElButton
            v-if="isStreaming"
            type="danger"
            class="send-btn-fullpage stop"
            @click="emit('stop')"
          >
            <ElIcon><VideoPause /></ElIcon>
          </ElButton>
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
</template>

<style scoped>
@import './mindmate.css';
</style>
