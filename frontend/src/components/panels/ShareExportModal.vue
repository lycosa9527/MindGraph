<script setup lang="ts">
/**
 * ShareExportModal - Modal for selecting messages and exporting as PNG
 * Uses html-to-image for PNG generation
 */
import { computed, nextTick, ref, watch } from 'vue'

import { ElButton, ElCheckbox, ElDialog, ElIcon, ElScrollbar } from 'element-plus'

import { Close, Download, Select } from '@element-plus/icons-vue'

import DOMPurify from 'dompurify'
import { toPng } from 'html-to-image'
import MarkdownIt from 'markdown-it'

import mindmateAvatar from '@/assets/mindmate-avatar-md.png'
import { useLanguage, useNotifications } from '@/composables'
import type { MindMateMessage } from '@/composables/useMindMate'
import { useAuthStore } from '@/stores'

const props = defineProps<{
  visible: boolean
  messages: MindMateMessage[]
  conversationTitle: string
}>()

// Auth store for user info
const authStore = useAuthStore()

// Get display name and avatar from auth store
const displayName = computed(() => authStore.user?.username || 'You')
const userAvatar = computed(() => authStore.user?.avatar || '👤')

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { isZh } = useLanguage()
const notify = useNotifications()

// Markdown renderer
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: true,
})

// Local state
const selectedMessageIds = ref<Set<string>>(new Set())
const isExporting = ref(false)
const previewRef = ref<HTMLElement | null>(null)

// Filter only user and assistant messages (exclude system)
const selectableMessages = computed(() =>
  props.messages.filter((m) => m.role === 'user' || m.role === 'assistant')
)

// Selected messages in order
const selectedMessages = computed(() =>
  selectableMessages.value.filter((m) => selectedMessageIds.value.has(m.id))
)

// Watch for dialog open to reset selection
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      // By default, select all messages
      selectedMessageIds.value = new Set(selectableMessages.value.map((m) => m.id))
    }
  }
)

function closeDialog() {
  emit('update:visible', false)
}

function toggleMessage(messageId: string) {
  const newSet = new Set(selectedMessageIds.value)
  if (newSet.has(messageId)) {
    newSet.delete(messageId)
  } else {
    newSet.add(messageId)
  }
  selectedMessageIds.value = newSet
}

function selectAll() {
  selectedMessageIds.value = new Set(selectableMessages.value.map((m) => m.id))
}

function deselectAll() {
  selectedMessageIds.value = new Set()
}

function renderMarkdown(content: string): string {
  if (!content) return ''
  const html = md.render(content)
  return DOMPurify.sanitize(html)
}

/**
 * Check if a URL is an external URL that needs proxying
 * Local assets (bundled by Vite) don't need proxying
 */
function isExternalUrl(url: string): boolean {
  return url.startsWith('http://') || url.startsWith('https://')
}

/**
 * Convert an external image URL to base64 data URL using a proxy to avoid CORS issues
 */
async function imageToBase64(url: string): Promise<string> {
  // Only proxy external URLs
  if (!isExternalUrl(url)) {
    // For local/bundled assets, fetch directly
    try {
      const response = await fetch(url)
      if (!response.ok) return url
      const blob = await response.blob()
      return new Promise((resolve) => {
        const reader = new FileReader()
        reader.onloadend = () => resolve(reader.result as string)
        reader.onerror = () => resolve(url)
        reader.readAsDataURL(blob)
      })
    } catch {
      return url
    }
  }

  try {
    // Use the backend proxy to fetch external images and avoid CORS
    const proxyUrl = `/api/proxy-image?url=${encodeURIComponent(url)}`
    const response = await fetch(proxyUrl)
    if (!response.ok) {
      console.warn(`Failed to fetch image via proxy: ${url}`)
      return url // Return original URL as fallback
    }
    const blob = await response.blob()
    return new Promise((resolve) => {
      const reader = new FileReader()
      reader.onloadend = () => resolve(reader.result as string)
      reader.onerror = () => resolve(url) // Fallback to original URL
      reader.readAsDataURL(blob)
    })
  } catch (error) {
    console.warn(`Failed to convert image to base64: ${url}`, error)
    return url // Return original URL as fallback
  }
}

