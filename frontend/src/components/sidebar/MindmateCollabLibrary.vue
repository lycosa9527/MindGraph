<script setup lang="ts">
/**
 * Owner's saved MindMate seminars, listed above personal chat history.
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Edit3, MoreHorizontal, Pin, Trash2 } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { promptSwissGlassName } from '@/composables/sidebar/promptSwissGlassName'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'
import {
  MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT,
  notifyMindmateCollabLibraryChanged,
  leaveSavedMindmateSeminar,
  openSavedMindmateSeminar,
} from '@/utils/mindmateCollabLibrarySave'
import { MINDMATE_COLLAB_SESSION_REMOVED_EVENT } from '@/utils/mindmateCollabSessions'

interface SavedSeminarRow {
  session_id: string
  title: string
  pinned?: boolean
}

const emit = defineEmits<{
  (e: 'visibleChange', visible: boolean): void
}>()

const route = useRoute()
const { t } = useLanguage()
const notify = useNotifications()
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

function leaveOpenSeminar(sessionId: string): void {
  if (!isActive(sessionId)) {
    return
  }
  leaveSavedMindmateSeminar()
}

async function patchSeminar(
  sessionId: string,
  body: { title?: string; pinned?: boolean }
): Promise<SavedSeminarRow | null> {
  try {
    const response = await authFetch(
      `/api/mindmate/collab/my/library/${encodeURIComponent(sessionId)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    )
    if (!response.ok) {
      return null
    }
    const data = (await response.json()) as { seminar?: SavedSeminarRow }
    return data.seminar ?? null
  } catch {
    return null
  }
}

async function handleRename(seminar: SavedSeminarRow): Promise<void> {
  const currentName = seminar.title || ''
  const name = await promptSwissGlassName(
    t,
    'mindmate.collabSavedRenameTitle',
    'mindmate.collabSavedRenamePrompt',
    'mindmate.collabSavedLibraryTitle',
    currentName
  )
  if (!name || name === currentName) {
    return
  }
  const updated = await patchSeminar(seminar.session_id, { title: name })
  if (!updated) {
    notify.errorKey('mindmate.collabSavedRenameFailed')
    return
  }
  seminars.value = seminars.value.map((row) =>
    row.session_id === seminar.session_id ? { ...row, title: updated.title } : row
  )
  notifyMindmateCollabLibraryChanged({
    sessionId: seminar.session_id,
    title: updated.title,
  })
  notify.successKey('mindmate.collabSavedRenamed')
}

function placePinned(sessionId: string, pinned: boolean): void {
  const current = seminars.value.find((row) => row.session_id === sessionId)
  if (!current) {
    return
  }
  const next = { ...current, pinned }
  const rest = seminars.value.filter((row) => row.session_id !== sessionId)
  if (pinned) {
    seminars.value = [next, ...rest]
    return
  }
  const pinnedRows = rest.filter((row) => row.pinned)
  const others = rest.filter((row) => !row.pinned)
  seminars.value = [...pinnedRows, next, ...others]
}

async function handlePin(seminar: SavedSeminarRow): Promise<void> {
  const pinned = !seminar.pinned
  const updated = await patchSeminar(seminar.session_id, { pinned })
  if (!updated) {
    notify.errorKey('mindmate.collabSavedPinFailed')
    return
  }
  placePinned(seminar.session_id, Boolean(updated.pinned))
}

async function handleDelete(seminar: SavedSeminarRow): Promise<void> {
  try {
    await swissGlassConfirm(
      t('mindmate.collabSavedDeleteConfirm'),
      t('mindmate.collabSavedDeleteTitle'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
  } catch {
    return
  }
  try {
    const response = await authFetch(
      `/api/mindmate/collab/my/library/${encodeURIComponent(seminar.session_id)}`,
      { method: 'DELETE' }
    )
    if (!response.ok) {
      notify.errorKey('mindmate.collabSavedDeleteFailed')
      return
    }
  } catch {
    notify.errorKey('mindmate.collabSavedDeleteFailed')
    return
  }
  seminars.value = seminars.value.filter((row) => row.session_id !== seminar.session_id)
  leaveOpenSeminar(seminar.session_id)
  notify.successKey('mindmate.collabSavedDeleted')
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
    <div
      v-for="seminar in seminars"
      :key="seminar.session_id"
      class="mindmate-collab-library__row"
      :class="{ 'mindmate-collab-library__row--active': isActive(seminar.session_id) }"
      @click="openSavedMindmateSeminar(seminar.session_id)"
    >
      <span class="mindmate-collab-library__title">
        <Pin
          v-if="seminar.pinned"
          class="mindmate-collab-library__pin"
        />
        <span class="mindmate-collab-library__name">
          <template v-if="seminar.title">{{ seminar.title }}</template
          ><I18nText
            v-else
            k="mindmate.collabSavedLibraryTitle"
          />
        </span>
      </span>
      <ElDropdown
        trigger="click"
        placement="bottom-end"
        popper-class="user-dropdown-popper"
        class="more-dropdown"
        @click.stop
      >
        <button
          type="button"
          class="more-btn"
          @click.stop
        >
          <MoreHorizontal class="w-4 h-4" />
        </button>
        <template #dropdown>
          <ElDropdownMenu class="user-dropdown-menu">
            <ElDropdownItem @click="handlePin(seminar)">
              <Pin
                class="w-4 h-4 mr-2"
                :class="seminar.pinned ? 'text-amber-500 rotate-45' : ''"
              />
              <I18nText
                v-if="seminar.pinned"
                k="sidebar.actions.unpin"
              /><I18nText
                v-else
                k="sidebar.actions.pinToTop"
              />
            </ElDropdownItem>
            <ElDropdownItem @click="handleRename(seminar)">
              <Edit3 class="w-4 h-4 mr-2" />
              <I18nText k="sidebar.actions.rename" />
            </ElDropdownItem>
            <ElDropdownItem
              divided
              class="user-dropdown-item--logout"
              @click="handleDelete(seminar)"
            >
              <Trash2 class="w-4 h-4 mr-2" />
              <I18nText k="sidebar.actions.delete" />
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>
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
  align-items: center;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
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
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.mindmate-collab-library__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mindmate-collab-library__pin {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: #f59e0b;
  transform: rotate(45deg);
}

.more-dropdown {
  flex-shrink: 0;
}

.more-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0;
  color: #78716c;
  transition: all 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
}

.mindmate-collab-library__row:hover .more-btn,
.mindmate-collab-library__row--active .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background-color: #e7e5e4;
  color: #1c1917;
}
</style>
