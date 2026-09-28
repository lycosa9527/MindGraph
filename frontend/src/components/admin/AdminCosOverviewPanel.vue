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
  <div
    v-loading="loading"
    class="admin-cos-overview"
  >
    <el-alert
      v-if="error"
      type="error"
      :title="t('admin.cos.loadError')"
      show-icon
      class="mb-4"
    />
    <div class="admin-cos-kpi-row">
      <AdminSwissKpiCard title-key="admin.cos.connection">
        <template #value>
          <I18nText :k="connection.ok ? 'admin.cos.connected' : 'admin.cos.disconnected'" />
        </template>
      </AdminSwissKpiCard>
      <AdminSwissKpiCard
        title-key="admin.cos.syncRole"
        :value="String(data?.sync_role ?? 'off')"
      />
      <AdminSwissKpiCard
        title-key="admin.cos.bucket"
        :value="String(config.bucket ?? '—')"
      />
      <AdminSwissKpiCard
        title-key="admin.cos.nextRun"
        :value="String(data?.next_scheduled_run ?? '—')"
      />
    </div>
    <el-descriptions
      :column="2"
      border
      class="mt-4"
    >
      <el-descriptions-item>
        <template #label>
          <I18nText k="admin.cos.region" />
        </template>
        {{ config.region }}
      </el-descriptions-item>
      <el-descriptions-item>
        <template #label>
          <I18nText k="admin.cos.keyPrefix" />
        </template>
        {{ config.key_prefix }}
      </el-descriptions-item>
      <el-descriptions-item>
        <template #label>
          <I18nText k="admin.cos.backupEnabled" />
        </template>
        <I18nText
          v-if="config.backup_enabled"
          k="admin.cos.yes"
        /><I18nText
          v-else
          k="admin.cos.no"
        />
      </el-descriptions-item>
      <el-descriptions-item>
        <template #label>
          <I18nText k="admin.cos.syncEnabled" />
        </template>
        <I18nText
          v-if="config.sync_enabled"
          k="admin.cos.yes"
        /><I18nText
          v-else
          k="admin.cos.no"
        />
      </el-descriptions-item>
    </el-descriptions>
    <h4 class="admin-cos-subtitle"><I18nText k="admin.cos.artifactHealth" /></h4>
    <ul class="admin-cos-health-list">
      <li><I18nText k="admin.cos.sectionBackups" />: {{ healthLabel('database_backups') }}</li>
      <li><I18nText k="admin.cos.sectionCrowdsec" />: {{ healthLabel('crowdsec') }}</li>
      <li><I18nText k="admin.cos.sectionQdrant" />: {{ healthLabel('qdrant') }}</li>
      <li><I18nText k="admin.cos.sectionPlaywright" />: {{ healthLabel('playwright') }}</li>
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
