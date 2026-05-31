<script setup lang="ts">
/**
 * Apply button for 系统设置 → 功能 (AdminPage header, top right).
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { useAdminFeaturesHeaderToolbarModel } from '@/composables/admin/useAdminFeaturesHeaderToolbar'

const { t } = useLanguage()
const toolbarState = useAdminFeaturesHeaderToolbarModel()
const saving = computed(() => toolbarState.value?.saving.value ?? false)

function onApply(): void {
  void toolbarState.value?.save()
}
</script>

<template>
  <el-button
    v-if="toolbarState"
    type="primary"
    size="small"
    class="admin-features-apply-btn shrink-0"
    :loading="saving"
    @click="onApply"
  >
    {{ t('admin.featuresSave') }}
  </el-button>
</template>

<style scoped>
.admin-features-apply-btn {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-text-color: #fafaf9;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  --el-button-hover-text-color: #fafaf9;
  --el-button-active-bg-color: #44403c;
  --el-button-active-border-color: #44403c;
  font-weight: 500;
  border-radius: 9999px;
}
</style>
