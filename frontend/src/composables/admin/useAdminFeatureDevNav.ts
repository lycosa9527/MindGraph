/**
 * Sidebar state and navigation for 新功能开发 (top-level panel tab).
 */
import type { ComputedRef, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  defaultFeatureDevSubtab,
  resolveFeatureDevSubtab,
  type FeatureDevSubtab,
  visibleFeatureDevNavItems,
} from '@/composables/admin/adminFeatureDevNav'

export interface FeatureDevNavLeafItemView {
  kind: 'leaf'
  name: FeatureDevSubtab
  labelKey: string
  label: string
}

export function useAdminFeatureDevNav(options: {
  t: (key: string) => string
  canViewSettingsSubtab: (subtab: string) => boolean
  featureSmartResponse: Ref<boolean>
  featureTeacherUsage: Ref<boolean>
  featureKittyAgent: Ref<boolean>
  currentAdminTab: ComputedRef<string | null>
}) {
  const router = useRouter()
  const route = useRoute()
  const featureDevNavExpanded = ref(false)

  const visibilityOptions = computed(() => ({
    canViewSettingsSubtab: options.canViewSettingsSubtab,
    featureSmartResponse: options.featureSmartResponse.value,
    featureTeacherUsage: options.featureTeacherUsage.value,
    featureKittyAgent: options.featureKittyAgent.value,
  }))

  const currentFeatureDevSubtab = computed((): FeatureDevSubtab | null => {
    if (options.currentAdminTab.value !== 'feature_dev') {
      return null
    }
    return resolveFeatureDevSubtab(route.query.subtab as string, visibilityOptions.value)
  })

  const featureDevNavItems = computed((): FeatureDevNavLeafItemView[] => {
    return visibleFeatureDevNavItems(visibilityOptions.value).map((item) => ({
      ...item,
      label: options.t(item.labelKey),
    }))
  })

  const visibleSubtabNames = computed(() => featureDevNavItems.value.map((item) => item.name))

  function navigateFeatureDevSubtab(subtab: FeatureDevSubtab): void {
    const query: Record<string, string> = {
      ...route.query,
      tab: 'feature_dev',
      subtab,
    }
    delete query.view
    void router.push({ path: '/admin', query })
  }

  function toggleFeatureDevNav(): void {
    const first = defaultFeatureDevSubtab(visibilityOptions.value)
    if (!first) {
      return
    }
    if (options.currentAdminTab.value === 'feature_dev') {
      featureDevNavExpanded.value = !featureDevNavExpanded.value
      return
    }
    featureDevNavExpanded.value = true
    navigateFeatureDevSubtab(first)
  }

  function featureDevSubItemClass(subtab: FeatureDevSubtab) {
    return {
      'is-active': currentFeatureDevSubtab.value === subtab,
    }
  }

  watch(
    visibleSubtabNames,
    (names) => {
      const current = currentFeatureDevSubtab.value
      if (current != null && names.length > 0 && !names.includes(current)) {
        navigateFeatureDevSubtab(names[0])
      }
    },
    { immediate: true }
  )

  return {
    featureDevNavExpanded,
    currentFeatureDevSubtab,
    featureDevNavItems,
    navigateFeatureDevSubtab,
    toggleFeatureDevNav,
    featureDevSubItemClass,
    visibilityOptions,
  }
}
