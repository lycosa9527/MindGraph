<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { Award, Search, Trash2 } from '@lucide/vue'
import { ElMessageBox } from 'element-plus'

import ShowcaseDetailModal from '@/components/showcase/ShowcaseDetailModal.vue'
import ShowcaseFilterDropdown from '@/components/showcase/ShowcaseFilterDropdown.vue'
import { type ShowcaseCaseType } from '@/components/showcase/showcaseShared'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage, useNotifications } from '@/composables'
import { useShowcaseMeta } from '@/composables/showcase/useShowcaseMeta'
import { eventBus } from '@/composables/core/useEventBus'
import {
  type ShowcasePost,
  deleteAdminShowcasePost,
  getShowcasePosts,
  toggleShowcaseExpertRecommend,
} from '@/utils/apiClient'

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
  { value: 'hot', labelKey: 'showcase.sort.hot' },
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
const notify = useNotifications()
const { can: adminCan } = useAdminAccess()
const { subjectOptions, gradeOptions } = useShowcaseMeta()

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
const filterExpertOnly = ref(false)
const activeSort = ref<string>('newest')

const showDetailModal = ref(false)
const selectedPostId = ref<string | null>(null)
const selectedPostPreview = ref<ShowcasePost | null>(null)

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

const canRecommend = computed(() => adminCan('tab.showcase.recommend'))

const canDelete = computed(() => adminCan('tab.showcase.edit'))

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

function canRecommendPost(post: ShowcasePost): boolean {
  return canRecommend.value || !!post.can_expert_recommend
}

function canDeletePost(post: ShowcasePost): boolean {
  return canDelete.value || !!post.can_delete
}

async function loadPosts(): Promise<void> {
  isLoading.value = true
  loadError.value = null
  try {
    const res = await getShowcasePosts({
      page: page.value,
      pageSize,
      status: 'approved',
      sort: activeSort.value,
      search: searchQuery.value.trim() || undefined,
      subject: filterSubject.value || undefined,
      grade: filterGrade.value || undefined,
      caseType: filterCaseType.value || undefined,
      publishSource: filterPublishSource.value || undefined,
      expertRecommended: filterExpertOnly.value || undefined,
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

function openPost(post: ShowcasePost): void {
  selectedPostId.value = post.id
  selectedPostPreview.value = post
  showDetailModal.value = true
}

function patchPost(updated: ShowcasePost): void {
  const idx = posts.value.findIndex((p) => p.id === updated.id)
  if (idx >= 0) {
    posts.value[idx] = updated
  }
  if (selectedPostPreview.value?.id === updated.id) {
    selectedPostPreview.value = updated
  }
}

function onDetailUpdated(updated: ShowcasePost): void {
  if (updated.status !== 'approved') {
    posts.value = posts.value.filter((p) => p.id !== updated.id)
    total.value = Math.max(0, total.value - 1)
    return
  }
  patchPost(updated)
  eventBus.emit('admin:showcase_updated', {})
  eventBus.emit('showcase:feed_invalidate', { reason: 'admin_published' })
}

function onDetailDeleted(): void {
  showDetailModal.value = false
  void loadPosts()
  eventBus.emit('admin:showcase_updated', {})
  eventBus.emit('showcase:feed_invalidate', { reason: 'admin_delete' })
}

async function confirmDeletePost(post: ShowcasePost): Promise<void> {
  if (!canDeletePost(post)) return
  try {
    await ElMessageBox.confirm(
      String(t('admin.showcase.published.deleteConfirm', { title: post.title })),
      String(t('admin.showcase.published.deleteTitle')),
      {
        confirmButtonText: String(t('admin.delete')),
        cancelButtonText: String(t('admin.cancel')),
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return
  }
  try {
    await deleteAdminShowcasePost(post.id)
    notify.success(String(t('showcase.deleted')))
    posts.value = posts.value.filter((p) => p.id !== post.id)
    total.value = Math.max(0, total.value - 1)
    eventBus.emit('admin:showcase_updated', {})
    eventBus.emit('showcase:feed_invalidate', { reason: 'admin_delete' })
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function toggleRecommend(post: ShowcasePost): Promise<void> {
  if (!canRecommendPost(post)) return
  try {
    const res = await toggleShowcaseExpertRecommend(post.id)
    patchPost(res.post)
    notify.success(
      String(
        res.post.is_expert_recommended
          ? t('admin.showcase.published.recommended')
          : t('admin.showcase.published.unrecommended')
      ),
      2000
    )
    eventBus.emit('admin:showcase_updated', {})
    eventBus.emit('showcase:feed_invalidate', { reason: 'admin_recommend' })
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
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

watch(
  [filterSubject, filterGrade, filterCaseType, filterPublishSource, filterExpertOnly, activeSort],
  () => reload()
)

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => reload(), 300)
})

onMounted(() => {
  void loadPosts()
})
</script>

<template>
  <div
    v-loading="isLoading"
    class="space-y-4"
  >
    <p class="text-sm text-gray-500">
      {{ t('admin.showcase.published.intro') }}
    </p>

    <div class="flex flex-wrap items-center justify-between gap-3">
      <button
        type="button"
        :class="[
          'rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
          filterExpertOnly
            ? 'border-amber-300 bg-amber-50 text-amber-700'
            : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50',
        ]"
        @click="filterExpertOnly = !filterExpertOnly"
      >
        {{ t('showcase.expertRecommend') }}
      </button>
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
              <span
                v-if="row.is_expert_recommended"
                class="ml-1 text-xs text-amber-600"
              >
                · {{ t('showcase.expertBadge') }}
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
        :label="t('admin.showcase.colReviewer')"
        min-width="120"
      >
        <template #default="{ row }">
          {{ row.reviewer?.name || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.showcase.colReviewedAt')"
        min-width="150"
      >
        <template #default="{ row }">
          {{ formatDate(row.reviewed_at) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.showcase.colExpertRecommender')"
        min-width="120"
      >
        <template #default="{ row }">
          {{ row.expert_recommender?.name || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.actions')"
        width="180"
        fixed="right"
      >
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="text-sm font-medium text-gray-700"
              @click.stop="openPost(row)"
            >
              {{ t('admin.showcase.review') }}
            </button>
            <button
              v-if="canRecommendPost(row)"
              type="button"
              :title="
                row.is_expert_recommended
                  ? String(t('admin.showcase.published.unrecommend'))
                  : String(t('admin.showcase.published.recommend'))
              "
              :class="[
                'rounded-lg p-1.5 transition-colors',
                row.is_expert_recommended
                  ? 'text-amber-600 hover:bg-amber-50'
                  : 'text-gray-400 hover:bg-gray-100 hover:text-amber-600',
              ]"
              @click.stop="toggleRecommend(row)"
            >
              <Award class="h-4 w-4" :class="row.is_expert_recommended ? 'fill-current' : ''" />
            </button>
            <button
              v-if="canDeletePost(row)"
              type="button"
              :title="String(t('admin.showcase.published.deleteTitle'))"
              class="rounded-lg p-1.5 text-red-500 transition-colors hover:bg-red-50"
              @click.stop="confirmDeletePost(row)"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div
      v-else-if="!isLoading"
      class="rounded-xl border border-dashed border-gray-200 bg-white px-6 py-12 text-center text-sm text-gray-400"
    >
      {{ t('admin.showcase.published.empty') }}
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
      published-manage
      @updated="onDetailUpdated"
      @deleted="onDetailDeleted"
    />
  </div>
</template>
