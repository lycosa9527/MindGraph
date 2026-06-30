<script setup lang="ts">
import { computed } from 'vue'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage } from '@/composables'

const props = defineProps<{
  data?: Record<string, unknown> | null
  loading?: boolean
  error?: unknown
}>()

const { t } = useLanguage()

const connection = computed(() => (props.data?.connection as Record<string, unknown>) ?? {})
const config = computed(() => (props.data?.config as Record<string, unknown>) ?? {})
const artifacts = computed(() => (props.data?.artifacts as Record<string, unknown>) ?? {})

function healthLabel(key: string): string {
  const item = artifacts.value[key] as Record<string, unknown> | undefined
  const health = item?.health as string | undefined
  if (health === 'ok') return t('admin.cos.healthOk')
  if (health === 'missing') return t('admin.cos.healthMissing')
  if (health === 'error') return t('admin.cos.healthError')
  return t('admin.cos.healthDisabled')
}
</script>

<template>
  <div v-loading="loading" class="admin-cos-overview">
    <el-alert
      v-if="error"
      type="error"
      :title="t('admin.cos.loadError')"
      show-icon
      class="mb-4"
    />
    <div class="admin-cos-kpi-row">
      <AdminSwissKpiCard
        :title="t('admin.cos.connection')"
        :value="connection.ok ? t('admin.cos.connected') : t('admin.cos.disconnected')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.syncRole')"
        :value="String(data?.sync_role ?? 'off')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.bucket')"
        :value="String(config.bucket ?? '—')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.nextRun')"
        :value="String(data?.next_scheduled_run ?? '—')"
      />
    </div>
    <el-descriptions :column="2" border class="mt-4">
      <el-descriptions-item :label="t('admin.cos.region')">
        {{ config.region }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('admin.cos.keyPrefix')">
        {{ config.key_prefix }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('admin.cos.backupEnabled')">
        {{ config.backup_enabled ? t('admin.cos.yes') : t('admin.cos.no') }}
      </el-descriptions-item>
      <el-descriptions-item :label="t('admin.cos.syncEnabled')">
        {{ config.sync_enabled ? t('admin.cos.yes') : t('admin.cos.no') }}
      </el-descriptions-item>
    </el-descriptions>
    <h4 class="admin-cos-subtitle">{{ t('admin.cos.artifactHealth') }}</h4>
    <ul class="admin-cos-health-list">
      <li>{{ t('admin.cos.sectionBackups') }}: {{ healthLabel('database_backups') }}</li>
      <li>{{ t('admin.cos.sectionCrowdsec') }}: {{ healthLabel('crowdsec') }}</li>
      <li>{{ t('admin.cos.sectionQdrant') }}: {{ healthLabel('qdrant') }}</li>
    </ul>
  </div>
</template>

<style scoped>
.admin-cos-kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
.admin-cos-subtitle {
  margin: 20px 0 8px;
  font-size: 14px;
  font-weight: 600;
}
.admin-cos-health-list {
  margin: 0;
  padding-left: 18px;
}
.mb-4 {
  margin-bottom: 16px;
}
.mt-4 {
  margin-top: 16px;
}
</style>
