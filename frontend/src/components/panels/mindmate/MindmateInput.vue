<script setup lang="ts">
import { computed, ref } from 'vue'

import { ElButton, ElIcon, ElInput, ElTooltip } from 'element-plus'

import { Close, Promotion, UploadFilled, VideoPause } from '@element-plus/icons-vue'

import { Paperclip, Send } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import type { MindMateFile } from '@/composables/useMindMate'
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
  }>(),
  {
    mode: 'panel',
    inputText: '',
    isLoading: false,
    isStreaming: false,
    isUploading: false,
    pendingFiles: () => [],
    showSuggestions: false,
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

const { isZh } = useLanguage()
const authStore = useAuthStore()
const isFullpageMode = computed(() => props.mode === 'fullpage')
const fileInputRef = ref<HTMLInputElement | null>(null)

// Computed for send button disabled state
const isSendDisabled = computed(() => {
  return (
    (!props.inputText.trim() && props.pendingFiles.length === 0) ||
    props.isLoading ||
    !authStore.isAuthenticated
  )
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

// Format file size
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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

    <!-- Input Area - Fullpage Mode -->
    <div
      v-if="isFullpageMode"
      class="input-area-fullpage"
    >
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
        v-if="pendingFiles.length > 0"
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
            :placeholder="isZh ? '输入你的问题...' : 'Type your question...'"
            :disabled="isLoading || !authStore.isAuthenticated"
            class="fullpage-textarea"
            @update:model-value="emit('update:inputText', $event)"
            @keydown="handleKeydown"
            @focus="handleInputFocus"
          />
        </div>

        <!-- Action buttons (right side) -->
        <div class="input-actions-fullpage">
          <!-- Upload Button (Paperclip) -->
          <ElTooltip :content="isZh ? '上传文件' : 'Attach file'">
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

    <!-- Input Area - Panel Mode (Swiss Design) -->
    <div
      v-else
      class="input-area-swiss"
    >
      <!-- Pending Files Preview -->
      <div
        v-if="pendingFiles.length > 0"
        class="pending-files-swiss"
      >
        <div
          v-for="file in pendingFiles"
          :key="file.id"
          class="pending-file-chip"
        >
          <img
            v-if="file.preview_url"
            :src="file.preview_url"
            :alt="file.name"
            class="w-6 h-6 object-cover"
          />
          <span
            v-else
            class="file-icon"
            >{{ getFileIcon(file.type) }}</span
          >
          <span class="file-name">{{ file.name }}</span>
          <span class="file-size">{{ formatFileSize(file.size) }}</span>
          <button
            class="file-remove"
            @click="emit('removeFile', file.id)"
          >
            <ElIcon><Close /></ElIcon>
          </button>
        </div>
      </div>

      <!-- Hidden file input -->
      <input
        ref="fileInputRef"
        type="file"
        class="hidden"
        accept="image/*"
        multiple
        @change="handleFileSelect"
      />

      <!-- Input Container -->
      <div class="input-container-swiss">
        <!-- Attach Button -->
        <button
          class="attach-btn"
          :disabled="isLoading || isUploading || !authStore.isAuthenticated"
          :class="{ 'is-loading': isUploading }"
          @click="triggerFileUpload"
        >
          <ElIcon v-if="!isUploading"><UploadFilled /></ElIcon>
          <span
            v-else
            class="loading-spinner"
          />
        </button>

        <!-- Text Input -->
        <div class="input-wrapper">
          <ElInput
            :model-value="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 6 }"
            :placeholder="
              isZh
                ? '提问、分析图表、或请求修改...'
                : 'Ask questions, analyze diagrams, or request changes...'
            "
            :disabled="isLoading || !authStore.isAuthenticated"
            class="swiss-textarea"
            @update:model-value="emit('update:inputText', $event)"
            @keydown="handleKeydown"
            @focus="handleInputFocus"
          />
        </div>

        <!-- Send/Stop Button -->
        <button
          v-if="isStreaming"
          class="send-btn stop-btn"
          @click="emit('stop')"
        >
          <ElIcon><VideoPause /></ElIcon>
        </button>
        <button
          v-else
          class="send-btn"
          :disabled="isSendDisabled"
          @click="handleSend"
        >
          <ElIcon><Promotion /></ElIcon>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';
</style>
