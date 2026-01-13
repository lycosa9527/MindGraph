<script setup lang="ts">
/**
 * DocumentUpload - Modal/drawer for document upload with drag and drop
 */
import { ref } from 'vue'
import { ElDrawer, ElUpload, ElMessage, ElProgress } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  visible: boolean
  uploading: boolean
  canUpload: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'upload', file: File): void
  (e: 'close'): void
}>()

const { isZh } = useLanguage()
const uploadRef = ref()

const handleFileChange = (file: UploadFile) => {
  if (file.raw) {
    // Validate file size (10MB)
    const maxSize = 10 * 1024 * 1024
    if (file.raw.size > maxSize) {
      ElMessage.error(isZh ? '文件大小不能超过10MB' : 'File size cannot exceed 10MB')
      uploadRef.value?.clearFiles()
      return false
    }

    // Validate file type
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      'text/markdown',
      'image/jpeg',
      'image/png',
      'image/jpg',
    ]
    
    // Also check by extension as fallback
    const ext = file.name.split('.').pop()?.toLowerCase()
    const allowedExts = ['pdf', 'docx', 'txt', 'md', 'jpg', 'jpeg', 'png']
    
    if (!allowedTypes.includes(file.raw.type) && !allowedExts.includes(ext || '')) {
      ElMessage.error(isZh ? '不支持的文件类型' : 'Unsupported file type')
      uploadRef.value?.clearFiles()
      return false
    }

    emit('upload', file.raw)
    uploadRef.value?.clearFiles() // Clear after emit
  }
  return false // Prevent auto upload
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    handleFileChange({ raw: files[0] } as UploadFile)
  }
}

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}
</script>

<template>
  <ElDrawer
    :model-value="visible"
    :title="isZh ? '上传文档' : 'Upload Document'"
    size="500px"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div class="upload-content-wrapper p-4">
      <div
        v-if="!canUpload"
        class="mb-4 p-3 bg-stone-100 rounded-lg text-sm text-stone-600"
      >
        {{ isZh ? '已达到最大文档数量限制 (5个)' : 'Maximum document limit reached (5)' }}
      </div>

      <div
        class="document-upload border-2 border-dashed border-stone-300 rounded-lg p-12 text-center cursor-pointer hover:border-stone-400 transition-colors"
        :class="{ 'opacity-50 cursor-not-allowed': uploading || !canUpload }"
        @drop="handleDrop"
        @dragover="handleDragOver"
      >
        <ElUpload
          ref="uploadRef"
          :auto-upload="false"
          :show-file-list="false"
          :disabled="uploading || !canUpload"
          :on-change="handleFileChange"
          accept=".pdf,.docx,.txt,.md,.jpg,.jpeg,.png"
          drag
        >
          <div class="upload-content">
            <el-icon class="text-5xl text-stone-400 mb-4">
              <Upload />
            </el-icon>
            <div class="text-stone-600 mb-2">
              <span class="text-stone-900 font-medium">
                {{ isZh ? '点击上传' : 'Click to upload' }}
              </span>
              {{ isZh ? '或拖拽文件到此处' : 'or drag file here' }}
            </div>
            <div class="text-xs text-stone-500">
              {{ isZh ? '支持 PDF, DOCX, TXT, MD, 图片 (最大10MB)' : 'Supports PDF, DOCX, TXT, MD, Images (max 10MB)' }}
            </div>
          </div>
        </ElUpload>
      </div>

      <ElProgress
        v-if="uploading"
        :percentage="100"
        :indeterminate="true"
        class="mt-4"
      />
    </div>
  </ElDrawer>
</template>

<style scoped>
.upload-content-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.document-upload {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
