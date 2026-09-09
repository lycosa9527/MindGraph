<script setup lang="ts">
/**
 * Emoji picker dialog for a mind-map node icon adornment.
 */
import { ElButton, ElDialog } from 'element-plus'

import EmojiPicker from '@/components/workshop-chat/EmojiPicker.vue'
import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [icon: string]
  clear: []
}>()

const { t } = useLanguage()

function close(): void {
  emit('update:modelValue', false)
}

function onSelect(_name: string, code: string): void {
  emit('confirm', code)
  close()
}

function clearAndClose(): void {
  emit('clear')
  close()
}
</script>

<template>
  <ElDialog
    :model-value="props.modelValue"
    :title="t('canvas.ribbon.insertIcon')"
    width="380px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <EmojiPicker
      hide-search
      lead-category="objects"
      @select="onSelect"
    />
    <template #footer>
      <ElButton @click="clearAndClose">{{ t('canvas.ribbon.clearIcon') }}</ElButton>
      <ElButton @click="close">{{ t('common.cancel') }}</ElButton>
    </template>
  </ElDialog>
</template>
