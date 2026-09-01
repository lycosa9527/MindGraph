<script setup lang="ts">
import AdminSwissModuleStatCard from '@/components/admin/swiss/AdminSwissModuleStatCard.vue'
import type { SchoolFeatureUsageModule } from '@/composables/queries/adminSchoolFeatureUsageApi'
import { useLanguage } from '@/composables'
import { moduleUsageTheme } from '@/utils/schoolFeatureUsageTheme'

const props = defineProps<{
  modules: SchoolFeatureUsageModule[]
  timestamp: string
}>()

const { t } = useLanguage()

function moduleTitle(key: string): string {
  return t(`admin.schoolFeatureUsage.module.${key}`)
}

function moduleRemark(key: string): string {
  return t(`admin.schoolFeatureUsage.remark.${key}`)
}

function opsLabel(value: number): string {
  return value.toFixed(1)
}
</script>

<template>
  <section class="school-activity-section">
    <h2 class="school-activity-section__title">
      {{ t('admin.schoolFeatureUsage.sectionAccess') }}
    </h2>
    <div class="school-activity-section__grid">
      <AdminSwissModuleStatCard
        v-for="row in props.modules"
        :key="row.key"
        :title="moduleTitle(row.key)"
        :value="row.visits"
        :value-label="t('admin.schoolFeatureUsage.visits')"
        :timestamp="props.timestamp"
        :theme="moduleUsageTheme(row.key)"
        :chips="[
          { label: t('admin.schoolFeatureUsage.uses'), value: row.uses.toLocaleString() },
          { label: t('admin.schoolFeatureUsage.ops'), value: opsLabel(row.ops_per_visitor) },
        ]"
        :remark="moduleRemark(row.key)"
        show-chart
        :labels="row.monthly_uses.map((point) => point.date)"
        :values="row.monthly_uses.map((point) => point.value)"
      />
    </div>
  </section>
</template>
