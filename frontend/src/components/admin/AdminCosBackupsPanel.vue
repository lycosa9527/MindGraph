<script setup lang="ts">
import { computed } from 'vue'

import { ElMessageBox } from 'element-plus'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage, useNotifications } from '@/composables'
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
  await ElMessageBox.confirm(t('admin.cos.confirmBackup'), t('admin.cos.runBackup'), {
    type: 'warning',
  })
  try {
    const result = await triggerBackup.mutateAsync()
    if (result.ok) notify.success(t('admin.cos.backupTriggered'))
    else notify.error(t('admin.cos.backupFailed'))
  } catch {
    notify.error(t('admin.cos.backupFailed'))
  }
}
</script>

<template>
  <div v-loading="loading" class="admin-cos-backups">
    <div class="admin-cos-kpi-row">
      <AdminSwissKpiCard
        :title="t('admin.cos.localBackupCount')"
        :value="String(localBackups.length)"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.cosBackupCount')"
        :value="String(cosBackups.length)"
      />
    </div>
    <div class="admin-cos-actions">
      <el-button type="primary" :loading="triggerBackup.isPending.value" @click="onTriggerBackup">
        {{ t('admin.cos.runBackup') }}
      </el-button>
    </div>
    <h4>{{ t('admin.cos.cosObjects') }}</h4>
    <el-table :data="cosBackups" size="small" stripe>
      <el-table-column prop="filename" :label="t('admin.cos.fileName')" />
      <el-table-column prop="size_mb" :label="t('admin.cos.sizeMb')" width="100" />
      <el-table-column prop="last_modified" :label="t('admin.cos.lastModified')" />
      <el-table-column prop="has_manifest" :label="t('admin.cos.manifest')" width="90">
        <template #default="{ row }">
          {{ row.has_manifest ? t('admin.cos.yes') : t('admin.cos.no') }}
        </template>
      </el-table-column>
    </el-table>
    <h4 class="mt-4">{{ t('admin.cos.localObjects') }}</h4>
    <el-table :data="localBackups" size="small" stripe>
      <el-table-column prop="filename" :label="t('admin.cos.fileName')" />
      <el-table-column prop="size_mb" :label="t('admin.cos.sizeMb')" width="100" />
      <el-table-column prop="created" :label="t('admin.cos.lastModified')" />
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
