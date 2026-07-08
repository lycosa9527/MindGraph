<script setup lang="ts">
/**
 * Case Square admin shell — sub-tab router.
 */
import { computed, onMounted, ref, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import AdminCaseSquareDashboard from '@/components/admin/AdminCaseSquareDashboard.vue'
import AdminCaseSquareFields from '@/components/admin/AdminCaseSquareFields.vue'
import AdminCaseSquareModeration from '@/components/admin/AdminCaseSquareModeration.vue'
import AdminCaseSquarePermissions from '@/components/admin/AdminCaseSquarePermissions.vue'
import AdminCaseSquareProxyPublish from '@/components/admin/AdminCaseSquareProxyPublish.vue'
import AdminCaseSquarePublished from '@/components/admin/AdminCaseSquarePublished.vue'
import {
  CASE_SQUARE_SUBTABS,
  caseSquareSubtabLabelKey,
  resolveCaseSquareSubtab,
  type CaseSquareSubtab,
} from '@/composables/admin/adminCaseSquareNav'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAuthStore } from '@/stores'
import { getCaseSquarePendingCount } from '@/utils/apiClient'

const { t } = useLanguage()
const { can } = useAdminAccess()
const authStore = useAuthStore()
const { featureCaseSquare } = useFeatureFlags()
const route = useRoute()
const router = useRouter()

const activeSubtab = computed(() => resolveCaseSquareSubtab(route.query.subtab))
const moderationPendingCount = ref(0)

async function refreshModerationCounts(): Promise<void> {
  if (!can('tab.case_square.edit') && !can('tab.case_square.view')) {
    moderationPendingCount.value = 0
    return
  }
  try {
    const res = await getCaseSquarePendingCount()
    moderationPendingCount.value = res.pending
  } catch {
    moderationPendingCount.value = 0
  }
}

const visibleSubtabs = computed(() =>
  CASE_SQUARE_SUBTABS.filter((tab) => {
    if (authStore.isSuperAdmin) return true
    if (tab === 'permissions') return can('tab.case_square.permissions')
    if (tab === 'fields') return can('tab.case_square.fields')
    if (tab === 'publish') return can('tab.case_square.edit')
    if (tab === 'dashboard') return can('tab.case_square.dashboard') || can('tab.case_square.view')
    if (tab === 'published') {
      return (
        can('tab.case_square.view') ||
        can('tab.case_square.edit') ||
        can('tab.case_square.recommend')
      )
    }
    return can('tab.case_square.view') || can('tab.case_square.edit')
  })
)

const subtabOptions = computed(() =>
  visibleSubtabs.value.map((value) => ({
    value,
    label: String(t(caseSquareSubtabLabelKey(value))),
    count: value === 'moderation' ? moderationPendingCount.value : undefined,
  }))
)

function setSubtab(subtab: CaseSquareSubtab): void {
  const query: Record<string, string> = { ...route.query, tab: 'case_square', subtab }
  if (subtab !== 'moderation') {
    delete query.queue
  }
  void router.replace({ query })
}

function redirectLegacyApprovedQueue(): void {
  if (route.query.subtab === 'moderation' && route.query.queue === 'approved') {
    const query: Record<string, string> = { ...route.query, tab: 'case_square', subtab: 'published' }
    delete query.queue
    void router.replace({ query })
  }
}

onMounted(() => {
  redirectLegacyApprovedQueue()
  void refreshModerationCounts()
  eventBus.on('admin:case_square_updated', refreshModerationCounts)
})

watch(
  () => route.query.queue,
  () => {
    redirectLegacyApprovedQueue()
  }
)
</script>

<template>
  <div class="admin-case-square-shell space-y-6">
    <p
      v-if="!featureCaseSquare"
      class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      {{ t('admin.caseSquare.featureDisabled') }}
    </p>

    <div>
      <h2 class="mb-1 text-base font-semibold text-gray-900">
        {{ t('admin.caseSquare.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('admin.caseSquare.intro') }}
      </p>
    </div>

    <AdminSwissSegmented
      v-if="subtabOptions.length > 0"
      :model-value="activeSubtab"
      :options="subtabOptions"
      :aria-label="t('admin.caseSquare.subtabAria')"
      fit
      @update:model-value="setSubtab"
    />

    <AdminCaseSquareDashboard v-if="activeSubtab === 'dashboard'" />
    <AdminCaseSquarePublished v-else-if="activeSubtab === 'published'" />
    <AdminCaseSquareModeration v-else-if="activeSubtab === 'moderation'" />
    <AdminCaseSquareProxyPublish v-else-if="activeSubtab === 'publish'" />
    <AdminCaseSquareFields v-else-if="activeSubtab === 'fields'" />
    <AdminCaseSquarePermissions v-else-if="activeSubtab === 'permissions'" />
  </div>
</template>
