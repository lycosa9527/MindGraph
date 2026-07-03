<script setup lang="ts">
/**
 * MindMate collab session list for sidebar — matches ChatHistory row styling.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElDropdown, ElDropdownItem, ElDropdownMenu, ElIcon, ElMessageBox } from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { MoreHorizontal, Power } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import CollabLiveBadge from '@/components/social/CollabLiveBadge.vue'
import {
  embeddedCollabRoomCode,
  setEmbeddedCollabRoomCode,
} from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'
import {
  formatMindmateCollabCode,
  loadLocalMindmateCollabSessions,
  normalizeMindmateCollabCode,
  persistLocalMindmateCollabSessions,
  trackLocalMindmateCollabSession,
  type LocalMindmateCollabSession,
} from '@/utils/mindmateCollabSessions'

const ORG_REFRESH_INTERVAL_MS = 30_000

const props = withDefaults(
  defineProps<{
    /** Render inside ChatHistory scroll list (no outer chrome). */
    inline?: boolean
  }>(),
  {
    inline: false,
  },
)

const emit = defineEmits<{
  (e: 'visible-change', visible: boolean): void
}>()

interface CollabSessionRow extends LocalMindmateCollabSession {
  owner_name: string | null
  participant_count: number
}

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()

const loading = ref(false)
const orgSessions = ref<CollabSessionRow[]>([])
const localSessions = ref<CollabSessionRow[]>([])
let refreshTimer: ReturnType<typeof setInterval> | null = null

const activeCode = computed(() => {
  const raw = route.query.code
  return typeof raw === 'string' ? raw.replace(/-/g, '').toUpperCase() : null
})

const inMindmateCollabRoute = computed(() => route.path.startsWith('/mindmate/collab'))

const mergedSessions = computed(() => {
  const byCode = new Map<string, CollabSessionRow>()
  for (const row of orgSessions.value) {
    byCode.set(normalizeCode(row.code), row)
  }
  for (const row of localSessions.value) {
    const key = normalizeCode(row.code)
    if (!byCode.has(key)) {
      byCode.set(key, row)
    }
  }
  return Array.from(byCode.values())
})

const isVisible = computed(() => loading.value || mergedSessions.value.length > 0)

watch(
  isVisible,
  (visible) => {
    emit('visible-change', visible)
  },
  { immediate: true },
)

function normalizeCode(code: string): string {
  return normalizeMindmateCollabCode(code)
}

function formatCode(code: string): string {
  return formatMindmateCollabCode(code)
}

function loadLocalSessions(): void {
  localSessions.value = loadLocalMindmateCollabSessions() as CollabSessionRow[]
}

function persistLocalSessions(): void {
  persistLocalMindmateCollabSessions(localSessions.value)
}

async function pruneStaleLocalSessions(): Promise<void> {
  const orgKeys = new Set(orgSessions.value.map((s) => normalizeCode(s.code)))
  const survivors: CollabSessionRow[] = []
  for (const row of localSessions.value) {
    const key = normalizeCode(row.code)
    if (orgKeys.has(key)) {
      survivors.push(row)
      continue
    }
    const formatted = formatCode(row.code)
    try {
      const response = await authFetch(
        `/api/mindmate/collab/status?code=${encodeURIComponent(formatted)}`,
      )
      if (!response.ok) {
        continue
      }
      const status = (await response.json()) as { live?: boolean }
      if (status.live) {
        survivors.push(row)
      }
    } catch {
      survivors.push(row)
    }
  }
  if (survivors.length !== localSessions.value.length) {
    localSessions.value = survivors
    persistLocalSessions()
  }
}

async function fetchSessions(showSpinner = true): Promise<void> {
  if (!authStore.isAuthenticated) return
  if (showSpinner) loading.value = true
  try {
    const response = await authFetch('/api/mindmate/collab/organization/sessions')
    if (response.ok) {
      const data = await response.json()
      orgSessions.value = (data.sessions || []) as CollabSessionRow[]
    }
    const hostedRes = await authFetch('/api/mindmate/collab/my/hosted')
    if (hostedRes.ok) {
      const hostedData = await hostedRes.json()
      const hosted = hostedData.session as CollabSessionRow | null
      if (hosted?.code) {
        trackLocalMindmateCollabSession(hosted)
        loadLocalSessions()
      }
    }
    await pruneStaleLocalSessions()
  } finally {
    if (showSpinner) loading.value = false
  }
}

