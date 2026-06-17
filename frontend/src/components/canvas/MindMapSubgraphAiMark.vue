<script setup lang="ts">
/**
 * Compact colorful "AI" wordmark + sparkles for mind-map subgraph generation.
 */
import { Loader2, Sparkles } from '@lucide/vue'

defineProps<{
  loading?: boolean
}>()
</script>

<template>
  <span
    class="mg-subgraph-ai-mark"
    :class="{ 'mg-subgraph-ai-mark--loading': loading }"
    aria-hidden="true"
  >
    <span class="mg-subgraph-ai-mark__letters">AI</span>
    <Loader2
      v-if="loading"
      class="mg-subgraph-ai-mark__sparkles mg-subgraph-ai-mark__sparkles--spin"
      :stroke-width="2.25"
    />
    <Sparkles
      v-else
      class="mg-subgraph-ai-mark__sparkles"
      :stroke-width="2.25"
    />
  </span>
</template>

<style scoped>
.mg-subgraph-ai-mark {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  line-height: 1;
  user-select: none;
}

.mg-subgraph-ai-mark__letters {
  font-family: 'Inter', 'Space Grotesk', ui-sans-serif, system-ui, sans-serif;
  font-size: 11px;
  font-weight: 800;
  font-style: italic;
  letter-spacing: -0.06em;
  line-height: 1;
  padding-right: 1px;
  background: linear-gradient(
    120deg,
    #2563eb 0%,
    #6366f1 38%,
    #a855f7 68%,
    #ec4899 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 0 6px rgba(99, 102, 241, 0.22));
  transition: filter 0.2s ease, opacity 0.2s ease;
}

.mg-subgraph-ai-mark__sparkles {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  color: #8b5cf6;
  filter: drop-shadow(0 0 4px rgba(139, 92, 246, 0.42));
  transition: color 0.2s ease, transform 0.2s ease, filter 0.2s ease;
}

.mg-subgraph-ai-mark__sparkles--spin {
  color: #6366f1;
  animation: mg-subgraph-ai-spin 0.85s linear infinite;
}

.mg-subgraph-ai-mark--loading .mg-subgraph-ai-mark__letters {
  opacity: 0.72;
  filter: none;
}

@keyframes mg-subgraph-ai-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
