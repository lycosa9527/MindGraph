<script setup lang="ts">
/**
 * Collapsible Kitty node-action library — same card style as shortcut / voice guides.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ChevronDown, ListTree } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { formatKittyVoiceCommandLabel } from '@/composables/kitty/kittyVoiceCommandLabels'
import { ONE_SENTENCE_NODE_ACTION_GUIDE_ROWS } from '@/config/oneSentenceNodeActionGuide'

const props = withDefaults(
  defineProps<{
    /** CSS selector for click targets that should not dismiss the guide (e.g. Kitty mascot). */
    excludeSelector?: string
  }>(),
  {
    excludeSelector: '',
  }
)

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  (e: 'select', example: string): void
}>()

const { t } = useLanguage()
const rootRef = ref<HTMLElement | null>(null)

const rows = computed(() =>
  ONE_SENTENCE_NODE_ACTION_GUIDE_ROWS.map((row) => {
    const raw = formatKittyVoiceCommandLabel(row.action, undefined, (key, params) =>
      t(key, params ?? {})
    )
    return {
      id: row.id,
      label: raw.replace(/[：:]\s*$/u, '').trim() || raw,
      example: t(row.exampleKey),
    }
  })
)

function close(): void {
  open.value = false
}

function onSelect(example: string): void {
  emit('select', example)
  close()
}

function onDocumentPointerDown(event: PointerEvent): void {
  if (!open.value) {
    return
  }
  const root = rootRef.value
  const target = event.target
  if (!(target instanceof Node) || !root) {
    return
  }
  if (root.contains(target)) {
    return
  }
  if (
    props.excludeSelector
    && target instanceof Element
    && target.closest(props.excludeSelector)
  ) {
    return
  }
  close()
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && open.value) {
    close()
  }
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('pointerdown', onDocumentPointerDown, true)
    document.addEventListener('keydown', onDocumentKeydown)
  } else {
    document.removeEventListener('pointerdown', onDocumentPointerDown, true)
    document.removeEventListener('keydown', onDocumentKeydown)
  }
})

onMounted(() => {
  if (open.value) {
    document.addEventListener('pointerdown', onDocumentPointerDown, true)
    document.addEventListener('keydown', onDocumentKeydown)
  }
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  document.removeEventListener('keydown', onDocumentKeydown)
})
</script>

<template>
  <div
    ref="rootRef"
    class="one-sentence-node-action-guide select-none"
  >
    <Transition name="one-sentence-node-action-guide-card">
      <div
        v-if="open"
        class="one-sentence-node-action-guide-card w-60 overflow-hidden rounded-xl border border-violet-200/80 bg-white shadow-lg"
        role="dialog"
        :aria-label="t('canvas.mindMapOneSentence.nodeActionGuide.title')"
      >
        <div
          class="flex items-center justify-between gap-2 border-b border-violet-100 px-3 pb-1 pt-2"
        >
          <div class="flex min-w-0 items-center gap-2">
            <ListTree
              class="shrink-0 text-violet-500"
              :size="15"
              :stroke-width="2"
            />
            <span class="truncate text-xs font-bold text-slate-800">
              {{ t('canvas.mindMapOneSentence.nodeActionGuide.title') }}
            </span>
          </div>
          <button
            type="button"
            class="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200/80 bg-slate-50 text-slate-500 transition-colors hover:border-slate-300 hover:bg-white hover:text-slate-700"
            :aria-label="t('canvas.mindMapOneSentence.nodeActionGuide.collapse')"
            @click="close"
          >
            <ChevronDown
              :size="14"
              :stroke-width="2"
            />
          </button>
        </div>

        <ul class="flex max-h-[min(40vh,15rem)] flex-col gap-1 overflow-y-auto px-2 pb-1.5 pt-0">
          <li
            v-for="row in rows"
            :key="row.id"
          >
            <button
              type="button"
              class="flex w-full flex-col gap-0.5 rounded-md border border-violet-50 bg-violet-50/60 px-2 py-1.5 text-left transition-colors hover:border-violet-200 hover:bg-violet-50"
              @click="onSelect(row.example)"
            >
              <span class="text-xs font-medium text-slate-700">
                {{ row.label }}
              </span>
              <span class="text-[10px] leading-snug text-slate-500">
                {{ row.example }}
              </span>
            </button>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.one-sentence-node-action-guide-card-enter-active,
.one-sentence-node-action-guide-card-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.22s ease;
  transform-origin: bottom left;
}

.one-sentence-node-action-guide-card-enter-from,
.one-sentence-node-action-guide-card-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.one-sentence-node-action-guide-card-enter-to,
.one-sentence-node-action-guide-card-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}
</style>
