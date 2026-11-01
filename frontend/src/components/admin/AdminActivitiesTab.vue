<script setup lang="ts">
/**
 * System settings — log of writes by superadmins, researchers, experts, and school managers.
 */
import { computed, ref, watch } from 'vue'

import { ElTable } from 'element-plus'

import { useQuery } from '@tanstack/vue-query'

import AdminSwissPagination from '@/components/admin/AdminSwissPagination.vue'
import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'
import { type AdminActivityItem, fetchAdminActivityLog } from '@/composables/queries/adminApi'
import { formatInBeijing } from '@/utils/beijingClock'
import { userRoleLabel } from '@/utils/userRoleDisplay'

const ACTIVITY_ACTIONS = [
  'organization.create',
  'organization.update',
  'organization.delete',
  'organization.invitation_rotate',
  'organization.manager_add',
  'organization.manager_remove',
  'organization.avatar',
  'organization.oauth_update',
  'organization.expert_binding',
  'organization.branding',
  'school.invitation_rotate',
  'school_user.create',
  'school_user.batch_create',
  'school_user.update',
  'school_user.delete',
  'school_user.unlock',
  'user.update',
  'user.delete',
  'user.unlock',
  'user.password_reset',
  'user.role_update',
  'feature.flag_update',
  'feature.access_update',
  'settings.update',
  'settings.reload',
  'settings.restore',
  'api_key.create',
  'api_key.update',
  'api_key.delete',
  'api_key.toggle',
  'llm_control.update',
  'database.export',
  'database.import',
  'database.merge',
  'database.cleanup',
  'learning_space.class_create',
  'learning_space.class_update',
  'learning_space.code_rotate',
  'learning_space.import',
  'learning_space.member_remove',
  'learning_space.password_reset',
  'learning_space.pilot_create',
  'learning_space.pilot_update',
  'learning_space.pilot_delete',
  'learning_space.change',
  'vod.change',
  'showcase.change',
  'mindbot.config_create',
  'mindbot.config_update',
  'mindbot.config_delete',
  'mindbot.token_rotate',
  'mindbot.change',
  'library.change',
  'thinking_coins.change',
  'teaching_design.change',
  'user_dropdown.change',
  'teacher_usage.change',
  'kitty_llmops.change',
  'cos.change',
  'mindmate_export.change',
  'update_notification.change',
  'quick_register.open',
  'quick_register.close',
  'error_group.mute',
  'admin.mutate',
] as const

const PANEL_ROLES = ['superadmin', 'platform_bd', 'expert', 'school_admin'] as const

type HoursWindow = 24 | 168 | 720

const { t } = useLanguage()
const page = ref(1)
const hours = ref<HoursWindow>(168)
const role = ref('')
const action = ref('')
const searchDraft = ref('')
const search = ref('')

const hourOptions = computed(() => [
  { labelKey: 'admin.adminActivities.hours24', value: 24 as HoursWindow },
  { labelKey: 'admin.adminActivities.hours7d', value: 168 as HoursWindow },
  { labelKey: 'admin.adminActivities.hours30d', value: 720 as HoursWindow },
])

const listParams = computed(() => ({
  page: page.value,
  page_size: 50,
  hours: hours.value,
  role: role.value || undefined,
  action: action.value || undefined,
  q: search.value || undefined,
}))

const listQuery = useQuery({
  queryKey: computed(() => ['admin', 'activity-log', listParams.value]),
  queryFn: () => fetchAdminActivityLog(listParams.value),
})

const items = computed(() => listQuery.data.value?.items ?? [])
const total = computed(() => listQuery.data.value?.total ?? 0)
const totalPages = computed(() => listQuery.data.value?.total_pages ?? 1)
const loading = computed(() => listQuery.isFetching.value)

const pageInfo = computed(() =>
  t('admin.adminActivities.pageInfo', {
    page: String(page.value),
    totalPages: String(totalPages.value),
    total: String(total.value),
  })
)

watch([hours, role, action, search], () => {
  page.value = 1
})

function applySearch(): void {
  search.value = searchDraft.value.trim()
}

function actionLabel(actionKey: string): string {
  return t(`admin.adminActivities.action.${actionKey}`, actionKey)
}

function roleLabel(roleKey: string): string {
  return userRoleLabel(t, roleKey)
}

