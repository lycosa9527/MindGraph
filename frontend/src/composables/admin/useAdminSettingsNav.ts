/**
 * Sidebar state and navigation for 系统设置 (top-level panel tab).
 */
import type { ComputedRef, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  type SettingsSubtab,
  defaultSettingsSubtab,
  isSettingsSubtab,
  visibleSettingsNavItems,
} from '@/composables/admin/adminSettingsNav'

export function useAdminSettingsNav(options: {
  canViewSettingsSubtab: (subtab: string) => boolean
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

  const settingsNavItems = computed(() =>
    visibleSettingsNavItems({
      canViewSettingsSubtab: options.canViewSettingsSubtab,
      featureLibrary: options.featureLibrary.value,
    })
  )

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
