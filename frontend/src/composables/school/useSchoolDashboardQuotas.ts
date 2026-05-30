/**
 * Format school dashboard quota data from the stats API.
 */
import { computed, type Ref } from 'vue'

import { formatStorageBytes, formatStorageRemainingBytes } from '@/utils/formatStorageBytes'

export interface SchoolDashboardQuotas {
  schoolTier: string
  memberCount: number
  memberLimit: number
  managerCount: number
  managerLimit: number
  storageUsedBytes: number
  storageLimitBytes: number
}

export interface SchoolDashboardQuotasApi {
  school_tier?: string
  member_count?: number
  member_limit?: number
  manager_count?: number
  manager_limit?: number
  storage_used_bytes?: number
  storage_limit_bytes?: number
}

const BYTES_PER_GIB = 1024 ** 3

function emptyQuotas(): SchoolDashboardQuotas {
  return {
    schoolTier: 'standard',
    memberCount: 0,
    memberLimit: 0,
    managerCount: 0,
    managerLimit: 0,
    storageUsedBytes: 0,
    storageLimitBytes: 0,
  }
}

export function parseSchoolDashboardQuotas(
  raw: SchoolDashboardQuotasApi | null | undefined
): SchoolDashboardQuotas {
  if (!raw) {
    return emptyQuotas()
  }
  return {
    schoolTier: String(raw.school_tier ?? 'standard'),
    memberCount: Number(raw.member_count ?? 0),
    memberLimit: Number(raw.member_limit ?? 0),
    managerCount: Number(raw.manager_count ?? 0),
    managerLimit: Number(raw.manager_limit ?? 0),
    storageUsedBytes: Number(raw.storage_used_bytes ?? 0),
    storageLimitBytes: Number(raw.storage_limit_bytes ?? 0),
  }
}

export function useSchoolDashboardQuotas(quotas: Ref<SchoolDashboardQuotas>) {
  const storageUsedGb = computed(() => quotas.value.storageUsedBytes / BYTES_PER_GIB)
  const storageLimitGb = computed(() => quotas.value.storageLimitBytes / BYTES_PER_GIB)
  const storageRemainingBytes = computed(() =>
    Math.max(0, quotas.value.storageLimitBytes - quotas.value.storageUsedBytes)
  )
  const storageUsedLabel = computed(() => formatStorageBytes(quotas.value.storageUsedBytes))
  const storageLimitLabel = computed(() => formatStorageBytes(quotas.value.storageLimitBytes))
  const storageRemainingLabel = computed(() =>
    formatStorageRemainingBytes(storageRemainingBytes.value, quotas.value.storageUsedBytes)
  )

  const memberRemaining = computed(() =>
    Math.max(0, quotas.value.memberLimit - quotas.value.memberCount)
  )
  const managerRemaining = computed(() =>
    Math.max(0, quotas.value.managerLimit - quotas.value.managerCount)
  )

  return {
    storageUsedGb,
    storageLimitGb,
    storageRemainingGb: computed(() => storageRemainingBytes.value / BYTES_PER_GIB),
    storageUsedLabel,
    storageLimitLabel,
    storageRemainingLabel,
    memberRemaining,
    managerRemaining,
  }
}
