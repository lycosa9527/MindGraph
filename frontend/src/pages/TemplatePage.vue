<script setup lang="ts">
/**
 * TemplatePage - Template library with filters and thumbnail grid
 * Features: Scene filters, Subject filters, Template thumbnails
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { Folder, Search } from '@lucide/vue'

import { LoginModal } from '@/components/auth'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { notify } from '@/composables/core/notifications'
import {
  MARKET_PAY_NEED_LOGIN,
  fetchMarketOrder,
  formatListingYuan,
  isAlipayReturnQuery,
  parseAlipayReturnOrderId,
  startMarketPagePay,
} from '@/composables/markets/marketPagePay'
import {
  MOCK_TEMPLATE_LISTINGS,
  listingRowToTemplate,
  type MarketListingRow,
  type TemplateResource,
} from '@/composables/markets/templateCatalog'
import { apiRequest } from '@/utils/apiClient'

// Filter options
const typeOptions = ['全部', 'MindMate', 'MindGraph'] as const
const sceneOptions = ['全部', '教学通用', '主题班会', '总结汇报'] as const
const subjectOptions = [
  '全部',
  '语文',
  '数学',
  '英语',
  '物理',
  '化学',
  '生物',
  '历史',
  '地理',
  '政治',
  '音乐',
  '美术',
  '体育',
  '信息技术',
  '综合实践',
] as const

// Active filters
const activeType = ref<string>('全部')
const activeScene = ref<string>('全部')
const activeSubject = ref<string>('全部')
const searchQuery = ref('')

const { featureMarkets } = useFeatureFlags()
const route = useRoute()
const apiListings = ref<TemplateResource[]>([])
const payingListingId = ref<number | null>(null)
const showLoginModal = ref(false)
const returnBanner = ref('')

async function fetchMarketTemplateListings(): Promise<void> {
  if (!featureMarkets.value) {
    apiListings.value = []
    return
  }
  const params = new URLSearchParams()
  params.set('listing_kind', 'template')
  if (activeScene.value !== '全部') {
    params.set('scene', activeScene.value)
  }
  if (activeSubject.value !== '全部') {
    params.set('subject', activeSubject.value)
  }
  if (activeType.value !== '全部') {
    params.set('product_type', activeType.value)
  }
  const res = await apiRequest(`/api/markets/listings?${params.toString()}`)
  if (!res.ok) {
    apiListings.value = []
    return
  }
  const rows = (await res.json()) as MarketListingRow[]
  apiListings.value = rows.map(listingRowToTemplate)
}

watch(
  [featureMarkets, activeType, activeScene, activeSubject],
  () => {
    void fetchMarketTemplateListings()
  },
  { immediate: true }
)

const baseTemplates = computed(() => {
  if (featureMarkets.value) {
    return apiListings.value
  }
  return MOCK_TEMPLATE_LISTINGS
})

// Filtered templates
const filteredTemplates = computed(() => {
  return baseTemplates.value.filter((template) => {
    const matchesType = activeType.value === '全部' || template.type === activeType.value
    const matchesScene = activeScene.value === '全部' || template.scene === activeScene.value
    const matchesSubject =
      activeSubject.value === '全部' || template.subject === activeSubject.value
    const matchesSearch =
      !searchQuery.value || template.title.toLowerCase().includes(searchQuery.value.toLowerCase())
    return matchesType && matchesScene && matchesSubject && matchesSearch
  })
})

// Shuffle templates for randomized display
const displayTemplates = computed(() => {
  const templates = [...filteredTemplates.value]
  // Fisher-Yates shuffle for randomization
  for (let i = templates.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[templates[i], templates[j]] = [templates[j], templates[i]]
  }
  return templates
})

function setType(type: string) {
  activeType.value = type
}

function setScene(scene: string) {
  activeScene.value = scene
}

function setSubject(subject: string) {
  activeSubject.value = subject
}

function formatNumber(num: number): string {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

// Generate placeholder colors based on template id
function getPlaceholderColor(id: string): string {
  const colors = [
    'from-amber-400 to-orange-500',
    'from-emerald-400 to-teal-500',
    'from-blue-400 to-indigo-500',
    'from-purple-400 to-pink-500',
    'from-rose-400 to-red-500',
    'from-cyan-400 to-blue-500',
    'from-lime-400 to-green-500',
    'from-fuchsia-400 to-purple-500',
  ]
  let hash = 0
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0
  }
  return colors[hash % colors.length]
}

async function confirmAlipayReturn(): Promise<void> {
  if (!isAlipayReturnQuery(route.query)) {
    return
  }
  const orderId = parseAlipayReturnOrderId(route.query)
  if (orderId === null) {
    returnBanner.value = '正在确认支付结果，请稍候刷新本页。'
    return
  }
  returnBanner.value = '正在确认支付结果…'
  try {
    const order = await fetchMarketOrder(orderId)
    if (order.status === 'paid') {
      returnBanner.value = '支付成功，模板已开通。'
      return
    }
    returnBanner.value = '支付处理中，到账后可直接使用模板。'
  } catch (error) {
    if (error instanceof Error && error.message === MARKET_PAY_NEED_LOGIN) {
      showLoginModal.value = true
      returnBanner.value = '请登录后查看支付结果。'
      return
    }
    returnBanner.value = '暂时无法确认支付结果，请稍后刷新。'
  }
}

async function onTemplateCardClick(template: TemplateResource): Promise<void> {
  if (!featureMarkets.value || template.listingId === null) {
    return
  }
  if (payingListingId.value !== null) {
    return
  }
  payingListingId.value = template.listingId
  try {
    await startMarketPagePay(template.listingId)
  } catch (error) {
    if (error instanceof Error && error.message === MARKET_PAY_NEED_LOGIN) {
      showLoginModal.value = true
      notify.warning('请先登录后再购买模板')
      return
    }
    const message = error instanceof Error ? error.message : '发起支付失败'
    notify.error(message)
  } finally {
    payingListingId.value = null
  }
}

onMounted(() => {
  void confirmAlipayReturn()
})
</script>

<template>
  <div class="template-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header -->
    <div class="template-header px-6 py-5 bg-white border-b border-stone-200">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-semibold text-stone-900">模板资源</h1>
        <!-- Search -->
        <div class="relative">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索模板..."
            class="pl-10 pr-4 py-2 w-64 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 transition-all"
          />
        </div>
      </div>

      <!-- Filter rows -->
      <div class="space-y-3">
        <!-- Type filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">类型</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="type in typeOptions"
              :key="type"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeType === type
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setType(type)"
            >
              {{ type }}
            </button>
          </div>
        </div>

        <!-- Scene filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">场景</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="scene in sceneOptions"
              :key="scene"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeScene === scene
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setScene(scene)"
            >
              {{ scene }}
            </button>
          </div>
        </div>

        <!-- Subject filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">科目</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="subject in subjectOptions"
              :key="subject"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeSubject === subject
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setSubject(subject)"
            >
              {{ subject }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="returnBanner"
      class="mx-6 mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      {{ returnBanner }}
    </div>

    <!-- Template grid -->
    <div class="template-grid flex-1 overflow-y-auto p-6">
      <div
        v-if="displayTemplates.length > 0"
        class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-5"
      >
        <div
          v-for="template in displayTemplates"
          :key="template.id"
          class="template-card group cursor-pointer"
          @click="onTemplateCardClick(template)"
        >
          <!-- Thumbnail -->
          <div
            :class="[
              'aspect-[4/3] rounded-xl overflow-hidden mb-3 relative',
              'bg-gradient-to-br',
              getPlaceholderColor(template.id),
            ]"
          >
            <!-- Placeholder pattern -->
            <div class="absolute inset-0 flex items-center justify-center opacity-30">
              <svg
                class="w-16 h-16 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="3"
                />
                <path d="M12 9V3" />
                <path d="M12 15v6" />
                <path d="M9 12H3" />
                <path d="M15 12h6" />
                <path d="M9.17 9.17L4.93 4.93" />
                <path d="M14.83 14.83l4.24 4.24" />
                <path d="M9.17 14.83L4.93 19.07" />
                <path d="M14.83 9.17l4.24-4.24" />
              </svg>
            </div>
            <!-- Hover overlay -->
            <div
              class="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center"
            >
              <span
                class="text-white text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity bg-black/40 px-3 py-1.5 rounded-full"
              >
                {{
                  featureMarkets && template.listingId
                    ? payingListingId === template.listingId
                      ? '正在跳转支付宝…'
                      : '支付宝购买'
                    : '使用模板'
                }}
              </span>
            </div>
          </div>

          <!-- Info -->
          <div class="px-1">
            <h3
              class="text-sm font-medium text-stone-800 line-clamp-2 mb-2 group-hover:text-amber-600 transition-colors"
            >
              {{ template.title }}
            </h3>
            <div class="flex items-center gap-3 text-xs text-stone-400">
              <span v-if="template.priceMinor !== null">{{ formatListingYuan(template.priceMinor) }}</span>
              <span v-else>{{ formatNumber(template.views) }} 浏览</span>
              <span v-if="template.priceMinor === null">{{ formatNumber(template.downloads) }} 使用</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else
        class="flex flex-col items-center justify-center h-full text-stone-400"
      >
        <Folder class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium mb-1">没有找到匹配的模板</p>
        <p class="text-sm">尝试调整筛选条件或搜索关键词</p>
      </div>
    </div>
    <LoginModal
      v-model:visible="showLoginModal"
      @success="showLoginModal = false"
    />
  </div>
</template>

<style scoped>
.template-page {
  min-height: 0;
}

.template-card {
  transition: transform 0.2s ease;
}

.template-card:hover {
  transform: translateY(-2px);
}

/* Custom scrollbar */
.template-grid::-webkit-scrollbar {
  width: 6px;
}

.template-grid::-webkit-scrollbar-track {
  background: transparent;
}

.template-grid::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.template-grid::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}

/* Line clamp */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
