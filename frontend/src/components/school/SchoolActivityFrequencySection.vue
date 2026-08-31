<script setup lang="ts">
import { computed } from 'vue'

import { Clock, Histogram, User } from '@element-plus/icons-vue'

import AdminSwissChartCard from '@/components/admin/swiss/AdminSwissChartCard.vue'
import type { SchoolUserActivityFrequency } from '@/composables/queries/adminSchoolUserActivityApi'
import { useLanguage } from '@/composables'

const props = defineProps<{
  frequency: SchoolUserActivityFrequency
  timestamp: string
}>()

const { t } = useLanguage()

const roster = computed(() =>
  props.frequency.login_count_buckets.reduce((sum, bucket) => sum + bucket.value, 0)
)

const highRest = computed(() => Math.max(roster.value - props.frequency.high_freq_count, 0))
const lowRest = computed(() => Math.max(roster.value - props.frequency.low_freq_count, 0))

function oneDecimal(value: number): string {
  return value.toFixed(1)
}
</script>

<template>
  <section class="school-activity-section">
    <h2 class="school-activity-section__title">
      {{ t('admin.schoolActivity.sectionFrequency') }}
    </h2>
    <div class="school-activity-section__grid">
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.loginFrequency')"
        :value="roster"
        :timestamp="props.timestamp"
        theme="members"
        :icon="Histogram"
        chart-kind="bar"
        :labels="props.frequency.login_count_buckets.map((bucket) => bucket.label)"
        :values="props.frequency.login_count_buckets.map((bucket) => bucket.value)"
      />
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.highFreq')"
        :value="t('admin.schoolActivity.countWithShare', {
          count: props.frequency.high_freq_count,
          share: oneDecimal(props.frequency.high_freq_share),
        })"
        :timestamp="props.timestamp"
        theme="success"
        :icon="User"
        chart-kind="bar"
        :labels="[
          t('admin.schoolActivity.highFreq'),
          t('admin.schoolActivity.otherUsers'),
        ]"
        :values="[props.frequency.high_freq_count, highRest]"
      />
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.lowFreq')"
        :value="t('admin.schoolActivity.countWithShare', {
          count: props.frequency.low_freq_count,
          share: oneDecimal(props.frequency.low_freq_share),
        })"
        :timestamp="props.timestamp"
        theme="warn"
        :icon="User"
        chart-kind="bar"
        :labels="[
          t('admin.schoolActivity.lowFreq'),
          t('admin.schoolActivity.otherUsers'),
        ]"
        :values="[props.frequency.low_freq_count, lowRest]"
      />
      <AdminSwissChartCard
        :title="t('admin.schoolActivity.hourDistribution')"
        :value="props.frequency.hour_of_day.reduce((sum, point) => sum + point.value, 0)"
        :timestamp="props.timestamp"
        theme="storage"
        :icon="Clock"
        chart-kind="bar"
        :labels="props.frequency.hour_of_day.map((point) => String(point.hour))"
        :values="props.frequency.hour_of_day.map((point) => point.value)"
      />
    </div>
  </section>
</template>
