<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Search, X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'

const props = defineProps<{
  visible: boolean
  /** Keep picker open after each selection (diagram-case gallery). */
  multiSelect?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'select', diagram: SavedDiagram): void
}>()

const { t } = useLanguage()
const savedDiagramsStore = useSavedDiagramsStore()

const searchQuery = ref('')

const filteredDiagrams = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const list = savedDiagramsStore.diagrams
  if (!q) return list
  return list.filter((d) => d.title.toLowerCase().includes(q))
})

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      searchQuery.value = ''
      return
    }
    void savedDiagramsStore.fetchDiagrams().then((loaded) => {
      if (!loaded) return
      void savedDiagramsStore.prefetchDiagramSpecs(
        savedDiagramsStore.diagrams.map((d) => d.id)
      )
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

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN')
  } catch {
    return iso
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4"
      @click.self="close"
    >
      <div class="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        <div class="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h3 class="text-base font-bold text-gray-900">
            {{ t('caseSquare.publishModal.historyTitle') }}
          </h3>
          <button
            type="button"
            class="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            @click="close"
          >
            <X class="h-5 w-5" />
          </button>
        </div>

        <div class="border-b border-gray-100 px-5 py-3">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              v-model="searchQuery"
              type="text"
              :placeholder="t('caseSquare.publishModal.historySearch')"
              class="w-full rounded-xl border border-gray-100 py-2 pl-9 pr-4 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
            />
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-5">
          <p v-if="savedDiagramsStore.isLoading" class="py-8 text-center text-sm text-gray-400">…</p>
          <p
            v-else-if="filteredDiagrams.length === 0"
            class="py-8 text-center text-sm text-gray-400"
          >
            {{ t('caseSquare.publishModal.historyEmpty') }}
          </p>
          <div v-else class="grid grid-cols-3 gap-3">
            <button
              v-for="diagram in filteredDiagrams"
              :key="diagram.id"
              type="button"
              class="overflow-hidden rounded-xl border border-gray-100 text-left shadow-sm transition-all hover:border-gray-200 hover:shadow-md"
              @click="pick(diagram)"
            >
              <div
                class="flex h-20 items-center justify-center bg-gradient-to-br from-violet-400 to-purple-500"
              >
                <img
                  v-if="diagram.thumbnail"
                  :src="diagram.thumbnail"
                  :alt="diagram.title"
                  class="h-full w-full object-cover"
                />
              </div>
              <div class="p-2.5">
                <p class="truncate text-xs font-medium text-gray-900">{{ diagram.title }}</p>
                <p class="mt-0.5 truncate text-[10px] text-gray-400">
                  {{ diagram.diagram_type }} · {{ formatDate(diagram.updated_at) }}
                </p>
              </div>
            </button>
          </div>
        </div>

        <div
          v-if="multiSelect"
          class="border-t border-gray-100 px-5 py-3"
        >
          <button
            type="button"
            class="w-full rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
            @click="close"
          >
            {{ t('caseSquare.publishModal.galleryPickerDone') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
