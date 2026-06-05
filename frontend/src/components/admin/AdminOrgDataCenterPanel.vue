<script setup lang="ts">
/**
 * Org-scoped data center stats (school admin / superadmin org preview).
 */
import { computed, ref, toRef } from 'vue'

import AdminOrgTokenTrendDialog from '@/components/admin/AdminOrgTokenTrendDialog.vue'
import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import AdminTokenUsageByServicePanel from '@/components/admin/AdminTokenUsageByServicePanel.vue'
import AdminTrendChartModal from '@/components/admin/AdminTrendChartModal.vue'
import SchoolDashboardQuotaCard from '@/components/school/SchoolDashboardQuotaCard.vue'
import { Connection, DocumentCopy, FolderOpened, Key, Loading, Stamp, User } from '@element-plus/icons-vue'

import type {
  TokenTrendPeriod,
  TokenTrendService,
} from '@/composables/admin/useOrgTokenTrendModal'
import { copySchoolInvitationPayload } from '@/utils/admin/copySchoolInvitationCode'
import { useSchoolDashboardStats } from '@/composables/admin/useSchoolDashboardStats'
import { useSchoolDashboardQuotas } from '@/composables/school/useSchoolDashboardQuotas'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { isManagerAssignmentUnavailable, isUnlimitedMemberLimit } from '@/constants/schoolTier'

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

const orgTrendDialogRef = ref<InstanceType<typeof AdminOrgTokenTrendDialog> | null>(null)
const userTrendModalVisible = ref(false)
const userTrendUserId = ref<number>()
const userTrendUserName = ref<string>()

const invitationCodeDisplay = computed(
  () => (stats.value.organization?.invitation_code || '').trim() || '—'
)

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function openOrgTrend(
  period: TokenTrendPeriod = 'week',
  service: TokenTrendService = null
): void {
  orgTrendDialogRef.value?.openTrend({
    orgId: props.orgId,
    orgName: stats.value.organization?.name ?? '',
    period,
    service,
    useSchoolStatsEndpoint: false,
  })
}

function openUserTrend(userName: string, userId: number | undefined): void {
  if (userId == null || !Number.isFinite(userId) || userId <= 0) {
    notify.warning(t('admin.userTrendRequiresId'))
    return
  }
  userTrendUserId.value = userId
  userTrendUserName.value = userName
  userTrendModalVisible.value = true
}

async function copyInvitationCode(event: MouseEvent): Promise<void> {
  event.stopPropagation()
  const text = t('admin.schoolInviteCopyPayload', {
    siteUrl: publicSiteUrl.value,
    code: (stats.value.organization?.invitation_code || '').trim(),
  })
  await copySchoolInvitationPayload(
    text,
    () => notify.success(t('notification.copied')),
    () => notify.error(t('notification.copyFailed'))
  )
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
        :limit-display-override="
          isUnlimitedMemberLimit(stats.quotas.memberLimit) ? t('admin.unlimited') : ''
        "
        :remaining-label="
          memberRemaining === null
            ? t('admin.unlimitedMembers')
            : t('admin.seatsRemaining', { count: memberRemaining.toLocaleString() })
        "
        :icon="User"
        accent="blue"
      />
      <SchoolDashboardQuotaCard
        :title="t('admin.managerSeats')"
        :used="stats.quotas.managerCount"
        :limit="stats.quotas.managerLimit"
        :limit-display-override="
          isManagerAssignmentUnavailable(stats.quotas.managerLimit)
            ? t('admin.noSchoolManagersShort')
            : ''
        "
        :remaining-label="
          managerRemaining === null
            ? t('admin.schoolManagerNotAvailableTrial')
            : t('admin.seatsRemaining', { count: managerRemaining.toLocaleString() })
        "
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
        :title="`${t('admin.tokens')} (${t('admin.pastWeek')})`"
        :value="formatNumber(stats.totalTokens)"
        :icon="Connection"
        theme="storage"
        clickable
        @click="openOrgTrend('week')"
      />
    </div>
    <AdminTokenUsageByServicePanel
      v-if="showUsage"
      class="mt-6"
      :organization-id="orgId"
      clickable
      show-overall-summary
      @service-click="openOrgTrend('week', $event)"
      @overall-click="openOrgTrend('week')"
      @period-click="(service, period) => openOrgTrend(period, service)"
    />

    <el-card
      v-if="showUsage && topUsers.length > 0"
      shadow="hover"
      class="mt-6"
    >
      <template #header>
        <div>
          <span class="font-medium">{{ t('admin.topUsersByTokens') }}</span>
          <p class="text-sm text-gray-500 dark:text-gray-400 mt-2 mb-0">
            {{ t('admin.rankingBeijingTodayHint') }}
          </p>
        </div>
      </template>
      <el-table
        :data="topUsers"
        stripe
        size="small"
        :empty-text="t('admin.noData')"
      >
        <el-table-column prop="name" :label="t('admin.name')">
          <template #default="{ row }">
            <span
              class="cursor-pointer hover:text-primary-500 hover:underline"
              @click="openUserTrend(row.name, row.id)"
            >
              {{ row.name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="phone" :label="t('admin.phone')" width="140" />
        <el-table-column prop="total_tokens" :label="t('admin.tokensUsed')" width="120">
          <template #default="{ row }">
            <span
              class="cursor-pointer hover:text-primary-500"
              @click="openUserTrend(row.name, row.id)"
            >
              {{ formatNumber(row.total_tokens) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </template>

  <AdminOrgTokenTrendDialog ref="orgTrendDialogRef" />

  <AdminTrendChartModal
    v-if="userTrendUserId != null"
    v-model:visible="userTrendModalVisible"
    type="user"
    :user-id="userTrendUserId"
    :user-name="userTrendUserName"
    initial-trend-period="today"
  />
</template>
