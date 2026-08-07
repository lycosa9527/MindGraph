<script setup lang="ts">
/**
 * Mindmap-only library picker for 图示生图 header.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { ChevronDown } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

const props = defineProps<{
  modelValue: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [id: string | null]
  select: [diagram: SavedDiagram]
}>()

const { t } = useLanguage()
const authStore = useAuthStore()
const store = useSavedDiagramsStore()
const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const mindmaps = computed(() =>
  store.diagrams.filter((d) => {
    const type = (d.diagram_type || '').toLowerCase().replace('-', '_')
    return type === 'mindmap' || type === 'mind_map'
  })
)

const selected = computed(
  () => mindmaps.value.find((d) => d.id === props.modelValue) ?? null
)

const label = computed(() => {
  if (selected.value?.title) return selected.value.title
  return String(t('zhihui.diagram.selectMindmap'))
})

function onDocumentPointerDown(event: MouseEvent): void {
  const root = rootRef.value
  if (!root || !open.value) return
  const target = event.target
  if (target instanceof Node && !root.contains(target)) {
    open.value = false
  }
}

onMounted(() => {
  if (authStore.isAuthenticated) {
    void store.fetchDiagrams()
  }
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
})

function toggle(): void {
  if (props.disabled) return
  open.value = !open.value
}

function pick(diagram: SavedDiagram): void {
  emit('update:modelValue', diagram.id)
  emit('select', diagram)
  open.value = false
}
</script>

<template>
  <div
    ref="rootRef"
    class="zhihui-diagram-dropdown relative min-w-0"
  >
    <button
      type="button"
      class="flex max-w-xs items-center gap-1 truncate rounded-lg border border-stone-200 bg-white px-2.5 py-1.5 text-xs text-stone-700 hover:bg-stone-50 disabled:opacity-50"
      :disabled="disabled"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="truncate">{{ label }}</span>
      <ChevronDown class="h-3.5 w-3.5 shrink-0 text-stone-400" />
    </button>
    <div
      v-if="open"
      class="absolute left-0 top-full z-20 mt-1 max-h-64 w-72 overflow-auto rounded-xl border border-stone-200 bg-white py-1 shadow-lg"
      role="listbox"
    >
      <div
        v-if="store.isLoading"
        class="px-3 py-2 text-xs text-stone-400"
      >
        {{ t('common.loading') }}
      </div>
      <div
        v-else-if="mindmaps.length === 0"
        class="px-3 py-2 text-xs text-stone-400"
      >
        {{ t('zhihui.diagram.emptyLibrary') }}
      </div>
      <button
        v-for="diagram in mindmaps"
        :key="diagram.id"
        type="button"
        class="flex w-full px-3 py-2 text-left text-xs text-stone-700 hover:bg-stone-50"
        :class="{ 'bg-stone-100': diagram.id === modelValue }"
        role="option"
        @click="pick(diagram)"
      >
        <span class="truncate">{{ diagram.title || t('sidebar.history.untitled') }}</span>
      </button>
    </div>
  </div>
</template>
