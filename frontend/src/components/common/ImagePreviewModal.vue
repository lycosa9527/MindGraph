<script setup lang="ts">
/**
 * ImagePreviewModal - Modal for previewing and downloading gallery images
 */
import { ElMessage } from 'element-plus'

import { Download } from 'lucide-vue-next'

const props = defineProps<{
  visible: boolean
  title: string
  imageUrl: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

function handleClose() {
  emit('update:visible', false)
  emit('close')
}

async function handleDownload() {
  try {
    const link = document.createElement('a')
    link.href = props.imageUrl
    link.download = `${props.title}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    ElMessage.success('图片下载成功')
  } catch {
    ElMessage.error('图片下载失败，请稍后再试')
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="80%"
    :before-close="handleClose"
    class="image-preview-modal"
  >
    <div class="flex-1 overflow-auto p-4 flex items-center justify-center bg-gray-50 min-h-[400px]">
      <img
        :src="imageUrl"
        :alt="title"
        class="max-w-full max-h-[70vh] object-contain"
      />
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="handleClose">关闭</el-button>
        <el-button
          type="primary"
          @click="handleDownload"
        >
          <Download class="w-4 h-4 mr-2" />
          下载 PNG
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.image-preview-modal :deep(.el-dialog__body) {
  padding: 0;
}
</style>
