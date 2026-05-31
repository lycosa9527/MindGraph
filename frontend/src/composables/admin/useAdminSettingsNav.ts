/**
 * Sidebar state and navigation for 系统设置 (top-level panel tab).
 */
import type { ComputedRef, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  defaultSettingsSubtab,
  isSettingsSubtab,
  type SettingsSubtab,
  visibleSettingsNavItems,
} from '@/composables/admin/adminSettingsNav'

export interface SettingsNavLeafItemView {
  kind: 'leaf'
  name: SettingsSubtab
  labelKey: string
  label: string
}

export function useAdminSettingsNav(options: {
  t: (key: string) => string
  canViewSettingsSubtab: (subtab: string) => boolean
  featureGewe: Ref<boolean>
  featureLibrary: Ref<boolean>
  currentAdminTab: ComputedRef<string | null>
}) {
  const router = useRouter()
  const route = useRoute()
  const settingsNavExpanded = ref(false)

  const currentSettingsSubtab = computed((): SettingsSubtab | null => {
    if (options.currentAdminTab.value !== 'settings') {
      return null
    }
    const raw = route.query.subtab
    if (typeof raw === 'string' && isSettingsSubtab(raw)) {
      return raw
    }
    return defaultSettingsSubtab()
  })

  const settingsNavItems = computed((): SettingsNavLeafItemView[] => {
    return visibleSettingsNavItems({
      canViewSettingsSubtab: options.canViewSettingsSubtab,
      featureGewe: options.featureGewe.value,
      featureLibrary: options.featureLibrary.value,
    }).map((item) => ({
      ...item,
      label: options.t(item.labelKey),
    }))
  })

  const visibleSubtabNames = computed(() => settingsNavItems.value.map((item) => item.name))

  function navigateSettingsSubtab(subtab: SettingsSubtab): void {
    const query: Record<string, string> = {
      ...route.query,
      tab: 'settings',
      subtab,
    }
    delete query.view
    void router.push({ path: '/admin', query })
  }

  function toggleSettingsNav(): void {
    if (options.currentAdminTab.value === 'settings') {
      settingsNavExpanded.value = !settingsNavExpanded.value
      return
    }
    settingsNavExpanded.value = true
    navigateSettingsSubtab(defaultSettingsSubtab())
  }

  function settingsSubItemClass(subtab: SettingsSubtab) {
    return {
      'is-active': currentSettingsSubtab.value === subtab,
    }
  }

  watch(
    visibleSubtabNames,
    (names) => {
      const current = currentSettingsSubtab.value
      if (current != null && names.length > 0 && !names.includes(current)) {
        navigateSettingsSubtab(names[0])
      }
    },
    { immediate: true }
  )

  return {
    settingsNavExpanded,
    currentSettingsSubtab,
    settingsNavItems,
    navigateSettingsSubtab,
    toggleSettingsNav,
    settingsSubItemClass,
  }
}