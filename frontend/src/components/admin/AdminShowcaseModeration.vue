<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { Search } from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import ShowcaseDetailModal from '@/components/showcase/ShowcaseDetailModal.vue'
import ShowcaseFilterDropdown from '@/components/showcase/ShowcaseFilterDropdown.vue'
import { type ShowcaseCaseType } from '@/components/showcase/showcaseShared'
import {
  SHOWCASE_QUEUES,
  showcaseQueueLabelKey,
  resolveShowcaseQueue,
  type ShowcaseQueue,
} from '@/composables/admin/adminShowcaseNav'
import { useLanguage } from '@/composables'
import { useShowcaseMeta } from '@/composables/showcase/useShowcaseMeta'
import { eventBus } from '@/composables/core/useEventBus'
import { type ShowcasePost, getShowcasePendingCount, getShowcasePosts } from '@/utils/apiClient'

const ADMIN_SORT_OPTIONS = [
  { value: 'newest', labelKey: 'admin.showcase.sort.newest' },
  { value: 'oldest', labelKey: 'admin.showcase.sort.oldest' },
  { value: 'title_asc', labelKey: 'admin.showcase.sort.titleAsc' },
  { value: 'title_desc', labelKey: 'admin.showcase.sort.titleDesc' },
  { value: 'subject_asc', labelKey: 'admin.showcase.sort.subjectAsc' },
  { value: 'subject_desc', labelKey: 'admin.showcase.sort.subjectDesc' },
  { value: 'grade_asc', labelKey: 'admin.showcase.sort.gradeAsc' },
  { value: 'grade_desc', labelKey: 'admin.showcase.sort.gradeDesc' },
  { value: 'reviewed_newest', labelKey: 'admin.showcase.sort.reviewedNewest' },
  { value: 'reviewed_oldest', labelKey: 'admin.showcase.sort.reviewedOldest' },
] as const

const CASE_TYPE_FILTER_OPTIONS = [
  { value: 'teaching_design', labelKey: 'showcase.type.teachingDesign' },
  { value: 'diagram_case', labelKey: 'showcase.type.diagramCase' },
  { value: 'diagram_template', labelKey: 'showcase.type.diagramTemplate' },
] as const

const PUBLISH_SOURCE_OPTIONS = [
  { value: 'self', labelKey: 'admin.showcase.publishSource.self' },
  { value: 'proxy', labelKey: 'admin.showcase.publishSource.proxy' },
] as const

const { t } = useLanguage()
const { subjectOptions, gradeOptions } = useShowcaseMeta()
const route = useRoute()
const router = useRouter()

