<script setup lang="ts">
/**
 * Film-style caption strip — max 3 visible lines (2 committed + 1 forming).
 *
 * The pill is draggable: grab the grip bar at the top to reposition.
 * Double-click the grip to snap back to the default bottom-centre position.
 *
 * Teleported to <body> so it floats above all presentation layers.
 */
import { computed, ref } from 'vue'
import { useDraggable, useWindowSize } from '@vueuse/core'

interface CaptionLine {
  /** Stable numeric ID (global index in committedLines). Used as TransitionGroup key. */
  id: number
  text: string
}

const props = defineProps<{
  visible: boolean
  /** Last 2 committed sentences with stable IDs — produced by the parent. */
  lines: CaptionLine[]
  /** Currently streaming sentence. Empty string when idle. */
  live: string
}>()

// ── drag ────────────────────────────────────────────────────────────────────
const pillRef = ref<HTMLElement | null>(null)
const gripRef = ref<HTMLElement | null>(null)
const { width: winW, height: winH } = useWindowSize()

/** Pill occupies 90% of window width. */
const pillW = computed(() => winW.value * 0.9)

/** Default top-left position: horizontally centred, near the bottom. */
const defaultPos = computed(() => ({
  x: (winW.value - pillW.value) / 2,
  y: winH.value - 110,
}))

const hasDragged = ref(false)

const { x, y, isDragging } = useDraggable(pillRef, {
  handle: gripRef,
  initialValue: defaultPos,
  onMove(pos) {
    hasDragged.value = true
    // Clamp so the pill stays fully in the viewport
    const pad = 8
    pos.x = Math.max(pad, Math.min(winW.value - pillW.value - pad, pos.x))
    pos.y = Math.max(pad, Math.min(winH.value - 60, pos.y))
  },
})

function resetPosition(): void {
  hasDragged.value = false
  x.value = defaultPos.value.x
  y.value = defaultPos.value.y
}

const pillStyle = computed(() => {
  if (!hasDragged.value) {
    return {
      position: 'fixed' as const,
      left: `${defaultPos.value.x}px`,
      top: `${defaultPos.value.y}px`,
      width: `${pillW.value}px`,
    }
  }
  return {
    position: 'fixed' as const,
    left: `${x.value}px`,
    top: `${y.value}px`,
    width: `${pillW.value}px`,
  }
})

// ── content ─────────────────────────────────────────────────────────────────

/** Graduated opacity: oldest fades most, giving depth to the stack. */
function lineOpacity(idx: number): number {
  const total = props.lines.length
  if (total <= 1) return 0.55
  return idx === 0 ? 0.38 : 0.58
}

const showListening = computed(
  () => props.visible && props.lines.length === 0 && !props.live.trim()
)
</script>

<template>
  <Teleport to="body">
    <Transition name="sub-mount">
      <div
        v-if="visible"
        ref="pillRef"
        class="subtitle-pill"
        :style="pillStyle"
        :class="{ 'is-dragging': isDragging }"
        aria-live="polite"
        aria-atomic="false"
      >
        <!-- Drag grip -->
        <div
          ref="gripRef"
          class="drag-grip"
          title="Drag to reposition · double-click to reset"
          @dblclick="resetPosition"
        >
          <span class="grip-dots" />
        </div>

        <!-- Listening pulse — connected but silent -->
        <Transition name="dots-fade">
          <div v-if="showListening" class="dots-row">
            <span class="listening-dots" aria-label="listening">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </span>
          </div>
        </Transition>

        <!-- Committed lines + live sentence -->
        <TransitionGroup name="caption-line" tag="div" class="captions-stack">
          <p
            v-for="(line, idx) in lines"
            :key="line.id"
            class="caption-line caption-past"
            :style="{ opacity: lineOpacity(idx) }"
          >
            {{ line.text }}
          </p>
          <p
            v-if="live.trim()"
            key="live"
            class="caption-line caption-live"
          >
            {{ live }}
          </p>
        </TransitionGroup>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ── pill container ─────────────────────────────────────────────── */
