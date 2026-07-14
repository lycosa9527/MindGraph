<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { useInfiniteScroll } from '@vueuse/core'

import { ElSkeleton } from 'element-plus'

import {
  ArrowUpDown,
  Award,
  BookOpen,
  Eye,
  FileText,
  Heart,
  Image as ImageIcon,
  LayoutTemplate,
  Plus,
  Search,
  Star,
} from '@lucide/vue'

import {
  CaseSquareDetailModal,
  CaseSquareFilterDropdown,
  MyFavoriteCasesModal,
  MyPublishedCasesModal,
  PublishCaseSquareModal,
} from '@/components/caseSquare'
import {
  caseTypeEmoji,
  caseTypeTheme,
  isMostlyBlankImageBlob,
  type CaseSquareCaseType,
} from '@/components/caseSquare/caseSquareShared'
import { useLanguage } from '@/composables'
import { useCaseSquareMeta } from '@/composables/caseSquare/useCaseSquareMeta'
import { useAuthStore } from '@/stores'
import {
  type CaseSquarePost,
  getCaseSquarePosts,
} from '@/utils/apiClient'

const { t } = useLanguage()
const authStore = useAuthStore()
const { subjectOptions, gradeOptions } = useCaseSquareMeta()

const typeTabs = [
  { key: 'all', labelKey: 'caseSquare.filter.all', api: undefined as string | undefined },
  { key: 'teaching_design', labelKey: 'caseSquare.type.teachingDesign', api: 'teaching_design' },
  { key: 'diagram_case', labelKey: 'caseSquare.type.diagramCase', api: 'diagram_case' },
  { key: 'diagram_template', labelKey: 'caseSquare.type.diagramTemplate', api: 'diagram_template' },
] as const

const diagramTypeOptions = [
  { value: 'circle_map', label: '圆圈图' },
  { value: 'bubble_map', label: '气泡图' },
  { value: 'double_bubble_map', label: '双气泡图' },
  { value: 'brace_map', label: '括号图' },
  { value: 'tree_map', label: '树形图' },
  { value: 'flow_map', label: '流程图' },
  { value: 'multi_flow_map', label: '复流程图' },
  { value: 'bridge_map', label: '桥型图' },
  { value: 'mind_map', label: '思维导图' },
  { value: 'concept_map', label: '概念图' },
  { value: 'combined', label: '组合应用' },
]

const sortOptions = [
  { value: 'default', labelKey: 'caseSquare.sort.default' },
  { value: 'hot', labelKey: 'caseSquare.sort.hot' },
  { value: 'newest', labelKey: 'caseSquare.sort.newest' },
]

const activeType = ref<(typeof typeTabs)[number]['key']>('all')
const expertOnly = ref(false)
const activeSubject = ref('')
const activeGrade = ref('')
const activeDiagramType = ref('')
const activeSort = ref('default')
const searchQuery = ref('')

const posts = ref<CaseSquarePost[]>([])
const blankThumbIds = ref(new Set<string>())
const total = ref(0)
const page = ref(1)
const pageSize = 20
const isLoading = ref(false)
const isLoadingMore = ref(false)
const loadError = ref<string | null>(null)

const showPublishModal = ref(false)
const showMyCasesModal = ref(false)
const showMyFavoritesModal = ref(false)
const editPostId = ref<string | null>(null)
const showDetailModal = ref(false)
const selectedPostId = ref<string | null>(null)
const selectedPostPreview = ref<CaseSquarePost | null>(null)

const scrollContainerRef = ref<HTMLElement | null>(null)

function displayTags(tags: string[]): string[] {
  return tags.filter((tag) => tag !== 'demo_seed_v1').slice(0, 3)
}

function showPostThumbnail(post: CaseSquarePost): boolean {
  return Boolean(post.thumbnail_url) && !blankThumbIds.value.has(post.id)
}

function hideBlankThumb(postId: string): void {
  if (blankThumbIds.value.has(postId)) return
  blankThumbIds.value = new Set([...blankThumbIds.value, postId])
}

