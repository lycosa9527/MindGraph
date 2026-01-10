<script setup lang="ts">
import { ref, watch } from 'vue'

import { ElAvatar, ElButton, ElIcon, ElInput, ElTooltip } from 'element-plus'

import { CopyDocument, Edit, RefreshRight, Share } from '@element-plus/icons-vue'

import DOMPurify from 'dompurify'
import { ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import MarkdownIt from 'markdown-it'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import ImagePreviewModal from '@/components/common/ImagePreviewModal.vue'
import { useLanguage } from '@/composables'
import type { FeedbackRating, MindMateMessage } from '@/composables/useMindMate'

const props = defineProps<{
  message: MindMateMessage
  userAvatar: string
  isEditing?: boolean
  editingContent?: string
  isHovered?: boolean
  isLastAssistant?: boolean
  hasPreviousUserMessage?: boolean
  isLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', message: MindMateMessage): void
  (e: 'cancelEdit'): void
  (e: 'saveEdit', content: string): void
  (e: 'copy', content: string): void
  (e: 'regenerate', messageId: string): void
  (e: 'feedback', messageId: string, rating: FeedbackRating): void
  (e: 'share'): void
  (e: 'mouseenter'): void
  (e: 'mouseleave'): void
}>()

const { isZh } = useLanguage()

// Markdown renderer
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true,
})

// Local editing state
const localEditingContent = ref(props.editingContent || props.message.content)

// Watch editingContent prop
watch(
  () => props.editingContent,
  (newVal) => {
    if (newVal !== undefined) {
      localEditingContent.value = newVal
    }
  }
)

// Remove <think> blocks from content
function removeThinkBlocks(content: string): string {
  // Remove <think>...</think> blocks (including multiline)
  return content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
}

// Render markdown with sanitization
function renderMarkdown(content: string): string {
  if (!content) return ''
  const cleanedContent = removeThinkBlocks(content)
  const html = md.render(cleanedContent)
  return DOMPurify.sanitize(html)
}

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

function handleSaveEdit() {
  emit('saveEdit', localEditingContent.value.trim())
}

function handleCancelEdit() {
  localEditingContent.value = props.message.content
  emit('cancelEdit')
}

// Image preview state
const showImagePreview = ref(false)
const previewImageUrl = ref('')

// Handle click on markdown content to detect image clicks
function handleMarkdownClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (target.tagName === 'IMG') {
    const imgSrc = (target as HTMLImageElement).src
    if (imgSrc) {
      previewImageUrl.value = imgSrc
      showImagePreview.value = true
    }
  }
}
</script>

