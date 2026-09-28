<script setup lang="ts">
/**
 * Owner's saved MindMate seminars, listed above personal chat history.
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'
import {
  MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT,
  openSavedMindmateSeminar,
} from '@/utils/mindmateCollabLibrarySave'
import { MINDMATE_COLLAB_SESSION_REMOVED_EVENT } from '@/utils/mindmateCollabSessions'

interface SavedSeminarRow {
  session_id: string
  title: string
}

const emit = defineEmits<{
  (e: 'visibleChange', visible: boolean): void
}>()

const route = useRoute()
const { t } = useLanguage()
const authStore = useAuthStore()
const seminars = ref<SavedSeminarRow[]>([])

watch(
  () => seminars.value.length > 0,
  (visible) => {
    emit('visibleChange', visible)
  },
  { immediate: true }
)

async function loadSavedSeminars(): Promise<void> {
  if (!authStore.isAuthenticated) {
    seminars.value = []
    return
  }
  try {
    const response = await authFetch('/api/mindmate/collab/my/library')
    if (!response.ok) {
      return
    }
    const data = (await response.json()) as { seminars?: SavedSeminarRow[] }
    seminars.value = Array.isArray(data.seminars) ? data.seminars : []
  } catch {
    seminars.value = []
  }
}

function isActive(sessionId: string): boolean {
  return route.query.saved_seminar === sessionId
}

function onLibraryVisibility(): void {
  if (document.visibilityState !== 'visible') {
    return
  }
  void loadSavedSeminars()
}

onMounted(() => {
  void loadSavedSeminars()
  window.addEventListener(MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT, loadSavedSeminars)
  window.addEventListener(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, loadSavedSeminars)
  document.addEventListener('visibilitychange', onLibraryVisibility)
})

onUnmounted(() => {
  window.removeEventListener(MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT, loadSavedSeminars)
  window.removeEventListener(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, loadSavedSeminars)
  document.removeEventListener('visibilitychange', onLibraryVisibility)
})
</script>

<template>
  <div
    v-if="seminars.length > 0"
    class="mindmate-collab-library"
  >
    <div class="mindmate-collab-library__label">
      <I18nText k="mindmate.collabSavedLibraryTitle" />
    </div>
    <button
      v-for="seminar in seminars"
      :key="seminar.session_id"
      type="button"
      class="mindmate-collab-library__row"
      :class="{ 'mindmate-collab-library__row--active': isActive(seminar.session_id) }"
      @click="openSavedMindmateSeminar(seminar.session_id)"
    >
      <span class="mindmate-collab-library__title">
        <template v-if="seminar.title">{{ seminar.title }}</template
        ><I18nText
          v-else
          k="mindmate.collabSavedLibraryTitle"
        />
      </span>
    </button>
  </div>
</template>

<style scoped>
.mindmate-collab-library {
  padding: 0 0 8px;
  margin-bottom: 4px;
}

.mindmate-collab-library__label {
  padding: 4px 8px 6px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #a8a29e;
}

.mindmate-collab-library__row {
  display: flex;
  width: 100%;
  padding: 6px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.mindmate-collab-library__row:hover {
  background-color: #f5f5f4;
}

.mindmate-collab-library__row--active {
  background-color: #e7e5e4;
  color: #1c1917;
}

.mindmate-collab-library__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
