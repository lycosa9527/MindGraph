<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Folder, History, Search } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

const props = defineProps<{
  visible: boolean
  /** Keep picker open after each selection (diagram-case gallery). */
  multiSelect?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'select', diagram: SavedDiagram): void
}>()

const { t, currentLanguage } = useLanguage()
const savedDiagramsStore = useSavedDiagramsStore()

const open = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const searchQuery = ref('')

const folderNameById = computed(() => {
  const map = new Map<string, string>()
  for (const folder of savedDiagramsStore.folders) {
    map.set(folder.id, folder.name)
  }
  return map
})

const filteredDiagrams = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const list = savedDiagramsStore.diagrams
  if (!q) return list
  return list.filter((d) => {
    if (d.title.toLowerCase().includes(q)) return true
    const folderName = folderLabel(d).toLowerCase()
    return folderName.includes(q)
  })
})

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      searchQuery.value = ''
      return
    }
    void savedDiagramsStore.fetchDiagrams(1, 50, { force: true }).then((loaded) => {
      if (!loaded) return
      void savedDiagramsStore.prefetchDiagramSpecs(savedDiagramsStore.diagrams.map((d) => d.id))
    })
  }
)

function close() {
  emit('update:visible', false)
}

function pick(diagram: SavedDiagram) {
  emit('select', diagram)
  if (!props.multiSelect) {
    close()
  }
}

function folderLabel(diagram: SavedDiagram): string {
  const folderId = diagram.folder_id
  if (folderId) {
    return (
      folderNameById.value.get(folderId) ?? String(t('showcase.publishModal.historyUncategorized'))
    )
  }
  return String(t('showcase.publishModal.historyUncategorized'))
}

function formatModifiedAt(iso: string): string {
  try {
    const locale =
      currentLanguage.value === 'zh' || currentLanguage.value === 'zh-tw'
        ? currentLanguage.value === 'zh-tw'
          ? 'zh-TW'
          : 'zh-CN'
        : currentLanguage.value || undefined
    return new Date(iso).toLocaleString(locale, {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
</script>

<template>
  <SwissGlassCard
    v-model="open"
    :ribbon="t('swissGlass.hero.historyPicker.ribbon')"
    :title="t('swissGlass.hero.historyPicker.title')"
    :line1="t('swissGlass.hero.historyPicker.line1')"
    :icon="History"
    card-class="swiss-glass-card--xl"
    @close="close"
  >
    <div class="flex max-h-[70vh] flex-col">
      <div class="border-b border-gray-100 pb-3">
        <div class="relative">
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('showcase.publishModal.historySearch')"
            class="w-full rounded-xl border border-gray-100 py-2 pl-9 pr-4 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
          />
        </div>
      </div>

      <div class="flex-1 overflow-y-auto py-3">
        <p
          v-if="savedDiagramsStore.isLoading"
          class="py-8 text-center text-sm text-gray-400"
        >
          …
        </p>
        <p
          v-else-if="filteredDiagrams.length === 0"
          class="py-8 text-center text-sm text-gray-400"
        >
          {{ t('showcase.publishModal.historyEmpty') }}
        </p>
        <ul
          v-else
          class="divide-y divide-gray-100 rounded-xl border border-gray-100"
        >
          <li
            v-for="diagram in filteredDiagrams"
            :key="diagram.id"
          >
            <button
              type="button"
              class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-50"
              @click="pick(diagram)"
            >
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-gray-900">
                  {{ diagram.title }}
                </p>
                <p class="mt-0.5 truncate text-xs text-gray-400">
                  {{ formatModifiedAt(diagram.updated_at) }}
                </p>
              </div>
              <span
                class="inline-flex max-w-[40%] shrink-0 items-center gap-1 truncate rounded-full border border-stone-200 bg-stone-50 px-2.5 py-0.5 text-[11px] font-medium text-stone-600"
                :title="folderLabel(diagram)"
              >
                <Folder class="h-3 w-3 shrink-0 text-stone-400" />
                <span class="truncate">{{ folderLabel(diagram) }}</span>
              </span>
            </button>
          </li>
        </ul>
      </div>

      <div
        v-if="multiSelect"
        class="border-t border-gray-100 pt-3"
      >
        <button
          type="button"
          class="w-full rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
          @click="close"
        >
          {{ t('showcase.publishModal.galleryPickerDone') }}
        </button>
      </div>
    </div>
  </SwissGlassCard>
</template>
