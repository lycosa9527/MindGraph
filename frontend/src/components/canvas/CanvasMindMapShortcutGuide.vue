<script setup lang="ts">
/**
 * Collapsible mind-map keyboard shortcut guide — sits left of the bottom toolbar.
 */
import { computed, onMounted, ref } from 'vue'

import { ChevronDown, ChevronUp, Hand, Keyboard, MousePointer2 } from '@lucide/vue'

import { useLanguage } from '@/composables'

const STORAGE_KEY = 'mindgraph.mindmap.shortcutGuide.expanded'

type ShortcutRow =
  | {
      id: string
      labelKey: string
      kind: 'keys'
      keys: string[]
    }
  | {
      id: string
      labelKey: string
      kind: 'edit'
    }
  | {
      id: string
      labelKey: string
      kind: 'arrows'
    }
  | {
      id: string
      labelKey: string
      kind: 'hint'
      hintKey: string
      icon: 'mouse' | 'hand'
    }

const { t } = useLanguage()

const expanded = ref(true)

const rows = computed((): ShortcutRow[] => [
  { id: 'tab', labelKey: 'canvas.shortcutGuide.addChild', kind: 'keys', keys: ['Tab'] },
  { id: 'enter', labelKey: 'canvas.shortcutGuide.addSibling', kind: 'keys', keys: ['Enter'] },
  { id: 'edit', labelKey: 'canvas.shortcutGuide.editText', kind: 'edit' },
  { id: 'delete', labelKey: 'canvas.shortcutGuide.deleteNode', kind: 'keys', keys: ['Delete', 'Backspace'] },
  { id: 'arrows', labelKey: 'canvas.shortcutGuide.selectNav', kind: 'arrows' },
  { id: 'undo', labelKey: 'canvas.shortcutGuide.undo', kind: 'keys', keys: ['Ctrl+Z'] },
  {
    id: 'multiSelect',
    labelKey: 'canvas.shortcutGuide.multiSelect',
    kind: 'hint',
    hintKey: 'canvas.shortcutGuide.multiSelectHint',
    icon: 'mouse',
  },
  {
    id: 'canvasPan',
    labelKey: 'canvas.shortcutGuide.canvasPan',
    kind: 'hint',
    hintKey: 'canvas.shortcutGuide.canvasPanHint',
    icon: 'hand',
  },
])

onMounted(() => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored !== null) {
      expanded.value = stored === 'true'
    }
  } catch {
    /* ignore private mode */
  }
})

function toggleExpanded(): void {
  expanded.value = !expanded.value
  try {
    localStorage.setItem(STORAGE_KEY, String(expanded.value))
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <div class="select-none shrink-0">
    <!-- Collapsed pill -->
    <button
      v-if="!expanded"
      type="button"
      class="inline-flex items-center gap-2 rounded-xl border border-gray-200/80 bg-white/90 dark:border-gray-600/80 dark:bg-gray-800/90 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 shadow-lg backdrop-blur-md transition-all hover:border-slate-300 hover:bg-white dark:hover:bg-gray-800"
      :aria-expanded="false"
      :aria-label="t('canvas.shortcutGuide.title')"
      @click="toggleExpanded"
    >
      <Keyboard
        class="shrink-0 text-blue-500"
        :size="15"
        :stroke-width="2"
      />
      <span class="whitespace-nowrap">{{ t('canvas.shortcutGuide.title') }}</span>
      <ChevronUp
        class="shrink-0 text-slate-400"
        :size="14"
        :stroke-width="2"
      />
    </button>

    <!-- Expanded card -->
    <Transition name="shortcut-guide-card">
      <div
        v-if="expanded"
        class="shortcut-guide-card w-60 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-600 dark:bg-gray-900"
      >
        <div
          class="flex items-center justify-between gap-2 border-b border-slate-100 px-3 pb-1 pt-2 dark:border-slate-700"
        >
          <div class="flex min-w-0 items-center gap-2">
            <Keyboard
              class="shrink-0 text-blue-500"
              :size="15"
              :stroke-width="2"
            />
            <span class="truncate text-xs font-bold text-slate-800 dark:text-slate-100">
              {{ t('canvas.shortcutGuide.title') }}
            </span>
          </div>
          <button
            type="button"
            class="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200/80 bg-slate-50 text-slate-500 transition-colors hover:border-slate-300 hover:bg-white hover:text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400"
            :aria-label="t('canvas.shortcutGuide.collapse')"
            @click="toggleExpanded"
          >
            <ChevronDown
              :size="14"
              :stroke-width="2"
            />
          </button>
        </div>

        <ul class="flex flex-col gap-1 px-2 pb-1.5 pt-0">
          <li
            v-for="row in rows"
            :key="row.id"
            class="flex items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50/80 px-2 py-1.5 dark:border-slate-700/80 dark:bg-slate-800/60"
          >
            <span class="text-xs text-slate-700 dark:text-slate-200">
              {{ t(row.labelKey) }}
            </span>

            <div
              v-if="row.kind === 'keys'"
              class="flex shrink-0 items-center gap-1"
            >
              <kbd
                v-for="(key, index) in row.keys"
                :key="`${row.id}-${index}`"
                class="shortcut-kbd"
              >
                {{ key }}
              </kbd>
            </div>

            <div
              v-else-if="row.kind === 'edit'"
              class="flex shrink-0 items-center gap-1"
            >
              <kbd class="shortcut-kbd">Space</kbd>
              <span class="text-[10px] text-slate-400">{{ t('canvas.shortcutGuide.doubleClick') }}</span>
            </div>

            <kbd
              v-else-if="row.kind === 'arrows'"
              class="shortcut-kbd shortcut-kbd--group"
            >
              ↑ ↓ ← →
            </kbd>

            <div
              v-else
              class="flex max-w-[52%] shrink-0 items-center justify-end gap-1 text-right"
            >
              <MousePointer2
                v-if="row.icon === 'mouse'"
                class="shrink-0 text-blue-500"
                :size="13"
                :stroke-width="2"
              />
              <Hand
                v-else
                class="shrink-0 text-blue-500"
                :size="13"
                :stroke-width="2"
              />
              <span class="text-[10px] leading-tight text-slate-500 dark:text-slate-400">
                {{ t(row.hintKey) }}
              </span>
            </div>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.shortcut-kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 1.25rem;
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
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.08);
}

.shortcut-kbd--group {
  padding-inline: 0.375rem;
  letter-spacing: 0.02em;
}

:global(.dark) .shortcut-kbd {
  border-color: rgb(75 85 99);
  background: rgb(30 41 59);
  color: rgb(226 232 240);
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.25);
}

.shortcut-guide-card-enter-active,
.shortcut-guide-card-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.22s ease;
  transform-origin: bottom left;
}

.shortcut-guide-card-enter-from,
.shortcut-guide-card-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.shortcut-guide-card-enter-to,
.shortcut-guide-card-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}
</style>