function detailText(row: AdminActivityItem): string {
  const detail = row.detail
  if (detail?.changes?.length) {
    return detail.changes.map((change) => `${change.key}=${change.value}`).join(', ')
  }
  if (detail?.rules?.length) {
    return detail.rules
      .map((rule) =>
        rule.restrict ? `${rule.key} (${t('admin.adminActivities.restricted')})` : rule.key
      )
      .join(', ')
  }
  if (detail?.keys?.length) {
    return detail.keys.join(', ')
  }
  return row.path
}
</script>

<template>
  <div class="admin-activities">
    <header class="admin-activities__header">
      <h2 class="admin-activities__title">
        <I18nText k="admin.adminActivities.title" />
      </h2>
      <p class="admin-activities__subtitle">
        <I18nText k="admin.adminActivities.subtitle" />
      </p>
    </header>

    <div class="admin-activities__toolbar">
      <AdminSwissSegmented
        v-model="hours"
        :options="hourOptions"
        fit
      />
      <el-select
        v-model="role"
        class="admin-activities__select"
        clearable
        :placeholder="t('admin.adminActivities.allRoles')"
      >
        <el-option
          v-for="roleKey in PANEL_ROLES"
          :key="roleKey"
          :label="roleLabel(roleKey)"
          :value="roleKey"
        />
      </el-select>
      <el-select
        v-model="action"
        class="admin-activities__select admin-activities__select--wide"
        clearable
        filterable
        :placeholder="t('admin.adminActivities.allActions')"
      >
        <el-option
          v-for="actionKey in ACTIVITY_ACTIONS"
          :key="actionKey"
          :label="actionLabel(actionKey)"
          :value="actionKey"
        />
      </el-select>
      <el-input
        v-model="searchDraft"
        class="admin-activities__search"
        clearable
        :placeholder="t('admin.adminActivities.search')"
        @change="applySearch"
        @clear="applySearch"
        @keyup.enter="applySearch"
      />
    </div>

    <p
      v-if="listQuery.isError.value"
      class="admin-activities__error"
    >
      <I18nText k="admin.adminActivities.loadFailed" />
    </p>
    <p
      v-else-if="loading && items.length === 0"
      class="admin-activities__muted"
    >
      <I18nText k="common.loading" />
    </p>
    <p
      v-else-if="items.length === 0"
      class="admin-activities__muted"
    >
      <I18nText k="admin.adminActivities.empty" />
    </p>

    <ElTable
      v-if="items.length > 0"
      :data="items"
      class="admin-swiss-table w-full"
      stripe
      size="small"
    >
      <el-table-column width="168">
        <template #header>
          <I18nText k="admin.adminActivities.colTime" />
        </template>
        <template #default="{ row }">
          {{ formatInBeijing(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column min-width="140">
        <template #header>
          <I18nText k="admin.adminActivities.colActor" />
        </template>
        <template #default="{ row }">
          {{ row.actor_label }}
        </template>
      </el-table-column>
      <el-table-column width="140">
        <template #header>
          <I18nText k="admin.adminActivities.colRole" />
        </template>
        <template #default="{ row }">
          {{ roleLabel(row.actor_role) }}
        </template>
      </el-table-column>
      <el-table-column min-width="180">
        <template #header>
          <I18nText k="admin.adminActivities.colAction" />
        </template>
        <template #default="{ row }">
          {{ actionLabel(row.action) }}
        </template>
      </el-table-column>
      <el-table-column min-width="240">
        <template #header>
          <I18nText k="admin.adminActivities.colDetail" />
        </template>
        <template #default="{ row }">
          <span :title="row.path">{{ detailText(row as AdminActivityItem) }}</span>
        </template>
      </el-table-column>
    </ElTable>

    <AdminSwissPagination
      v-if="total > 0"
      :page-info="pageInfo"
      :page="page"
      :total-pages="totalPages"
      @previous="page = Math.max(1, page - 1)"
      @next="page = Math.min(totalPages, page + 1)"
    />
  </div>
</template>

<style scoped>
.admin-activities__header {
  margin-bottom: 16px;
}

.admin-activities__title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 600;
}

.admin-activities__subtitle,
.admin-activities__muted,
.admin-activities__error {
  margin: 0 0 12px;
}

.admin-activities__error {
  color: var(--el-color-danger);
}

.admin-activities__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.admin-activities__select {
  width: 160px;
}

.admin-activities__select--wide {
  width: 240px;
}

.admin-activities__search {
  width: 240px;
}
</style>
