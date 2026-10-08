<script setup lang="ts">
/**
 * Start a seminar from a MindMate library conversation (school or public).
 */
import { computed, ref, watch } from 'vue'

import { ArrowLeft, Loader2 } from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import I18nText from '@/components/common/I18nText.vue'
import MindMateDingtalkBadge from '@/components/sidebar/MindMateDingtalkBadge.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useConversations } from '@/composables/queries'
import type { DifyConversation } from '@/composables/queries/useDifyQueries'
import { authFetch } from '@/utils/api'
import { difyConversationRouteQuerySuffix } from '@/utils/difyConversationRoute'
import { type CollabSeedDraft, difyMessagesToCollabSeed } from '@/utils/mindmateCollabSeed'
import { displayMindmateUserQueryForUi } from '@/utils/mindmateExtensionPageContext'

const props = defineProps<{
  starting: boolean
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (
    e: 'start',
    payload: {
      visibility: 'organization' | 'network'
      title: string
      seedMessages: CollabSeedDraft[]
    }
  ): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const visibility = ref<'organization' | 'network'>('organization')
const pendingId = ref<string | null>(null)

const { data, isLoading, isError } = useConversations()

const conversations = computed(() => {
  const rows = data.value ?? []
  return [...rows].sort((left, right) => (right.updated_at || 0) - (left.updated_at || 0))
})

const scopeOptions = computed(() => [
  { value: 'organization' as const, labelKey: 'mindmate.collabStartSessionOrg' },
  { value: 'network' as const, labelKey: 'mindmate.collabStartSessionPublic' },
])

const busy = computed(() => props.starting || pendingId.value !== null)

watch(
  () => props.starting,
  (value) => {
    if (!value) {
      pendingId.value = null
    }
  }
)

function isMindbotConversation(conv: DifyConversation): boolean {
  if (conv.channel === 'mindbot') {
    return true
  }
  return (conv.dify_user || '').startsWith('mindbot_')
}

async function startFrom(conv: DifyConversation): Promise<void> {
  if (busy.value) {
    return
  }
  pendingId.value = conv.id
  try {
    const suffix = difyConversationRouteQuerySuffix({
      difyUser: conv.dify_user,
      server: conv.server,
      mindbotConfigId: conv.mindbot_config_id,
    })
    const response = await authFetch(
      `/api/dify/conversations/${encodeURIComponent(conv.id)}/messages?limit=50${suffix}`
    )
    if (!response.ok) {
      pendingId.value = null
      notify.errorKey('mindmate.collabStartSessionOpenFailed')
      return
    }
    const body = (await response.json()) as {
      data?: Array<{ query?: string; answer?: string }>
    }
    emit('start', {
      visibility: visibility.value,
      title: conv.name?.trim() || t('sidebar.history.untitled'),
      seedMessages: difyMessagesToCollabSeed(body.data || [], displayMindmateUserQueryForUi),
    })
  } catch {
    pendingId.value = null
    notify.errorKey('mindmate.collabStartSessionOpenFailed')
  }
}
</script>

<template>
  <div class="sw-panel">
    <div class="sw-panel__header">
      <button
        type="button"
        class="sw-panel__back"
        @click="emit('back')"
      >
        <ArrowLeft
          class="sw-panel__back-icon"
          aria-hidden="true"
        />
        <I18nText k="mindmate.collabStartSession" />
      </button>
    </div>

    <AdminSwissSegmented
      v-model="visibility"
      block
      :aria-label="t('mindmate.collabStartSessionScope')"
      :disabled="busy"
      :options="scopeOptions"
    />

    <p class="sw-panel__hint">
      <I18nText k="mindmate.collabStartSessionHint" />
    </p>

    <div
      v-if="isLoading"
      class="sw-panel__loading"
    >
      <Loader2
        class="sw-panel__loading-icon"
        aria-hidden="true"
      />
      <span><I18nText k="common.loading" /></span>
    </div>

    <p
      v-else-if="isError"
      class="sw-panel__empty"
    >
      <I18nText k="mindmate.collabStartSessionLoadFailed" />
    </p>

    <p
      v-else-if="conversations.length === 0"
      class="sw-panel__empty"
    >
      <I18nText k="mindmate.noHistory" />
    </p>

    <ul
      v-else
      class="sw-sessions"
    >
      <li
        v-for="conv in conversations"
        :key="conv.id"
        class="sw-session-row"
      >
        <div class="sw-session-body">
          <div class="sw-session-title">
            <MindMateDingtalkBadge
              v-if="isMindbotConversation(conv)"
              class="sw-session-badge"
            />
            <span v-if="conv.name">{{ conv.name }}</span>
            <I18nText
              v-else
              k="sidebar.history.untitled"
            />
          </div>
        </div>
        <button
          type="button"
          class="sw-session-join"
          :disabled="busy"
          @click="startFrom(conv)"
        >
          <Loader2
            v-if="pendingId === conv.id"
            class="sw-session-join__spinner"
            aria-hidden="true"
          />
          <I18nText
            k="mindmate.collabStartSessionAction"
            dense
          />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.sw-panel {
  padding: 4px 0 2px;
}

.sw-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid #e7e5e4;
}

.sw-panel__back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #57534e;
  line-height: 1.25;
}

.sw-panel__back:hover {
  color: #1c1917;
}

.sw-panel__back-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

.sw-panel__hint {
  font-size: 12px;
  color: #78716c;
  margin: 12px 0;
  line-height: 1.5;
}

.sw-panel__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 0;
  font-size: 13px;
  color: #a8a29e;
}

.sw-panel__loading-icon {
  width: 15px;
  height: 15px;
  animation: mmc-start-spin 0.8s linear infinite;
  flex-shrink: 0;
}

.sw-panel__empty {
  font-size: 12px;
  color: #a8a29e;
  text-align: center;
  padding: 20px 0 12px;
  margin: 0;
  line-height: 1.5;
}

.sw-sessions {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 260px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sw-session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f5f4;
}

.sw-session-row:hover {
  background: #e7e5e4;
}

.sw-session-body {
  min-width: 0;
  flex: 1;
}

.sw-session-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #1c1917;
  line-height: 1.3;
  min-width: 0;
}

.sw-session-title > span {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sw-session-badge {
  flex-shrink: 0;
}

.sw-session-join {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 28px;
  padding: 4px 10px;
  background: #1c1917;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.sw-session-join:hover:not(:disabled) {
  background: #292524;
}

.sw-session-join:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sw-session-join__spinner {
  width: 12px;
  height: 12px;
  animation: mmc-start-spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes mmc-start-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
