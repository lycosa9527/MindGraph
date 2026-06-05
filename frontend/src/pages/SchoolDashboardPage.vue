<script setup lang="ts">
/**
 * School Dashboard - Org-scoped dashboard for managers (principals)
 * Admins can use dropdown to preview any school's dashboard
 */
import { computed, onMounted, ref, watch } from 'vue'

import {
  Connection,
  DocumentCopy,
  FolderOpened,
  Key,
  Loading,
  Plus,
  Stamp,
  User,
} from '@element-plus/icons-vue'

import AdminOrgTokenTrendDialog from '@/components/admin/AdminOrgTokenTrendDialog.vue'
import AdminTrendChartModal from '@/components/admin/AdminTrendChartModal.vue'
import SchoolDashboardOrgPicker from '@/components/school/SchoolDashboardOrgPicker.vue'
import SchoolDashboardQuotaCard from '@/components/school/SchoolDashboardQuotaCard.vue'
import SchoolDashboardUsersTab from '@/components/school/SchoolDashboardUsersTab.vue'
import SchoolAddMemberDialog from '@/components/school/SchoolAddMemberDialog.vue'
import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import AdminTokenUsageByServicePanel from '@/components/admin/AdminTokenUsageByServicePanel.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import type {
  TokenTrendPeriod,
  TokenTrendService,
} from '@/composables/admin/useOrgTokenTrendModal'
import { copySchoolInvitationPayload } from '@/utils/admin/copySchoolInvitationCode'
import { useSchoolDashboardStats } from '@/composables/admin/useSchoolDashboardStats'
import { useAdminOrgScope } from '@/composables/admin/useAdminOrgScope'
import {
  useSchoolDashboardQuotas,
} from '@/composables/school/useSchoolDashboardQuotas'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { useAuthStore } from '@/stores'
import { isManagerAssignmentUnavailable, isUnlimitedMemberLimit } from '@/constants/schoolTier'

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const props = withDefaults(
  defineProps<{
    embedded?: boolean
  }>(),
  { embedded: false }
)

const authStore = useAuthStore()
const { loadCapabilities, can, isReadOnly } = useAdminAccess()
const { effectiveOrgId, refetchOrganizations, syncSelectedOrgFromUser, showPicker, effectiveOrgName } =
  useAdminOrgScope()
const { on: onAdminEvent, emit: emitAdminEvent } = useAdminEventBus('SchoolDashboardPage')

const orgTrendDialogRef = ref<InstanceType<typeof AdminOrgTokenTrendDialog> | null>(null)

const userTrendModalVisible = ref(false)
const userTrendUserId = ref<number>()
const userTrendUserName = ref<string>()

const effectiveOrgIdRef = computed(() => effectiveOrgId.value)
const { isLoading, stats, topUsers, loadStats } = useSchoolDashboardStats(effectiveOrgIdRef)

const addMemberVisible = ref(false)

const showAddMemberButton = computed(
  () =>
    effectiveOrgId.value != null &&
    !isReadOnly.value &&
    (can('tab.users.edit') ||
      (can('scope.org') && (can('tab.school_dashboard.view') || can('tab.data_center.view'))))
)

function onMemberCreated(): void {
  void loadStats()
  emitAdminEvent('admin:mutation_completed', { domain: 'school_users' })
}

const addMemberSchoolName = computed(() =>
  (stats.value.organization?.name || effectiveOrgName.value || authStore.user?.schoolName || '').trim()
)
const {
  storageUsedGb,
  storageLimitGb,
  storageUsedLabel,
  storageLimitLabel,
  storageRemainingLabel,
  memberRemaining,
  managerRemaining,
} = useSchoolDashboardQuotas(computed(() => stats.value.quotas))

const activeTab = ref<'overview' | 'tokens' | 'users'>('overview')

