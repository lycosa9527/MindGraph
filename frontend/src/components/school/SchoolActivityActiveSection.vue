<script setup lang="ts">
import { Calendar, DataLine } from '@element-plus/icons-vue'

import AdminSwissChartCard from '@/components/admin/swiss/AdminSwissChartCard.vue'
import type { SchoolUserActivityActive } from '@/composables/queries/adminSchoolUserActivityApi'
import { useLanguage } from '@/composables'
import { beijingCalendarParts } from '@/utils/schoolActivityAsOf'

const props = defineProps<{
  activity: SchoolUserActivityActive
  timestamp: string
}>()

const { t } = useLanguage()

function seriesLabels(points: { date: string }[]): string[] {
  return points.map((point) => point.date)
}

function seriesValues(points: { value: number }[]): number[] {
  return points.map((point) => point.value)
}

function oneDecimal(value: number): string {
  return value.toFixed(1)
}

function latestElapsedValue(points: { date: string; value: number }[]): number {
  if (points.length === 0) {
    return 0
  }
  const { year, month } = beijingCalendarParts()
  const monthKey = `${year}-${String(month).padStart(2, '0')}`
  const quarterKey = `${year}-Q${Math.floor((month - 1) / 3) + 1}`
  const cutoff = points[0].date.includes('Q') ? quarterKey : monthKey
  const elapsed = points.filter((point) => point.date <= cutoff)
  return (elapsed[elapsed.length - 1] ?? points[0]).value
}
</script>

<template>
  <section class="school-activity-section">
    <h2 class="school-activity-section__title">
      {{ t('admin.schoolActivity.sectionActive') }}
    </h2>
    <div class="school-activity-section__grid">
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.monthlyActive')"
        :value="latestElapsedValue(props.activity.monthly_active)"
        :timestamp="props.timestamp"
        theme="members"
        :icon="Calendar"
        chart-kind="bar"
        :labels="seriesLabels(props.activity.monthly_active)"
        :values="seriesValues(props.activity.monthly_active)"
      />
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.quarterlyActive')"
        :value="latestElapsedValue(props.activity.quarterly_active)"
        :timestamp="props.timestamp"
        theme="managers"
        :icon="Calendar"
        chart-kind="bar"
        :labels="seriesLabels(props.activity.quarterly_active)"
        :values="seriesValues(props.activity.quarterly_active)"
      />
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.avgDailyActive')"
        :value="oneDecimal(props.activity.avg_daily_active)"
        :timestamp="props.timestamp"
        theme="success"
        :icon="DataLine"
        chart-kind="line"
        :labels="seriesLabels(props.activity.daily_active)"
        :values="seriesValues(props.activity.daily_active)"
      />
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.avgMonthlyActive')"
        :value="oneDecimal(props.activity.avg_monthly_active)"
        :timestamp="props.timestamp"
        theme="storage"
        :icon="DataLine"
        chart-kind="bar"
        :labels="seriesLabels(props.activity.monthly_active)"
        :values="seriesValues(props.activity.monthly_active)"
      />
    </div>
  </section>
</template>
