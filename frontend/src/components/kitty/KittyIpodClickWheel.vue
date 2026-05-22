<script setup lang="ts">
/**
 * Light iPod-style click wheel overlay for cycling Kitty diagram child nodes.
 */
import { computed, useTemplateRef } from 'vue'

import { useKittyClickWheel } from '@/composables/kitty/useKittyClickWheel'
import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  onSelectionChange?: () => void
}>()

const { t } = useLanguage()
const wheelRef = useTemplateRef<HTMLDivElement>('wheelRef')

const {
  children,
  hasNodes,
  activeIndex,
  activeChild,
  wheelRotationDeg,
  isDragging,
  onWheelRingPointerDown,
  onWheelRingPointerMove,
  onWheelRingPointerUp,
  onWheelRingWheel,
  tickRotationDeg,
} = useKittyClickWheel({
  onSelectionChange: () => props.onSelectionChange?.(),
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

function handlePointerDown(ev: PointerEvent): void {
  const el = wheelRef.value
  if (!el) {
    return
  }
  onWheelRingPointerDown(ev, el)
}

function handlePointerMove(ev: PointerEvent): void {
  const el = wheelRef.value
  if (!el) {
    return
  }
  onWheelRingPointerMove(ev, el)
}

function handlePointerUp(ev: PointerEvent): void {
  const el = wheelRef.value
  if (!el) {
    return
  }
  onWheelRingPointerUp(ev, el)
}
</script>

<template>
  <div
    v-if="hasNodes"
    class="kitty-click-wheel-host"
  >
    <div
      ref="wheelRef"
      class="kitty-click-wheel"
      :class="{ 'kitty-click-wheel--dragging': isDragging }"
      role="slider"
      :aria-label="t('mobile.kittyClickWheelAria', '滑动转盘选择节点')"
      :aria-valuemin="1"
      :aria-valuemax="children.length"
      :aria-valuenow="activeIndex + 1"
      :aria-valuetext="displayLabel"
      tabindex="0"
      @pointerdown="handlePointerDown"
      @pointermove="handlePointerMove"
      @pointerup="handlePointerUp"
      @pointercancel="handlePointerUp"
      @wheel.prevent="onWheelRingWheel"
    >
      <div
        class="kitty-click-wheel__dial"
        :style="{ transform: `rotate(${wheelRotationDeg}deg)` }"
        aria-hidden="true"
      >
        <span
          v-for="(child, idx) in children"
          :key="child.id"
          class="kitty-click-wheel__tick"
          :class="{ 'kitty-click-wheel__tick--active': idx === activeIndex }"
          :style="{ transform: `rotate(${tickRotationDeg(idx, children.length)}deg)` }"
        />
        <span class="kitty-click-wheel__indicator" />
      </div>

      <div class="kitty-click-wheel__center">
        <span class="kitty-click-wheel__label">{{ displayLabel }}</span>
        <span class="kitty-click-wheel__meta">{{ positionLabel }}</span>
      </div>
    </div>
    <p class="kitty-click-wheel__hint">
      {{ t('mobile.kittyClickWheelHint', '沿外圈滑动切换节点') }}
    </p>
  </div>
</template>

<style scoped>
.kitty-click-wheel-host {
  position: relative;
  z-index: 4;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  margin-top: 0.25rem;
  pointer-events: none;
}

.kitty-click-wheel {
  --wheel-size: min(9.5rem, 42vw);
  position: relative;
  width: var(--wheel-size);
  height: var(--wheel-size);
  border-radius: 9999px;
  pointer-events: auto;
  touch-action: none;
  user-select: none;
  background: radial-gradient(
    circle at 50% 42%,
    rgba(255, 255, 255, 0.72) 0%,
    rgba(255, 255, 255, 0.38) 58%,
    rgba(248, 250, 252, 0.22) 100%
  );
  border: 1px solid rgba(148, 163, 184, 0.28);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(6px);
  transition: box-shadow 0.18s ease, transform 0.18s ease;
}

.kitty-click-wheel--dragging {
  box-shadow:
    0 4px 14px rgba(79, 70, 229, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.75);
  transform: scale(1.02);
}

.kitty-click-wheel__dial {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  transition: transform 0.08s linear;
}

.kitty-click-wheel__tick {
  position: absolute;
  left: 50%;
  top: 0.42rem;
  width: 2px;
  height: 0.55rem;
  margin-left: -1px;
  transform-origin: 50% calc(var(--wheel-size) / 2 - 0.42rem);
  border-radius: 9999px;
  background: rgba(148, 163, 184, 0.45);
}

.kitty-click-wheel__tick--active {
  background: rgba(109, 40, 217, 0.85);
  height: 0.72rem;
  width: 3px;
  margin-left: -1.5px;
}

.kitty-click-wheel__indicator {
  position: absolute;
  left: 50%;
  top: 0.28rem;
  width: 4px;
  height: 0.85rem;
  margin-left: -2px;
  transform-origin: 50% calc(var(--wheel-size) / 2 - 0.28rem);
  border-radius: 9999px;
  background: linear-gradient(to bottom, #8b5cf6, #6366f1);
  box-shadow: 0 0 6px rgba(99, 102, 241, 0.35);
}

.kitty-click-wheel__center {
  position: absolute;
  inset: 38%;
  border-radius: 9999px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
  padding: 0.35rem;
  text-align: center;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(226, 232, 240, 0.75);
  pointer-events: none;
}

.kitty-click-wheel__label {
  width: 100%;
  font-size: clamp(0.625rem, 2.8vw, 0.75rem);
  font-weight: 600;
  line-height: 1.25;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.kitty-click-wheel__meta {
  font-size: 0.625rem;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.kitty-click-wheel__hint {
  margin: 0.45rem 0 0;
  font-size: 0.6875rem;
  color: rgba(100, 116, 139, 0.85);
  pointer-events: none;
}

.dark .kitty-click-wheel {
  background: radial-gradient(
    circle at 50% 42%,
    rgba(30, 41, 59, 0.72) 0%,
    rgba(30, 41, 59, 0.42) 58%,
    rgba(15, 23, 42, 0.28) 100%
  );
  border-color: rgba(71, 85, 105, 0.45);
}

.dark .kitty-click-wheel__center {
  background: rgba(15, 23, 42, 0.55);
  border-color: rgba(51, 65, 85, 0.75);
}

.dark .kitty-click-wheel__label {
  color: #e2e8f0;
}

.dark .kitty-click-wheel__meta,
.dark .kitty-click-wheel__hint {
  color: rgba(148, 163, 184, 0.9);
}
</style>