/**
 * Pre-process all images in the export container to convert URLs to base64
 * This fixes CORS issues with html-to-image for external images
 */
async function convertImagesToBase64(container: HTMLElement): Promise<void> {
  const images = container.querySelectorAll('img')
  const promises: Promise<void>[] = []

  images.forEach((img) => {
    const src = img.getAttribute('src')
    // Skip already-converted images (data: or blob:)
    if (src && !src.startsWith('data:') && !src.startsWith('blob:')) {
      promises.push(
        imageToBase64(src).then((base64) => {
          img.setAttribute('src', base64)
        })
      )
    }
  })

  await Promise.all(promises)
}

async function exportAsPng() {
  if (!previewRef.value || selectedMessages.value.length === 0) {
    notify.warning(isZh.value ? '请至少选择一条消息' : 'Please select at least one message')
    return
  }

  isExporting.value = true

  try {
    // Wait for Vue DOM updates before capturing
    await nextTick()

    // Convert all external images to base64 to avoid CORS issues
    await convertImagesToBase64(previewRef.value)

    const dataUrl = await toPng(previewRef.value, {
      backgroundColor: '#ffffff',
      pixelRatio: 2,
      style: {
        transform: 'none',
      },
    })

    // Create download link
    const link = document.createElement('a')
    const timestamp = new Date().toISOString().slice(0, 10)
    const filename = `${props.conversationTitle || 'MindMate'}_${timestamp}.png`
    link.download = filename.replace(/[/\\?%*:|"<>]/g, '-')
    link.href = dataUrl
    link.click()

    notify.success(isZh.value ? '导出成功' : 'Export successful')
    closeDialog()
  } catch (error) {
    console.error('Failed to export PNG:', error)
    notify.error(isZh.value ? '导出失败，请重试' : 'Export failed, please try again')
  } finally {
    isExporting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="isZh ? '分享对话' : 'Share Conversation'"
    width="640px"
    :close-on-click-modal="false"
    :append-to-body="true"
    class="share-export-modal"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="modal-content">
      <!-- Header with selection info -->
      <div class="modal-header">
        <div class="header-info">
          <div class="header-title">
            {{ isZh ? '选择要导出的消息' : 'Select messages to export' }}
          </div>
          <div class="header-count">
            <span class="count-selected">{{ selectedMessages.length }}</span>
            <span class="count-divider">/</span>
            <span class="count-total">{{ selectableMessages.length }}</span>
            <span class="count-label">{{ isZh ? '条已选' : 'selected' }}</span>
          </div>
        </div>
        <div class="header-actions">
          <el-button
            size="small"
            @click="selectAll"
          >
            <el-icon><Select /></el-icon>
            {{ isZh ? '全选' : 'All' }}
          </el-button>
          <el-button
            size="small"
            @click="deselectAll"
          >
            <el-icon><Close /></el-icon>
            {{ isZh ? '清除' : 'Clear' }}
          </el-button>
        </div>
      </div>

      <!-- Message Selection List with proper scrolling -->
      <div class="message-list-container">
        <el-scrollbar class="message-list-scrollbar">
          <div class="message-list">
            <div
              v-for="message in selectableMessages"
              :key="message.id"
              class="message-item"
              :class="{
                selected: selectedMessageIds.has(message.id),
                'is-user': message.role === 'user',
                'is-assistant': message.role === 'assistant',
              }"
              @click="toggleMessage(message.id)"
            >
              <el-checkbox
                :model-value="selectedMessageIds.has(message.id)"
                size="large"
                @click.stop
                @update:model-value="toggleMessage(message.id)"
              />
              <div class="message-avatar">
                <span
                  v-if="message.role === 'user'"
                  class="avatar-emoji"
                  >{{ userAvatar }}</span
                >
                <img
                  v-else
                  :src="mindmateAvatar"
                  alt="MindMate"
                  class="avatar-img"
                />
              </div>
              <div class="message-info">
                <div class="message-role">
                  {{ message.role === 'user' ? displayName : 'MindMate' }}
                </div>
                <div class="message-content-preview">
                  {{ message.content.slice(0, 120) }}{{ message.content.length > 120 ? '...' : '' }}
                </div>
              </div>
            </div>
          </div>
        </el-scrollbar>
      </div>

      <!-- Selection tip -->
      <div class="selection-tip">
        <span
          v-if="selectedMessages.length === 0"
          class="tip-warning"
        >
          {{ isZh ? '请至少选择一条消息' : 'Please select at least one message' }}
        </span>
        <span
          v-else
          class="tip-info"
        >
          {{ isZh ? '点击消息可切换选中状态' : 'Click messages to toggle selection' }}
        </span>
      </div>

      <!-- Export Container (off-screen, used for PNG generation) -->
      <div class="export-container-wrapper">
        <div
          ref="previewRef"
          class="export-container"
        >
          <!-- Header -->
          <div class="export-header">
            <div class="export-logo">MindMate</div>
            <div class="export-title">{{ conversationTitle }}</div>
          </div>

          <!-- Messages -->
          <div class="export-messages">
            <div
              v-for="message in selectedMessages"
              :key="message.id"
              class="export-message-row"
              :class="message.role === 'user' ? 'export-row-user' : 'export-row-assistant'"
            >
              <!-- MindMate message: Avatar on left -->
              <template v-if="message.role === 'assistant'">
                <img
                  :src="mindmateAvatar"
                  alt="MindMate"
                  class="export-avatar export-avatar-mindmate"
                />
                <div class="export-bubble export-bubble-assistant">
                  <div class="export-name">MindMate</div>
                  <div class="export-content">
                    <div
                      class="markdown-content"
                      v-html="renderMarkdown(message.content)"
                    />
                  </div>
                </div>
              </template>

              <!-- User message: Avatar on right -->
              <template v-else>
                <div class="export-bubble export-bubble-user">
                  <div class="export-name">{{ displayName }}</div>
                  <div class="export-content">
                    <div class="plain-content">{{ message.content }}</div>
                  </div>
                </div>
                <div class="export-avatar export-avatar-user">
                  {{ userAvatar }}
                </div>
              </template>
            </div>
          </div>

          <!-- Footer -->
          <div class="export-footer">
            <span>{{
              isZh ? '由 MindMate AI 助手生成' : 'Generated by MindMate AI Assistant'
            }}</span>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog">
          {{ isZh ? '取消' : 'Cancel' }}
        </el-button>
        <el-button
          type="primary"
          :loading="isExporting"
          :disabled="selectedMessages.length === 0"
          @click="exportAsPng"
        >
          <el-icon><Download /></el-icon>
          {{ isZh ? '导出 PNG' : 'Export PNG' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.modal-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Header Section */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.dark .modal-header {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
  border-color: #475569;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.dark .header-title {
  color: #f1f5f9;
}

.header-count {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.count-selected {
  font-weight: 700;
  color: #6366f1;
  font-size: 16px;
}

.count-divider {
  color: #94a3b8;
}

.count-total {
  color: #64748b;
}

.count-label {
  color: #94a3b8;
  margin-left: 4px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* Message List Container - Fixed height with scrolling */
.message-list-container {
  height: 380px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  background: #fafafa;
}

.dark .message-list-container {
  border-color: #475569;
  background: #1e293b;
}

.message-list-scrollbar {
  height: 100%;
}

.message-list-scrollbar :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}

.message-list-scrollbar :deep(.el-scrollbar__bar.is-vertical) {
  width: 8px;
}

.message-list-scrollbar :deep(.el-scrollbar__thumb) {
  background-color: rgba(99, 102, 241, 0.3);
  border-radius: 4px;
}

.message-list-scrollbar :deep(.el-scrollbar__thumb:hover) {
  background-color: rgba(99, 102, 241, 0.5);
}

/* Checkbox styling */
.message-item :deep(.el-checkbox) {
  flex-shrink: 0;
}

.message-item :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: #6366f1;
  border-color: #6366f1;
}

.message-item :deep(.el-checkbox__inner:hover) {
  border-color: #6366f1;
}

.message-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 6px;
}

.message-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 2px solid transparent;
  background: white;
}

.dark .message-item {
  background: #334155;
}

.message-item:hover {
  background: #f1f5f9;
  transform: translateX(2px);
}

.dark .message-item:hover {
  background: #475569;
}

.message-item.selected {
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
  border-color: #6366f1;
}

.dark .message-item.selected {
  background: linear-gradient(135deg, #312e81 0%, #3730a3 100%);
  border-color: #818cf8;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-emoji {
  font-size: 18px;
  background: #f1f5f9;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.dark .avatar-emoji {
  background: #475569;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.message-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
}

.is-user .message-role {
  color: #3b82f6;
}

.is-assistant .message-role {
  color: #8b5cf6;
}

.message-content-preview {
  font-size: 13px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.dark .message-content-preview {
  color: #94a3b8;
}

/* Selection Tip */
.selection-tip {
  text-align: center;
  padding: 8px;
  font-size: 12px;
}

.tip-warning {
  color: #f59e0b;
  font-weight: 500;
}

.tip-info {
  color: #94a3b8;
}

/* Export Container (off-screen for PNG generation) */
.export-container-wrapper {
  position: fixed;
  left: -9999px;
  top: 0;
  pointer-events: none;
}

/* Export Container (for PNG generation) */
.export-container {
  width: 600px;
  padding: 32px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.export-header {
  text-align: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e5e7eb;
}

.export-logo {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 8px;
}

.export-title {
  font-size: 16px;
  color: #6b7280;
}

.export-messages {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Message row - controls left/right alignment */
.export-message-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

/* User messages: align to the right */
.export-row-user {
  justify-content: flex-end;
}

/* Assistant messages: align to the left */
.export-row-assistant {
  justify-content: flex-start;
}

/* Avatar styles */
.export-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
}

.export-avatar-user {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border: 2px solid #93c5fd;
}

.export-avatar-mindmate {
  object-fit: cover;
  border: 2px solid #c4b5fd;
}

/* Message bubble - adaptive width */
.export-bubble {
  max-width: 75%;
  display: inline-flex;
  flex-direction: column;
}

.export-bubble-user {
  align-items: flex-end;
}

.export-bubble-assistant {
  align-items: flex-start;
}

/* Name label */
.export-name {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
  padding: 0 4px;
}

.export-bubble-user .export-name {
  color: #3b82f6;
  text-align: right;
}

.export-bubble-assistant .export-name {
  color: #8b5cf6;
}

/* Message content bubble */
.export-content {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-wrap: break-word;
}

.export-bubble-user .export-content {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.export-bubble-assistant .export-content {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  color: #1f2937;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
}

.export-footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
}

/* Markdown styling in preview and export */
.markdown-content :deep(p) {
  margin: 0 0 8px 0;
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(code) {
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.markdown-content :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
  line-height: 1.5;
}

.markdown-content :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-content :deep(li) {
  margin: 4px 0;
}

.markdown-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 8px 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
}

/* Dialog customization */
:deep(.el-dialog) {
  border-radius: 16px;
  overflow: hidden;
}

:deep(.el-dialog__header) {
  padding: 16px 20px;
  margin: 0;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
}

:deep(.el-dialog__title) {
  color: white;
  font-weight: 600;
  font-size: 16px;
}

:deep(.el-dialog__headerbtn) {
  top: 16px;
  right: 16px;
}

:deep(.el-dialog__headerbtn .el-dialog__close) {
  color: white;
}

:deep(.el-dialog__headerbtn:hover .el-dialog__close) {
  color: #e0e7ff;
}

:deep(.el-dialog__body) {
  padding: 20px;
}

:deep(.el-dialog__footer) {
  padding: 12px 20px 20px;
  border-top: 1px solid #e2e8f0;
}

.dark :deep(.el-dialog__footer) {
  border-top-color: #475569;
}
</style>
