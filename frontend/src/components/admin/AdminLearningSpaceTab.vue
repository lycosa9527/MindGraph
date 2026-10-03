<script setup lang="ts">
/**
 * Learning Space admin shell — pilots / classes, student-space chrome.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ScanLine } from '@lucide/vue'

import AdminLearningSpaceClassesPanel from '@/components/admin/AdminLearningSpaceClassesPanel.vue'
import AdminLearningSpacePilotsPanel from '@/components/admin/AdminLearningSpacePilotsPanel.vue'
import AdminLearningSpaceStudentsPanel from '@/components/admin/AdminLearningSpaceStudentsPanel.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  LEARNING_SPACE_SUBTABS,
  type LearningSpaceSubtab,
  learningSpaceSubtabLabelKey,
  resolveLearningSpaceSubtab,
} from '@/composables/admin/adminLearningSpaceNav'
import { runLearningSpaceThumbnailBackfill } from '@/composables/admin/adminLearningSpaceThumbnails'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import '@/styles/learning-space.css'
import { backfillAdminThumbnails } from '@/utils/learningSpaceApi'

const { t } = useLanguage()
const notify = useNotifications()
const { can } = useAdminAccess()
const route = useRoute()
const router = useRouter()

const canEdit = computed(() => can('tab.learning_space.edit'))
const scanning = ref(false)
const scanRemaining = ref<number | null>(null)

const activeSubtab = computed(() => resolveLearningSpaceSubtab(route.query.subtab))

async function onScanThumbnails(): Promise<void> {
  if (scanning.value || !canEdit.value) return
  scanning.value = true
  scanRemaining.value = null
  let filled = 0
  try {
    const totals = await runLearningSpaceThumbnailBackfill(backfillAdminThumbnails, (state) => {
      scanRemaining.value = state.remaining
      filled = state.done
    })
    filled = totals.stored + totals.generated
    if (filled === 0 && totals.failed === 0) {
      notify.infoKey('admin.learningSpace.scanThumbnailsNone')
      return
    }
    if (totals.failed > 0) {
      notify.warningKey('admin.learningSpace.scanThumbnailsPartial', {
        ok: filled,
        failed: totals.failed,
      })
      return
    }
    notify.successKey('admin.learningSpace.scanThumbnailsDone', { count: filled })
  } catch {
    if (filled > 0) {
      notify.warningKey('admin.learningSpace.scanThumbnailsPartial', {
        ok: filled,
        failed: scanRemaining.value ?? 0,
      })
      return
    }
    notify.errorKey('admin.learningSpace.scanThumbnailsFailed')
  } finally {
    scanning.value = false
    scanRemaining.value = null
  }
}

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
            <h1><I18nText k="admin.tabs.learningSpace" /></h1>
            <p><I18nText k="admin.learningSpace.intro" /></p>
          </div>
          <div
            v-if="canEdit"
            class="ls-page-head__actions"
          >
            <button
              type="button"
              class="ls-btn ls-btn--primary ls-btn--sm"
              :disabled="scanning"
              @click="onScanThumbnails"
            >
              <ScanLine :size="15" />
              <I18nText
                v-if="!scanning"
                k="admin.learningSpace.scanThumbnails"
              />
              <I18nText
                v-else
                k="admin.learningSpace.scanThumbnailsRunning"
                :params="{ remaining: scanRemaining === null ? '…' : scanRemaining }"
              />
            </button>
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
            <span class="ls-app__tab-text"
              ><I18nText :k="learningSpaceSubtabLabelKey(subtab)"
            /></span>
          </button>
        </nav>

        <AdminLearningSpacePilotsPanel v-if="activeSubtab === 'pilots'" />
        <AdminLearningSpaceClassesPanel v-else-if="activeSubtab === 'classes'" />
        <AdminLearningSpaceStudentsPanel v-else />
      </div>
    </div>
  </div>
</template>