function openOrgTrend(
  period: TokenTrendPeriod = 'week',
  service: TokenTrendService = null
): void {
  const orgId = effectiveOrgId.value
  if (orgId == null) {
    return
  }
  orgTrendDialogRef.value?.openTrend({
    orgId,
    orgName: stats.value.organization?.name ?? effectiveOrgName.value ?? '',
    period,
    service,
    useSchoolStatsEndpoint: true,
  })
}

function openUserTrend(userName: string, userId: number): void {
  userTrendUserId.value = userId
  userTrendUserName.value = userName
  userTrendModalVisible.value = true
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

const invitationCodeDisplay = computed(
  () => (stats.value.organization?.invitation_code || '').trim() || '—'
)

async function copyInvitationCode(event: MouseEvent) {
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

onAdminEvent('admin:toolbar_action', (payload) => {
  if (
    payload.action === 'open_add_school_member' &&
    props.embedded &&
    showAddMemberButton.value
  ) {
    addMemberVisible.value = true
  }
})

onAdminEvent('admin:mutation_completed', ({ domain, entityId }) => {
  if (domain !== 'organizations' || entityId == null || effectiveOrgId.value == null) {
    return
  }
  if (effectiveOrgId.value === Number(entityId)) {
    void loadStats()
  }
})

watch(
  () => [authStore.adminCapabilitiesLoaded, authStore.user?.schoolId] as const,
  () => {
    syncSelectedOrgFromUser()
  }
)

onMounted(async () => {
  await loadCapabilities()
  syncSelectedOrgFromUser()
  await refetchOrganizations()
  syncSelectedOrgFromUser()
})
</script>

<template>
  <div
    class="school-dashboard flex flex-col min-h-0 min-w-0"
    :class="
      embedded
        ? 'school-dashboard--embedded'
        : 'school-dashboard--standalone flex-1 bg-stone-50 overflow-hidden'
    "
  >
    <div
      v-if="!embedded"
      class="school-header h-14 px-4 flex items-center justify-between gap-3 bg-white border-b border-stone-200 shrink-0"
    >
      <h1 class="text-sm font-semibold text-stone-900 truncate min-w-0">
        {{ t('admin.schoolDashboard') }}
      </h1>
      <div class="flex items-center gap-2 shrink-0">
        <el-button
          v-if="showAddMemberButton"
          type="primary"
          round
          class="school-add-member-btn admin-swiss-btn"
          @click="addMemberVisible = true"
        >
          <el-icon class="el-icon--left"><Plus /></el-icon>
          {{ t('admin.schoolAddMemberButton') }}
        </el-button>
        <SchoolDashboardOrgPicker
          v-if="showPicker"
          compact
        />
      </div>
    </div>

    <div
      class="school-body min-w-0"
      :class="embedded ? 'school-body--embedded' : 'school-body--standalone flex-1 overflow-y-auto p-6'"
    >
      <div
        v-if="effectiveOrgId == null && !isLoading"
        class="text-center py-20 text-gray-500"
      >
        <p>{{ t('admin.schoolDashboardNoOrg') }}</p>
      </div>

      <template v-else-if="effectiveOrgId != null">
        <el-tabs
          v-model="activeTab"
          class="school-tabs admin-swiss-tabs"
        >
          <el-tab-pane
            :label="t('admin.dashboard')"
            name="overview"
          />
          <el-tab-pane
            :label="t('admin.tokens')"
            name="tokens"
          />
          <el-tab-pane
            :label="t('admin.schoolUsersTab')"
            name="users"
          />
        </el-tabs>

        <div
          v-if="activeTab === 'overview' && isLoading"
          class="flex justify-center py-20"
        >
          <el-icon
            class="is-loading"
            :size="32"
          >
            <Loading />
          </el-icon>
        </div>

        <template v-else-if="activeTab === 'overview'">
          <div
            class="grid grid-cols-1 md:grid-cols-3 gap-6"
            :class="embedded ? 'pt-0' : 'pt-4'"
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
              :remaining-label="
                t('admin.storageRemaining', {
                  amount: storageRemainingLabel,
                })
              "
              :icon="FolderOpened"
              accent="orange"
            />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <AdminSwissKpiCard
              :title="`${t('admin.tokens')} (${t('admin.pastWeek')})`"
              :value="formatNumber(stats.totalTokens)"
              :icon="Connection"
              theme="storage"
              clickable
              @click="openOrgTrend('week')"
            />
            <AdminSwissKpiCard
              :title="t('admin.invitationCode')"
              :value="invitationCodeDisplay"
              :icon="Key"
              theme="managers"
            >
              <template #footer>
                <el-button
                  type="primary"
                  size="small"
                  round
                  class="self-start !rounded-full"
                  :disabled="!(stats.organization?.invitation_code || '').trim()"
                  @click="copyInvitationCode"
                >
                  <el-icon class="el-icon--left">
                    <DocumentCopy />
                  </el-icon>
                  {{ t('admin.copyShareMessage') }}
                </el-button>
              </template>
            </AdminSwissKpiCard>
          </div>

          <el-card
            v-if="topUsers.length > 0"
            shadow="hover"
            class="mt-6"
          >
            <template #header>
              <div class="flex flex-wrap items-start justify-between gap-2 w-full">
                <span class="font-medium">{{ t('admin.topUsersByTokens') }}</span>
                <el-button
                  text
                  size="small"
                  @click="loadStats"
                >
                  {{ t('common.refresh') }}
                </el-button>
              </div>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-2 mb-0">
                {{ t('admin.rankingBeijingTodayHint') }}
              </p>
            </template>
            <el-table
              :data="topUsers"
              stripe
              size="small"
            >
              <el-table-column
                prop="name"
                :label="t('admin.name')"
              >
                <template #default="{ row }">
                  <span
                    class="cursor-pointer hover:text-primary-500 hover:underline"
                    @click="openUserTrend(row.name, row.id)"
                  >
                    {{ row.name }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column
                prop="phone"
                :label="t('admin.phone')"
                width="140"
              />
              <el-table-column
                prop="total_tokens"
                :label="t('admin.tokensUsed')"
                width="120"
              >
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

        <!-- Token Usage Tab -->
        <template v-else-if="activeTab === 'tokens'">
          <div class="mt-4 mb-6">
            <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
              {{ t('admin.tokenUsageByService') }} - {{ stats.organization?.name }}
            </h2>
            <p class="text-sm text-gray-500">
              {{ t('admin.tokenUsageCompare') }}
            </p>
          </div>
          <AdminTokenUsageByServicePanel
            v-if="effectiveOrgId != null"
            :organization-id="effectiveOrgId"
            use-school-stats-endpoint
            show-overall-summary
            clickable
            @service-click="openOrgTrend('week', $event)"
            @overall-click="openOrgTrend('week')"
            @period-click="(service, period) => openOrgTrend(period, service)"
          />
        </template>

        <template v-else-if="activeTab === 'users'">
          <SchoolDashboardUsersTab
            v-if="effectiveOrgId != null"
            :org-id="effectiveOrgId"
          />
        </template>
      </template>
    </div>

    <AdminOrgTokenTrendDialog ref="orgTrendDialogRef" />

    <AdminTrendChartModal
      v-if="userTrendUserId != null"
      v-model:visible="userTrendModalVisible"
      type="user"
      :user-id="userTrendUserId"
      :user-name="userTrendUserName"
      initial-trend-period="today"
    />

    <SchoolAddMemberDialog
      v-if="effectiveOrgId != null"
      v-model:visible="addMemberVisible"
      :org-id="effectiveOrgId"
      :school-name="addMemberSchoolName"
      @created="onMemberCreated"
    />
  </div>
</template>

<style scoped>
.school-dashboard--embedded {
  background: transparent;
}

.school-body--standalone {
  min-height: 0;
}

.school-dashboard--embedded .admin-swiss-tabs :deep(.el-tabs__header) {
  margin-top: 0;
}

.school-add-member-btn.el-button {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-text-color: #fafaf9;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
}

</style>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
