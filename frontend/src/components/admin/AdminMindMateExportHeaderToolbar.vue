<script setup lang="ts">
/**
 * MindMate export mode toggle — AdminPage header, top right (Swiss segmented control).
 */
import { computed } from 'vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useMindMateExportPanelTab, type MindMateExportPanelTab } from '@/composables/admin/useMindMateExportPanelTab'
import { useLanguage } from '@/composables'

const { t } = useLanguage()
const { panelTab } = useMindMateExportPanelTab()

const tabOptions = computed(() => [
  { label: t('admin.mindmateExport.tabExport'), value: 'export' as MindMateExportPanelTab },
  { label: t('admin.mindmateExport.tabDumps'), value: 'dumps' as MindMateExportPanelTab },
])
</script>

<template>
  <div class="admin-swiss-toolbar admin-swiss-toolbar--header mindmate-export-header-toolbar">
    <AdminSwissSegmented
      v-model="panelTab"
      :options="tabOptions"
      fit
      :aria-label="t('admin.mindmateExport.panelModeLabel')"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>

<style scoped>
.mindmate-export-header-toolbar {
  flex-shrink: 0;
}
</style>