function openSession(row: CollabSessionRow): void {
  const formatted = formatCode(row.code)
  if (route.path === '/mindmate') {
    setEmbeddedCollabRoomCode(formatted)
    return
  }
  void router.push({ path: '/mindmate/collab', query: { code: formatted } })
}

function isHost(row: CollabSessionRow): boolean {
  if (row.owner_user_id != null) {
    return row.owner_user_id === Number(authStore.user?.id)
  }
  return row.owner_name === authStore.user?.username
}

function isRowActive(row: CollabSessionRow): boolean {
  const key = normalizeCode(row.code)
  if (inMindmateCollabRoute.value && key === activeCode.value) {
    return true
  }
  if (embeddedCollabRoomCode.value && key === normalizeCode(embeddedCollabRoomCode.value)) {
    return true
  }
  return false
}

async function stopSession(row: CollabSessionRow): Promise<void> {
  try {
    await ElMessageBox.confirm(t('sidebar.mindmateCollabHistory.stopConfirm'), {
      type: 'warning',
    })
  } catch {
    return
  }
  const response = await authFetch('/api/mindmate/collab/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: row.session_id }),
  })
  if (response.ok) {
    notify.success(t('collab.ended'))
    orgSessions.value = orgSessions.value.filter((s) => s.session_id !== row.session_id)
    localSessions.value = localSessions.value.filter((s) => s.session_id !== row.session_id)
    persistLocalSessions()
    const rowKey = normalizeCode(row.code)
    if (rowKey === activeCode.value || rowKey === normalizeCode(embeddedCollabRoomCode.value || '')) {
      setEmbeddedCollabRoomCode(null)
      if (inMindmateCollabRoute.value) {
        void router.push('/mindmate')
      }
    }
  } else {
    notify.error(t('collab.endFailed'))
  }
}

onMounted(() => {
  loadLocalSessions()
  void fetchSessions(true)
  refreshTimer = setInterval(() => void fetchSessions(false), ORG_REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div
    v-if="isVisible"
    class="mindmate-collab-history"
    :class="{ 'mindmate-collab-history--inline': props.inline }"
  >
    <div
      v-if="loading && mergedSessions.length === 0"
      class="flex items-center justify-center py-4"
    >
      <ElIcon class="animate-spin text-stone-400">
        <Loading />
      </ElIcon>
    </div>

    <div
      v-else-if="mergedSessions.length > 0"
      class="group-section"
    >
      <div
        v-for="session in mergedSessions"
        :key="session.session_id"
        class="conversation-item"
        :class="{ active: isRowActive(session) }"
      >
        <button
          type="button"
          class="conv-name conv-name-btn"
          @click="openSession(session)"
        >
          <span class="conv-name-text">
            {{ session.title || t('mindmate.collabPill') }}
          </span>
          <CollabLiveBadge :title="t('sidebar.diagramHistory.collabLive')" />
        </button>
        <ElDropdown
          v-if="isHost(session)"
          trigger="click"
          placement="bottom-end"
          popper-class="user-dropdown-popper"
          class="more-dropdown shrink-0"
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
              <ElDropdownItem
                class="user-dropdown-item--logout"
                @click="stopSession(session)"
              >
                <Power class="w-4 h-4 mr-2" />
                {{ t('sidebar.actions.turnOffOnlineCollab') }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mindmate-collab-history {
  flex-shrink: 0;
  padding: 0 12px 4px;
}

.mindmate-collab-history--inline {
  padding: 0 0 8px;
  margin-bottom: 4px;
}

.mindmate-collab-history--inline .group-section {
  margin-bottom: 0;
}

.group-section {
  margin-bottom: 4px;
}

.conversation-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  transition: background-color 0.15s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.conversation-item:hover {
  background-color: #f5f5f4;
}

.conversation-item.active {
  background-color: #e7e5e4;
  color: #1c1917;
}

.conv-name {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.conv-name-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: inherit;
  font: inherit;
}

.conv-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: #1c1917;
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

.conversation-item:hover .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background-color: #e7e5e4;
  color: #1c1917;
}

.more-dropdown {
  flex-shrink: 0;
}
</style>
