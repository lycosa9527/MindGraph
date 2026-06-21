<script setup lang="ts">
/**
 * Traveling conic-gradient ring for LLM load phases (sending / waiting / streaming).
 * Shared by MindMate avatar; canvas AIModelSelector uses inline CSS (future refactor target).
 */
import { computed } from 'vue'

import type { ModelLoadPhase } from '@/stores/llmResults'

import { isActiveLlmPhaseRing } from '@/utils/llmLoadPhase'

export type LlmPhaseRingStreamingVariant = 'primary' | 'qwen' | 'deepseek' | 'doubao'

const props = withDefaults(
  defineProps<{
    phase?: ModelLoadPhase
    active?: boolean
    borderRadius?: string
    streamingVariant?: LlmPhaseRingStreamingVariant
    ringPadding?: string
  }>(),
  {
    phase: 'idle',
    active: true,
    borderRadius: '8px',
    streamingVariant: 'primary',
    ringPadding: '2px',
  }
)

const showRing = computed(() => props.active && isActiveLlmPhaseRing(props.phase))

const ringClass = computed(() => {
  if (!showRing.value) {
    return ['llm-phase-ring']
  }
  const classes = ['llm-phase-ring', 'llm-phase-ring--active']
  if (props.phase === 'sending') {
    classes.push('phase-sending')
  } else if (props.phase === 'waiting') {
    classes.push('phase-waiting')
  } else if (props.phase === 'streaming') {
    classes.push('phase-streaming', `phase-streaming--${props.streamingVariant}`)
  }
  return classes
})

const ringStyle = computed(() => ({
  borderRadius: props.borderRadius,
  '--llm-phase-ring-padding': props.ringPadding,
}))
</script>

<template>
  <div
    :class="ringClass"
    :style="ringStyle"
  >
    <slot />
  </div>
</template>

<style scoped>
@property --llm-phase-ring-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.llm-phase-ring {
  position: relative;
  display: inline-flex;
  flex-shrink: 0;
}

.llm-phase-ring--active {
  overflow: visible;
}

.llm-phase-ring--active::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: var(--llm-phase-ring-padding, 2px);
  --llm-phase-ring-angle: 0deg;
  pointer-events: none;
  z-index: 1;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: llm-phase-ring-spin 2.5s linear infinite;
}

.llm-phase-ring--active > :deep(*) {
  position: relative;
  z-index: 0;
}

.llm-phase-ring--active.phase-sending::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(16, 185, 129, 0.15) 0deg,
    rgba(16, 185, 129, 0.08) 50deg,
    #86efac 130deg,
    #22c55e 180deg,
    #4ade80 230deg,
    rgba(16, 185, 129, 0.08) 310deg,
    rgba(16, 185, 129, 0.15) 360deg
  );
}

.llm-phase-ring--active.phase-waiting::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(16, 185, 129, 0.15) 0deg,
    rgba(16, 185, 129, 0.08) 50deg,
    #93c5fd 130deg,
    #3b82f6 180deg,
    #60a5fa 230deg,
    rgba(16, 185, 129, 0.08) 310deg,
    rgba(16, 185, 129, 0.15) 360deg
  );
}

.llm-phase-ring--active.phase-streaming.phase-streaming--primary::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(64, 158, 255, 0.2) 0deg,
    rgba(226, 232, 240, 0.85) 55deg,
    #79bbff 130deg,
    #409eff 180deg,
    #66b1ff 230deg,
    rgba(226, 232, 240, 0.85) 305deg,
    rgba(64, 158, 255, 0.2) 360deg
  );
}

.llm-phase-ring--active.phase-streaming.phase-streaming--qwen::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(99, 102, 241, 0.2) 0deg,
    rgba(226, 232, 240, 0.85) 55deg,
    #a5b4fc 130deg,
    #6366f1 180deg,
    #818cf8 230deg,
    rgba(226, 232, 240, 0.85) 305deg,
    rgba(99, 102, 241, 0.2) 360deg
  );
}

.llm-phase-ring--active.phase-streaming.phase-streaming--deepseek::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(16, 185, 129, 0.2) 0deg,
    rgba(226, 232, 240, 0.85) 55deg,
    #6ee7b7 130deg,
    #10b981 180deg,
    #34d399 230deg,
    rgba(226, 232, 240, 0.85) 305deg,
    rgba(16, 185, 129, 0.2) 360deg
  );
}

.llm-phase-ring--active.phase-streaming.phase-streaming--doubao::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(249, 115, 22, 0.2) 0deg,
    rgba(226, 232, 240, 0.85) 55deg,
    #fdba74 130deg,
    #f97316 180deg,
    #fb923c 230deg,
    rgba(226, 232, 240, 0.85) 305deg,
    rgba(249, 115, 22, 0.2) 360deg
  );
}

@keyframes llm-phase-ring-spin {
  to {
    --llm-phase-ring-angle: 360deg;
  }
}

.dark .llm-phase-ring--active.phase-sending::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(52, 211, 153, 0.12) 0deg,
    rgba(31, 41, 55, 0.9) 50deg,
    #4ade80 130deg,
    #16a34a 180deg,
    #86efac 230deg,
    rgba(31, 41, 55, 0.9) 310deg,
    rgba(52, 211, 153, 0.12) 360deg
  );
}

.dark .llm-phase-ring--active.phase-waiting::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(52, 211, 153, 0.12) 0deg,
    rgba(31, 41, 55, 0.9) 50deg,
    #60a5fa 130deg,
    #2563eb 180deg,
    #38bdf8 230deg,
    rgba(31, 41, 55, 0.9) 310deg,
    rgba(52, 211, 153, 0.12) 360deg
  );
}

.dark .llm-phase-ring--active.phase-streaming.phase-streaming--primary::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(64, 158, 255, 0.25) 0deg,
    rgba(31, 41, 55, 0.95) 55deg,
    #66b1ff 130deg,
    #409eff 180deg,
    #79bbff 230deg,
    rgba(31, 41, 55, 0.95) 305deg,
    rgba(64, 158, 255, 0.25) 360deg
  );
}

.dark .llm-phase-ring--active.phase-streaming.phase-streaming--qwen::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(99, 102, 241, 0.25) 0deg,
    rgba(31, 41, 55, 0.95) 55deg,
    #818cf8 130deg,
    #6366f1 180deg,
    #a78bfa 230deg,
    rgba(31, 41, 55, 0.95) 305deg,
    rgba(99, 102, 241, 0.25) 360deg
  );
}

.dark .llm-phase-ring--active.phase-streaming.phase-streaming--deepseek::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(16, 185, 129, 0.25) 0deg,
    rgba(31, 41, 55, 0.95) 55deg,
    #34d399 130deg,
    #10b981 180deg,
    #6ee7b7 230deg,
    rgba(31, 41, 55, 0.95) 305deg,
    rgba(16, 185, 129, 0.25) 360deg
  );
}

.dark .llm-phase-ring--active.phase-streaming.phase-streaming--doubao::before {
  background: conic-gradient(
    from var(--llm-phase-ring-angle) at 50% 50%,
    rgba(249, 115, 22, 0.25) 0deg,
    rgba(31, 41, 55, 0.95) 55deg,
    #fb923c 130deg,
    #f97316 180deg,
    #fdba74 230deg,
    rgba(31, 41, 55, 0.95) 305deg,
    rgba(249, 115, 22, 0.25) 360deg
  );
}
</style>
