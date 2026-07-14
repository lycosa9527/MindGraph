<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage } from '@/composables'
import {
  getAdminShowcaseStats,
  getShowcasePendingCount,
  getShowcasePosts,
  type ShowcaseStatsOverview,
} from '@/utils/apiClient'

const { t } = useLanguage()

const stats = ref<ShowcaseStatsOverview | null>(null)
const isLoading = ref(false)
const loadError = ref<string | null>(null)

const emptyStats = (): ShowcaseStatsOverview => ({
  pending: 0,
  approved_total: 0,
  rejected_total: 0,
  total_posts: 0,
  created_recent: 0,
  approved_recent: 0,
  rejected_recent: 0,
  proxy_total: 0,
  self_total: 0,
  expert_recommended_total: 0,
  rejection_rate_recent: 0,
  by_case_type: {},
  total_views: 0,
  total_likes: 0,
  period_days: 30,
})

async function loadStatsFromPosts(): Promise<ShowcaseStatsOverview> {
  const [pendingCount, pendingList, approvedList, rejectedList] = await Promise.all([
    getShowcasePendingCount(),
    getShowcasePosts({ status: 'pending', pageSize: 1, page: 1 }),
    getShowcasePosts({ status: 'approved', pageSize: 1, page: 1 }),
    getShowcasePosts({ status: 'rejected', pageSize: 1, page: 1 }),
  ])
  const pending = pendingCount.count || pendingList.total
  const approved = approvedList.total
  const rejected = rejectedList.total
  return {
    ...emptyStats(),
    pending,
    approved_total: approved,
    rejected_total: rejected,
    total_posts: pending + approved + rejected,
  }
}

async function loadStats(): Promise<void> {
  isLoading.value = true
  loadError.value = null
  try {
    stats.value = await getAdminShowcaseStats()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : String(t('admin.showcase.statsLoadError'))
    try {
      stats.value = await loadStatsFromPosts()
    } catch {
      stats.value = emptyStats()
    }
  } finally {
    isLoading.value = false
  }
}

const caseTypeBreakdown = computed(() => {
  const map = stats.value?.by_case_type ?? {}
  return [
    { key: 'teaching_design', label: t('showcase.type.teachingDesign'), value: map.teaching_design ?? 0 },
    { key: 'diagram_case', label: t('showcase.type.diagramCase'), value: map.diagram_case ?? 0 },
    { key: 'diagram_template', label: t('showcase.type.diagramTemplate'), value: map.diagram_template ?? 0 },
  ]
})

onMounted(() => {
  void loadStats()
})
</script>

<template>
  <div
    v-loading="isLoading"
    class="space-y-6"
  >
    <p
      v-if="loadError"
      class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      {{ loadError }}
      <button
        type="button"
        class="ml-2 font-medium underline"
        @click="loadStats"
      >
        {{ t('admin.showcase.statsRetry') }}
      </button>
    </p>

    <template v-if="stats">
      <div>
        <h3 class="mb-3 text-sm font-semibold text-gray-900">
          {{ t('admin.showcase.stats.sectionOverview') }}
        </h3>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.totalPosts')"
            :value="stats.total_posts ?? stats.pending + stats.approved_total + stats.rejected_total"
            theme="neutral"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.pending')"
            :value="stats.pending"
            theme="warn"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.approvedTotal')"
            :value="stats.approved_total"
            theme="success"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.rejectedTotal')"
            :value="stats.rejected_total"
            theme="warn"
          />
        </div>
      </div>

      <div>
        <h3 class="mb-3 text-sm font-semibold text-gray-900">
          {{ t('admin.showcase.stats.sectionRecent') }}
        </h3>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.createdRecent')"
            :value="stats.created_recent"
            theme="neutral"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.approvedRecent')"
            :value="stats.approved_recent ?? 0"
            theme="success"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.rejectedRecent')"
            :value="stats.rejected_recent ?? 0"
            theme="warn"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.rejectionRate')"
            :value="`${Math.round(stats.rejection_rate_recent * 100)}%`"
            theme="warn"
          />
        </div>
      </div>

      <div>
        <h3 class="mb-3 text-sm font-semibold text-gray-900">
          {{ t('admin.showcase.stats.sectionPublish') }}
        </h3>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.selfTotal')"
            :value="stats.self_total ?? 0"
            theme="neutral"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.proxyTotal')"
            :value="stats.proxy_total"
            theme="neutral"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.expertTotal')"
            :value="stats.expert_recommended_total"
            theme="neutral"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.totalViews')"
            :value="stats.total_views ?? 0"
            theme="neutral"
          />
          <AdminSwissKpiCard
            :title="t('admin.showcase.stats.totalLikes')"
            :value="stats.total_likes ?? 0"
            theme="neutral"
          />
        </div>
      </div>

      <div>
        <h3 class="mb-3 text-sm font-semibold text-gray-900">
          {{ t('admin.showcase.stats.sectionCaseType') }}
        </h3>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <AdminSwissKpiCard
            v-for="item in caseTypeBreakdown"
            :key="item.key"
            :title="String(item.label)"
            :value="item.value"
            theme="neutral"
            compact
          />
        </div>
      </div>
    </template>
  </div>
</template>