async function onThumbLoad(post: CaseSquarePost, event: Event): Promise<void> {
  const img = event.target as HTMLImageElement
  if (!img.naturalWidth || img.naturalHeight < 2) {
    hideBlankThumb(post.id)
    return
  }
  try {
    const canvas = document.createElement('canvas')
    const sampleW = Math.min(48, img.naturalWidth)
    const sampleH = Math.min(48, img.naturalHeight)
    canvas.width = sampleW
    canvas.height = sampleH
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(img, 0, 0, sampleW, sampleH)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
    if (blob && (await isMostlyBlankImageBlob(blob))) {
      hideBlankThumb(post.id)
    }
  } catch {
    // keep showing image when blank detection fails
  }
}

function onThumbError(post: CaseSquarePost): void {
  hideBlankThumb(post.id)
}

const showDiagramTypeFilter = computed(() => activeType.value !== 'teaching_design')

const sortFilterOptions = computed(() =>
  sortOptions.map((s) => ({ value: s.value, label: String(t(s.labelKey)) }))
)

const subjectFilterOptions = computed(() => subjectOptions.value)
const gradeFilterOptions = computed(() => gradeOptions.value)

function filterAllLabel(): string {
  return String(t('caseSquare.filter.all'))
}

function caseTypeLabel(caseType: CaseSquareCaseType): string {
  if (caseType === 'teaching_design') return String(t('caseSquare.type.teachingDesign'))
  if (caseType === 'diagram_case') return String(t('caseSquare.type.diagramCase'))
  return String(t('caseSquare.type.diagramTemplate'))
}

function typeTabIcon(key: (typeof typeTabs)[number]['key']) {
  if (key === 'teaching_design') return BookOpen
  if (key === 'diagram_case') return ImageIcon
  if (key === 'diagram_template') return LayoutTemplate
  return null
}

async function fetchPosts(append = false) {
  if (append) isLoadingMore.value = true
  else isLoading.value = true
  loadError.value = null

  try {
    const typeTab = typeTabs.find((x) => x.key === activeType.value)
    const res = await getCaseSquarePosts({
      page: page.value,
      pageSize,
      caseType: typeTab?.api,
      expertRecommended: expertOnly.value,
      subject: activeSubject.value || undefined,
      grade: activeGrade.value || undefined,
      diagramType: showDiagramTypeFilter.value && activeDiagramType.value ? activeDiagramType.value : undefined,
      sort: activeSort.value,
      search: searchQuery.value.trim() || undefined,
    })
    posts.value = append ? [...posts.value, ...res.posts] : res.posts
    total.value = res.total
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Failed to load'
    if (!append) posts.value = []
  } finally {
    isLoading.value = false
    isLoadingMore.value = false
  }
}

function reload() {
  page.value = 1
  void fetchPosts()
}

function loadMore() {
  if (isLoading.value || isLoadingMore.value) return
  if (page.value >= Math.ceil(total.value / pageSize)) return
  page.value += 1
  void fetchPosts(true)
}

useInfiniteScroll(scrollContainerRef, () => loadMore(), {
  distance: 200,
  direction: 'bottom',
  canLoadMore: () =>
    !isLoading.value && !isLoadingMore.value && page.value < Math.ceil(total.value / pageSize),
})

function openDetail(post: CaseSquarePost) {
  selectedPostId.value = post.id
  selectedPostPreview.value = post
  showDetailModal.value = true
}

function openDetailFromKeyboard(post: CaseSquarePost, event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    openDetail(post)
  }
}

function handleDetailUpdated(updated: CaseSquarePost) {
  if (updated.status === 'withdrawn') {
    posts.value = posts.value.filter((p) => p.id !== updated.id)
    total.value = Math.max(0, total.value - 1)
    return
  }
  const idx = posts.value.findIndex((p) => p.id === updated.id)
  if (idx >= 0) posts.value[idx] = { ...posts.value[idx], ...updated }
}

function openPublishModal() {
  editPostId.value = null
  showPublishModal.value = true
}

function openEditPost(postId: string) {
  editPostId.value = postId
  showPublishModal.value = true
}

function handleDetailDeleted() {
  handleMyCaseDeleted(selectedPostId.value ?? '')
}

