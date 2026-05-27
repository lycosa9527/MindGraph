<script setup lang="ts">
/**
 * Edge-frame click wheel: large rounded rectangle near screen edges; mascot stays centered.
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
    class="kitty-frame-wheel-host"
  >
    <div
      ref="wheelRef"
      class="kitty-frame-wheel"
      :class="{ 'kitty-frame-wheel--dragging': isDragging }"
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
        class="kitty-frame-wheel__dial"
        :style="{ transform: `rotate(${wheelRotationDeg}deg)` }"
        aria-hidden="true"
      >
        <span
          v-for="(child, idx) in children"
          :key="child.id"
          class="kitty-frame-wheel__tick"
          :class="{ 'kitty-frame-wheel__tick--active': idx === activeIndex }"
          :style="{ transform: `rotate(${tickRotationDeg(idx, children.length)}deg)` }"
        />
        <span class="kitty-frame-wheel__indicator" />
      </div>

      <div class="kitty-frame-wheel__readout">
        <span class="kitty-frame-wheel__label">{{ displayLabel }}</span>
        <span class="kitty-frame-wheel__meta">{{ positionLabel }}</span>
      </div>
    </div>
    <p class="kitty-frame-wheel__hint">
      {{ t('mobile.kittyClickWheelHint', '沿外框滑动切换节点') }}
    </p>
  </div>
</template>

<style scoped>
.kitty-frame-wheel-host {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: stretch;
  pointer-events: none;
}

.kitty-frame-wheel {
  --frame-radius: clamp(1.1rem, 4vw, 1.75rem);
  --frame-band: clamp(2.75rem, 11vw, 4.25rem);
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  border-radius: var(--frame-radius);
  pointer-events: auto;
  touch-action: none;
  user-select: none;
  background: transparent;
  border: 3px solid rgba(148, 163, 184, 0.42);
  box-shadow:
    0 2px 10px rgba(15, 23, 42, 0.06),
    inset 0 0 0 1px rgba(255, 255, 255, 0.45),
    inset 0 0 24px rgba(248, 250, 252, 0.35);
  backdrop-filter: blur(4px);
  transition: box-shadow 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.kitty-frame-wheel::before {
  content: '';
  position: absolute;
  inset: var(--frame-band);
  border-radius: calc(var(--frame-radius) * 0.72);
  border: 1px dashed rgba(148, 163, 184, 0.28);
  pointer-events: none;
}

.kitty-frame-wheel--dragging {
  border-color: rgba(109, 40, 217, 0.55);
  box-shadow:
    0 6px 20px rgba(79, 70, 229, 0.14),
    inset 0 0 0 1px rgba(255, 255, 255, 0.55),
    inset 0 0 28px rgba(237, 233, 254, 0.45);
  transform: scale(1.005);
}

.kitty-frame-wheel__dial {
  position: absolute;
  inset: var(--frame-band);
  border-radius: inherit;
  transition: transform 0.08s linear;
  pointer-events: none;
}

.kitty-frame-wheel__tick {
  position: absolute;
  left: 50%;
  top: 0.15rem;
  width: 2px;
  height: clamp(0.45rem, 2vw, 0.65rem);
  margin-left: -1px;
  transform-origin: 50% calc(100% + 50% - 0.15rem);
  border-radius: 9999px;
  background: rgba(148, 163, 184, 0.5);
}

.kitty-frame-wheel__tick--active {
  background: rgba(109, 40, 217, 0.9);
  height: clamp(0.55rem, 2.4vw, 0.82rem);
  width: 3px;
  margin-left: -1.5px;
}

.kitty-frame-wheel__indicator {
  position: absolute;
  left: 50%;
  top: 0.05rem;
  width: 4px;
  height: clamp(0.55rem, 2.5vw, 0.85rem);
  margin-left: -2px;
  transform-origin: 50% calc(100% + 50% - 0.05rem);
  border-radius: 9999px;
  background: linear-gradient(to bottom, #8b5cf6, #6366f1);
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.4);
}

.kitty-frame-wheel__readout {
  position: absolute;
  left: 50%;
  bottom: clamp(0.55rem, 2.5vh, 1rem);
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.12rem;
  max-width: min(72%, 16rem);
  padding: 0.35rem 0.65rem;
  text-align: center;
  border-radius: 0.75rem;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(226, 232, 240, 0.85);
  pointer-events: none;
  backdrop-filter: blur(6px);
}

.kitty-frame-wheel__label {
  width: 100%;
  font-size: clamp(0.6875rem, 2.8vw, 0.8125rem);
  font-weight: 600;
  line-height: 1.25;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.kitty-frame-wheel__meta {
  font-size: 0.625rem;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.kitty-frame-wheel__hint {
  position: absolute;
  left: 50%;
  bottom: -1.35rem;
  transform: translateX(-50%);
  margin: 0;
  font-size: 0.6875rem;
  color: rgba(100, 116, 139, 0.85);
  pointer-events: none;
  white-space: nowrap;
}

.dark .kitty-frame-wheel {
  border-color: rgba(71, 85, 105, 0.55);
  box-shadow:
    0 2px 10px rgba(0, 0, 0, 0.2),
    inset 0 0 0 1px rgba(51, 65, 85, 0.65),
    inset 0 0 24px rgba(15, 23, 42, 0.35);
}

.dark .kitty-frame-wheel::before {
  border-color: rgba(71, 85, 105, 0.45);
}

.dark .kitty-frame-wheel__readout {
  background: rgba(15, 23, 42, 0.72);
  border-color: rgba(51, 65, 85, 0.85);
}

.dark .kitty-frame-wheel__label {
  color: #e2e8f0;
}

.dark .kitty-frame-wheel__meta,
.dark .kitty-frame-wheel__hint {
  color: rgba(148, 163, 184, 0.9);
}
</style>
