<script setup lang="ts">
/**
 * Admin COS tab — mirror sync overview, backups, CrowdSec, Qdrant.
 */
import { computed, ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'

import AdminCosBackupsPanel from '@/components/admin/AdminCosBackupsPanel.vue'
import AdminCosCrowdsecPanel from '@/components/admin/AdminCosCrowdsecPanel.vue'
import AdminCosOverviewPanel from '@/components/admin/AdminCosOverviewPanel.vue'
import AdminCosQdrantPanel from '@/components/admin/AdminCosQdrantPanel.vue'
import AdminMindbotSwissSegmented from '@/components/admin/swiss/AdminMindbotSwissSegmented.vue'
import { useLanguage } from '@/composables'
import {
  useAdminCosBackups,
  useAdminCosCrowdsecStatus,
  useAdminCosQdrantStatus,
  useAdminCosStatus,
} from '@/composables/queries'

type CosSection = 'overview' | 'backups' | 'crowdsec' | 'qdrant'

const { t } = useLanguage()
const section = ref<CosSection>('overview')

const statusQuery = useAdminCosStatus()
const backupsQuery = useAdminCosBackups({ enabled: computed(() => section.value === 'backups') })
const crowdsecQuery = useAdminCosCrowdsecStatus({
  enabled: computed(() => section.value === 'crowdsec'),
})
const qdrantQuery = useAdminCosQdrantStatus({ enabled: computed(() => section.value === 'qdrant') })

const sectionOptions = computed(() => [
  { label: t('admin.cos.sectionOverview'), value: 'overview' as const },
  { label: t('admin.cos.sectionBackups'), value: 'backups' as const },
  { label: t('admin.cos.sectionCrowdsec'), value: 'crowdsec' as const },
  { label: t('admin.cos.sectionQdrant'), value: 'qdrant' as const },
])

watch(section, (value) => {
  if (value === 'backups') backupsQuery.refetch()
  if (value === 'crowdsec') crowdsecQuery.refetch()
  if (value === 'qdrant') qdrantQuery.refetch()
})

async function refreshAll() {
  await statusQuery.refetch()
  if (section.value === 'backups') await backupsQuery.refetch()
  if (section.value === 'crowdsec') await crowdsecQuery.refetch()
  if (section.value === 'qdrant') await qdrantQuery.refetch()
}
</script>

<template>
  <div class="admin-cos-tab">
    <div class="admin-cos-tab__header">
      <AdminMindbotSwissSegmented
        v-model="section"
        :options="sectionOptions"
        :aria-label="t('admin.cos.tab')"
        block
      />
      <el-button size="small" @click="refreshAll">{{ t('admin.cos.refresh') }}</el-button>
    </div>

    <AdminCosOverviewPanel
      v-if="section === 'overview'"
      :data="statusQuery.data.value"
      :loading="statusQuery.isFetching.value"
      :error="statusQuery.error.value"
    />
    <AdminCosBackupsPanel
      v-else-if="section === 'backups'"
      :data="backupsQuery.data.value"
      :loading="backupsQuery.isFetching.value"
    />
    <AdminCosCrowdsecPanel
      v-else-if="section === 'crowdsec'"
      :data="crowdsecQuery.data.value"
      :loading="crowdsecQuery.isFetching.value"
      :sync-role="(statusQuery.data.value?.sync_role as string) ?? 'off'"
    />
    <AdminCosQdrantPanel
      v-else-if="section === 'qdrant'"
      :data="qdrantQuery.data.value"
      :loading="qdrantQuery.isFetching.value"
      :sync-role="(statusQuery.data.value?.sync_role as string) ?? 'off'"
    />
  </div>
</template>

<style scoped>
.admin-cos-tab__header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.admin-cos-tab__header :deep(.mindbot-swiss-segmented) {
  flex: 1;
}
</style>