function handleMyCaseDeleted(postId: string) {
  if (!postId) return
  posts.value = posts.value.filter((p) => p.id !== postId)
  total.value = Math.max(0, total.value - 1)
  if (selectedPostId.value === postId) {
    selectedPostId.value = null
    selectedPostPreview.value = null
  }
}

function handlePublishSuccess() {
  editPostId.value = null
  void reload()
}

onMounted(() => {
  void fetchPosts()
})

watch(
  [activeType, expertOnly, activeSubject, activeGrade, activeDiagramType, activeSort],
  () => reload()
)

watch(activeType, (type) => {
  if (type === 'teaching_design') activeDiagramType.value = ''
})

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchQuery, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => reload(), 300)
})
</script>

<template>
  <div class="case-square-page flex flex-1 flex-col min-h-0 overflow-hidden bg-gray-50/50">
    <div ref="scrollContainerRef" class="case-square-scroll flex-1 min-h-0 overflow-y-auto overscroll-y-contain">
      <div class="mx-auto w-[90%] px-4 py-3 pb-6 sm:px-5">
      <!-- Header -->
      <div class="mb-3 flex items-center justify-between gap-4">
        <div class="min-w-0">
          <h1 class="text-xl font-bold text-gray-900">{{ t('caseSquare.title') }}</h1>
          <p class="mt-0.5 truncate text-xs text-gray-500">{{ t('caseSquare.subtitle') }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <button
            v-if="authStore.isAuthenticated"
            type="button"
            class="flex h-9 items-center gap-1.5 rounded-xl border border-gray-100 bg-white px-4 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            @click="showMyFavoritesModal = true"
          >
            <Star class="h-4 w-4" />
            {{ t('caseSquare.myFavorites') }}
          </button>
          <button
            v-if="authStore.isAuthenticated"
            type="button"
            class="flex h-9 items-center gap-1.5 rounded-xl border border-gray-100 bg-white px-4 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            @click="showMyCasesModal = true"
          >
            <FileText class="h-4 w-4" />
            {{ t('caseSquare.myCases') }}
          </button>
          <button
            type="button"
            class="flex h-9 items-center gap-1.5 rounded-xl bg-gray-900 px-4 text-sm font-medium text-white transition-colors hover:bg-gray-800"
            @click="openPublishModal"
          >
            <Plus class="h-4 w-4" />
            {{ t('caseSquare.publish') }}
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="mb-3 space-y-2">
        <div class="flex flex-wrap items-center gap-2">
          <div class="case-square-type-switch flex h-9 items-center gap-0.5 rounded-xl border border-gray-100 bg-white p-0.5 shadow-sm">
            <button
              v-for="tab in typeTabs"
              :key="tab.key"
              type="button"
              :class="[
                'case-square-type-tab flex h-8 items-center gap-1 rounded-lg px-3 text-sm border-0 outline-none transition-all duration-200',
                activeType === tab.key
                  ? 'case-square-type-tab--active bg-gray-900 font-medium text-white shadow-none'
                  : 'case-square-type-tab--idle bg-transparent text-gray-600 shadow-none hover:bg-gray-100',
              ]"
              @click="activeType = tab.key"
            >
              <component
                :is="typeTabIcon(tab.key)"
                v-if="typeTabIcon(tab.key)"
                class="h-3.5 w-3.5 shrink-0"
              />
              {{ t(tab.labelKey) }}
            </button>
          </div>

          <button
            type="button"
            :class="[
              'flex h-9 items-center gap-1.5 rounded-xl px-3 text-sm',
              expertOnly
                ? 'border border-amber-100 bg-amber-50 text-amber-700 shadow-sm'
                : 'border border-gray-100 bg-white text-gray-600 shadow-sm hover:bg-gray-50',
            ]"
            @click="expertOnly = !expertOnly"
          >
            <Award class="h-3.5 w-3.5 shrink-0" />
            {{ t('caseSquare.expertRecommend') }}
          </button>

          <CaseSquareFilterDropdown
            v-model="activeSubject"
            :label="String(t('caseSquare.subject'))"
            :options="subjectFilterOptions"
            :all-label="filterAllLabel()"
          />

          <CaseSquareFilterDropdown
            v-model="activeGrade"
            :label="String(t('caseSquare.grade'))"
            :options="gradeFilterOptions"
            :all-label="filterAllLabel()"
          />

          <CaseSquareFilterDropdown
            v-if="showDiagramTypeFilter"
            v-model="activeDiagramType"
            :label="String(t('caseSquare.diagramType'))"
            :options="diagramTypeOptions"
            :all-label="filterAllLabel()"
          />
        </div>

        <div class="flex items-center gap-2">
          <CaseSquareFilterDropdown
            v-model="activeSort"
            variant="plain"
            panel-size="sm"
            :prefix-icon="ArrowUpDown"
            :options="sortFilterOptions"
            :include-all="false"
          />

          <div class="relative min-w-[160px] flex-1">
            <Search class="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" />
            <input
              v-model="searchQuery"
              type="text"
              :placeholder="t('caseSquare.searchPlaceholder')"
              class="h-9 w-full rounded-full border border-gray-100 bg-white pl-9 pr-3 text-sm shadow-sm outline-none transition-all focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
            />
          </div>
        </div>
      </div>

      <p v-if="!isLoading && !loadError" class="mb-4 text-xs text-gray-400">
        {{ t('caseSquare.caseCount', { n: total }) }}
      </p>

      <!-- Grid -->
      <ElSkeleton v-if="isLoading" :rows="6" animated />
      <p v-else-if="loadError" class="text-sm text-red-500">{{ loadError }}</p>
      <div
        v-else-if="posts.length === 0"
        class="flex flex-col items-center justify-center py-20"
      >
        <Search class="mb-3 h-10 w-10 text-gray-300" />
        <p class="text-sm text-gray-400">{{ t('caseSquare.empty') }}</p>
      </div>
      <div v-else class="case-square-grid">
        <article
          v-for="post in posts"
          :key="post.id"
          role="button"
          tabindex="0"
          class="case-square-card group flex flex-col overflow-hidden rounded-xl border border-gray-100 bg-white text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
          @click="openDetail(post)"
          @keydown="openDetailFromKeyboard(post, $event)"
        >
          <!-- Cover (full card width) -->
          <div
            :class="[
              'case-square-card-cover relative aspect-[5/3] w-full shrink-0 overflow-hidden',
              showPostThumbnail(post)
                ? 'bg-gray-100'
                : ['bg-gradient-to-br', caseTypeTheme(post.case_type).coverFallback],
            ]"
          >
            <img
              v-if="showPostThumbnail(post)"
              :src="post.thumbnail_url!"
              :alt="post.title"
              loading="lazy"
              class="absolute inset-0 block h-full w-full min-w-full object-cover object-center"
              @load="onThumbLoad(post, $event)"
              @error="onThumbError(post)"
            />
            <div
              v-if="showPostThumbnail(post)"
              class="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/45 to-transparent"
            />
            <div class="absolute inset-x-0 top-0 z-10 flex flex-wrap items-center gap-1 p-2">
              <span
                v-if="post.is_expert_recommended"
                class="flex items-center gap-0.5 rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white shadow-sm"
              >
                <Award class="h-2.5 w-2.5" />
                {{ t('caseSquare.expertBadge') }}
              </span>
              <span
                :class="[
                  'rounded-full px-2 py-0.5 text-[10px] font-semibold shadow-sm',
                  caseTypeTheme(post.case_type).caseTypeTagClass,
                ]"
              >
                {{ caseTypeEmoji(post.case_type) }}{{ caseTypeLabel(post.case_type) }}
              </span>
              <span
                v-if="post.subject"
                :class="[
                  'rounded-full px-2 py-0.5 text-[10px] font-semibold shadow-sm',
                  caseTypeTheme(post.case_type).subjectTagClass,
                ]"
              >
                {{ post.subject }}
              </span>
            </div>
            <div class="absolute bottom-2 right-2 z-10 flex items-center gap-0.5 text-white">
              <Eye class="h-3 w-3" />
              <span class="text-[10px] font-medium">{{ post.views_count }}</span>
            </div>
          </div>

          <!-- Content -->
          <div class="flex flex-1 flex-col p-2">
            <h3 class="mb-0.5 line-clamp-1 text-[13px] font-semibold leading-tight text-gray-900 group-hover:text-gray-700">
              {{ post.title }}
            </h3>
            <p class="mb-1.5 line-clamp-1 text-[11px] leading-tight text-gray-500">
              {{ post.description }}
            </p>
            <div v-if="displayTags(post.tags).length > 0" class="mb-1.5 flex flex-wrap gap-1">
              <span
                v-for="tag in displayTags(post.tags).slice(0, 2)"
                :key="tag"
                class="rounded bg-gray-100 px-1.5 py-px text-[10px] leading-none text-gray-500"
              >
                {{ tag }}
              </span>
            </div>
            <div class="mt-auto border-t border-gray-100 pt-1.5">
              <div class="flex items-center justify-between gap-1.5">
                <div class="flex min-w-0 flex-1 items-center gap-1">
                  <div class="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[9px] leading-none">
                    {{ post.author.avatar ?? '👤' }}
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-[11px] font-medium leading-[1.15] text-gray-700">
                      {{ post.author.name }}
                    </div>
                    <div
                      v-if="post.author.organization"
                      class="truncate text-[10px] leading-[1.15] text-gray-400"
                    >
                      {{ post.author.organization }}
                    </div>
                  </div>
                </div>
                <span
                  :class="[
                    'inline-flex shrink-0 items-center gap-0.5 text-[10px] leading-none',
                    post.is_liked ? 'text-red-500' : 'text-gray-400',
                  ]"
                >
                  <Heart class="h-3 w-3" :class="post.is_liked ? 'fill-current' : ''" />
                  {{ post.likes_count }}
                </span>
              </div>
            </div>
          </div>
        </article>
      </div>
      <p v-if="isLoadingMore" class="py-4 text-center text-sm text-gray-400">…</p>
      </div>
    </div>

    <PublishCaseSquareModal
      v-model:visible="showPublishModal"
      :edit-post-id="editPostId"
      @success="handlePublishSuccess"
    />
    <MyPublishedCasesModal
      v-model:visible="showMyCasesModal"
      @open="openDetail"
      @edit="openEditPost"
      @updated="handleDetailUpdated"
      @deleted="handleMyCaseDeleted"
    />
    <MyFavoriteCasesModal
      v-model:visible="showMyFavoritesModal"
      @open="openDetail"
    />
    <CaseSquareDetailModal
      v-model:visible="showDetailModal"
      :post-id="selectedPostId"
      :post-preview="selectedPostPreview"
      @updated="handleDetailUpdated"
      @deleted="handleDetailDeleted"
      @edit="openEditPost"
    />
  </div>
