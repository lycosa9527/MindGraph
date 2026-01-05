<script setup lang="ts">
/**
 * ShareExportModal - Modal for selecting messages and exporting as PNG
 * Uses html-to-image for PNG generation
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElCheckbox, ElDialog, ElIcon, ElScrollbar } from 'element-plus'

import { Close, Download, Select } from '@element-plus/icons-vue'

import DOMPurify from 'dompurify'
import { toPng } from 'html-to-image'
import MarkdownIt from 'markdown-it'

import { useLanguage, useNotifications } from '@/composables'
import type { MindMateMessage } from '@/composables/useMindMate'

const props = defineProps<{
  visible: boolean
  messages: MindMateMessage[]
  conversationTitle: string
}>()

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

async function exportAsPng() {
  if (!previewRef.value || selectedMessages.value.length === 0) {
    notify.warning(isZh.value ? '请至少选择一条消息' : 'Please select at least one message')
    return
  }

  isExporting.value = true

  try {
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
    width="700px"
    :close-on-click-modal="false"
    :append-to-body="true"
    class="share-export-modal"
    @update:model-value="emit('update:visible', $event)"
  >
    <div class="modal-content">
      <!-- Selection Controls -->
      <div class="selection-controls">
        <span class="selection-label">
          {{ isZh ? '选择要导出的消息' : 'Select messages to export' }}
          ({{ selectedMessages.length }}/{{ selectableMessages.length }})
        </span>
        <div class="selection-actions">
          <el-button
            text
            size="small"
            @click="selectAll"
          >
            <el-icon><Select /></el-icon>
            {{ isZh ? '全选' : 'Select All' }}
          </el-button>
          <el-button
            text
            size="small"
            @click="deselectAll"
          >
            <el-icon><Close /></el-icon>
            {{ isZh ? '取消全选' : 'Deselect All' }}
          </el-button>
        </div>
      </div>

      <!-- Message Selection List -->
      <el-scrollbar class="message-list-scroll">
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
              @click.stop
              @update:model-value="toggleMessage(message.id)"
            />
            <div class="message-preview">
              <span class="message-role">
                {{ message.role === 'user' ? (isZh ? '我' : 'You') : 'AI' }}
              </span>
              <span class="message-content-preview">
                {{ message.content.slice(0, 100) }}{{ message.content.length > 100 ? '...' : '' }}
              </span>
            </div>
          </div>
        </div>
      </el-scrollbar>

      <!-- Preview Area (Hidden but used for export) -->
      <div
        v-show="false"
        class="export-container-wrapper"
      >
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
              class="export-message"
              :class="message.role === 'user' ? 'export-user' : 'export-assistant'"
            >
              <div class="export-avatar">
                {{ message.role === 'user' ? (isZh ? '我' : 'You') : 'AI' }}
              </div>
              <div class="export-content">
                <div
                  v-if="message.role === 'assistant'"
                  class="markdown-content"
                  v-html="renderMarkdown(message.content)"
                />
                <div
                  v-else
                  class="plain-content"
                >
                  {{ message.content }}
                </div>
              </div>
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

      <!-- Visible Preview -->
      <div
        v-if="selectedMessages.length > 0"
        class="preview-section"
      >
        <div class="preview-label">{{ isZh ? '预览' : 'Preview' }}</div>
        <el-scrollbar class="preview-scroll">
          <div class="preview-content">
            <div
              v-for="message in selectedMessages"
              :key="message.id"
              class="preview-message"
              :class="message.role === 'user' ? 'preview-user' : 'preview-assistant'"
            >
              <div class="preview-avatar">
                {{ message.role === 'user' ? (isZh ? '我' : 'You') : 'AI' }}
              </div>
              <div class="preview-text">
                <div
                  v-if="message.role === 'assistant'"
                  class="markdown-content"
                  v-html="renderMarkdown(message.content)"
                />
                <div
                  v-else
                  class="plain-content"
                >
                  {{ message.content }}
                </div>
              </div>
            </div>
          </div>
        </el-scrollbar>
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
  gap: 16px;
}

.selection-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e5e7eb;
}

.selection-label {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

.dark .selection-label {
  color: #e5e7eb;
}

.selection-actions {
  display: flex;
  gap: 8px;
}

.message-list-scroll {
  max-height: 200px;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px;
}

.message-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s;
  border: 1px solid transparent;
}

.message-item:hover {
  background-color: #f3f4f6;
}

.dark .message-item:hover {
  background-color: #374151;
}

.message-item.selected {
  background-color: #eff6ff;
  border-color: #3b82f6;
}

.dark .message-item.selected {
  background-color: #1e3a5f;
  border-color: #3b82f6;
}

.message-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.is-user .message-role {
  color: #3b82f6;
}

.is-assistant .message-role {
  color: #8b5cf6;
}

.message-content-preview {
  font-size: 13px;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dark .message-content-preview {
  color: #d1d5db;
}

/* Preview Section */
.preview-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.dark .preview-section {
  border-color: #4b5563;
}

.preview-label {
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  background-color: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.dark .preview-label {
  background-color: #374151;
  border-color: #4b5563;
  color: #9ca3af;
}

.preview-scroll {
  max-height: 200px;
}

.preview-content {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-message {
  display: flex;
  gap: 10px;
}

.preview-avatar {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.preview-user .preview-avatar {
  background-color: #3b82f6;
  color: white;
}

.preview-assistant .preview-avatar {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  color: white;
}

.preview-text {
  flex: 1;
  font-size: 13px;
  line-height: 1.5;
  color: #374151;
}

.dark .preview-text {
  color: #e5e7eb;
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
  gap: 16px;
}

.export-message {
  display: flex;
  gap: 12px;
}

.export-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.export-user .export-avatar {
  background-color: #3b82f6;
  color: white;
}

.export-assistant .export-avatar {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  color: white;
}

.export-content {
  flex: 1;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}

.export-user .export-content {
  background-color: #3b82f6;
  color: white;
}

.export-assistant .export-content {
  background-color: #f3f4f6;
  color: #1f2937;
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
