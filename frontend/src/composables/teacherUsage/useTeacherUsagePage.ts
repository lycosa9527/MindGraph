/**
 * Teacher usage analytics: state, charts, modals, and API.
 */
import type { InjectionKey } from 'vue'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  GROUPS,
  type GroupStats,
  SUB_GROUPS,
  type StatCardType,
  TOP_LEVEL_GROUPS,
  type Teacher,
  type UserDetailData,
} from '@/composables/teacherUsage/teacherUsageTypes'
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

export function useTeacherUsagePage() {
  const { t, currentLanguage } = useLanguage()
  const uiStore = useUIStore()
  const notify = useNotifications()

  function teacherGroupName(groupId: string): string {
    return t(`teacher.analytics.group.${groupId}.name`)
  }

  function teacherGroupDescription(groupId: string): string {
    return t(`teacher.analytics.group.${groupId}.description`)
  }

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

  const userDetailData = ref<UserDetailData | null>(null)

  const groupStats = ref<Record<string, GroupStats>>({})

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
          for (const teacher of gs.teachers) {
            if (!seen.has(teacher.id)) {
              seen.add(teacher.id)
              allTeachers.push(teacher)
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
    const data = GROUPS.map((g) => ({
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

  return {
    t,
    uiStore,
    TOP_LEVEL_GROUPS,
    SUB_GROUPS,
    teacherGroupName,
    teacherGroupDescription,
    expandedGroupIds,
    configForm,
    isSavingConfig,
    isRecomputing,
    toggleGroupExpanded,
    isGroupExpanded,
    showTeachersModal,
    modalTeachers,
    modalTitle,
    modalStatCardType,
    showUserChartModal,
    selectedUser,
    userChartLoading,
    userChartRef,
    activeTab,
    allUsers,
    allUsersLoading,
    usersTotal,
    usersPage,
    usersPageSize,
    userDetailData,
    groupStats,
    openTeachersModal,
    openUserChart,
    loadTeacherUsage,
    loadAllUsers,
    onUsersPageChange,
    openUserDetailFromList,
    closeUserChartModal,
    onUserChartModalOpened,
    saveConfig,
    recomputeClassifications,
    isLoading,
    pieChartRef,
    barChartRef,
    groupChartRefs,
    stats,
    formatNumber,
  }
}

export type TeacherUsagePageContext = ReturnType<typeof useTeacherUsagePage>

export const teacherUsageInjectionKey: InjectionKey<TeacherUsagePageContext> =
  Symbol('teacherUsage')
