<script setup lang="ts">
/**
 * Full-width generate action with 思维讲堂 busy ring + fill.
 */
import { Sparkles } from '@lucide/vue'

import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'

const props = withDefaults(
  defineProps<{
    busy: boolean
    disabled: boolean
    label: string
    title?: string
    block?: boolean
  }>(),
  { title: '', block: true }
)

const emit = defineEmits<{
  click: []
}>()
</script>

<template>
  <LlmPhaseRing
    class="ai-busy-generate-ring !flex"
    :class="props.block ? 'w-full' : 'ai-busy-generate-ring--inline'"
    :phase="props.busy ? 'waiting' : 'idle'"
    :active="props.busy"
    border-radius="10px"
    streaming-variant="primary"
    ring-padding="2px"
  >
    <button
      type="button"
      class="ai-busy-generate-btn"
      :class="{ 'is-busy': props.busy, 'ai-busy-generate-btn--inline': !props.block }"
      :disabled="props.disabled"
      :aria-busy="props.busy"
      :title="props.title || undefined"
      @click="emit('click')"
    >
      <Sparkles
        class="h-4 w-4 shrink-0"
        :stroke-width="2"
      />
      <span class="ai-busy-generate-btn__label">{{ props.label }}</span>
    </button>
  </LlmPhaseRing>
</template>

<style scoped>
.ai-busy-generate-ring {
  display: flex;
  width: 100%;
}

.ai-busy-generate-ring--inline {
  width: auto;
}

.ai-busy-generate-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: 44px;
  padding: 10px 16px;
  border: 1px solid var(--swiss-ink, #1c1917);
  border-radius: 10px;
  background: var(--swiss-ink, #1c1917);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: #fafaf9;
  cursor: pointer;
  overflow: hidden;
  transition:
    opacity 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease;
}

.ai-busy-generate-btn--inline {
  width: auto;
  min-width: 8.5rem;
}

.ai-busy-generate-btn__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-busy-generate-btn:hover:not(:disabled) {
  background: #292524;
  border-color: #292524;
}

.ai-busy-generate-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ai-busy-generate-btn.is-busy {
  position: relative;
  background: #1e3a8a;
  border-color: transparent;
  box-shadow: none;
}

.ai-busy-generate-btn.is-busy::after {
  content: '';
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: 2px;
  width: 0;
  max-width: calc(100% - 4px);
  border-radius: 8px;
  pointer-events: none;
  z-index: 0;
  background: linear-gradient(90deg, #1d4ed8 0%, #2563eb 40%, #3b82f6 72%, #93c5fd 100%);
  animation: ai-busy-generate-fill 12s ease-out forwards;
}

.ai-busy-generate-btn.is-busy > * {
  position: relative;
  z-index: 1;
}

.ai-busy-generate-btn.is-busy:disabled {
  opacity: 1;
  cursor: wait;
}

.ai-busy-generate-btn.is-busy .ai-busy-generate-btn__label {
  text-shadow: 0 1px 2px rgb(15 23 42 / 0.35);
}

@keyframes ai-busy-generate-fill {
  to {
    width: 88%;
  }
}

.ai-gen-shell .ai-busy-generate-btn {
  background: var(--ai-ribbon-fill);
  border-color: transparent;
}

.ai-gen-shell .ai-busy-generate-btn:hover:not(:disabled) {
  background: var(--ai-ribbon-fill);
  border-color: transparent;
  filter: brightness(1.06);
}

.ai-gen-shell .ai-busy-generate-btn.is-busy,
.ai-gen-shell .ai-busy-generate-btn.is-busy:hover:not(:disabled) {
  background: #1e3a8a;
  filter: none;
}
</style>
