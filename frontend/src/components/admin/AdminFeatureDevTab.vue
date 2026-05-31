<script setup lang="ts">
/**
 * 新功能开发 — experimental feature tools.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AdminKittyLlmopsTab from '@/components/admin/AdminKittyLlmopsTab.vue'
import SmartResponsePanel from '@/components/admin/SmartResponsePanel.vue'
import TeacherUsagePanel from '@/components/admin/TeacherUsagePanel.vue'
import {
  resolveFeatureDevSubtab,
  type FeatureDevSubtab,
  visibleFeatureDevSubtabs,
} from '@/composables/admin/adminFeatureDevNav'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'

const route = useRoute()
const router = useRouter()
const { canViewSettingsSubtab } = useAdminAccess()
const { featureSmartResponse, featureTeacherUsage, featureKittyAgent } = useFeatureFlags()

const visibilityOptions = computed(() => ({
  canViewSettingsSubtab,
  featureSmartResponse: featureSmartResponse.value,
  featureTeacherUsage: featureTeacherUsage.value,
  featureKittyAgent: featureKittyAgent.value,
}))

const activeSubtab = ref<FeatureDevSubtab | null>(
  resolveFeatureDevSubtab(route.query.subtab as string, visibilityOptions.value)
)

const allowedSubtabs = computed(() => visibleFeatureDevSubtabs(visibilityOptions.value))

watch(
  () => route.query.subtab,
  (sub) => {
    activeSubtab.value = resolveFeatureDevSubtab(sub as string, visibilityOptions.value)
  }
)

watch(activeSubtab, (sub) => {
  if (!sub) {
    return
  }
  const current = route.query.subtab as string
  if (sub !== current) {
    router.replace({ query: { ...route.query, tab: 'feature_dev', subtab: sub } })
  }
})

watch(
  allowedSubtabs,
  (names) => {
    if (names.length === 0) {
      activeSubtab.value = null
      return
    }
    if (!activeSubtab.value || !names.includes(activeSubtab.value)) {
      activeSubtab.value = names[0]
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="embedded-feature-dev-body">
    <AdminKittyLlmopsTab v-if="activeSubtab === 'kitty_llmops'" />
    <SmartResponsePanel v-else-if="activeSubtab === 'smart_response'" />
    <TeacherUsagePanel v-else-if="activeSubtab === 'teacher_usage'" />
  </div>
</template>

<style scoped>
.embedded-feature-dev-body :deep(.smart-response-page),
.embedded-feature-dev-body :deep(.teacher-usage-page) {
  padding: 0;
}
</style>