const posts = ref<ShowcasePost[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const isLoading = ref(false)
const loadError = ref<string | null>(null)
const searchQuery = ref('')
const filterSubject = ref('')
const filterGrade = ref('')
const filterCaseType = ref('')
const filterPublishSource = ref('')
const activeSort = ref<string>('newest')

const showDetailModal = ref(false)
const selectedPostId = ref<string | null>(null)
const selectedPostPreview = ref<ShowcasePost | null>(null)

const activeQueue = computed((): ShowcaseQueue => resolveShowcaseQueue(route.query.queue))

const queuePendingCount = ref(0)
const queueRejectedCount = ref(0)

async function refreshQueueCounts(): Promise<void> {
  try {
    const res = await getShowcasePendingCount()
    queuePendingCount.value = res.pending
    queueRejectedCount.value = res.rejected
  } catch {
    queuePendingCount.value = 0
    queueRejectedCount.value = 0
  }
}

const queueOptions = computed(() =>
  SHOWCASE_QUEUES.map((value) => ({
    value,
    label: String(t(showcaseQueueLabelKey(value))),
    count: value === 'pending' ? queuePendingCount.value : queueRejectedCount.value,
  }))
)

const sortOptions = computed(() =>
  ADMIN_SORT_OPTIONS.map((opt) => ({
    value: opt.value,
    label: String(t(opt.labelKey)),
  }))
)

const caseTypeFilterOptions = computed(() =>
  CASE_TYPE_FILTER_OPTIONS.map((opt) => ({
    value: opt.value,
    label: String(t(opt.labelKey)),
  }))
)

const publishSourceFilterOptions = computed(() =>
  PUBLISH_SOURCE_OPTIONS.map((opt) => ({
    value: opt.value,
    label: String(t(opt.labelKey)),
  }))
)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const showReviewColumns = computed(() => activeQueue.value !== 'pending')

function caseTypeLabel(caseType: ShowcaseCaseType): string {
  if (caseType === 'teaching_design') return String(t('showcase.type.teachingDesign'))
  if (caseType === 'diagram_case') return String(t('showcase.type.diagramCase'))
  return String(t('showcase.type.diagramTemplate'))
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

async function loadPosts(): Promise<void> {
  isLoading.value = true
  loadError.value = null
  try {
    const res = await getShowcasePosts({
      page: page.value,
      pageSize,
      status: activeQueue.value,
      sort: activeSort.value,
      search: searchQuery.value.trim() || undefined,
      subject: filterSubject.value || undefined,
      grade: filterGrade.value || undefined,
      caseType: filterCaseType.value || undefined,
      publishSource: filterPublishSource.value || undefined,
    })
    posts.value = res.posts
    total.value = res.total
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Failed to load'
    posts.value = []
    total.value = 0
  } finally {
    isLoading.value = false
  }
}

function reload(): void {
  page.value = 1
  void loadPosts()
}

function setQueue(queue: ShowcaseQueue): void {
  void router.replace({
    query: { ...route.query, tab: 'showcase', subtab: 'moderation', queue },
  })
}

function openPost(post: ShowcasePost): void {
  selectedPostId.value = post.id
  selectedPostPreview.value = post
  showDetailModal.value = true
}

function onDetailUpdated(updated: ShowcasePost): void {
  if (updated.status !== activeQueue.value) {
    void loadPosts()
  }
  void refreshQueueCounts()
  eventBus.emit('admin:showcase_updated', {})
  eventBus.emit('showcase:feed_invalidate', { reason: 'admin_moderation' })
}

function onDetailDeleted(): void {
  showDetailModal.value = false
  void loadPosts()
  void refreshQueueCounts()
  eventBus.emit('admin:showcase_updated', {})
  eventBus.emit('showcase:feed_invalidate', { reason: 'admin_delete' })
}

function goPrevPage(): void {
  if (page.value <= 1) return
  page.value -= 1
  void loadPosts()
}

function goNextPage(): void {
  if (page.value >= totalPages.value) return
  page.value += 1
  void loadPosts()
}

watch(activeQueue, () => {
  if (activeQueue.value === 'pending' && activeSort.value.startsWith('reviewed_')) {
    activeSort.value = 'newest'
  }
  reload()
})

watch([filterSubject, filterGrade, filterCaseType, filterPublishSource, activeSort], () => reload())

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => reload(), 300)
})

onMounted(() => {
  if (route.query.subtab === 'moderation' && typeof route.query.queue !== 'string') {
    setQueue('pending')
  }
  void loadPosts()
  void refreshQueueCounts()
})
</script>

