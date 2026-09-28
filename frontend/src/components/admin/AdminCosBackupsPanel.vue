<script setup lang="ts">
import { computed } from 'vue'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { useTriggerAdminCosBackup } from '@/composables/queries'

const props = defineProps<{
  data?: Record<string, unknown> | null
  loading?: boolean
}>()

const { t } = useLanguage()
const notify = useNotifications()
const triggerBackup = useTriggerAdminCosBackup()

const local = computed(() => (props.data?.local as Record<string, unknown>) ?? {})
const cos = computed(() => (props.data?.cos as Record<string, unknown>) ?? {})
const localBackups = computed(() => (local.value.backups as Array<Record<string, unknown>>) ?? [])
const cosBackups = computed(() => (cos.value.backups as Array<Record<string, unknown>>) ?? [])

async function onTriggerBackup() {
  await swissGlassConfirm(t('admin.cos.confirmBackup'), t('admin.cos.runBackup'), {
    type: 'warning',
  })
  try {
    const result = await triggerBackup.mutateAsync()
    if (result.ok) notify.successKey('admin.cos.backupTriggered')
    else notify.errorKey('admin.cos.backupFailed')
  } catch {
    notify.errorKey('admin.cos.backupFailed')
  }
}
</script>

<template>
  <div
    v-loading="loading"
    class="admin-cos-backups"
  >
    <div class="admin-cos-kpi-row">
      <AdminSwissKpiCard
        title-key="admin.cos.localBackupCount"
        :value="String(localBackups.length)"
      />
      <AdminSwissKpiCard
        title-key="admin.cos.cosBackupCount"
        :value="String(cosBackups.length)"
      />
    </div>
    <div class="admin-cos-actions">
      <el-button
        type="primary"
        :loading="triggerBackup.isPending.value"
        @click="onTriggerBackup"
      >
        <I18nText k="admin.cos.runBackup" />
      </el-button>
    </div>
    <h4><I18nText k="admin.cos.cosObjects" /></h4>
    <el-table
      :data="cosBackups"
      size="small"
      stripe
    >
      <el-table-column prop="filename">
        <template #header>
          <I18nText k="admin.cos.fileName" />
        </template>
      </el-table-column>
      <el-table-column
        prop="size_mb"
        width="100"
      >
        <template #header>
          <I18nText k="admin.cos.sizeMb" />
        </template>
      </el-table-column>
      <el-table-column prop="last_modified">
        <template #header>
          <I18nText k="admin.cos.lastModified" />
        </template>
      </el-table-column>
      <el-table-column
        prop="has_manifest"
        width="90"
      >
        <template #header>
          <I18nText k="admin.cos.manifest" />
        </template>
        <template #default="{ row }">
          <I18nText
            v-if="row.has_manifest"
            k="admin.cos.yes"
          /><I18nText
            v-else
            k="admin.cos.no"
          />
        </template>
      </el-table-column>
    </el-table>
    <h4 class="mt-4"><I18nText k="admin.cos.localObjects" /></h4>
    <el-table
      :data="localBackups"
      size="small"
      stripe
    >
      <el-table-column prop="filename">
        <template #header>
          <I18nText k="admin.cos.fileName" />
        </template>
      </el-table-column>
      <el-table-column
        prop="size_mb"
        width="100"
      >
        <template #header>
          <I18nText k="admin.cos.sizeMb" />
        </template>
      </el-table-column>
      <el-table-column prop="created">
        <template #header>
          <I18nText k="admin.cos.lastModified" />
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.admin-cos-kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.admin-cos-actions {
  margin-bottom: 16px;
}
.mt-4 {
  margin-top: 16px;
}
</style>
