<script setup lang="ts">
/**
 * Org-scoped data center stats (school admin / superadmin org preview).
 */
import { computed, toRef } from 'vue'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import AdminTokenUsageByServicePanel from '@/components/admin/AdminTokenUsageByServicePanel.vue'
import SchoolDashboardQuotaCard from '@/components/school/SchoolDashboardQuotaCard.vue'
import { Connection, DocumentCopy, FolderOpened, Key, Loading, Stamp, User } from '@element-plus/icons-vue'

import { useSchoolDashboardStats } from '@/composables/admin/useSchoolDashboardStats'
import { useSchoolDashboardQuotas } from '@/composables/school/useSchoolDashboardQuotas'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'

const props = withDefaults(
  defineProps<{
    orgId: number
    readOnly?: boolean
    section?: 'operations' | 'usage' | 'all'
  }>(),
  { section: 'all' }
)

const showOperations = computed(
  () => props.section === 'all' || props.section === 'operations'
)
const showUsage = computed(() => props.section === 'all' || props.section === 'usage')

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const orgIdRef = toRef(props, 'orgId')
const { isLoading, stats, topUsers } = useSchoolDashboardStats(orgIdRef)
const {
  storageUsedGb,
  storageLimitGb,
  storageUsedLabel,
  storageLimitLabel,
  storageRemainingLabel,
  memberRemaining,
  managerRemaining,
} = useSchoolDashboardQuotas(computed(() => stats.value.quotas))

const invitationCodeDisplay = computed(
  () => (stats.value.organization?.invitation_code || '').trim() || '—'
)

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

async function copyInvitationCode(event: MouseEvent): Promise<void> {
  event.stopPropagation()
  const code = (stats.value.organization?.invitation_code || '').trim()
  if (!code) return
  const text = t('admin.schoolInviteCopyPayload', {
    siteUrl: publicSiteUrl.value,
    code,
  })
  try {
    await navigator.clipboard.writeText(text)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}
</script>

<template>
  <div v-if="isLoading" class="flex justify-center py-20">
    <el-icon class="is-loading" :size="32"><Loading /></el-icon>
  </div>
  <template v-else>
    <p v-if="stats.organization.name" class="text-sm text-gray-500 mb-4">
      {{ stats.organization.name }}
    </p>
    <div
      v-if="showOperations"
      class="grid grid-cols-1 md:grid-cols-3 gap-6"
    >
      <SchoolDashboardQuotaCard
        :title="t('admin.memberSeats')"
        :used="stats.quotas.memberCount"
        :limit="stats.quotas.memberLimit"
        :remaining-label="t('admin.seatsRemaining', { count: memberRemaining.toLocaleString() })"
        :icon="User"
        accent="blue"
      />
      <SchoolDashboardQuotaCard
        :title="t('admin.managerSeats')"
        :used="stats.quotas.managerCount"
        :limit="stats.quotas.managerLimit"
        :remaining-label="t('admin.seatsRemaining', { count: managerRemaining.toLocaleString() })"
        :icon="Stamp"
        accent="purple"
      />
      <SchoolDashboardQuotaCard
        :title="t('admin.resourceSpace')"
        :used="storageUsedGb"
        :limit="storageLimitGb"
        :used-display-override="storageUsedLabel"
        :limit-display-override="storageLimitLabel"
        :remaining-label="t('admin.storageRemaining', { amount: storageRemainingLabel })"
        :icon="FolderOpened"
        accent="orange"
      />
    </div>
    <div
      v-if="showOperations"
      class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6"
    >
      <AdminSwissKpiCard
        :title="t('admin.invitationCode')"
        :value="invitationCodeDisplay"
        :icon="Key"
        theme="managers"
      >
        <template v-if="!readOnly" #footer>
          <el-button
            type="primary"
            size="small"
            round
            class="mt-2 !rounded-full"
            :disabled="!(stats.organization?.invitation_code || '').trim()"
            @click="copyInvitationCode"
          >
            <el-icon class="el-icon--left"><DocumentCopy /></el-icon>
            {{ t('admin.copyShareMessage') }}
          </el-button>
        </template>
      </AdminSwissKpiCard>
    </div>
    <div
      v-if="showUsage"
      class="grid grid-cols-1 md:grid-cols-2 gap-6"
      :class="{ 'mt-6': showOperations }"
    >
      <AdminSwissKpiCard
        :title="t('admin.tokens')"
        :value="formatNumber(stats.totalTokens)"
        :icon="Connection"
        theme="storage"
      />
    </div>
    <AdminTokenUsageByServicePanel
      v-if="showUsage"
      class="mt-6"
      :organization-id="orgId"
    />

    <el-card
      v-if="showUsage && topUsers.length > 0"
      shadow="hover"
      class="mt-6"
    >
      <template #header>
        <span class="font-medium">{{ t('admin.topUsersByTokens') }}</span>
      </template>
      <el-table :data="topUsers" stripe size="small">
        <el-table-column prop="name" :label="t('admin.name')" />
        <el-table-column prop="phone" :label="t('admin.phone')" width="140" />
        <el-table-column prop="total_tokens" :label="t('admin.tokensUsed')" width="120">
          <template #default="{ row }">
            {{ formatNumber(row.total_tokens) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </template>
</template>
