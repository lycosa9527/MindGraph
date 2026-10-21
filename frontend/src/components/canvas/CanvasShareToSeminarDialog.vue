<script setup lang="ts">
/**
 * Pick a live seminar and post the saved canvas diagram into it.
 */
import { ref, watch } from 'vue'

import { ElButton, ElDialog, ElInput } from 'element-plus'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { authFetch } from '@/utils/api'

const open = defineModel<boolean>({ required: true })

const { t } = useLanguage()
const notify = useNotifications()
const savedDiagrams = useSavedDiagramsStore()

interface SeminarShareTarget {
  sessionId: string
  title: string
  code: string
}

const loading = ref(false)
const sharing = ref(false)
const sessions = ref<SeminarShareTarget[]>([])
const selectedId = ref('')
const note = ref('')

function mapSessions(payload: unknown): SeminarShareTarget[] {
  if (!payload || typeof payload !== 'object') {
    return []
  }
  const rows = (payload as { sessions?: unknown }).sessions
  if (!Array.isArray(rows)) {
    return []
  }
  const found: SeminarShareTarget[] = []
  for (const row of rows) {
    if (!row || typeof row !== 'object') {
      continue
    }
    const item = row as { session_id?: unknown; title?: unknown; code?: unknown }
    const sessionId = typeof item.session_id === 'string' ? item.session_id.trim() : ''
    if (!sessionId) {
      continue
    }
    const title = typeof item.title === 'string' ? item.title.trim() : ''
    const code = typeof item.code === 'string' ? item.code.trim() : ''
    found.push({ sessionId, title: title || code || sessionId, code })
  }
  return found
}

async function loadSessions(): Promise<void> {
  loading.value = true
  selectedId.value = ''
  note.value = ''
  try {
    const [hostedRes, orgRes] = await Promise.all([
      authFetch('/api/mindmate/collab/my/hosted'),
      authFetch('/api/mindmate/collab/organization/sessions'),
    ])
    const hosted = hostedRes.ok ? mapSessions(await hostedRes.json()) : []
    const org = orgRes.ok ? mapSessions(await orgRes.json()) : []
    const seen = new Set<string>()
    const merged: SeminarShareTarget[] = []
    for (const row of [...hosted, ...org]) {
      if (seen.has(row.sessionId)) {
        continue
      }
      seen.add(row.sessionId)
      merged.push(row)
    }
    sessions.value = merged
    if (merged.length === 1) {
      selectedId.value = merged[0].sessionId
    }
  } catch {
    sessions.value = []
    notify.errorKey('canvas.ribbon.shareToSeminarFailed')
  } finally {
    loading.value = false
  }
}

async function confirmShare(): Promise<void> {
  const sessionId = selectedId.value
  const diagramId = savedDiagrams.activeDiagramId?.trim() ?? ''
  if (!sessionId || !diagramId || sharing.value) {
    return
  }
  sharing.value = true
  try {
    const response = await authFetch(
      `/api/mindmate/collab/${encodeURIComponent(sessionId)}/share-diagram`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ diagram_id: diagramId, note: note.value.trim() }),
      }
    )
    if (!response.ok) {
      notify.errorKey('canvas.ribbon.shareToSeminarFailed')
      return
    }
    const target = sessions.value.find((row) => row.sessionId === sessionId)
    notify.successKey('canvas.ribbon.shareToSeminarDone', { title: target?.title || '' })
    open.value = false
  } catch {
    notify.errorKey('canvas.ribbon.shareToSeminarFailed')
  } finally {
    sharing.value = false
  }
}

watch(open, (visible) => {
  if (visible) {
    void loadSessions()
  }
})
</script>

<template>
  <ElDialog
    v-model="open"
    append-to-body
    class="mm-share-seminar"
    width="min(420px, 92vw)"
    :title="t('canvas.ribbon.shareToSeminar')"
  >
    <p
      v-if="loading"
      class="mm-share-seminar__hint"
    >
      <I18nText k="common.loading" />
    </p>
    <template v-else-if="sessions.length === 0">
      <p class="mm-share-seminar__hint">
        <I18nText k="canvas.ribbon.shareToSeminarEmpty" />
      </p>
      <p class="mm-share-seminar__hint">
        <I18nText k="canvas.ribbon.shareToSeminarHint" />
      </p>
    </template>
    <ul
      v-else
      class="mm-share-seminar__list"
    >
      <li
        v-for="row in sessions"
        :key="row.sessionId"
      >
        <button
          type="button"
          class="mm-share-seminar__row"
          :class="{ 'is-on': selectedId === row.sessionId }"
          @click="selectedId = row.sessionId"
        >
          <span class="mm-share-seminar__title">{{ row.title }}</span>
        </button>
      </li>
    </ul>
    <ElInput
      v-if="!loading && sessions.length > 0"
      v-model="note"
      class="mm-share-seminar__note"
      type="textarea"
      :rows="2"
      maxlength="500"
      show-word-limit
      :placeholder="t('canvas.ribbon.shareToSeminarNote')"
    />
    <template #footer>
      <ElButton @click="open = false">
        <I18nText k="common.cancel" />
      </ElButton>
      <ElButton
        type="primary"
        :disabled="!selectedId || sharing || sessions.length === 0"
        :loading="sharing"
        @click="confirmShare"
      >
        <I18nText k="canvas.ribbon.shareToSeminarConfirm" />
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.mm-share-seminar__hint {
  margin: 0 0 8px;
  color: #57534e;
  font-size: 14px;
  line-height: 1.5;
}

.mm-share-seminar__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: min(48vh, 360px);
  overflow-y: auto;
}

.mm-share-seminar__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e7e5e4;
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.mm-share-seminar__note {
  margin-top: 12px;
}

.mm-share-seminar__row.is-on {
  border-color: #c4b5fd;
  background: #f5f3ff;
}

.mm-share-seminar__title {
  min-width: 0;
  color: #1c1917;
  font-size: 14px;
  font-weight: 600;
}

.mm-share-seminar__code {
  flex-shrink: 0;
  color: #78716c;
  font-size: 12px;
}
</style>
