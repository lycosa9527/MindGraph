<script setup lang="ts">
/**
 * Teacher Usage Page (教师使用度)
 * Admin-only analytics dashboard for teacher engagement classification.
 * 2-tier: 未使用/持续使用/非持续使用 + 拒绝使用/停止使用/间歇式使用
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ArrowDown, ArrowUp, Loading } from '@element-plus/icons-vue'

import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import type { EChartsType } from 'echarts/core'
import { LabelLayout } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'

import { useLanguage } from '@/composables/useLanguage'
import { useNotifications } from '@/composables/useNotifications'
import { useUIStore } from '@/stores/ui'
import { apiRequest } from '@/utils/apiClient'
import { formatUserNumber } from '@/utils/intlDisplay'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  LabelLayout,
  CanvasRenderer,
])

const { t, currentLanguage } = useLanguage()
const uiStore = useUIStore()
const notify = useNotifications()

interface GroupDefinition {
  id: string
}

const TOP_LEVEL_GROUPS: GroupDefinition[] = [{ id: 'unused' }, { id: 'continuous' }]

const SUB_GROUPS: GroupDefinition[] = [
  { id: 'rejection' },
  { id: 'stopped' },
  { id: 'intermittent' },
]

const GROUPS = [...TOP_LEVEL_GROUPS, ...SUB_GROUPS]

function teacherGroupName(groupId: string): string {
  return t(`teacher.analytics.group.${groupId}.name`)
}

function teacherGroupDescription(groupId: string): string {
  return t(`teacher.analytics.group.${groupId}.description`)
}

interface Teacher {
  id: number
  username: string
  diagrams: number
  conceptGen: number
  relationshipLabels: number
  tokens: number
  lastActive: string
}

interface GroupStats {
  count: number
  totalTokens: number
  teachers: Teacher[]
  weeklyTokens?: number[]
}

type StatCardType = 'total' | 'unused' | 'continuous' | 'rejection' | 'stopped' | 'intermittent'

const expandedGroupIds = ref<string[]>([])
const configForm = ref({
  continuous: {
    active_weeks_min: 5,
    active_weeks_first4_min: 1,
    active_weeks_last4_min: 1,
    max_zero_gap_days_max: 10,
  },
  rejection: {
    active_days_max: 3,
    active_days_first10_min: 1,
    active_days_last25_max: 0,
    max_zero_gap_days_min: 25,
  },
  stopped: {
    active_days_first25_min: 3,
    active_days_last14_max: 0,
    max_zero_gap_days_min: 14,
  },
  intermittent: {
    n_bursts_min: 2,
    internal_max_zero_gap_days_min: 7,
  },
})
const isSavingConfig = ref(false)
const isRecomputing = ref(false)

function toggleGroupExpanded(groupId: string) {
  const idx = expandedGroupIds.value.indexOf(groupId)
  if (idx >= 0) {
    expandedGroupIds.value = expandedGroupIds.value.filter((id) => id !== groupId)
  } else {
    expandedGroupIds.value = [...expandedGroupIds.value, groupId]
  }
}

function isGroupExpanded(groupId: string): boolean {
  return expandedGroupIds.value.includes(groupId)
}

const showTeachersModal = ref(false)
const modalTeachers = ref<Teacher[]>([])
const modalTitle = ref('')
const modalStatCardType = ref<StatCardType | null>(null)
const showUserChartModal = ref(false)
const selectedUser = ref<Teacher | null>(null)
const userChartLoading = ref(false)
const userChartRef = ref<HTMLDivElement | null>(null)
let userChart: EChartsType | null = null

const activeTab = ref('overview')
const allUsers = ref<Teacher[]>([])
const allUsersLoading = ref(false)
const usersTotal = ref(0)
const usersPage = ref(1)
const usersPageSize = 50
interface WeeklyDataPoint {
  date: string
  tokens: number
}

interface ActivityTrendPoint {
  date: string
  editCount: number
  exportCount: number
  autocompleteCount: number
}

interface UserDetailData {
  diagrams: number
  conceptGen: number
  relationshipLabels: number
  weeklyData: WeeklyDataPoint[]
  activityTrends: ActivityTrendPoint[]
  tokenStats: {
    today: { input_tokens: number; output_tokens: number; total_tokens: number }
    week: { input_tokens: number; output_tokens: number; total_tokens: number }
    month: { input_tokens: number; output_tokens: number; total_tokens: number }
    total: { input_tokens: number; output_tokens: number; total_tokens: number }
  }
}
const userDetailData = ref<UserDetailData | null>(null)

function getTeachersForStatCard(type: StatCardType): Teacher[] {
  switch (type) {
    case 'total':
      return groupStats.value.total?.teachers ?? []
    case 'unused':
      return groupStats.value.unused?.teachers ?? []
    case 'continuous':
      return groupStats.value.continuous?.teachers ?? []
    case 'rejection':
      return groupStats.value.rejection?.teachers ?? []
    case 'stopped':
      return groupStats.value.stopped?.teachers ?? []
    case 'intermittent':
      return groupStats.value.intermittent?.teachers ?? []
    default:
      return []
  }
}

function getModalTitle(type: StatCardType): string {
  return t(`teacher.analytics.modalTitle.${type}`)
}

function openTeachersModal(type: StatCardType) {
  modalTeachers.value = getTeachersForStatCard(type)
  modalTitle.value = getModalTitle(type)
  modalStatCardType.value = type
  if (type !== 'total') {
    loadConfig()
  }
  showTeachersModal.value = true
}

async function openUserChart(row: Teacher) {
  selectedUser.value = row
  userDetailData.value = null
  showUserChartModal.value = true
  userChartLoading.value = true
  try {
    const response = await apiRequest(`auth/admin/teacher-usage/user/${row.id}/detail`)
    if (response.ok) {
      const data = await response.json()
      userDetailData.value = {
        diagrams: data.diagrams ?? 0,
        conceptGen: data.conceptGen ?? 0,
        relationshipLabels: data.relationshipLabels ?? 0,
        weeklyData: data.weeklyData ?? [],
        activityTrends: data.activityTrends ?? [],
        tokenStats: data.tokenStats ?? {
          today: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
          week: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
          month: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
          total: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
        },
      }
    }
  } catch (error) {
    console.error('Failed to load user detail:', error)
    notify.error(t('teacher.analytics.notify.loadFailed'))
  } finally {
    userChartLoading.value = false
  }
}

function initUserChart() {
  if (!userChartRef.value || !showUserChartModal.value) return
  userChart?.dispose()
  userChart = echarts.init(userChartRef.value)
  const data = userDetailData.value
  const activityTrends = data?.activityTrends ?? []
  const dates = activityTrends.map((d) => d.date)
  const editCounts = activityTrends.map((d) => d.editCount)
  const exportCounts = activityTrends.map((d) => d.exportCount)
  const autocompleteCounts = activityTrends.map((d) => d.autocompleteCount)
  const hasData = dates.length > 0
  userChart.setOption({
    title: {
      text: t('teacher.analytics.chart.dailyTrend'),
      left: 'center',
    },
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: [
        t('teacher.analytics.chart.edits'),
        t('teacher.analytics.chart.exports'),
        t('teacher.analytics.chart.autoGen'),
      ],
      top: 28,
    },
    xAxis: {
      type: 'category',
      data: hasData ? dates : [t('teacher.analytics.chart.noData')],
      axisLabel: { rotate: dates.length > 14 ? 45 : 0 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (value: number) => String(Math.round(value)) },
    },
    series: [
      {
        name: t('teacher.analytics.chart.edits'),
        type: 'line',
        data: hasData ? editCounts : [0],
        smooth: true,
      },
      {
        name: t('teacher.analytics.chart.exports'),
        type: 'line',
        data: hasData ? exportCounts : [0],
        smooth: true,
      },
      {
        name: t('teacher.analytics.chart.autoGen'),
        type: 'line',
        data: hasData ? autocompleteCounts : [0],
        smooth: true,
      },
    ],
  })
}

async function loadAllUsers(page = 1) {
  allUsersLoading.value = true
  try {
    const response = await apiRequest(
      `auth/admin/teacher-usage/users?page=${page}&page_size=${usersPageSize}`
    )
    if (response.ok) {
      const data = await response.json()
      allUsers.value = data.users ?? []
      usersTotal.value = data.total ?? 0
      usersPage.value = data.page ?? page
    } else {
      notify.error(t('teacher.analytics.notify.loadUsersFailed'))
    }
  } catch (error) {
    console.error('Failed to load users:', error)
    notify.error(t('teacher.analytics.notify.loadUsersFailed'))
  } finally {
    allUsersLoading.value = false
  }
}

function onUsersPageChange(page: number) {
  usersPage.value = page
  loadAllUsers(page)
}

function openUserDetailFromList(row: Teacher) {
  openUserChart(row)
}

function closeUserChartModal() {
  showUserChartModal.value = false
  userChart?.dispose()
  userChart = null
  selectedUser.value = null
  userDetailData.value = null
}

function onUserChartModalOpened() {
  if (!userChartLoading.value && showUserChartModal.value) {
    nextTick().then(() => {
      setTimeout(() => {
        if (userChartRef.value) {
          initUserChart()
          userChart?.resize()
        }
      }, 50)
    })
  }
}

async function loadConfig() {
  try {
    const response = await apiRequest('auth/admin/teacher-usage/config')
    if (response.ok) {
      const data = await response.json()
      configForm.value = {
        continuous: { ...configForm.value.continuous, ...data.continuous },
        rejection: { ...configForm.value.rejection, ...data.rejection },
        stopped: { ...configForm.value.stopped, ...data.stopped },
        intermittent: { ...configForm.value.intermittent, ...data.intermittent },
      }
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

async function saveConfig() {
  isSavingConfig.value = true
  try {
    const response = await apiRequest('auth/admin/teacher-usage/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configForm.value),
    })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      notify.error(data.detail || t('teacher.analytics.notify.saveFailed'))
      return
    }
    notify.success(t('teacher.analytics.notify.configSaved'))
    await loadTeacherUsage()
  } catch (error) {
    console.error('Failed to save config:', error)
    notify.error(t('teacher.analytics.notify.saveFailed'))
  } finally {
    isSavingConfig.value = false
  }
}

async function recomputeClassifications() {
  isRecomputing.value = true
  try {
    const saveRes = await apiRequest('auth/admin/teacher-usage/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configForm.value),
    })
    if (!saveRes.ok) {
      notify.error(t('teacher.analytics.notify.saveFailed'))
      return
    }
    const recomputeRes = await apiRequest('auth/admin/teacher-usage/recompute', {
      method: 'POST',
    })
    if (!recomputeRes.ok) {
      const data = await recomputeRes.json().catch(() => ({}))
      notify.error(data.detail || t('teacher.analytics.notify.recomputeFailed'))
      return
    }
    const data = await recomputeRes.json()
    notify.success(t('teacher.analytics.notify.savedRecomputed', { n: data.recomputed }))
    await loadTeacherUsage()
  } catch (error) {
    console.error('Failed to recompute:', error)
    notify.error(t('teacher.analytics.notify.recomputeFailed'))
  } finally {
    isRecomputing.value = false
  }
}

const isLoading = ref(true)
const pieChartRef = ref<HTMLDivElement | null>(null)
const barChartRef = ref<HTMLDivElement | null>(null)
const groupChartRefs: Record<string, HTMLDivElement | null> = {}

const stats = ref({
  totalTeachers: 0,
  unused: 0,
  continuous: 0,
  rejection: 0,
  stopped: 0,
  intermittent: 0,
})

const groupStats = ref<Record<string, GroupStats>>({})

let pieChart: EChartsType | null = null
let barChart: EChartsType | null = null
const groupCharts: Record<string, EChartsType | null> = {}

async function loadTeacherUsage() {
  isLoading.value = true
  try {
    const response = await apiRequest('auth/admin/teacher-usage')
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      notify.error(data.detail || t('teacher.analytics.notify.loadDataFailed'))
      return
    }
    const data = await response.json()
    stats.value = {
      totalTeachers: data.stats?.totalTeachers ?? 0,
      unused: data.stats?.unused ?? 0,
      continuous: data.stats?.continuous ?? 0,
      rejection: data.stats?.rejection ?? 0,
      stopped: data.stats?.stopped ?? 0,
      intermittent: data.stats?.intermittent ?? 0,
    }
    for (const g of GROUPS) {
      const gData = data.groups?.[g.id]
      groupStats.value[g.id] = {
        count: gData?.count ?? 0,
        totalTokens: gData?.totalTokens ?? 0,
        teachers: gData?.teachers ?? [],
        weeklyTokens: gData?.weeklyTokens ?? [],
      }
    }
    const seen = new Set<number>()
    const allTeachers: Teacher[] = []
    let totalTokensSum = 0
    const maxWeeks = Math.max(
      0,
      ...GROUPS.map((gr) => groupStats.value[gr.id]?.weeklyTokens?.length ?? 0)
    )
    const weeklyTokensTotal = new Array(maxWeeks).fill(0)
    for (const g of GROUPS) {
      const gs = groupStats.value[g.id]
      if (gs) {
        totalTokensSum += gs.totalTokens
        for (const t of gs.teachers) {
          if (!seen.has(t.id)) {
            seen.add(t.id)
            allTeachers.push(t)
          }
        }
        const wt = gs.weeklyTokens ?? []
        wt.forEach((v, i) => {
          weeklyTokensTotal[i] = (weeklyTokensTotal[i] ?? 0) + v
        })
      }
    }
    groupStats.value.total = {
      count: stats.value.totalTeachers,
      totalTokens: totalTokensSum,
      teachers: allTeachers,
      weeklyTokens: weeklyTokensTotal,
    }
  } catch (error) {
    console.error('Failed to load teacher usage:', error)
    notify.error(t('teacher.analytics.notify.networkError'))
  } finally {
    isLoading.value = false
  }
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return formatUserNumber(num, uiStore.language)
}

function initPieChart() {
  if (!pieChartRef.value) return
  pieChart = echarts.init(pieChartRef.value)
  const data = GROUPS.map((g, _i) => ({
    name: t(`teacher.analytics.group.${g.id}.name`),
    value: groupStats.value[g.id]?.count ?? 0,
  }))
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', left: 'left', top: 'center' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['60%', '50%'],
        data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  })
}

function initBarChart() {
  if (!barChartRef.value) return
  barChart = echarts.init(barChartRef.value)
  const xData = GROUPS.map((g) => t(`teacher.analytics.group.${g.id}.name`))
  const yData = GROUPS.map((g) => groupStats.value[g.id]?.totalTokens ?? 0)
  barChart.setOption({
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: number) => formatNumber(value),
    },
    xAxis: { type: 'category', data: xData },
    yAxis: {
      type: 'value',
      name: 'Tokens',
      axisLabel: {
        formatter: (value: number) => formatNumber(value),
      },
    },
    series: [{ type: 'bar', data: yData }],
  })
}

function initGroupChart(groupId: string) {
  const el = groupChartRefs[groupId]
  if (!el || groupCharts[groupId]) return
  const chart = echarts.init(el)
  groupCharts[groupId] = chart
  const weeklyTokens = groupStats.value[groupId]?.weeklyTokens ?? []
  const weeks = weeklyTokens.map((_, i) => `W${i + 1}`)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: weeks.length ? weeks : ['-'] },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'line',
        data: weeklyTokens.length ? weeklyTokens : [0],
        smooth: true,
      },
    ],
  })
}

function initGroupCharts() {
  expandedGroupIds.value.forEach((groupId) => {
    initGroupChart(groupId)
  })
}

function resizeCharts() {
  pieChart?.resize()
  barChart?.resize()
  Object.values(groupCharts).forEach((c) => c?.resize())
  userChart?.resize()
}

watch(expandedGroupIds, async () => {
  await nextTick()
  setTimeout(initGroupCharts, 150)
})

watch(currentLanguage, () => {
  initPieChart()
  initBarChart()
  if (showUserChartModal.value && userChartRef.value) {
    initUserChart()
    userChart?.resize()
  }
})

watch([userDetailData, userChartLoading], async ([, loading]) => {
  if (!loading && showUserChartModal.value) {
    await nextTick()
    setTimeout(() => {
      if (userChartRef.value) {
        initUserChart()
        userChart?.resize()
      }
    }, 150)
  }
})

watch(activeTab, (tab) => {
  if (tab === 'teachers') {
    loadAllUsers(usersPage.value)
  }
})

onMounted(async () => {
  await loadTeacherUsage()
  await loadConfig()
  window.addEventListener('resize', resizeCharts)
  await nextTick()
  setTimeout(() => {
    initPieChart()
    initBarChart()
  }, 100)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  pieChart?.dispose()
  barChart?.dispose()
  Object.values(groupCharts).forEach((c) => c?.dispose())
  userChart?.dispose()
})
</script>

<template>
  <div class="teacher-usage-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header (same as Library, Gewe modules) -->
    <div
      class="teacher-usage-header h-14 px-4 flex items-center justify-between bg-white border-b border-stone-200"
    >
      <h1 class="text-sm font-semibold text-stone-900">
        {{ t('teacher.analytics.title') }}
      </h1>
      <el-button
        size="small"
        :loading="isLoading || allUsersLoading"
        @click="activeTab === 'overview' ? loadTeacherUsage() : loadAllUsers(usersPage)"
      >
        {{ t('common.refresh') }}
      </el-button>
    </div>

    <!-- Scrollable content -->
    <div class="teacher-usage-content flex-1 overflow-y-auto px-6 pt-6 pb-6">
      <el-tabs
        v-model="activeTab"
        class="teacher-usage-tabs"
      >
        <el-tab-pane
          :label="t('teacher.analytics.overview')"
          name="overview"
        >
          <div
            v-if="isLoading"
            class="flex items-center justify-center py-20"
          >
            <el-icon
              class="is-loading"
              :size="32"
              ><Loading
            /></el-icon>
          </div>

          <div
            v-else
            class="max-w-7xl mx-auto"
          >
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('total')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.totalTeachers') }}
                </p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatUserNumber(stats.totalTeachers, uiStore.language) }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('unused')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.unused') }}
                </p>
                <p class="text-2xl font-bold text-gray-500 dark:text-gray-400">
                  {{ stats.unused }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('continuous')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.continuous') }}
                </p>
                <p class="text-2xl font-bold text-green-600 dark:text-green-400">
                  {{ stats.continuous }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('rejection')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.rejection') }}
                </p>
                <p class="text-2xl font-bold text-orange-600 dark:text-orange-400">
                  {{ stats.rejection }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('stopped')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.stopped') }}
                </p>
                <p class="text-2xl font-bold text-red-600 dark:text-red-400">
                  {{ stats.stopped }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('intermittent')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.intermittent') }}
                </p>
                <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {{ stats.intermittent }}
                </p>
              </el-card>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <el-card shadow="hover">
                <template #header>
                  <span class="font-medium">
                    {{ t('teacher.analytics.groupDistribution') }}
                  </span>
                </template>
                <div
                  ref="pieChartRef"
                  class="h-64"
                />
              </el-card>
              <el-card shadow="hover">
                <template #header>
                  <span class="font-medium">
                    {{ t('teacher.analytics.tokenByGroup') }}
                  </span>
                </template>
                <div
                  ref="barChartRef"
                  class="h-64"
                />
              </el-card>
            </div>

            <!-- Diagram cards: Total, 未使用, 持续使用, then 非持续使用 box with 3 sub-cards -->
            <div class="space-y-4">
              <!-- Total -->
              <el-card
                shadow="hover"
                class="group-card cursor-pointer transition-colors"
                :class="{ 'group-card-expanded': isGroupExpanded('total') }"
                @click="toggleGroupExpanded('total')"
              >
                <div class="flex items-center justify-between">
                  <div>
                    <span class="font-semibold text-stone-900">
                      {{ t('teacher.analytics.group.total.name') }}
                    </span>
                    <div class="text-xs text-stone-500 mt-0.5">
                      {{ t('teacher.analytics.group.total.description') }}
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <el-tag size="small">
                      {{ groupStats.total?.count ?? 0 }}
                      {{ t('teacher.analytics.teachersUnit') }}
                    </el-tag>
                    <el-icon
                      :size="18"
                      class="text-stone-400"
                    >
                      <ArrowDown v-if="!isGroupExpanded('total')" />
                      <ArrowUp v-else />
                    </el-icon>
                  </div>
                </div>
                <div
                  v-show="isGroupExpanded('total')"
                  class="mt-6 pt-6 border-t border-stone-200"
                  @click.stop
                >
                  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                      <el-table
                        :data="groupStats.total?.teachers ?? []"
                        stripe
                        size="small"
                      >
                        <el-table-column
                          prop="username"
                          :label="t('teacher.analytics.colTeacher')"
                          width="140"
                        />
                        <el-table-column
                          prop="diagrams"
                          :label="t('teacher.analytics.colAutocompleteCount')"
                          width="80"
                        />
                        <el-table-column
                          prop="conceptGen"
                          :label="t('teacher.analytics.colConceptGen')"
                          width="80"
                        />
                        <el-table-column
                          prop="relationshipLabels"
                          :label="t('teacher.analytics.colRelLabels')"
                          width="80"
                        />
                        <el-table-column
                          prop="tokens"
                          :label="t('teacher.analytics.colTokens')"
                          width="100"
                        >
                          <template #default="{ row }">
                            {{ formatNumber(row.tokens) }}
                          </template>
                        </el-table-column>
                        <el-table-column
                          prop="lastActive"
                          :label="t('teacher.analytics.colLastActive')"
                        />
                      </el-table>
                    </div>
                    <div>
                      <div
                        :ref="
                          (el) => {
                            if (el) groupChartRefs['total'] = el as HTMLDivElement
                          }
                        "
                        class="h-48"
                      />
                    </div>
                  </div>
                </div>
              </el-card>

              <!-- 未使用, 持续使用 -->
              <el-card
                v-for="group in TOP_LEVEL_GROUPS"
                :key="group.id"
                shadow="hover"
                class="group-card cursor-pointer transition-colors"
                :class="{ 'group-card-expanded': isGroupExpanded(group.id) }"
                @click="toggleGroupExpanded(group.id)"
              >
                <div class="flex items-center justify-between">
                  <div>
                    <span class="font-semibold text-stone-900">
                      {{ teacherGroupName(group.id) }}
                    </span>
                    <div class="text-xs text-stone-500 mt-0.5">
                      {{ teacherGroupDescription(group.id) }}
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <el-tag size="small">
                      {{ groupStats[group.id]?.count ?? 0 }}
                      {{ t('teacher.analytics.teachersUnit') }}
                    </el-tag>
                    <el-icon
                      :size="18"
                      class="text-stone-400"
                    >
                      <ArrowDown v-if="!isGroupExpanded(group.id)" />
                      <ArrowUp v-else />
                    </el-icon>
                  </div>
                </div>
                <div
                  v-show="isGroupExpanded(group.id)"
                  class="mt-6 pt-6 border-t border-stone-200"
                  @click.stop
                >
                  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                      <el-table
                        :data="groupStats[group.id]?.teachers ?? []"
                        stripe
                        size="small"
                      >
                        <el-table-column
                          prop="username"
                          :label="t('teacher.analytics.colTeacher')"
                          width="140"
                        />
                        <el-table-column
                          prop="diagrams"
                          :label="t('teacher.analytics.colAutocompleteCount')"
                          width="80"
                        />
                        <el-table-column
                          prop="conceptGen"
                          :label="t('teacher.analytics.colConceptGen')"
                          width="80"
                        />
                        <el-table-column
                          prop="relationshipLabels"
                          :label="t('teacher.analytics.colRelLabels')"
                          width="80"
                        />
                        <el-table-column
                          prop="tokens"
                          :label="t('teacher.analytics.colTokens')"
                          width="100"
                        >
                          <template #default="{ row }">
                            {{ formatNumber(row.tokens) }}
                          </template>
                        </el-table-column>
                        <el-table-column
                          prop="lastActive"
                          :label="t('teacher.analytics.colLastActive')"
                        />
                      </el-table>
                    </div>
                    <div>
                      <div
                        :ref="
                          (el) => {
                            if (el) groupChartRefs[group.id] = el as HTMLDivElement
                          }
                        "
                        class="h-48"
                      />
                    </div>
                  </div>
                </div>
              </el-card>

              <!-- 非持续使用: 拒绝使用, 停止使用, 间歇式使用 in a visual box -->
              <div
                class="sub-groups-box rounded-lg border-2 border-stone-300 bg-stone-100/50 p-4 dark:border-stone-600 dark:bg-stone-800/30"
              >
                <div class="text-sm font-semibold text-stone-700 dark:text-stone-300 mb-4">
                  {{ t('teacher.analytics.nonContinuous') }}
                </div>
                <div class="space-y-4">
                  <el-card
                    v-for="group in SUB_GROUPS"
                    :key="group.id"
                    shadow="hover"
                    class="group-card group-card-nested cursor-pointer transition-colors"
                    :class="{ 'group-card-expanded': isGroupExpanded(group.id) }"
                    @click="toggleGroupExpanded(group.id)"
                  >
                    <div class="flex items-center justify-between">
                      <div>
                        <span class="font-semibold text-stone-900">
                          {{ teacherGroupName(group.id) }}
                        </span>
                        <div class="text-xs text-stone-500 mt-0.5">
                          {{ teacherGroupDescription(group.id) }}
                        </div>
                      </div>
                      <div class="flex items-center gap-2">
                        <el-tag size="small">
                          {{ groupStats[group.id]?.count ?? 0 }}
                          {{ t('teacher.analytics.teachersUnit') }}
                        </el-tag>
                        <el-icon
                          :size="18"
                          class="text-stone-400"
                        >
                          <ArrowDown v-if="!isGroupExpanded(group.id)" />
                          <ArrowUp v-else />
                        </el-icon>
                      </div>
                    </div>
                    <div
                      v-show="isGroupExpanded(group.id)"
                      class="mt-6 pt-6 border-t border-stone-200"
                      @click.stop
                    >
                      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                          <el-table
                            :data="groupStats[group.id]?.teachers ?? []"
                            stripe
                            size="small"
                          >
                            <el-table-column
                              prop="username"
                              :label="t('teacher.analytics.colTeacher')"
                              width="140"
                            />
                            <el-table-column
                              prop="diagrams"
                              :label="t('teacher.analytics.colAutocompleteCount')"
                              width="80"
                            />
                            <el-table-column
                              prop="conceptGen"
                              :label="t('teacher.analytics.colConceptGen')"
                              width="80"
                            />
                            <el-table-column
                              prop="relationshipLabels"
                              :label="t('teacher.analytics.colRelLabels')"
                              width="80"
                            />
                            <el-table-column
                              prop="tokens"
                              :label="t('teacher.analytics.colTokens')"
                              width="100"
                            >
                              <template #default="{ row }">
                                {{ formatNumber(row.tokens) }}
                              </template>
                            </el-table-column>
                            <el-table-column
                              prop="lastActive"
                              :label="t('teacher.analytics.colLastActive')"
                            />
                          </el-table>
                        </div>
                        <div>
                          <div
                            :ref="
                              (el) => {
                                if (el) groupChartRefs[group.id] = el as HTMLDivElement
                              }
                            "
                            class="h-48"
                          />
                        </div>
                      </div>
                    </div>
                  </el-card>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane
          :label="t('teacher.analytics.teachersTab')"
          name="teachers"
        >
          <div
            v-if="allUsersLoading"
            class="flex items-center justify-center py-20"
          >
            <el-icon
              class="is-loading"
              :size="32"
              ><Loading
            /></el-icon>
          </div>
          <div
            v-else
            class="max-w-5xl"
          >
            <el-table
              :data="allUsers"
              stripe
              size="small"
              class="teachers-list-table"
              @row-click="(row: Teacher) => openUserDetailFromList(row)"
            >
              <el-table-column
                prop="username"
                :label="t('teacher.analytics.colTeacher')"
                width="180"
              />
              <el-table-column
                prop="diagrams"
                :label="t('teacher.analytics.colAutocomplete')"
                width="100"
              />
              <el-table-column
                prop="conceptGen"
                :label="t('teacher.analytics.colConceptGen')"
                width="100"
              />
              <el-table-column
                prop="relationshipLabels"
                :label="t('teacher.analytics.colRelLabels')"
                width="100"
              />
              <el-table-column
                prop="tokens"
                :label="t('teacher.analytics.colTokens')"
                width="120"
              >
                <template #default="{ row }">
                  {{ formatNumber(row.tokens) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="lastActive"
                :label="t('teacher.analytics.colLastActive')"
              />
            </el-table>
            <div class="mt-4 flex justify-end">
              <el-pagination
                v-model:current-page="usersPage"
                :page-size="usersPageSize"
                :total="usersTotal"
                layout="prev, pager, next, total"
                @current-change="onUsersPageChange"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- Teachers list modal -->
    <el-dialog
      v-model="showTeachersModal"
      :title="modalTitle"
      width="700px"
      destroy-on-close
    >
      <!-- Classification rules (for non-total): show only rules for the selected category -->
      <div
        v-if="modalStatCardType && modalStatCardType !== 'total'"
        class="mb-4 pb-4 border-b border-stone-200"
      >
        <h4 class="text-sm font-semibold text-stone-700 mb-3">
          {{ t('teacher.analytics.rulesTitle') }}
        </h4>
        <!-- 未使用: active_days = 0 (fixed, read-only) -->
        <div
          v-if="modalStatCardType === 'unused'"
          class="text-sm text-stone-600"
        >
          <code class="bg-stone-100 px-2 py-1 rounded">{{
            t('teacher.analytics.ruleUnusedLine')
          }}</code>
          <span class="ml-2">{{ t('teacher.analytics.ruleUnusedHint') }}</span>
        </div>
        <!-- 持续使用 -->
        <el-form
          v-else-if="modalStatCardType === 'continuous'"
          label-position="top"
          class="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          <el-form-item :label="t('teacher.analytics.form.activeWeeks')">
            <el-input-number
              v-model="configForm.continuous.active_weeks_min"
              :min="1"
              :max="20"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.activeWeeksFirst4')">
            <el-input-number
              v-model="configForm.continuous.active_weeks_first4_min"
              :min="0"
              :max="4"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.activeWeeksLast4')">
            <el-input-number
              v-model="configForm.continuous.active_weeks_last4_min"
              :min="0"
              :max="4"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.maxZeroGapMax')">
            <el-input-number
              v-model="configForm.continuous.max_zero_gap_days_max"
              :min="1"
              :max="56"
              size="small"
            />
          </el-form-item>
        </el-form>
        <!-- 拒绝使用 -->
        <el-form
          v-else-if="modalStatCardType === 'rejection'"
          label-position="top"
          class="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          <el-form-item :label="t('teacher.analytics.form.activeDaysMax')">
            <el-input-number
              v-model="configForm.rejection.active_days_max"
              :min="0"
              :max="10"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.activeDaysFirst10')">
            <el-input-number
              v-model="configForm.rejection.active_days_first10_min"
              :min="0"
              :max="10"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.activeDaysLast25')">
            <el-input-number
              v-model="configForm.rejection.active_days_last25_max"
              :min="0"
              :max="25"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.maxZeroGapMinRej')">
            <el-input-number
              v-model="configForm.rejection.max_zero_gap_days_min"
              :min="1"
              :max="56"
              size="small"
            />
          </el-form-item>
        </el-form>
        <!-- 停止使用 -->
        <el-form
          v-else-if="modalStatCardType === 'stopped'"
          label-position="top"
          class="grid grid-cols-2 md:grid-cols-3 gap-3"
        >
          <el-form-item :label="t('teacher.analytics.form.activeDaysFirst25')">
            <el-input-number
              v-model="configForm.stopped.active_days_first25_min"
              :min="0"
              :max="25"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.activeDaysLast14')">
            <el-input-number
              v-model="configForm.stopped.active_days_last14_max"
              :min="0"
              :max="14"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.maxZeroGapMinStop')">
            <el-input-number
              v-model="configForm.stopped.max_zero_gap_days_min"
              :min="1"
              :max="56"
              size="small"
            />
          </el-form-item>
        </el-form>
        <!-- 间歇式使用 -->
        <el-form
          v-else-if="modalStatCardType === 'intermittent'"
          label-position="top"
          class="grid grid-cols-2 gap-3"
        >
          <el-form-item :label="t('teacher.analytics.form.nBursts')">
            <el-input-number
              v-model="configForm.intermittent.n_bursts_min"
              :min="1"
              :max="10"
              size="small"
            />
          </el-form-item>
          <el-form-item :label="t('teacher.analytics.form.internalMaxGap')">
            <el-input-number
              v-model="configForm.intermittent.internal_max_zero_gap_days_min"
              :min="1"
              :max="56"
              size="small"
            />
          </el-form-item>
        </el-form>
        <div
          v-if="modalStatCardType !== 'unused'"
          class="flex gap-2 mt-2"
        >
          <el-button
            size="small"
            :loading="isSavingConfig"
            @click="saveConfig"
          >
            {{ t('teacher.analytics.saveOnly') }}
          </el-button>
          <el-button
            size="small"
            :loading="isRecomputing"
            @click="recomputeClassifications"
          >
            {{ t('teacher.analytics.saveRecompute') }}
          </el-button>
        </div>
      </div>
      <el-table
        :data="modalTeachers"
        stripe
        size="small"
        max-height="400"
        class="teachers-table-clickable"
        @row-click="(row: Teacher) => openUserChart(row)"
      >
        <el-table-column
          prop="username"
          :label="t('teacher.analytics.colTeacher')"
          width="160"
        />
        <el-table-column
          prop="diagrams"
          :label="t('teacher.analytics.colAutocompleteCount')"
          width="90"
        />
        <el-table-column
          prop="conceptGen"
          :label="t('teacher.analytics.colConceptGen')"
          width="90"
        />
        <el-table-column
          prop="relationshipLabels"
          :label="t('teacher.analytics.colRelLabels')"
          width="90"
        />
        <el-table-column
          prop="tokens"
          :label="t('teacher.analytics.colTokens')"
          width="100"
        >
          <template #default="{ row }">
            {{ formatNumber(row.tokens) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="lastActive"
          :label="t('teacher.analytics.colLastActive')"
        />
      </el-table>
      <template #footer>
        <el-button
          type="primary"
          @click="showTeachersModal = false"
        >
          {{ t('common.close') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- User detail modal: chart (3 numbers) + token tracking cards -->
    <el-dialog
      v-model="showUserChartModal"
      :title="selectedUser ? selectedUser.username : ''"
      width="640px"
      append-to-body
      destroy-on-close
      @close="closeUserChartModal"
      @opened="onUserChartModalOpened"
    >
      <div
        v-if="userChartLoading"
        class="flex items-center justify-center py-12"
      >
        <el-icon
          class="is-loading"
          :size="24"
          ><Loading
        /></el-icon>
      </div>
      <template v-else>
        <div
          ref="userChartRef"
          class="user-chart-container mb-6"
        />
        <div
          v-if="userDetailData"
          class="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          <el-card
            shadow="hover"
            class="token-stat-card"
          >
            <p class="text-xs text-gray-500 mb-1">
              {{ t('common.date.today') }}
            </p>
            <p class="text-lg font-semibold">
              {{ formatNumber(userDetailData.tokenStats.today.total_tokens) }}
            </p>
          </el-card>
          <el-card
            shadow="hover"
            class="token-stat-card"
          >
            <p class="text-xs text-gray-500 mb-1">
              {{ t('teacher.analytics.periodWeek') }}
            </p>
            <p class="text-lg font-semibold">
              {{ formatNumber(userDetailData.tokenStats.week.total_tokens) }}
            </p>
          </el-card>
          <el-card
            shadow="hover"
            class="token-stat-card"
          >
            <p class="text-xs text-gray-500 mb-1">
              {{ t('teacher.analytics.periodMonth') }}
            </p>
            <p class="text-lg font-semibold">
              {{ formatNumber(userDetailData.tokenStats.month.total_tokens) }}
            </p>
          </el-card>
          <el-card
            shadow="hover"
            class="token-stat-card"
          >
            <p class="text-xs text-gray-500 mb-1">
              {{ t('teacher.analytics.periodTotal') }}
            </p>
            <p class="text-lg font-semibold">
              {{ formatNumber(userDetailData.tokenStats.total.total_tokens) }}
            </p>
          </el-card>
        </div>
      </template>
      <template #footer>
        <el-button
          type="primary"
          @click="closeUserChartModal"
        >
          {{ t('common.close') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.teacher-usage-page {
  min-height: 0;
}

.teacher-usage-content {
  min-height: 0;
}

.stat-card {
  min-width: 0;
}

.stat-card-clickable {
  cursor: pointer;
}

.stat-card-clickable:hover {
  background-color: rgb(250 250 249);
}

.teachers-table-clickable :deep(.el-table__row) {
  cursor: pointer;
}

.teachers-table-clickable :deep(.el-table__row:hover) {
  background-color: rgb(245 245 244) !important;
}

.teachers-list-table :deep(.el-table__row) {
  cursor: pointer;
}

.teachers-list-table :deep(.el-table__row:hover) {
  background-color: rgb(245 245 244) !important;
}

.user-chart-container {
  width: 100%;
  min-height: 256px;
  height: 256px;
}

:global(.dark) .stat-card-clickable:hover {
  background-color: rgb(41 37 36);
}

.group-card:hover {
  background-color: rgb(250 250 249);
}

:global(.dark) .group-card:hover {
  background-color: rgb(41 37 36);
}

.group-card-expanded:hover {
  background-color: transparent;
}

.group-card :deep(.el-card__body) {
  padding: 1rem 1.25rem;
}

.group-card-nested :deep(.el-card__body) {
  padding: 0.75rem 1rem;
}
</style>
