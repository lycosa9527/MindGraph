<script setup lang="ts">
/**
 * Insert menu — association line, summary, image, icon, link, equation.
 */
import { computed, nextTick, ref } from 'vue'

import { ElDropdown, ElTooltip } from 'element-plus'

import {
  Braces,
  ChevronDown,
  FunctionSquare,
  Image,
  Link2,
  Plus,
  Smile,
  Spline,
} from '@lucide/vue'

import CanvasMathInsertDialog from '@/components/canvas/CanvasMathInsertDialog.vue'
import { joinLabelAndMathSnippet } from '@/composables/core/markdownKatexDelimiter'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramStore } from '@/stores'
import { shouldReplaceLabelWithMathInsert } from '@/stores/diagram/diagramDefaultLabels'

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const mathOpen = ref(false)
const dropdownOpen = ref(false)
const hasNodeSelection = computed(() => diagramStore.selectedNodes.length > 0)
const hasTwoNodeSelection = computed(() => {
  const ids = diagramStore.selectedNodes.filter((id, index, list) => list.indexOf(id) === index)
  return ids.length >= 2
})

function closeMenu(): void {
  dropdownOpen.value = false
}

function comingSoon(): void {
  closeMenu()
  notify.info(t('canvas.ribbon.insertComingSoon'))
}

function requireNodeCount(min: number, action: () => void): void {
  const ids = diagramStore.selectedNodes.filter((id, index, list) => list.indexOf(id) === index)
  if (ids.length < min) {
    closeMenu()
    notify.warning(t('canvas.toolbar.selectNodesFirst'))
    return
  }
  action()
}

function insertAssociation(): void {
  closeMenu()
  const ids = diagramStore.selectedNodes.filter((id, index, list) => list.indexOf(id) === index)
  if (ids.length < 2) {
    notify.warning(t('canvas.ribbon.selectTwoNodes'))
    return
  }
  diagramStore.pushHistory(t('canvas.ribbon.assocLine'))
  const created = diagramStore.addConnection(ids[0], ids[1])
  if (!created) {
    notify.warning(t('canvas.ribbon.selectTwoNodes'))
  }
}

function openMath(): void {
  closeMenu()
  if (diagramStore.selectedNodes.length === 0) {
    notify.warning(t('canvas.toolbar.insertEquationSelectNode'))
    return
  }
  mathOpen.value = true
}

function onMathConfirm(latex: string): void {
  const trimmed = latex.trim()
  if (!trimmed) return
  const nodeId = diagramStore.selectedNodes[0]
  if (!nodeId) return
  const snippet = `$${trimmed}$`
  let consumed = false
  const unsub = eventBus.on('node_editor:insert_text_consumed', ({ nodeId: id }) => {
    if (id === nodeId) consumed = true
  })
  eventBus.emit('node_editor:insert_text', { nodeId, snippet })
  unsub()
  if (!consumed) {
    void nextTick(() => {
      const node = diagramStore.data?.nodes?.find((item) => item.id === nodeId)
      const base = String(node?.text ?? (node?.data as { label?: string } | undefined)?.label ?? '')
      const nextText =
        diagramStore.type && shouldReplaceLabelWithMathInsert(diagramStore.type, nodeId, base)
          ? snippet
          : joinLabelAndMathSnippet(base, snippet)
      eventBus.emit('node:text_updated', { nodeId, text: nextText })
    })
  }
}
</script>

<template>
  <ElTooltip
    :content="t('canvas.ribbon.tabInsert')"
    placement="bottom"
    :disabled="!props.compact"
  >
    <span class="inline-flex shrink-0">
      <ElDropdown
        v-model:visible="dropdownOpen"
        trigger="click"
        placement="bottom-start"
        popper-class="mm-toolbar-popper"
      >
        <button
          type="button"
          class="mm-btn"
          :aria-label="t('canvas.ribbon.tabInsert')"
        >
          <Plus class="w-4 h-4" />
          <span
            v-if="!props.compact"
            class="mm-btn__label"
            >{{ t('canvas.ribbon.tabInsert') }}</span
          >
          <ChevronDown
            :size="12"
            class="mm-btn__chevron"
          />
        </button>
        <template #dropdown>
          <div class="mm-panel mm-panel--list mm-panel--insert">
            <button
              type="button"
              class="mm-list-item"
              :class="{ 'is-dimmed': !hasTwoNodeSelection }"
              :aria-disabled="!hasTwoNodeSelection"
              @click="requireNodeCount(2, insertAssociation)"
            >
              <Spline class="w-4 h-4 shrink-0" />
              <span>{{ t('canvas.ribbon.assocLine') }}</span>
            </button>
            <button
              type="button"
              class="mm-list-item"
              :class="{ 'is-dimmed': !hasNodeSelection }"
              :aria-disabled="!hasNodeSelection"
              @click="requireNodeCount(1, comingSoon)"
            >
              <Braces class="w-4 h-4 shrink-0" />
              <span>{{ t('canvas.ribbon.summary') }}</span>
            </button>
            <button
              type="button"
              class="mm-list-item"
              :class="{ 'is-dimmed': !hasNodeSelection }"
              :aria-disabled="!hasNodeSelection"
              @click="requireNodeCount(1, comingSoon)"
            >
              <Image class="w-4 h-4 shrink-0" />
              <span>{{ t('canvas.ribbon.insertImage') }}</span>
            </button>
            <button
              type="button"
              class="mm-list-item"
              :class="{ 'is-dimmed': !hasNodeSelection }"
              :aria-disabled="!hasNodeSelection"
              @click="requireNodeCount(1, comingSoon)"
            >
              <Smile class="w-4 h-4 shrink-0" />
              <span>{{ t('canvas.ribbon.insertIcon') }}</span>
            </button>
            <button
              type="button"
              class="mm-list-item"
              :class="{ 'is-dimmed': !hasNodeSelection }"
              :aria-disabled="!hasNodeSelection"
              @click="requireNodeCount(1, comingSoon)"
            >
              <Link2 class="w-4 h-4 shrink-0" />
              <span>{{ t('canvas.ribbon.insertLink') }}</span>
            </button>
            <button
              type="button"
              class="mm-list-item"
              :class="{ 'is-dimmed': !hasNodeSelection }"
              :aria-disabled="!hasNodeSelection"
              @click="requireNodeCount(1, openMath)"
            >
              <FunctionSquare class="w-4 h-4 shrink-0" />
              <span>{{ t('canvas.toolbar.insertEquation') }}</span>
            </button>
          </div>
        </template>
      </ElDropdown>
    </span>
  </ElTooltip>
  <CanvasMathInsertDialog
    v-model="mathOpen"
    @confirm="onMathConfirm"
  />
</template>
