<script setup lang="ts">
import { ElButton } from 'element-plus'

import { Users } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
}>()

const { t } = useLanguage()
</script>

<template>
  <ElButton
    class="contacts-toggle-btn shrink-0"
    :class="{ 'is-active': open }"
    size="small"
    :title="t('mindmate.collabToggleContactsTitle')"
    :aria-expanded="open"
    @click="emit('toggle')"
  >
    <Users class="w-3.5 h-3.5 mr-1" />
    <I18nText
      k="mindmate.collabToggleContacts"
      dense
    />
  </ElButton>
</template>

<style scoped>
.contacts-toggle-btn {
  --el-button-bg-color: #fafaf9;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #f5f5f4;
  --el-button-hover-border-color: #a8a29e;
  --el-button-hover-text-color: #1c1917;
  --el-button-active-bg-color: #e7e5e4;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #44403c;
  font-weight: 500;
  border-radius: 9999px;
  height: auto;
  min-height: 32px;
  padding-top: 4px;
  padding-bottom: 4px;
  line-height: 1.15;
}

.contacts-toggle-btn.is-active {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #a8a29e;
  --el-button-text-color: #1c1917;
}
</style>
