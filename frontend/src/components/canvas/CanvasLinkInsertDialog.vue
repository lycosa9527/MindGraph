<script setup lang="ts">
/**
 * Dialog to attach an http(s) hyperlink to the selected mind-map node.
 */
import { ref, watch } from 'vue'

import { ElButton, ElDialog, ElInput } from 'element-plus'

import { useLanguage } from '@/composables/core/useLanguage'
import { sanitizeMindMapHref } from '@/utils/mindMapAdornments'

const props = defineProps<{
  modelValue: boolean
  initialHref?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [href: string]
}>()

const { t } = useLanguage()
const href = ref('')
const error = ref('')

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      href.value = props.initialHref ?? ''
      error.value = ''
    }
  }
)

function close(): void {
  emit('update:modelValue', false)
}

function confirm(): void {
  const sanitized = sanitizeMindMapHref(href.value)
  if (!sanitized) {
    error.value = t('canvas.ribbon.linkInvalid')
    return
  }
  emit('confirm', sanitized)
  close()
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="t('canvas.ribbon.insertLink')"
    width="420px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElInput
      v-model="href"
      :placeholder="t('canvas.ribbon.linkUrl')"
      @keydown.enter.prevent="confirm"
    />
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
        @click="confirm"
        >{{ t('canvas.ribbon.linkConfirm') }}</ElButton
      >
    </template>
  </ElDialog>
</template>

<style scoped>
.mm-insert-error {
  margin: 8px 0 0;
  color: var(--el-color-danger);
  font-size: 12px;
}
</style>