</template>

<style scoped>
.case-square-page {
  min-height: 0;
}

.case-square-scroll {
  -webkit-overflow-scrolling: touch;
}

.case-square-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (min-width: 900px) {
  .case-square-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 1100px) {
  .case-square-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (min-width: 1360px) {
  .case-square-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
}

@media (min-width: 1600px) {
  .case-square-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}

.case-square-card {
  appearance: none;
  -webkit-appearance: none;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
  min-width: 0;
  padding: 0;
  margin: 0;
  box-sizing: border-box;
  border: 1px solid #f3f4f6;
  outline: none;
  cursor: pointer;
}

.case-square-card-cover {
  align-self: stretch;
  max-width: 100%;
}

.case-square-card:focus,
.case-square-card:focus-visible {
  outline: none;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
}

.case-square-card:hover {
  border-color: #e5e7eb;
}

.case-square-type-switch .case-square-type-tab {
  appearance: none;
  -webkit-appearance: none;
  border: none;
  outline: none;
}

.case-square-type-switch .case-square-type-tab:focus,
.case-square-type-switch .case-square-type-tab:focus-visible {
  outline: none;
}

.case-square-type-switch .case-square-type-tab--idle:focus,
.case-square-type-switch .case-square-type-tab--idle:focus-visible {
  box-shadow: none;
}

.case-square-type-switch .case-square-type-tab--idle:hover {
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
}

.case-square-type-switch .case-square-type-tab--active,
.case-square-type-switch .case-square-type-tab--active:hover,
.case-square-type-switch .case-square-type-tab--active:focus,
.case-square-type-switch .case-square-type-tab--active:focus-visible {
  box-shadow: none;
}
</style>
