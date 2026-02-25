<script setup lang="ts">
/**
 * Teacher Usage Page (教师使用度)
 * Admin-only analytics dashboard for teacher engagement classification.
 * 2-tier: 未使用/持续使用/非持续使用 + 拒绝使用/停止使用/间歇式使用
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { ArrowDown, ArrowUp, Loading } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const { isZh } = useLanguage()
const notify = useNotifications()

interface GroupDefinition {
  id: string
  nameEn: string
  nameZh: string
  descriptionEn: string
  descriptionZh: string
}

const TOTAL_GROUP: GroupDefinition = {
  id: 'total',
  nameEn: 'Total Teachers',
  nameZh: '总教师数',
  descriptionEn: 'All teachers in the system.',
  descriptionZh: '系统中所有教师。',
}

const TOP_LEVEL_GROUPS: GroupDefinition[] = [
  {
    id: 'unused',
    nameEn: 'Unused',
    nameZh: '未使用',
    descriptionEn: 'No usage records within the observation window.',
    descriptionZh: '观察窗内完全无使用记录。',
  },
  {
    id: 'continuous',
    nameEn: 'Continuous Usage',
    nameZh: '持续使用',
    descriptionEn:
      'Used most of the time, active in both halves, short gaps.',
    descriptionZh: '大部分时间在用，前后半窗均有活跃，且最长断档相对短。',
  },
]

const SUB_GROUPS: GroupDefinition[] = [
  {
    id: 'rejection',
    nameEn: 'Rejection',
    nameZh: '拒绝使用',
    descriptionEn: 'Early trial then long-term non-use.',
    descriptionZh: '早期试用后长期不再使用。',
  },
  {
    id: 'stopped',
    nameEn: 'Stopped Usage',
    nameZh: '停止使用',
    descriptionEn: 'Stopped using after a period of use.',
    descriptionZh: '教师在经历一段时间使用后不再使用。',
  },
  {
    id: 'intermittent',
    nameEn: 'Intermittent Usage',
    nameZh: '间歇式使用',
    descriptionEn: 'Burst-silent intermittent cycles.',
    descriptionZh: '教师使用呈现"爆发式——沉寂式"的间歇循环。',
  },
]

const GROUPS = [...TOP_LEVEL_GROUPS, ...SUB_GROUPS]

interface Teacher {
  id: number
  username: string
  diagrams: number
  tokens: number
  lastActive: string
}

interface GroupStats {
  count: number
  totalTokens: number
  teachers: Teacher[]
  weeklyTokens?: number[]
}

type StatCardType =
  | 'total'
  | 'unused'
  | 'continuous'
  | 'rejection'
  | 'stopped'
  | 'intermittent'

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
const userChartWeeklyTokens = ref<number[]>([])
const userChartLoading = ref(false)
const userChartRef = ref<HTMLDivElement | null>(null)
let userChart: echarts.ECharts | null = null

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
  const titles: Record<StatCardType, { zh: string; en: string }> = {
    total: { zh: '总教师数', en: 'Total Teachers' },
    unused: { zh: '未使用', en: 'Unused' },
    continuous: { zh: '持续使用', en: 'Continuous Usage' },
    rejection: { zh: '拒绝使用', en: 'Rejection' },
    stopped: { zh: '停止使用', en: 'Stopped Usage' },
    intermittent: { zh: '间歇式使用', en: 'Intermittent Usage' },
  }
  const t = titles[type]
  return isZh.value ? t.zh : t.en
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
  userChartWeeklyTokens.value = []
  showUserChartModal.value = true
  userChartLoading.value = true
  try {
    const response = await apiRequest(`auth/admin/teacher-usage/user/${row.id}/weekly-tokens`)
    if (response.ok) {
      const data = await response.json()
      userChartWeeklyTokens.value = data.weeklyTokens ?? []
    }
  } catch (error) {
    console.error('Failed to load user tokens:', error)
    notify.error(isZh.value ? '加载失败' : 'Load failed')
  } finally {
    userChartLoading.value = false
  }
}

function initUserChart() {
  if (!userChartRef.value || !showUserChartModal.value) return
  userChart?.dispose()
  userChart = echarts.init(userChartRef.value)
  const weeks = userChartWeeklyTokens.value.map((_, i) => `W${i + 1}`)
  userChart.setOption({
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: number) => formatNumber(value),
    },
    xAxis: { type: 'category', data: weeks.length ? weeks : ['-'] },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (value: number) => formatNumber(value) },
    },
    series: [
      {
        type: 'line',
        data: userChartWeeklyTokens.value.length ? userChartWeeklyTokens.value : [0],
        smooth: true,
      },
    ],
  })
}

function closeUserChartModal() {
  showUserChartModal.value = false
  userChart?.dispose()
  userChart = null
  selectedUser.value = null
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
      notify.error(data.detail || (isZh.value ? '保存失败' : 'Save failed'))
      return
    }
    notify.success(isZh.value ? '配置已保存' : 'Config saved')
    await loadTeacherUsage()
  } catch (error) {
    console.error('Failed to save config:', error)
    notify.error(isZh.value ? '保存失败' : 'Save failed')
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
      notify.error(isZh.value ? '保存失败' : 'Save failed')
      return
    }
    const recomputeRes = await apiRequest('auth/admin/teacher-usage/recompute', {
      method: 'POST',
    })
    if (!recomputeRes.ok) {
      const data = await recomputeRes.json().catch(() => ({}))
      notify.error(data.detail || (isZh.value ? '重算失败' : 'Recompute failed'))
      return
    }
    const data = await recomputeRes.json()
    notify.success(
      isZh.value
        ? `已保存并重算 ${data.recomputed} 位教师`
        : `Saved and recomputed ${data.recomputed} teachers`
    )
    await loadTeacherUsage()
  } catch (error) {
    console.error('Failed to recompute:', error)
    notify.error(isZh.value ? '重算失败' : 'Recompute failed')
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

let pieChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null
const groupCharts: Record<string, echarts.ECharts | null> = {}

async function loadTeacherUsage() {
  isLoading.value = true
  try {
    const response = await apiRequest('auth/admin/teacher-usage')
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      notify.error(
        data.detail ||
          (isZh.value ? '加载教师使用度数据失败' : 'Failed to load teacher usage data')
      )
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
      ...GROUPS.map((gr) => (groupStats.value[gr.id]?.weeklyTokens?.length ?? 0))
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
    notify.error(
      isZh.value ? '网络错误，加载教师使用度失败' : 'Network error, failed to load teacher usage'
    )
  } finally {
    isLoading.value = false
  }
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function initPieChart() {
  if (!pieChartRef.value) return
  pieChart = echarts.init(pieChartRef.value)
  const data = GROUPS.map((g, i) => ({
    name: isZh.value ? g.nameZh : g.nameEn,
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
  const xData = GROUPS.map((g) => (isZh.value ? g.nameZh : g.nameEn))
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

watch(isZh, () => {
  initPieChart()
  initBarChart()
})

watch(
  [userChartWeeklyTokens, userChartLoading],
  async ([, loading]) => {
    if (!loading && showUserChartModal.value) {
      await nextTick()
      setTimeout(() => {
        if (userChartRef.value) {
          initUserChart()
          userChart?.resize()
        }
      }, 150)
    }
  },
)

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
    <div class="teacher-usage-header h-14 px-4 flex items-center justify-between bg-white border-b border-stone-200">
      <h1 class="text-sm font-semibold text-stone-900">
        {{ isZh ? '教师使用度' : 'Teacher Usage' }}
      </h1>
      <el-button
        size="small"
        :loading="isLoading"
        @click="loadTeacherUsage"
      >
        {{ isZh ? '刷新' : 'Refresh' }}
      </el-button>
    </div>

    <!-- Scrollable content -->
    <div class="teacher-usage-content flex-1 overflow-y-auto px-6 pt-6 pb-6">
      <div
        v-if="isLoading"
        class="flex items-center justify-center py-20"
      >
        <el-icon
          class="is-loading"
          :size="32"
        ><Loading /></el-icon>
      </div>

      <template v-else>
      <div class="max-w-7xl mx-auto">
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <el-card
          shadow="hover"
          class="stat-card stat-card-clickable"
          @click="openTeachersModal('total')"
        >
          <p class="text-xs text-gray-500 mb-1">
            {{ isZh ? '总教师数' : 'Total Teachers' }}
          </p>
          <p class="text-2xl font-bold text-gray-800 dark:text-white">
            {{ stats.totalTeachers.toLocaleString() }}
          </p>
        </el-card>
        <el-card
          shadow="hover"
          class="stat-card stat-card-clickable"
          @click="openTeachersModal('unused')"
        >
          <p class="text-xs text-gray-500 mb-1">
            {{ isZh ? '未使用' : 'Unused' }}
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
            {{ isZh ? '持续使用' : 'Continuous Usage' }}
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
            {{ isZh ? '拒绝使用' : 'Rejection' }}
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
            {{ isZh ? '停止使用' : 'Stopped Usage' }}
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
            {{ isZh ? '间歇式使用' : 'Intermittent Usage' }}
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
              {{ isZh ? '教师分组分布' : 'Group Distribution' }}
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
              {{ isZh ? '各组 Token 使用量' : 'Token Usage by Group' }}
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
                {{ isZh ? TOTAL_GROUP.nameZh : TOTAL_GROUP.nameEn }}
              </span>
              <div class="text-xs text-stone-500 mt-0.5">
                {{ isZh ? TOTAL_GROUP.descriptionZh : TOTAL_GROUP.descriptionEn }}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <el-tag size="small">
                {{ groupStats.total?.count ?? 0 }}
                {{ isZh ? '位教师' : ' teachers' }}
              </el-tag>
              <el-icon :size="18" class="text-stone-400">
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
                    :label="isZh ? '教师' : 'Teacher'"
                    width="140"
                  />
                  <el-table-column
                    prop="diagrams"
                    :label="isZh ? '智能补全次数' : 'Auto-complete Count'"
                    width="80"
                  />
                  <el-table-column
                    prop="tokens"
                    :label="isZh ? 'Token' : 'Tokens'"
                    width="100"
                  >
                    <template #default="{ row }">
                      {{ formatNumber(row.tokens) }}
                    </template>
                  </el-table-column>
                  <el-table-column
                    prop="lastActive"
                    :label="isZh ? '最后活跃' : 'Last Active'"
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
                {{ isZh ? group.nameZh : group.nameEn }}
              </span>
              <div class="text-xs text-stone-500 mt-0.5">
                {{ isZh ? group.descriptionZh : group.descriptionEn }}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <el-tag size="small">
                {{ groupStats[group.id]?.count ?? 0 }}
                {{ isZh ? '位教师' : ' teachers' }}
              </el-tag>
              <el-icon :size="18" class="text-stone-400">
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
                    :label="isZh ? '教师' : 'Teacher'"
                    width="140"
                  />
                  <el-table-column
                    prop="diagrams"
                    :label="isZh ? '智能补全次数' : 'Auto-complete Count'"
                    width="80"
                  />
                  <el-table-column
                    prop="tokens"
                    :label="isZh ? 'Token' : 'Tokens'"
                    width="100"
                  >
                    <template #default="{ row }">
                      {{ formatNumber(row.tokens) }}
                    </template>
                  </el-table-column>
                  <el-table-column
                    prop="lastActive"
                    :label="isZh ? '最后活跃' : 'Last Active'"
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
        <div class="sub-groups-box rounded-lg border-2 border-stone-300 bg-stone-100/50 p-4 dark:border-stone-600 dark:bg-stone-800/30">
          <div class="text-sm font-semibold text-stone-700 dark:text-stone-300 mb-4">
            {{ isZh ? '非持续使用' : 'Non-continuous Usage' }}
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
                    {{ isZh ? group.nameZh : group.nameEn }}
                  </span>
                  <div class="text-xs text-stone-500 mt-0.5">
                    {{ isZh ? group.descriptionZh : group.descriptionEn }}
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <el-tag size="small">
                    {{ groupStats[group.id]?.count ?? 0 }}
                    {{ isZh ? '位教师' : ' teachers' }}
                  </el-tag>
                  <el-icon :size="18" class="text-stone-400">
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
                        :label="isZh ? '教师' : 'Teacher'"
                        width="140"
                      />
                      <el-table-column
                        prop="diagrams"
                        :label="isZh ? '智能补全次数' : 'Auto-complete Count'"
                        width="80"
                      />
                      <el-table-column
                        prop="tokens"
                        :label="isZh ? 'Token' : 'Tokens'"
                        width="100"
                      >
                        <template #default="{ row }">
                          {{ formatNumber(row.tokens) }}
                        </template>
                      </el-table-column>
                      <el-table-column
                        prop="lastActive"
                        :label="isZh ? '最后活跃' : 'Last Active'"
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
      </template>
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
          {{ isZh ? '操作判定规则' : 'Operation Judgment Rules' }}
        </h4>
        <!-- 未使用: active_days = 0 (fixed, read-only) -->
        <div v-if="modalStatCardType === 'unused'" class="text-sm text-stone-600">
          <code class="bg-stone-100 px-2 py-1 rounded">{{ isZh ? '活跃日数 = 0' : 'active_days = 0' }}</code>
          <span class="ml-2">{{ isZh ? '（观察窗内完全无使用记录）' : '(No usage within observation window)' }}</span>
        </div>
        <!-- 持续使用 -->
        <el-form
          v-else-if="modalStatCardType === 'continuous'"
          label-position="top"
          class="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          <el-form-item :label="isZh ? '活跃周数 ≥' : 'active_weeks ≥'">
            <el-input-number v-model="configForm.continuous.active_weeks_min" :min="1" :max="20" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '前4周活跃周数 ≥' : 'active_weeks_first4 ≥'">
            <el-input-number v-model="configForm.continuous.active_weeks_first4_min" :min="0" :max="4" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '后4周活跃周数 ≥' : 'active_weeks_last4 ≥'">
            <el-input-number v-model="configForm.continuous.active_weeks_last4_min" :min="0" :max="4" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '最长断档天数 ≤' : 'max_zero_gap_days ≤'">
            <el-input-number v-model="configForm.continuous.max_zero_gap_days_max" :min="1" :max="56" size="small" />
          </el-form-item>
        </el-form>
        <!-- 拒绝使用 -->
        <el-form
          v-else-if="modalStatCardType === 'rejection'"
          label-position="top"
          class="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          <el-form-item :label="isZh ? '活跃日数 ≤' : 'active_days ≤'">
            <el-input-number v-model="configForm.rejection.active_days_max" :min="0" :max="10" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '前10天活跃日数 ≥' : 'active_days_first10 ≥'">
            <el-input-number v-model="configForm.rejection.active_days_first10_min" :min="0" :max="10" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '后25天活跃日数 =' : 'active_days_last25 ='">
            <el-input-number v-model="configForm.rejection.active_days_last25_max" :min="0" :max="25" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '最长断档天数 ≥' : 'max_zero_gap_days ≥'">
            <el-input-number v-model="configForm.rejection.max_zero_gap_days_min" :min="1" :max="56" size="small" />
          </el-form-item>
        </el-form>
        <!-- 停止使用 -->
        <el-form
          v-else-if="modalStatCardType === 'stopped'"
          label-position="top"
          class="grid grid-cols-2 md:grid-cols-3 gap-3"
        >
          <el-form-item :label="isZh ? '前25天活跃日数 ≥' : 'active_days_first25 ≥'">
            <el-input-number v-model="configForm.stopped.active_days_first25_min" :min="0" :max="25" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '后14天活跃日数 =' : 'active_days_last14 ='">
            <el-input-number v-model="configForm.stopped.active_days_last14_max" :min="0" :max="14" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '最长断档天数 ≥' : 'max_zero_gap_days ≥'">
            <el-input-number v-model="configForm.stopped.max_zero_gap_days_min" :min="1" :max="56" size="small" />
          </el-form-item>
        </el-form>
        <!-- 间歇式使用 -->
        <el-form
          v-else-if="modalStatCardType === 'intermittent'"
          label-position="top"
          class="grid grid-cols-2 gap-3"
        >
          <el-form-item :label="isZh ? '活跃段数 ≥' : 'n_bursts ≥'">
            <el-input-number v-model="configForm.intermittent.n_bursts_min" :min="1" :max="10" size="small" />
          </el-form-item>
          <el-form-item :label="isZh ? '内部最大沉寂断档 ≥' : 'internal_max_zero_gap_days ≥'">
            <el-input-number v-model="configForm.intermittent.internal_max_zero_gap_days_min" :min="1" :max="56" size="small" />
          </el-form-item>
        </el-form>
        <div v-if="modalStatCardType !== 'unused'" class="flex gap-2 mt-2">
          <el-button size="small" :loading="isSavingConfig" @click="saveConfig">
            {{ isZh ? '仅保存' : 'Save Only' }}
          </el-button>
          <el-button size="small" :loading="isRecomputing" @click="recomputeClassifications">
            {{ isZh ? '保存并重算' : 'Save & Recompute' }}
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
          :label="isZh ? '教师' : 'Teacher'"
          width="160"
        />
        <el-table-column
          prop="diagrams"
          :label="isZh ? '智能补全次数' : 'Auto-complete Count'"
          width="90"
        />
        <el-table-column
          prop="tokens"
          :label="isZh ? 'Token' : 'Tokens'"
          width="100"
        >
          <template #default="{ row }">
            {{ formatNumber(row.tokens) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="lastActive"
          :label="isZh ? '最后活跃' : 'Last Active'"
        />
      </el-table>
      <template #footer>
        <el-button
          type="primary"
          @click="showTeachersModal = false"
        >
          {{ isZh ? '关闭' : 'Close' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- User token usage chart modal -->
    <el-dialog
      v-model="showUserChartModal"
      :title="selectedUser ? selectedUser.username : ''"
      width="600px"
      append-to-body
      destroy-on-close
      @close="closeUserChartModal"
      @opened="onUserChartModalOpened"
    >
      <div
        v-if="userChartLoading"
        class="flex items-center justify-center py-12"
      >
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div
        v-else
        ref="userChartRef"
        class="user-chart-container"
      />
      <template #footer>
        <el-button type="primary" @click="closeUserChartModal">
          {{ isZh ? '关闭' : 'Close' }}
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
