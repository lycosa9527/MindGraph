<script setup lang="ts">
import { computed } from 'vue'

import { ElMessageBox } from 'element-plus'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useInstallAdminCosQdrant, usePublishAdminCosQdrant } from '@/composables/queries'

const props = defineProps<{
  data?: Record<string, unknown> | null
  loading?: boolean
  syncRole?: string
}>()

const { t } = useLanguage()
const notify = useNotifications()
const publish = usePublishAdminCosQdrant()
const install = useInstallAdminCosQdrant()

const cosMeta = computed(() => (props.data?.cos_meta as Record<string, unknown>) ?? null)
const isPublisher = computed(() => props.syncRole === 'publisher')
const isConsumer = computed(() => props.syncRole === 'consumer')

async function onPublish() {
  await ElMessageBox.confirm(t('admin.cos.confirmQdrantPublish'), t('admin.cos.publishQdrant'), {
    type: 'warning',
  })
  try {
    const result = await publish.mutateAsync()
    if (result.ok) notify.success(t('admin.cos.publishOk'))
    else notify.error(String(result.error ?? t('admin.cos.publishFailed')))
  } catch {
    notify.error(t('admin.cos.publishFailed'))
  }
}

async function onInstall() {
  await ElMessageBox.confirm(t('admin.cos.confirmQdrantInstall'), t('admin.cos.installQdrant'), {
    type: 'warning',
  })
  try {
    const result = await install.mutateAsync()
    if (result.needs_root) {
      notify.warning(t('admin.cos.installNeedsRoot'))
      return
    }
    if (result.ok) notify.success(t('admin.cos.installOk'))
    else notify.error(String(result.error ?? t('admin.cos.installFailed')))
  } catch {
    notify.error(t('admin.cos.installFailed'))
  }
}
</script>

<template>
  <div v-loading="loading" class="admin-cos-qdrant">
    <div class="admin-cos-kpi-row">
      <AdminSwissKpiCard
        :title="t('admin.cos.targetVersion')"
        :value="String(data?.target_version ?? '—')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.installedVersion')"
        :value="String(data?.installed_version ?? '—')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.cosVersion')"
        :value="String(cosMeta?.version ?? '—')"
      />
      <AdminSwissKpiCard
        :title="t('admin.cos.status')"
        :value="String(data?.status ?? '—')"
      />
    </div>
    <div class="admin-cos-actions">
      <el-button
        v-if="isPublisher"
        type="primary"
        :loading="publish.isPending.value"
        @click="onPublish"
      >
        {{ t('admin.cos.publishQdrant') }}
      </el-button>
      <el-button
        v-if="isConsumer"
        type="primary"
        :loading="install.isPending.value"
        @click="onInstall"
      >
        {{ t('admin.cos.installQdrant') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.admin-cos-kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
.admin-cos-actions {
  margin-top: 16px;
}
</style>
