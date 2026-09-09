<script setup lang="ts">
/**
 * Dialog to attach an image URL or compressed file to the selected node.
 */
import { ref, watch } from 'vue'

import { ElButton, ElDialog, ElInput } from 'element-plus'

import { useLanguage } from '@/composables/core/useLanguage'
import { sanitizeMindMapImageUrl } from '@/utils/mindMapAdornments'
import { mindMapNodeImageFileToDataUrl } from '@/utils/mindMapNodeImageDataUrl'

const props = defineProps<{
  modelValue: boolean
  initialUrl?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [imageUrl: string]
}>()

const { t } = useLanguage()
const url = ref('')
const error = ref('')
const busy = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      url.value = props.initialUrl ?? ''
      error.value = ''
      busy.value = false
    }
  }
)

function close(): void {
  emit('update:modelValue', false)
}

function confirmUrl(): void {
  const sanitized = sanitizeMindMapImageUrl(url.value)
  if (!sanitized) {
    error.value = t('canvas.ribbon.imageInvalid')
    return
  }
  emit('confirm', sanitized)
  close()
}

async function onFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  busy.value = true
  error.value = ''
  const dataUrl = await mindMapNodeImageFileToDataUrl(file)
  busy.value = false
  if (!dataUrl) {
    error.value = t('canvas.ribbon.imageTooLarge')
    return
  }
  emit('confirm', dataUrl)
  close()
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="t('canvas.ribbon.insertImage')"
    width="420px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElInput
      v-model="url"
      :placeholder="t('canvas.ribbon.imageUrl')"
      :disabled="busy"
      @keydown.enter.prevent="confirmUrl"
    />
    <div class="mm-image-file-row">
      <input
        ref="fileInput"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        class="hidden"
        @change="onFile"
      />
      <ElButton
        :disabled="busy"
        @click="fileInput?.click()"
        >{{ t('canvas.ribbon.imagePick') }}</ElButton
      >
    </div>
    <p
      v-if="error"
      class="mm-insert-error"
    >
      {{ error }}
    </p>
    <template #footer>
      <ElButton @click="close">{{ t('common.cancel') }}</ElButton>
      <ElButton
        type="primary"
        :disabled="busy"
        @click="confirmUrl"
        >{{ t('canvas.ribbon.imageConfirm') }}</ElButton
      >
    </template>
  </ElDialog>
</template>

<style scoped>
.mm-image-file-row {
  margin-top: 12px;
}

.hidden {
  display: none;
}

.mm-insert-error {
  margin: 8px 0 0;
  color: var(--el-color-danger);
  font-size: 12px;
}
</style>
