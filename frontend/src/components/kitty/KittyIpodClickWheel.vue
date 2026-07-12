<script setup lang="ts">
/**
 * Swipeable node chip row for Kitty — mirrors inline-recommendations tab chips.
 */
import { computed, nextTick, useTemplateRef, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useKittyClickWheel } from '@/composables/kitty/useKittyClickWheel'

const props = defineProps<{
  onSelectionChange?: () => void
  /** Re-tap active chip (e.g. open 学习提示). */
  onActiveRetap?: (node: { id: string; text: string }) => void
}>()

const { t } = useLanguage()
const scrollerRef = useTemplateRef<HTMLDivElement>('scrollerRef')

const { children, hasNodes, activeIndex, activeChild, selectById } = useKittyClickWheel({
  onSelectionChange: () => props.onSelectionChange?.(),
  onActiveRetap: (node) => props.onActiveRetap?.({ id: node.id, text: node.text }),
  // Mobile has no Vue Flow; canvasHighlight would loop through voice selection bus.
  canvasHighlight: false,
})

const displayLabel = computed(() => {
  const text = activeChild.value?.text?.trim() ?? ''
  if (text.length > 0) {
    return text
  }
  return t('mobile.kittyClickWheelEmptyLabel', '未命名节点')
})

const positionLabel = computed(() => {
  const total = children.value.length
  if (total <= 0) {
    return ''
  }
  return t('mobile.kittyClickWheelPosition', {
    current: activeIndex.value + 1,
    total,
  })
})

let programmaticScroll = false
let programmaticScrollClear: ReturnType<typeof setTimeout> | null = null
let scrollEndTimer: ReturnType<typeof setTimeout> | null = null

function chipLabel(text: string): string {
  const trimmed = text.trim()
  if (trimmed.length > 0) {
    return trimmed
  }
  return t('mobile.kittyClickWheelEmptyLabel', '未命名节点')
}

function scrollActiveIntoView(smooth: boolean): void {
  const root = scrollerRef.value
  if (!root) {
    return
  }
  const chip = root.querySelector<HTMLElement>(`[data-chip-index="${activeIndex.value}"]`)
  if (!chip) {
    return
  }
  programmaticScroll = true
  if (programmaticScrollClear != null) {
    clearTimeout(programmaticScrollClear)
  }
  chip.scrollIntoView({
    behavior: smooth ? 'smooth' : 'instant',
    inline: 'center',
    block: 'nearest',
  })
  programmaticScrollClear = setTimeout(() => {
    programmaticScroll = false
    programmaticScrollClear = null
  }, 280)
}

function onChipClick(nodeId: string): void {
  selectById(nodeId)
  void nextTick(() => scrollActiveIntoView(true))
}

/** Select the chip closest to the scroller center when its id changes. */
function selectNearestChip(): void {
  if (programmaticScroll) {
    return
  }
  const root = scrollerRef.value
  if (!root || children.value.length === 0) {
    return
  }
  const mid = root.scrollLeft + root.clientWidth / 2
  let bestIdx = activeIndex.value
  let bestDist = Number.POSITIVE_INFINITY
  const chips = root.querySelectorAll<HTMLElement>('[data-chip-index]')
  chips.forEach((el) => {
    const idxRaw = el.dataset.chipIndex
    if (idxRaw == null) {
      return
    }
    const idx = Number(idxRaw)
    if (!Number.isFinite(idx)) {
      return
    }
    const center = el.offsetLeft + el.offsetWidth / 2
    const dist = Math.abs(center - mid)
    if (dist < bestDist) {
      bestDist = dist
      bestIdx = idx
    }
  })
  const nearestId = children.value[bestIdx]?.id ?? ''
  if (!nearestId || bestIdx === activeIndex.value) {
    return
  }
  selectById(nearestId)
}

function onScrollerScroll(): void {
  selectNearestChip()
  if (scrollEndTimer != null) {
    clearTimeout(scrollEndTimer)
  }
  scrollEndTimer = setTimeout(() => {
    scrollEndTimer = null
    selectNearestChip()
  }, 120)
}

watch(
  activeIndex,
  () => {
    void nextTick(() => scrollActiveIntoView(true))
  },
  { flush: 'post' }
)
</script>

<template>
  <div
    v-if="hasNodes"
    class="kitty-chip-host"
  >
    <div class="kitty-chip-readout">
      <span class="kitty-chip-readout__label">{{ displayLabel }}</span>
      <span class="kitty-chip-readout__meta">{{ positionLabel }}</span>
    </div>

    <div
      ref="scrollerRef"
      class="kitty-chip-scroller"
      role="listbox"
      :aria-label="t('mobile.kittyClickWheelAria', '滑动选择节点')"
      @scroll="onScrollerScroll"
    >
      <button
        v-for="(child, idx) in children"
        :key="child.id"
        type="button"
        class="kitty-chip"
        :class="{ 'kitty-chip--active': idx === activeIndex }"
        role="option"
        :aria-selected="idx === activeIndex"
        :data-chip-index="idx"
        @click="onChipClick(child.id)"
      >
        <span class="kitty-chip__index">{{ idx + 1 }}</span>
        <span class="kitty-chip__text">{{ chipLabel(child.text) }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.kitty-chip-host {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.3rem;
  width: 100%;
  padding: 0 0.25rem;
}

.kitty-chip-readout {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.05rem;
  text-align: center;
  min-height: 2.1rem;
}

.kitty-chip-readout__label {
  width: 100%;
  font-size: clamp(0.875rem, 3.4vw, 1rem);
  font-weight: 650;
  line-height: 1.25;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kitty-chip-readout__meta {
  font-size: 0.625rem;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.kitty-chip-scroller {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  padding: 0.2rem 0.5rem;
  scrollbar-width: none;
}

.kitty-chip-scroller::-webkit-scrollbar {
  display: none;
}

.kitty-chip {
  flex: 0 0 auto;
  scroll-snap-align: center;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  max-width: 9.5rem;
  padding: 0.35rem 0.55rem;
  border-radius: 0.5rem;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(248, 250, 252, 0.95);
  color: #64748b;
  font-size: 0.75rem;
  line-height: 1.2;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.kitty-chip__index {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: #94a3b8;
}

.kitty-chip__text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kitty-chip--active {
  color: #0f172a;
  background: rgba(220, 252, 231, 0.95);
  border-color: rgba(74, 222, 128, 0.85);
}

.kitty-chip--active .kitty-chip__index {
  color: #16a34a;
}

.dark .kitty-chip-readout__label {
  color: #f1f5f9;
}

.dark .kitty-chip-readout__meta {
  color: rgba(148, 163, 184, 0.9);
}

.dark .kitty-chip {
  background: rgba(30, 41, 59, 0.85);
  border-color: rgba(71, 85, 105, 0.9);
  color: #94a3b8;
}

.dark .kitty-chip--active {
  color: #ecfdf5;
  background: rgba(6, 78, 59, 0.55);
  border-color: rgba(52, 211, 153, 0.65);
}
</style>