.subtitle-pill {
  z-index: 120;
  border-radius: 1rem;
  padding: 0 2.5rem 1rem;
  background: rgba(55, 55, 58, 0.9);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  box-shadow:
    0 4px 24px rgba(0, 0, 0, 0.45),
    0 1px 4px rgba(0, 0, 0, 0.3);
  user-select: none;
  transition: box-shadow 0.15s ease;
}

.subtitle-pill.is-dragging {
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.55),
    0 2px 8px rgba(0, 0, 0, 0.4);
  cursor: grabbing;
}

/* ── drag grip ──────────────────────────────────────────────────── */
.drag-grip {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 1.4rem;
  cursor: grab;
  opacity: 0.3;
  transition: opacity 0.2s ease;
  margin-bottom: 0.2rem;
}

.drag-grip:hover {
  opacity: 0.7;
}

.drag-grip:active {
  cursor: grabbing;
}

/* Six-dot grid icon */
.grip-dots {
  display: grid;
  grid-template-columns: repeat(3, 5px);
  grid-template-rows: repeat(2, 5px);
  gap: 3px;
}

.grip-dots::before,
.grip-dots::after {
  display: none; /* dots rendered via box-shadow */
}

.grip-dots {
  width: 20px;
  height: 12px;
  background-image:
    radial-gradient(circle, #fff 2px, transparent 2px),
    radial-gradient(circle, #fff 2px, transparent 2px),
    radial-gradient(circle, #fff 2px, transparent 2px),
    radial-gradient(circle, #fff 2px, transparent 2px),
    radial-gradient(circle, #fff 2px, transparent 2px),
    radial-gradient(circle, #fff 2px, transparent 2px);
  background-size: 8px 6px;
  background-position:
    0 0, 8px 0, 16px 0,
    0 6px, 8px 6px, 16px 6px;
  background-repeat: no-repeat;
}

/* ── captions stack ─────────────────────────────────────────────── */
.captions-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1em;
  position: relative;
}

.caption-line {
  margin: 0;
  padding: 0.1em 0;
  font-size: 1.45rem;
  font-weight: 500;
  line-height: 1.35;
  letter-spacing: 0.01em;
  word-break: break-word;
  color: #fff;
  text-align: center;
  width: 100%;
  text-shadow:
    0 1px 6px rgba(0, 0, 0, 0.55),
    0 0 1px rgba(0, 0, 0, 0.3);
}

.caption-live {
  opacity: 1;
}

/* ── TransitionGroup animations ─────────────────────────────────── */
.caption-line-enter-active {
  transition:
    opacity 0.3s ease,
    transform 0.35s cubic-bezier(0.22, 1.2, 0.36, 1);
}

.caption-line-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
  position: absolute;
  width: 100%;
  left: 0;
  text-align: center;
}

.caption-line-move {
  transition: transform 0.35s ease;
}

.caption-line-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.caption-line-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── listening dots ─────────────────────────────────────────────── */
.dots-row {
  display: flex;
  justify-content: center;
}

.dots-fade-enter-active,
.dots-fade-leave-active {
  transition: opacity 0.3s ease;
}
.dots-fade-enter-from,
.dots-fade-leave-to {
  opacity: 0;
}

.listening-dots {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 2.4rem;
}

.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.45);
  animation: dot-pulse 1.5s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-pulse {
  0%, 80%, 100% { opacity: 0.25; transform: scale(0.85); }
  40%            { opacity: 1;    transform: scale(1.15); }
}

/* ── mount / unmount ────────────────────────────────────────────── */
.sub-mount-enter-active,
.sub-mount-leave-active {
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;
}
.sub-mount-enter-from {
  opacity: 0;
  transform: translateY(14px);
}
.sub-mount-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
