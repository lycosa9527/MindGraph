<script setup lang="ts">
/**
 * Compact diagram pairing summary for Mobile Kitty bottom bar (camera · card · mic).
 */
defineProps<{
  /** First line e.g. "Current diagram: My topic" */
  primaryLine: string
  /** Optional second line type · scope id */
  metaLine?: string | null
  /** Hub bootstrap source badge (localized short label) */
  sourceBadge?: string | null
  /** Accessible label summarizing pairing state */
  ariaLabel: string
}>()
</script>

<template>
  <div
    class="kitty-mobile-diag-card flex flex-col justify-center rounded-xl border border-violet-200/70 bg-white/95 px-2 py-1.5 min-h-[4rem] min-w-0 shadow-sm"
    role="status"
    :aria-label="ariaLabel"
  >
    <div
      class="text-[10px] sm:text-[11px] font-semibold text-gray-900 leading-tight truncate"
      :title="primaryLine"
    >
      {{ primaryLine }}
    </div>
    <div
      v-if="metaLine"
      class="text-[9px] text-gray-500 leading-tight truncate mt-0.5"
      :title="metaLine"
    >
      {{ metaLine }}
    </div>
    <div
      v-if="sourceBadge"
      class="mt-0.5"
    >
      <span
        class="inline-block max-w-full truncate rounded px-1 py-0.5 text-[9px] font-medium bg-violet-100 text-violet-800 tabular-nums"
        :title="sourceBadge"
      >
        {{ sourceBadge }}
      </span>
    </div>
  </div>
</template>
