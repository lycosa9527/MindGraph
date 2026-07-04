<script setup lang="ts">
import { ElButton } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'

const emit = defineEmits<{ close: [] }>()

const { t } = useLanguage()
</script>

<template>
  <ElButton
    text
    circle
    size="small"
    class="mind-map-side-panel-close"
    :icon="Close"
    :aria-label="t('canvas.mindMapSideToolbar.closePanel')"
    @click="emit('close')"
  />
</template>

<style scoped>
.mind-map-side-panel-close {
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
  flex-shrink: 0;
}
</style>
