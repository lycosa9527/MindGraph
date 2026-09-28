<script setup lang="ts">
import { TrendCharts, User, UserFilled } from '@element-plus/icons-vue'

import AdminSwissChartCard from '@/components/admin/swiss/AdminSwissChartCard.vue'
import type { SchoolUserActivityTotals } from '@/composables/queries/adminSchoolUserActivityApi'

const props = defineProps<{
  totals: SchoolUserActivityTotals
  timestamp: string
}>()

function seriesLabels(points: { date: string }[]): string[] {
  return points.map((point) => point.date)
}

function seriesValues(points: { value: number }[]): number[] {
  return points.map((point) => point.value)
}
</script>

<template>
  <section class="school-activity-section">
    <h2 class="school-activity-section__title">
      <I18nText k="admin.schoolActivity.sectionTotals" />
    </h2>
    <div class="school-activity-section__grid">
      <AdminSwissChartCard
        title-key="admin.schoolActivity.cumulativeRegistered"
        :value="props.totals.cumulative_registered"
        :timestamp="props.timestamp"
        theme="members"
        :icon="User"
        chart-kind="line"
        :labels="seriesLabels(props.totals.cumulative_series)"
        :values="seriesValues(props.totals.cumulative_series)"
      />
      <AdminSwissChartCard
        title-key="admin.schoolActivity.yearNewUsers"
        :value="props.totals.year_new_users"
        :timestamp="props.timestamp"
        theme="success"
        :icon="TrendCharts"
        chart-kind="bar"
        :labels="seriesLabels(props.totals.year_new_series)"
        :values="seriesValues(props.totals.year_new_series)"
      />
      <AdminSwissChartCard
        title-key="admin.schoolActivity.yearChurn"
        value="—"
        :timestamp="props.timestamp"
        theme="warn"
        empty
        empty-text-key="admin.schoolActivity.churnEmpty"
      />
      <AdminSwissChartCard
        title-key="admin.schoolActivity.enrolledToday"
        :value="props.totals.enrolled_today"
        :timestamp="props.timestamp"
        theme="platform"
        :icon="UserFilled"
        chart-kind="line"
        :labels="seriesLabels(props.totals.enrolled_series)"
        :values="seriesValues(props.totals.enrolled_series)"
      />
    </div>
  </section>
</template>
