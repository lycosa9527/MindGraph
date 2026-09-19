<script setup lang="ts">
/**
 * Learning Space admin shell — pilots / classes, student-space chrome.
 */
import { computed, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import AdminLearningSpaceClassesPanel from '@/components/admin/AdminLearningSpaceClassesPanel.vue'
import AdminLearningSpacePilotsPanel from '@/components/admin/AdminLearningSpacePilotsPanel.vue'
import {
  LEARNING_SPACE_SUBTABS,
  learningSpaceSubtabLabelKey,
  resolveLearningSpaceSubtab,
  type LearningSpaceSubtab,
} from '@/composables/admin/adminLearningSpaceNav'
import { useLanguage } from '@/composables'
import '@/styles/learning-space.css'

const { t } = useLanguage()
const route = useRoute()
const router = useRouter()

const activeSubtab = computed(() => resolveLearningSpaceSubtab(route.query.subtab))

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
  <div class="ls-app ls-admin-app">
    <div class="ls-app__body">
      <div class="ls-app__inner">
        <header class="ls-page-head">
          <div>
            <h1>{{ t('admin.tabs.learningSpace') }}</h1>
            <p>{{ t('admin.learningSpace.intro') }}</p>
          </div>
        </header>

        <nav
          class="ls-app__tabs"
          :aria-label="t('admin.learningSpace.subtabAria')"
        >
          <button
            v-for="subtab in LEARNING_SPACE_SUBTABS"
            :key="subtab"
            type="button"
            class="ls-app__tab"
            :class="{ 'ls-app__tab--active': activeSubtab === subtab }"
            @click="setSubtab(subtab)"
          >
            <span class="ls-app__tab-text">{{ t(learningSpaceSubtabLabelKey(subtab)) }}</span>
          </button>
        </nav>

        <AdminLearningSpacePilotsPanel v-if="activeSubtab === 'pilots'" />
        <AdminLearningSpaceClassesPanel v-else />
      </div>
    </div>
  </div>
</template>
