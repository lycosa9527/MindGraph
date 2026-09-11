<script setup lang="ts">
/**
 * Collapsible Kitty node-action library — same card style as shortcut / voice guides.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ChevronDown, ListTree } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { formatKittyVoiceCommandLabel } from '@/composables/kitty/kittyVoiceCommandLabels'
import { AI_CONTENT_LEVEL_IDS } from '@/config/aiContentLevels'
import {
  ONE_SENTENCE_NODE_ACTION_GUIDE_ROWS,
  VOICE_NUMBERING_STYLE_IDS,
} from '@/config/oneSentenceNodeActionGuide'

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

type GuideChip = { id: string; label: string; phrase: string }

const rows = computed(() =>
  ONE_SENTENCE_NODE_ACTION_GUIDE_ROWS.map((row) => {
    const raw = formatKittyVoiceCommandLabel(row.action, undefined, (key, params) =>
      t(key, params ?? {})
    )
    return {
      id: row.id,
      label: raw.replace(/[：:]\s*$/u, '').trim() || raw,
      example: t(row.exampleKey),
      hint:
        row.id === 'set_content_level'
          ? t('canvas.mindMapOneSentence.suggestion.set_content_level.hint')
          : row.id === 'set_branch_numbering'
            ? t('canvas.mindMapOneSentence.suggestion.set_branch_numbering.hint')
            : row.id === 'update_node'
              ? t('canvas.mindMapOneSentence.suggestion.update_node.hint')
              : '',
      chips: chipsForRow(row.id),
    }
  })
)

function chipsForRow(rowId: string): GuideChip[] {
  if (rowId === 'update_node') {
    return [
      {
        id: 'by_label',
        label: String(t('canvas.mindMapOneSentence.suggestion.update_node')),
        phrase: String(t('canvas.mindMapOneSentence.suggestion.update_node')),
      },
      {
        id: 'by_number',
        label: '2.1',
        phrase: String(t('canvas.mindMapOneSentence.suggestion.update_node.by_number')),
      },
    ]
  }
  if (rowId === 'set_content_level') {
    return AI_CONTENT_LEVEL_IDS.map((id) => {
      const title = String(t(`canvas.toolbar.professionalContent.level.${id}.title`))
      return {
        id,
        label: title,
        phrase: String(
          t('canvas.mindMapOneSentence.suggestion.set_content_level.phrase', { level: title })
        ),
      }
    })
  }
  if (rowId === 'set_branch_numbering') {
    const styles = VOICE_NUMBERING_STYLE_IDS.map((id) => {
      const title = String(t(`canvas.mindMapOneSentence.suggestion.set_branch_numbering.style.${id}`))
      return {
        id,
        label: title,
        phrase: String(
          t('canvas.mindMapOneSentence.suggestion.set_branch_numbering.phrase', { style: title })
        ),
      }
    })
    return [
      ...styles,
      {
        id: 'on',
        label: String(t('canvas.toolbar.mindMapAppearanceNumberingEnable')),
        phrase: String(t('canvas.mindMapOneSentence.suggestion.set_branch_numbering.on')),
      },
      {
        id: 'off',
        label: String(t('canvas.toolbar.mindMapAppearanceNumberingHide')),
        phrase: String(t('canvas.mindMapOneSentence.suggestion.set_branch_numbering_off')),
      },
    ]
  }
  return []
}

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
            <div
              class="flex w-full flex-col gap-0.5 rounded-md border border-violet-50 bg-violet-50/60 px-2 py-1.5 text-left"
            >
              <button
                type="button"
                class="flex flex-col gap-0.5 text-left transition-colors hover:text-violet-800"
                @click="onSelect(row.chips[0]?.phrase || row.example)"
              >
                <span class="text-xs font-medium text-slate-700">
                  {{ row.label }}
                </span>
                <span class="text-[10px] leading-snug text-slate-500">
                  {{ row.hint || row.example }}
                </span>
              </button>
              <div
                v-if="row.chips.length"
                class="mt-0.5 flex flex-wrap gap-1"
              >
                <button
                  v-for="chip in row.chips"
                  :key="chip.id"
                  type="button"
                  class="rounded border border-violet-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-violet-700 transition-colors hover:border-violet-400 hover:bg-violet-50"
                  @click="onSelect(chip.phrase)"
                >
                  {{ chip.label }}
                </button>
              </div>
            </div>
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
