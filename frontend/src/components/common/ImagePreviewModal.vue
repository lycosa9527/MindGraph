<script setup lang="ts">
/**
 * ImagePreviewModal - Simple modal for previewing images
 */
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
</script>

<template>
  <el-dialog
    :model-value="visible"
    :show-close="true"
    :close-on-click-modal="true"
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
  </el-dialog>
</template>

<style scoped>
.image-preview-modal :deep(.el-dialog__body) {
  padding: 0;
}
</style>
