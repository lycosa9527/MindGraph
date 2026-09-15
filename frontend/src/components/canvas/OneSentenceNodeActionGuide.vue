<script setup lang="ts">
/**
 * Collapsible Kitty node-action library — same card / row style as the shortcut guide.
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
    const example = String(t(row.exampleKey))
    const chips = chipsForRow(row.id)
    return {
      id: row.id,
      label: raw.replace(/[：:]\s*$/u, '').trim() || raw,
      example,
      pills: chips.length ? chips : [{ id: 'example', label: example, phrase: example }],
    }
  })
)

function chipsForRow(rowId: string): GuideChip[] {
  if (rowId === 'explain_node') {
    return [
      {
        id: 'by_label',
        label: String(t('canvas.mindMapOneSentence.nodeActionGuide.chip.byName')),
        phrase: String(t('canvas.mindMapOneSentence.suggestion.explain_node')),
      },
      {
        id: 'this_node',
        label: String(t('canvas.mindMapOneSentence.nodeActionGuide.chip.thisNode')),
        phrase: String(t('canvas.mindMapOneSentence.suggestion.explain_node.this')),
      },
    ]
  }
  if (rowId === 'update_node') {
    return [
      {
        id: 'by_label',
        label: String(t('canvas.mindMapOneSentence.nodeActionGuide.chip.byName')),
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
        class="one-sentence-node-action-guide-card w-60 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-600 dark:bg-gray-900"
        role="dialog"
        :aria-label="t('canvas.mindMapOneSentence.nodeActionGuide.title')"
      >
        <div
          class="flex items-center justify-between gap-2 border-b border-slate-100 px-3 pb-1 pt-2 dark:border-slate-700"
        >
          <div class="flex min-w-0 items-center gap-2">
            <ListTree
              class="shrink-0 text-blue-500"
              :size="15"
              :stroke-width="2"
            />
            <span class="truncate text-xs font-bold text-slate-800 dark:text-slate-100">
              {{ t('canvas.mindMapOneSentence.nodeActionGuide.title') }}
            </span>
          </div>
          <button
            type="button"
            class="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200/80 bg-slate-50 text-slate-500 transition-colors hover:border-slate-300 hover:bg-white hover:text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400"
            :aria-label="t('canvas.mindMapOneSentence.nodeActionGuide.collapse')"
            @click="close"
          >
            <ChevronDown
              :size="14"
              :stroke-width="2"
            />
          </button>
        </div>

        <ul class="flex max-h-[min(50vh,17.5rem)] flex-col gap-1 overflow-y-auto px-2 pb-1.5 pt-0">
          <li
            v-for="row in rows"
            :key="row.id"
            class="flex items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50/80 px-2 py-1.5 dark:border-slate-700/80 dark:bg-slate-800/60"
          >
            <button
              type="button"
              class="min-w-0 truncate text-left text-xs text-slate-700 dark:text-slate-200"
              @click="onSelect(row.pills[0]?.phrase || row.example)"
            >
              {{ row.label }}
            </button>
            <div class="flex max-w-[58%] shrink-0 flex-wrap items-center justify-end gap-1">
              <button
                v-for="pill in row.pills"
                :key="pill.id"
                type="button"
                class="node-action-kbd"
                @click="onSelect(pill.phrase)"
              >
                {{ pill.label }}
              </button>
            </div>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.node-action-kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 1.25rem;
  max-width: 100%;
  padding: 0.125rem 0.375rem;
  border: 1px solid rgb(226 232 240);
  border-radius: 0.25rem;
  background: rgb(255 255 255);
  color: rgb(51 65 85);
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.08);
}

:global(.dark) .node-action-kbd {
  border-color: rgb(75 85 99);
  background: rgb(30 41 59);
  color: rgb(226 232 240);
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.25);
}

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
