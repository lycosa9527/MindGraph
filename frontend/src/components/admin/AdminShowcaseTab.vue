<script setup lang="ts">
/**
 * Showcase admin shell — sub-tab router.
 */
import { computed, onMounted, ref, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import AdminShowcaseDashboard from '@/components/admin/AdminShowcaseDashboard.vue'
import AdminShowcaseFields from '@/components/admin/AdminShowcaseFields.vue'
import AdminShowcaseModeration from '@/components/admin/AdminShowcaseModeration.vue'
import AdminShowcasePermissions from '@/components/admin/AdminShowcasePermissions.vue'
import AdminShowcaseProxyPublish from '@/components/admin/AdminShowcaseProxyPublish.vue'
import AdminShowcasePublished from '@/components/admin/AdminShowcasePublished.vue'
import {
  SHOWCASE_SUBTABS,
  showcaseSubtabLabelKey,
  resolveShowcaseSubtab,
  type ShowcaseSubtab,
} from '@/composables/admin/adminShowcaseNav'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAuthStore } from '@/stores'
import { getShowcasePendingCount } from '@/utils/apiClient'

const { t } = useLanguage()
const { can } = useAdminAccess()
const authStore = useAuthStore()
const { featureShowcase } = useFeatureFlags()
const route = useRoute()
const router = useRouter()

const activeSubtab = computed(() => resolveShowcaseSubtab(route.query.subtab))
const moderationPendingCount = ref(0)

async function refreshModerationCounts(): Promise<void> {
  if (!can('tab.showcase.edit') && !can('tab.showcase.view')) {
    moderationPendingCount.value = 0
    return
  }
  try {
    const res = await getShowcasePendingCount()
    moderationPendingCount.value = res.pending
  } catch {
    moderationPendingCount.value = 0
  }
}

const visibleSubtabs = computed(() =>
  SHOWCASE_SUBTABS.filter((tab) => {
    if (authStore.isSuperAdmin) return true
    if (tab === 'permissions') return can('tab.showcase.permissions')
    if (tab === 'fields') return can('tab.showcase.fields')
    if (tab === 'publish') return can('tab.showcase.edit')
    if (tab === 'dashboard') return can('tab.showcase.dashboard') || can('tab.showcase.view')
    if (tab === 'published') {
      return (
        can('tab.showcase.view') ||
        can('tab.showcase.edit') ||
        can('tab.showcase.recommend')
      )
    }
    return can('tab.showcase.view') || can('tab.showcase.edit')
  })
)

const subtabOptions = computed(() =>
  visibleSubtabs.value.map((value) => ({
    value,
    label: String(t(showcaseSubtabLabelKey(value))),
    count: value === 'moderation' ? moderationPendingCount.value : undefined,
  }))
)

function setSubtab(subtab: ShowcaseSubtab): void {
  const query: Record<string, string> = { ...route.query, tab: 'showcase', subtab }
  if (subtab !== 'moderation') {
    delete query.queue
  }
  void router.replace({ query })
}

function redirectLegacyApprovedQueue(): void {
  if (route.query.subtab === 'moderation' && route.query.queue === 'approved') {
    const query: Record<string, string> = { ...route.query, tab: 'showcase', subtab: 'published' }
    delete query.queue
    void router.replace({ query })
  }
}

onMounted(() => {
  redirectLegacyApprovedQueue()
  void refreshModerationCounts()
  eventBus.on('admin:showcase_updated', refreshModerationCounts)
})

watch(
  () => route.query.queue,
  () => {
    redirectLegacyApprovedQueue()
  }
)
</script>

<template>
  <div class="admin-showcase-shell space-y-6">
    <p
      v-if="!featureShowcase"
      class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      {{ t('admin.showcase.featureDisabled') }}
    </p>

    <div>
      <h2 class="mb-1 text-base font-semibold text-gray-900">
        {{ t('admin.showcase.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('admin.showcase.intro') }}
      </p>
    </div>

    <AdminSwissSegmented
      v-if="subtabOptions.length > 0"
      :model-value="activeSubtab"
      :options="subtabOptions"
      :aria-label="t('admin.showcase.subtabAria')"
      fit
      @update:model-value="setSubtab"
    />

    <AdminShowcaseDashboard v-if="activeSubtab === 'dashboard'" />
    <AdminShowcasePublished v-else-if="activeSubtab === 'published'" />
    <AdminShowcaseModeration v-else-if="activeSubtab === 'moderation'" />
    <AdminShowcaseProxyPublish v-else-if="activeSubtab === 'publish'" />
    <AdminShowcaseFields v-else-if="activeSubtab === 'fields'" />
    <AdminShowcasePermissions v-else-if="activeSubtab === 'permissions'" />
  </div>
</template>
