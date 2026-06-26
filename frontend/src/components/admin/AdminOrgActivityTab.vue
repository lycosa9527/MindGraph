<script setup lang="ts">
/**
 * School modal — curated activity timeline for one organization.
 */
import { computed, ref, watch } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import AdminSwissPagination from '@/components/admin/AdminSwissPagination.vue'
import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useScopedAbort } from '@/composables/core/useScopedAbort'
import {
  fetchAdminOrgActivity,
  type AdminOrgActivityItem,
} from '@/composables/queries/adminApi'
import { useUIStore } from '@/stores/ui'
import {
  activitySourceLabel,
  formatAdminUserActivitySummary,
  type ActivitySummaryLabels,
} from '@/utils/adminUserActivitySummary'

const props = defineProps<{
  orgId: number | null | undefined
  canLoad: boolean
}>()

type SourceFilter = 'all' | 'mindgraph' | 'mindmate' | 'dingtalk'

const { t } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()
const { beginRequest, abort: abortActivityRequests } = useScopedAbort()

const PAGE_SIZE = 15

const sourceFilter = ref<SourceFilter>('all')
const page = ref(1)
const pagesCache = ref<AdminOrgActivityItem[][]>([])
const pageHasMore = ref<boolean[]>([])
const loading = ref(false)

const sourceFilterOptions = computed(() => [
  { label: t('admin.orgActivityTab.filterAll'), value: 'all' as const },
  { label: t('admin.orgActivityTab.filterMindgraph'), value: 'mindgraph' as const },
  { label: t('admin.orgActivityTab.filterMindmate'), value: 'mindmate' as const },
  { label: t('admin.orgActivityTab.filterDingtalk'), value: 'dingtalk' as const },
])

const summaryLabels = computed<ActivitySummaryLabels>(() => ({
  ask: t('admin.orgActivityTab.askPrefix'),
  answer: t('admin.orgActivityTab.answerPrefix'),
  generate: t('admin.orgActivityTab.generate'),
  save: t('admin.orgActivityTab.save'),
  dingtalkGenerate: t('admin.orgActivityTab.dingtalkGenerate'),
  sourceMindgraph: t('admin.orgActivityTab.sourceMindgraph'),
  sourceMindmate: t('admin.orgActivityTab.sourceMindmate'),
  sourceDingtalk: t('admin.orgActivityTab.sourceDingtalk'),
  failedSuffix: t('admin.orgActivityTab.failedSuffix'),
}))

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function rowSummary(row: AdminOrgActivityItem): string {
  return formatAdminUserActivitySummary(row, summaryLabels.value, uiStore.language)
}

function sourceBadge(row: AdminOrgActivityItem): string {
  return activitySourceLabel(row.source, summaryLabels.value)
}

function formatTokens(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return '—'
  }
  return String(value)
}

function userLabel(row: AdminOrgActivityItem): string {
  const name = row.userName?.trim()
  return name || `#${row.userId}`
}

const currentItems = computed(() => pagesCache.value[page.value - 1] ?? [])

const hasMore = computed(() => pageHasMore.value[page.value - 1] ?? false)

const totalPages = computed(() => {
  if (hasMore.value) {
    return page.value + 1
  }
  return Math.max(page.value, pagesCache.value.length, 1)
})

const pageInfo = computed(() => {
  const batch = currentItems.value
  if (batch.length === 0) {
    return t('admin.listRangeEmpty')
  }
  const start = (page.value - 1) * PAGE_SIZE + 1
  const end = (page.value - 1) * PAGE_SIZE + batch.length
  if (hasMore.value) {
    return t('admin.schoolModalPageInfo', { page: page.value, totalPages: totalPages.value })
  }
  return t('admin.listRange', { start, end, total: end })
})

async function fetchActivityPage(pageNumber: number): Promise<AdminOrgActivityItem[]> {
  const orgId = props.orgId
  if (orgId == null || orgId <= 0 || !props.canLoad) {
    return []
  }
  const signal = beginRequest()
  const params: Record<string, string | number | undefined> = { limit: PAGE_SIZE }
  if (sourceFilter.value !== 'all') {
    params.source = sourceFilter.value
  }
  if (pageNumber > 1) {
    const previousPage = pagesCache.value[pageNumber - 2]
    const cursor = previousPage?.[previousPage.length - 1]?.id
    if (cursor != null) {
      params.before_id = cursor
    }
  }
  const data = await fetchAdminOrgActivity(orgId, params, signal)
  const nextHasMore = [...pageHasMore.value]
  nextHasMore[pageNumber - 1] = Boolean(data.hasMore)
  pageHasMore.value = nextHasMore.slice(0, pageNumber)
  return data.items ?? []
}

