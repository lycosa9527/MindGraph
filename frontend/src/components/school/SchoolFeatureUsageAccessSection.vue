<script setup lang="ts">
import AdminSwissModuleStatCard from '@/components/admin/swiss/AdminSwissModuleStatCard.vue'
import type { SchoolFeatureUsageModule } from '@/composables/queries/adminSchoolFeatureUsageApi'
import { moduleUsageTheme } from '@/utils/schoolFeatureUsageTheme'

const props = defineProps<{
  modules: SchoolFeatureUsageModule[]
  timestamp: string
}>()

function opsLabel(value: number): string {
  return value.toFixed(1)
}
</script>

<template>
  <section class="school-activity-section">
    <h2 class="school-activity-section__title">
      <I18nText k="admin.schoolFeatureUsage.sectionAccess" />
    </h2>
    <div class="school-activity-section__grid">
      <AdminSwissModuleStatCard
        v-for="row in props.modules"
        :key="row.key"
        :title-key="`admin.schoolFeatureUsage.module.${row.key}`"
        :value="row.visits"
        value-label-key="admin.schoolFeatureUsage.visits"
        :timestamp="props.timestamp"
        :theme="moduleUsageTheme(row.key)"
        :chips="[
          { labelKey: 'admin.schoolFeatureUsage.uses', value: row.uses.toLocaleString() },
          { labelKey: 'admin.schoolFeatureUsage.ops', value: opsLabel(row.ops_per_visitor) },
        ]"
        :remark-key="`admin.schoolFeatureUsage.remark.${row.key}`"
        show-chart
        :labels="row.monthly_uses.map((point) => point.date)"
        :values="row.monthly_uses.map((point) => point.value)"
      />
    </div>
  </section>
</template>
