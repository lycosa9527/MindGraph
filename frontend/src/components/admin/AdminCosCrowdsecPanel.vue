<script setup lang="ts">
import { computed } from 'vue'

import { ElMessageBox } from 'element-plus'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useTriggerAdminCosCrowdsecSync } from '@/composables/queries'

const props = defineProps<{
  data?: Record<string, unknown> | null
  loading?: boolean
  syncRole?: string
}>()

const { t } = useLanguage()
const notify = useNotifications()
const triggerSync = useTriggerAdminCosCrowdsecSync()

const localMeta = computed(() => (props.data?.local_meta as Record<string, unknown>) ?? null)
const cosMeta = computed(() => (props.data?.cos_meta as Record<string, unknown>) ?? null)

async function onSync() {
  await ElMessageBox.confirm(t('admin.cos.confirmCrowdsecSync'), t('admin.cos.syncNow'), {
    type: 'warning',
  })
  try {
    const result = await triggerSync.mutateAsync()
    if (result.ok) notify.success(t('admin.cos.syncOk'))
    else notify.error(String(result.error ?? t('admin.cos.syncFailed')))
  } catch {
    notify.error(t('admin.cos.syncFailed'))
  }
}
</script>

<template>
  <div v-loading="loading" class="admin-cos-crowdsec">
    <el-alert
      :title="t('admin.cos.roleHint', { role: syncRole ?? 'off' })"
      type="info"
      show-icon
      class="mb-4"
    />
    <div class="admin-cos-kpi-row">
      <AdminSwissKpiCard
        :title="t('admin.cos.blacklistIpCount')"
        :value="String(data?.blacklist_ip_count ?? '—')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.syncState')"
        :value="String(data?.sync_state ?? '—')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.cosIpCount')"
        :value="String(cosMeta?.count ?? '—')"
      />
    </div>
    <el-descriptions :column="1" border>
      <el-descriptions-item :label="t('admin.cos.localLastMerge')">
        {{ localMeta?.last_merge_unix ?? '—' }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('admin.cos.cosLastMerge')">
        {{ data?.cos_last_merge_iso ?? '—' }}
      </el-descriptions-item>
    </el-descriptions>
    <div class="admin-cos-actions">
      <el-button type="primary" :loading="triggerSync.isPending.value" @click="onSync">
        {{ t('admin.cos.syncNow') }}
      </el-button>
    </div>
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
  margin-top: 16px;
}
.mb-4 {
  margin-bottom: 16px;
}
</style>
