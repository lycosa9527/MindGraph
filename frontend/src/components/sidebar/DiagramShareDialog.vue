<script setup lang="ts">
/**
 * Send one library diagram to other people in the same organization.
 */
import { ref, watch } from 'vue'

import { Share2 } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { authFetch } from '@/utils/api'

const open = defineModel<boolean>({ required: true })

const props = defineProps<{
  diagramId: string
}>()

interface ShareCandidate {
  id: number
  name: string
  already_shared: boolean
}

const { t } = useLanguage()
const notify = useNotifications()
const savedDiagramsStore = useSavedDiagramsStore()

const query = ref('')
const loading = ref(false)
const sending = ref(false)
const candidates = ref<ShareCandidate[]>([])
const selected = ref<number[]>([])

let searchTimer: ReturnType<typeof setTimeout> | null = null
let seedSelection = false

async function loadCandidates(): Promise<void> {
  const shouldSeed = seedSelection
  seedSelection = false
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (query.value.trim()) params.set('q', query.value.trim())
    const suffix = params.toString() ? `?${params.toString()}` : ''
    const response = await authFetch(`/api/diagrams/${props.diagramId}/share-candidates${suffix}`)
    if (!response.ok) {
      candidates.value = []
      return
    }
    const data = (await response.json()) as { items: ShareCandidate[]; granted_ids?: number[] }
    candidates.value = data.items
    if (shouldSeed) {
      selected.value = data.granted_ids ?? []
    }
  } finally {
    loading.value = false
  }
}

watch(open, (visible) => {
  if (!visible) return
  query.value = ''
  selected.value = []
  seedSelection = true
  void loadCandidates()
})

watch(query, () => {
  if (!open.value) return
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    void loadCandidates()
  }, 300)
})

function toggle(id: number): void {
  if (selected.value.includes(id)) {
    selected.value = selected.value.filter((item) => item !== id)
    return
  }
  selected.value = [...selected.value, id]
}

async function send(): Promise<void> {
  sending.value = true
  const ok = await savedDiagramsStore.replaceDiagramShares(props.diagramId, selected.value)
  sending.value = false
  if (!ok) {
    notify.error(t('sidebar.share.failed'))
    return
  }
  notify.success(t('sidebar.share.sent'))
  open.value = false
}
</script>

<template>
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('sidebar.share.ribbon')"
    :title="t('sidebar.share.title')"
    :line1="t('sidebar.share.line1')"
    :icon="Share2"
    width="min(420px, 92vw)"
  >
    <div class="flex flex-col gap-3">
      <input
        v-model="query"
        type="search"
        class="w-full rounded-md border border-stone-200 px-3 py-2 text-sm"
        :placeholder="t('sidebar.share.search')"
      />
      <p
        v-if="!loading && candidates.length === 0"
        class="text-sm text-stone-500"
      >
        {{ t('sidebar.share.empty') }}
      </p>
      <ul class="max-h-64 overflow-y-auto flex flex-col gap-1">
        <li
          v-for="person in candidates"
          :key="person.id"
        >
          <label class="flex items-center gap-2 px-1 py-1 text-sm cursor-pointer">
            <input
              type="checkbox"
              :checked="selected.includes(person.id)"
              @change="toggle(person.id)"
            />
            <span>{{ person.name }}</span>
          </label>
        </li>
      </ul>
    </div>
    <template #footer>
      <div class="flex justify-end">
        <button
          type="button"
          class="rounded-md bg-stone-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
          :disabled="sending"
          @click="send"
        >
          {{ t('sidebar.share.send') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