<template>
  <div
    v-loading="isLoading"
    class="space-y-4"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <AdminSwissSegmented
        :model-value="activeQueue"
        :options="queueOptions"
        :aria-label="t('admin.showcase.queueAria')"
        fit
        @update:model-value="setQueue"
      />
      <div class="relative min-w-[220px] flex-1 sm:max-w-xs">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          v-model="searchQuery"
          type="search"
          :placeholder="String(t('admin.showcase.searchPlaceholder'))"
          class="w-full rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-gray-400 focus:ring-2 focus:ring-gray-900/10"
        />
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <div>
        <label class="mb-1 block text-xs text-gray-500">{{ t('admin.showcase.colSubject') }}</label>
        <ShowcaseFilterDropdown
          v-model="filterSubject"
          block
          variant="plain"
          :options="subjectOptions"
          :all-label="t('showcase.filter.all')"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs text-gray-500">{{ t('showcase.grade') }}</label>
        <ShowcaseFilterDropdown
          v-model="filterGrade"
          block
          variant="plain"
          :options="gradeOptions"
          :all-label="t('showcase.filter.all')"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs text-gray-500">{{ t('admin.showcase.colType') }}</label>
        <ShowcaseFilterDropdown
          v-model="filterCaseType"
          block
          variant="plain"
          :options="caseTypeFilterOptions"
          :all-label="t('showcase.filter.all')"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs text-gray-500">{{ t('admin.showcase.colPublishSource') }}</label>
        <ShowcaseFilterDropdown
          v-model="filterPublishSource"
          block
          variant="plain"
          :options="publishSourceFilterOptions"
          :all-label="t('showcase.filter.all')"
        />
      </div>
      <div>
        <label class="mb-1 block text-xs text-gray-500">{{ t('admin.showcase.sortLabel') }}</label>
        <ShowcaseFilterDropdown
          v-model="activeSort"
          block
          variant="plain"
          :options="sortOptions"
          :include-all="false"
        />
      </div>
    </div>

    <p
      v-if="loadError"
      class="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {{ loadError }}
    </p>

    <el-table
      v-if="posts.length > 0 || isLoading"
      :data="posts"
      stripe
      style="width: 100%"
      max-height="520"
      @row-click="(row: ShowcasePost) => openPost(row)"
    >
      <el-table-column
        :label="t('admin.showcase.colTitle')"
        min-width="200"
      >
        <template #default="{ row }">
          <div class="flex items-center gap-3">
            <div
              v-if="row.thumbnail_url"
              class="h-10 w-14 shrink-0 overflow-hidden rounded-md bg-gray-100"
            >
              <img
                :src="row.thumbnail_url"
                :alt="row.title"
                class="h-full w-full object-cover"
              />
            </div>
            <div>
              <span class="line-clamp-2 font-medium text-gray-900">{{ row.title }}</span>
              <span
                v-if="row.publish_source === 'proxy'"
                class="ml-1 text-xs text-amber-600"
              >
                {{ t('admin.showcase.proxyBadge') }}
              </span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.showcase.colAuthor')"
        min-width="120"
      >
        <template #default="{ row }">
          <div class="text-sm text-gray-900">{{ row.author.name }}</div>
          <div
            v-if="row.author.organization"
            class="text-xs text-gray-400"
          >
            {{ row.author.organization }}
          </div>
        </template>
      </el-table-column>
      <el-table-column
        prop="subject"
        :label="t('admin.showcase.colSubject')"
        width="100"
      />
      <el-table-column
        prop="grade"
        :label="t('showcase.grade')"
        width="90"
      />
      <el-table-column
        :label="t('admin.showcase.colType')"
        width="120"
      >
        <template #default="{ row }">
          {{ caseTypeLabel(row.case_type) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.showcase.colSubmitted')"
        min-width="150"
      >
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="showReviewColumns"
        :label="t('admin.showcase.colReviewer')"
        min-width="120"
      >
        <template #default="{ row }">
          {{ row.reviewer?.name || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="showReviewColumns"
        :label="t('admin.showcase.colReviewedAt')"
        min-width="150"
      >
        <template #default="{ row }">
          {{ formatDate(row.reviewed_at) }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="activeQueue === 'rejected'"
        :label="t('admin.showcase.colRejectionReason')"
        min-width="180"
      >
        <template #default="{ row }">
          {{ row.rejection_reason || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.actions')"
        width="100"
        fixed="right"
      >
        <template #default="{ row }">
          <button
            type="button"
            class="text-sm font-medium text-gray-700"
            @click.stop="openPost(row)"
          >
            {{ t('admin.showcase.review') }}
          </button>
        </template>
      </el-table-column>
    </el-table>

    <div
      v-else-if="!isLoading"
      class="rounded-xl border border-dashed border-gray-200 bg-white px-6 py-12 text-center text-sm text-gray-400"
    >
      {{ t('admin.showcase.empty') }}
    </div>

    <div
      v-if="total > pageSize"
      class="flex items-center justify-between text-sm text-gray-600"
    >
      <span>{{ t('admin.showcase.stats.page') }} {{ page }} / {{ totalPages }} · {{ total }}</span>
      <div class="flex gap-2">
        <button
          type="button"
          class="rounded-lg border border-gray-200 px-3 py-1.5 disabled:opacity-40"
          :disabled="page <= 1"
          @click="goPrevPage"
        >
          {{ t('admin.showcase.prevPage') }}
        </button>
        <button
          type="button"
          class="rounded-lg border border-gray-200 px-3 py-1.5 disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="goNextPage"
        >
          {{ t('admin.showcase.nextPage') }}
        </button>
      </div>
    </div>

    <ShowcaseDetailModal
      v-model:visible="showDetailModal"
      :post-id="selectedPostId"
      :post-preview="selectedPostPreview"
      mode="admin"
      @updated="onDetailUpdated"
      @deleted="onDetailDeleted"
    />
  </div>
</template>