async function loadCurrentPage(forceFetch = false): Promise<void> {
  const orgId = props.orgId
  if (orgId == null || orgId <= 0 || !props.canLoad) {
    return
  }
  const cached = pagesCache.value[page.value - 1]
  if (cached && !forceFetch) {
    return
  }
  loading.value = true
  try {
    const batch = await fetchActivityPage(page.value)
    pagesCache.value = [...pagesCache.value.slice(0, page.value - 1), batch]
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return
    }
    notify.error(t('admin.orgActivityTab.loadError'))
  } finally {
    loading.value = false
  }
}

function resetAndLoad(): void {
  page.value = 1
  pagesCache.value = []
  pageHasMore.value = []
  void loadCurrentPage(true)
}

function goToPreviousPage(): void {
  if (page.value <= 1) {
    return
  }
  page.value -= 1
}

function goToNextPage(): void {
  if (page.value >= totalPages.value) {
    return
  }
  page.value += 1
  void loadCurrentPage()
}

watch(
  () => [props.orgId, props.canLoad] as const,
  ([orgId, canLoad]) => {
    abortActivityRequests()
    if (orgId != null && orgId > 0 && canLoad) {
      resetAndLoad()
    } else {
      pagesCache.value = []
      pageHasMore.value = []
      page.value = 1
    }
  },
  { immediate: true }
)

watch(sourceFilter, () => {
  if (props.canLoad && props.orgId != null) {
    resetAndLoad()
  }
})
</script>

<template>
  <div class="org-activity-tab space-y-3">
    <div class="org-activity-tab-toolbar">
      <p class="org-activity-tab-notice">
        {{ t('admin.orgActivityTab.privacyNotice') }}
      </p>
      <AdminSwissSegmented
        v-model="sourceFilter"
        class="org-activity-tab-filter"
        :options="sourceFilterOptions"
        fit
        :aria-label="t('admin.orgActivityTab.colProduct')"
      />
    </div>

    <div
      v-if="loading"
      class="school-modal-loading flex justify-center items-center h-40"
    >
      <el-icon
        class="is-loading"
        :size="28"
      >
        <Loading />
      </el-icon>
    </div>

    <div
      v-else-if="currentItems.length === 0"
      class="school-modal-empty h-40"
    >
      {{ t('admin.orgActivityTab.empty') }}
    </div>

    <div
      v-else
      class="overflow-x-auto"
    >
      <table class="school-modal-table">
        <thead>
          <tr class="school-modal-table__head-row">
            <th class="school-modal-table__head-cell">
              {{ t('admin.orgActivityTab.colTime') }}
            </th>
            <th class="school-modal-table__head-cell">
              {{ t('admin.orgActivityTab.colUser') }}
            </th>
            <th class="school-modal-table__head-cell">
              {{ t('admin.orgActivityTab.colProduct') }}
            </th>
            <th class="school-modal-table__head-cell min-w-[12rem]">
              {{ t('admin.orgActivityTab.colSummary') }}
            </th>
            <th class="school-modal-table__head-cell school-modal-table__head-cell--right">
              {{ t('admin.orgActivityTab.colTokens') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in currentItems"
            :key="row.id"
            class="school-modal-table__row"
          >
            <td class="school-modal-table__cell school-modal-table__time">
              {{ formatTime(row.createdAt) }}
            </td>
            <td class="school-modal-table__cell school-modal-table__user">
              {{ userLabel(row) }}
            </td>
            <td class="school-modal-table__cell whitespace-nowrap">
              <span class="school-modal-badge">
                {{ sourceBadge(row) }}
              </span>
            </td>
            <td class="school-modal-table__cell school-modal-table__summary">
              {{ rowSummary(row) }}
            </td>
            <td class="school-modal-table__cell school-modal-table__tokens">
              {{ formatTokens(row.totalTokens) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AdminSwissPagination
      v-if="currentItems.length > 0 && totalPages > 1 && !loading"
      class="school-modal-pagination"
      :page-info="pageInfo"
      :page="page"
      :total-pages="totalPages"
      @previous="goToPreviousPage"
      @next="goToNextPage"
    />
  </div>
</template>

<style scoped>
.org-activity-tab-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem 1rem;
}

.org-activity-tab-notice {
  flex: 1 1 12rem;
  min-width: 0;
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.45;
}

.org-activity-tab-filter {
  flex: 0 0 auto;
  margin-left: auto;
}
</style>