<template>
  <div
    class="message-wrapper group"
    :class="message.role === 'user' ? 'user-message' : 'assistant-message'"
    @mouseenter="emit('mouseenter')"
    @mouseleave="emit('mouseleave')"
  >
    <div
      class="message flex gap-3 items-start"
      :class="message.role === 'user' ? 'flex-row-reverse' : ''"
    >
      <!-- Avatar -->
      <template v-if="message.role === 'user'">
        <ElAvatar
          :size="40"
          class="flex-shrink-0 bg-[#FAFAFA] border-2 border-[#303133]"
        >
          {{ userAvatar }}
        </ElAvatar>
      </template>
      <template v-else>
        <!-- MindMate avatar -->
        <ElAvatar
          :src="mindmateAvatarMd"
          alt="MindMate"
          :size="40"
          class="mindmate-avatar flex-shrink-0"
        />
      </template>

      <!-- Content -->
      <div
        class="message-content-wrapper flex-1"
        :class="message.role === 'user' ? 'flex flex-col items-end' : 'flex flex-col items-start'"
      >
        <!-- User message editing -->
        <template v-if="message.role === 'user' && isEditing">
          <div class="edit-input-wrapper w-full max-w-[70%]">
            <ElInput
              v-model="localEditingContent"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              @keydown.enter.exact.prevent="handleSaveEdit"
              @keydown.esc.prevent="handleCancelEdit"
            />
            <div class="flex gap-2 mt-2 justify-end">
              <ElButton
                size="small"
                @click="handleCancelEdit"
              >
                {{ isZh ? '取消' : 'Cancel' }}
              </ElButton>
              <ElButton
                type="primary"
                size="small"
                @click="handleSaveEdit"
              >
                {{ isZh ? '保存' : 'Save' }}
              </ElButton>
            </div>
          </div>
        </template>

        <!-- Message content -->
        <template v-else>
          <div
            class="message-content max-w-[70%] relative"
            :class="[
              message.role === 'user'
                ? 'bg-[#606266] text-white px-4 py-1.5 rounded-2xl'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-white px-3 py-2 rounded-lg',
              message.isStreaming ? 'streaming' : '',
            ]"
          >
            <!-- User message - plain text with files -->
            <template v-if="message.role === 'user'">
              <!-- Attached files -->
              <div
                v-if="message.files && message.files.length > 0"
                class="message-files flex flex-wrap gap-2 mb-2"
              >
                <div
                  v-for="file in message.files"
                  :key="file.id"
                  class="file-attachment flex items-center gap-1.5 px-2 py-1 bg-white/20 rounded text-xs"
                >
                  <img
                    v-if="file.preview_url"
                    :src="file.preview_url"
                    :alt="file.name"
                    class="w-6 h-6 object-cover rounded"
                  />
                  <span v-else>{{ getFileIcon(file.type) }}</span>
                  <span class="max-w-[80px] truncate">{{ file.name }}</span>
                </div>
              </div>
              <p class="whitespace-pre-wrap text-sm leading-normal m-0">
                {{ message.content }}
              </p>
            </template>

            <!-- Assistant message - markdown rendered -->
            <template v-else>
              <!-- eslint-disable vue/no-v-html -- Content is sanitized via DOMPurify -->
              <div
                class="markdown-content text-sm leading-normal"
                @click="handleMarkdownClick"
                v-html="renderMarkdown(message.content)"
              />
              <!-- eslint-enable vue/no-v-html -->
              <!-- Streaming cursor -->
              <span
                v-if="message.isStreaming"
                class="inline-block w-0.5 h-4 bg-current animate-pulse ml-1"
              />
            </template>
          </div>

          <!-- User message actions (on hover) -->
          <div
            v-if="message.role === 'user'"
            class="message-actions flex gap-1 mt-1 px-1 justify-end"
            :style="{
              opacity: isHovered ? 1 : 0,
            }"
          >
            <ElTooltip :content="isZh ? '编辑' : 'Edit'">
              <ElButton
                text
                circle
                size="small"
                @click="emit('edit', message)"
              >
                <ElIcon class="text-xs"><Edit /></ElIcon>
              </ElButton>
            </ElTooltip>
            <ElTooltip :content="isZh ? '复制' : 'Copy'">
              <ElButton
                text
                circle
                size="small"
                @click="emit('copy', message.content)"
              >
                <ElIcon class="text-xs"><CopyDocument /></ElIcon>
              </ElButton>
            </ElTooltip>
          </div>

          <!-- AI message action bar -->
          <div
            v-if="message.role === 'assistant' && !message.isStreaming"
            class="action-bar mt-3 flex flex-wrap items-center gap-1"
            :class="{
              'action-bar-visible': isLastAssistant,
              'action-bar-hover': !isLastAssistant,
            }"
          >
            <!-- Copy -->
            <ElTooltip
              :content="isZh ? '复制' : 'Copy'"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                @click="emit('copy', message.content)"
              >
                <ElIcon :size="18"><CopyDocument /></ElIcon>
              </ElButton>
            </ElTooltip>

            <!-- Regenerate -->
            <ElTooltip
              v-if="hasPreviousUserMessage"
              :content="isZh ? '重新生成' : 'Regenerate'"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                :disabled="isLoading"
                @click="emit('regenerate', message.id)"
              >
                <ElIcon :size="18"><RefreshRight /></ElIcon>
              </ElButton>
            </ElTooltip>

            <!-- Like -->
            <ElTooltip
              :content="isZh ? '点赞' : 'Like'"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                :class="{ 'is-active': message.feedback === 'like' }"
                @click="emit('feedback', message.id, message.feedback === 'like' ? null : 'like')"
              >
                <ThumbsUp :size="16" />
              </ElButton>
            </ElTooltip>

            <!-- Dislike -->
            <ElTooltip
              :content="isZh ? '踩' : 'Dislike'"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                :class="{ 'is-active-dislike': message.feedback === 'dislike' }"
                @click="
                  emit('feedback', message.id, message.feedback === 'dislike' ? null : 'dislike')
                "
              >
                <ThumbsDown :size="16" />
              </ElButton>
            </ElTooltip>

            <!-- Share -->
            <ElTooltip
              :content="isZh ? '分享' : 'Share'"
              placement="top"
            >
              <ElButton
                text
                class="action-btn-lg"
                @click="emit('share')"
              >
                <ElIcon :size="18"><Share /></ElIcon>
              </ElButton>
            </ElTooltip>
          </div>
        </template>
      </div>
    </div>

    <!-- Image Preview Modal -->
    <ImagePreviewModal
      v-model:visible="showImagePreview"
      :title="isZh ? '图片预览' : 'Image Preview'"
      :image-url="previewImageUrl"
    />
  </div>
</template>

<style scoped>
@import './mindmate.css';
</style>
