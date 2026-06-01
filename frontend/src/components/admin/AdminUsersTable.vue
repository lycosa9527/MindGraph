<script setup lang="ts">
/**
 * Shared user-management table (global admin + school-scoped list).
 */
import { Edit, Loading } from '@element-plus/icons-vue'
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { formatBeijingDateTime } from '@/utils/formatBeijingDateTime'
import { userRolePillView } from '@/utils/userRoleDisplay'

const props = withDefaults(
  defineProps<{
    users: Record<string, unknown>[]
    isLoading: boolean
    showSchoolColumn?: boolean
    linkNameAndTokens?: boolean
    readOnly?: boolean
  }>(),
  {
    showSchoolColumn: true,
    linkNameAndTokens: true,
    readOnly: false,
  }
)

const emit = defineEmits<{
  edit: [row: Record<string, unknown>]
  openTrend: [row: Record<string, unknown>]
}>()

const { t, isZh } = useLanguage()

const dateTimeLocale = computed(() => (isZh.value ? 'zh-CN' : 'en-US'))

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function tokenTotal(row: Record<string, unknown>): number {
  const stats = row.token_stats as { total_tokens?: number } | undefined
  return stats?.total_tokens ?? 0
}

function diagramRemaining(row: Record<string, unknown>): string {
  const max = row.diagram_quota_max
  if (typeof max === 'number' && max <= 0) {
    return '∞'
  }
  const value = row.diagram_remaining
  return typeof value === 'number' ? String(value) : '0'
}

function paidBenefitLabel(row: Record<string, unknown>): string {
  if (row.paid_benefit_permanent === true) {
    return t('admin.paidBenefitPermanent')
  }
  const expires = row.paid_benefit_expires_at
  if (typeof expires === 'string' && expires.trim()) {
    return formatBeijingDateTime(expires, dateTimeLocale.value)
  }
  return '—'
}

function rolePillForRow(row: Record<string, unknown>) {
  const role = row.role
  if (typeof role !== 'string') {
    return null
  }
  return userRolePillView(t, role)
}

function displayName(row: Record<string, unknown>): string {
  const name = row.name
  const phone = row.phone
  if (typeof name === 'string' && name.trim()) {
    return name
  }
  if (typeof phone === 'string' && phone.trim()) {
    return phone
  }
  return '—'
}

function onNameClick(row: Record<string, unknown>): void {
  if (props.linkNameAndTokens) {
    emit('openTrend', row)
  }
}

function onTokenClick(row: Record<string, unknown>): void {
  if (props.linkNameAndTokens) {
    emit('openTrend', row)
  }
}

function registrationTimeLabel(row: Record<string, unknown>): string {
  const created = row.created_at
  if (typeof created !== 'string' || !created.trim()) {
    return '—'
  }
  return formatBeijingDateTime(created, dateTimeLocale.value)
}
</script>

<template>
  <div
    v-if="isLoading"
    class="flex justify-center py-12"
  >
    <el-icon
      class="is-loading"
      :size="32"
    >
      <Loading />
    </el-icon>
  </div>

  <el-table
    v-else
    :data="users"
    stripe
    size="small"
    class="admin-users-table"
  >
    <el-table-column
      prop="phone"
      :label="t('admin.phone')"
      width="128"
      show-overflow-tooltip
    />
    <el-table-column
      :label="t('admin.name')"
      min-width="100"
      show-overflow-tooltip
    >
      <template #default="{ row }">
        <span
          :class="
            linkNameAndTokens
              ? 'cursor-pointer hover:text-primary-500 hover:underline'
              : ''
          "
          @click="onNameClick(row)"
        >
          {{ displayName(row) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column
      v-if="showSchoolColumn"
      prop="organization_name"
      :label="t('admin.organization')"
      min-width="120"
      show-overflow-tooltip
    />
    <el-table-column
      :label="t('admin.userType')"
      width="128"
    >
      <template #default="{ row }">
        <span
          v-if="rolePillForRow(row)"
          class="inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-xs font-medium"
          :class="[
            rolePillForRow(row)?.bgClass,
            rolePillForRow(row)?.textClass,
            rolePillForRow(row)?.borderClass,
          ]"
        >
          {{ rolePillForRow(row)?.label }}
        </span>
        <span v-else>—</span>
      </template>
    </el-table-column>
    <el-table-column
      :label="t('admin.tokensUsed')"
      width="108"
      align="right"
    >
      <template #default="{ row }">
        <span
          :class="
            linkNameAndTokens
              ? 'cursor-pointer hover:text-primary-500 tabular-nums'
              : 'tabular-nums'
          "
          @click="onTokenClick(row)"
        >
          {{ formatNumber(tokenTotal(row)) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column
      :label="t('admin.remainingResourcePoints')"
      width="108"
      align="right"
    >
      <template #default="{ row }">
        <span class="tabular-nums">{{ diagramRemaining(row) }}</span>
      </template>
    </el-table-column>
    <el-table-column
      :label="t('admin.paidBenefitRemaining')"
      min-width="148"
      show-overflow-tooltip
    >
      <template #default="{ row }">
        {{ paidBenefitLabel(row) }}
      </template>
    </el-table-column>
    <el-table-column
      :label="t('admin.registrationTime')"
      width="168"
      show-overflow-tooltip
    >
      <template #default="{ row }">
        <span class="tabular-nums">{{ registrationTimeLabel(row) }}</span>
      </template>
    </el-table-column>
    <el-table-column
      :label="t('admin.actions')"
      width="88"
      fixed="right"
      align="center"
    >
      <template #default="{ row }">
        <slot
          name="actions"
          :row="row"
        >
          <el-button
            v-if="!props.readOnly"
            type="primary"
            plain
            size="small"
            class="admin-swiss-pill-btn admin-swiss-pill-btn--edit"
            @click="emit('edit', row)"
          >
            <el-icon class="mr-0.5"><Edit /></el-icon>
            {{ t('common.edit') }}
          </el-button>
        </slot>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
