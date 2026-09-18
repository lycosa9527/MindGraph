<script setup lang="ts">
/**
 * Learning Space admin shell — pilots / classes sub-pages.
 */
import { computed, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import AdminLearningSpaceClassesPanel from '@/components/admin/AdminLearningSpaceClassesPanel.vue'
import AdminLearningSpacePilotsPanel from '@/components/admin/AdminLearningSpacePilotsPanel.vue'
import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import {
  LEARNING_SPACE_SUBTABS,
  learningSpaceSubtabLabelKey,
  resolveLearningSpaceSubtab,
  type LearningSpaceSubtab,
} from '@/composables/admin/adminLearningSpaceNav'
import { useLanguage } from '@/composables'

const { t } = useLanguage()
const route = useRoute()
const router = useRouter()

const activeSubtab = computed(() => resolveLearningSpaceSubtab(route.query.subtab))

const subtabOptions = computed(() =>
  LEARNING_SPACE_SUBTABS.map((value) => ({
    value,
    label: String(t(learningSpaceSubtabLabelKey(value))),
  }))
)

function setSubtab(subtab: LearningSpaceSubtab): void {
  const query: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(route.query).filter(([, v]) => typeof v === 'string') as [string, string][]
    ),
    tab: 'learning_space',
    subtab,
  }
  if (subtab !== 'classes') {
    delete query.teacher_user_id
  }
  void router.replace({ query })
}

watch(
  () => route.query.subtab,
  (subtab) => {
    if (subtab == null || subtab === '') {
      setSubtab('pilots')
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="ls-admin-shell">
    <div>
      <h2 class="ls-title">
        {{ t('admin.tabs.learningSpace') }}
      </h2>
      <p class="ls-intro">
        {{ t('admin.learningSpace.intro') }}
      </p>
    </div>

    <AdminSwissSegmented
      :model-value="activeSubtab"
      :options="subtabOptions"
      :aria-label="t('admin.learningSpace.subtabAria')"
      fit
      @update:model-value="setSubtab"
    />

    <AdminLearningSpacePilotsPanel v-if="activeSubtab === 'pilots'" />
    <AdminLearningSpaceClassesPanel v-else />
  </div>
</template>

<style scoped>
.ls-admin-shell {
  padding: 1rem 1.25rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.ls-title {
  margin: 0 0 0.25rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: #111827;
}
.ls-intro {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
}
</style>
