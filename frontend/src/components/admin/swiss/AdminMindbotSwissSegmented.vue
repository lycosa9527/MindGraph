<script setup lang="ts" generic="T extends string | number">
/**
 * MindBot geek segmented control — plain buttons with radiogroup semantics.
 * Use inside `.mindbot-swiss-dialog` (styles in admin-mindbot-swiss-dialog-chrome.css).
 */
export type MindbotSwissSegmentOption<T extends string | number = string | number> = {
  label: string
  value: T
}

withDefaults(
  defineProps<{
    options: MindbotSwissSegmentOption<T>[]
    ariaLabel?: string
    /** Full-width equal segments (long labels). */
    block?: boolean
  }>(),
  {
    ariaLabel: undefined,
    block: false,
  }
)

const model = defineModel<T>({ required: true })
</script>

<template>
  <div
    class="mindbot-swiss-segmented"
    :class="{ 'mindbot-swiss-segmented--block': block }"
    role="radiogroup"
    :aria-label="ariaLabel"
  >
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      role="radio"
      class="mindbot-swiss-segment"
      :class="{ 'is-active': model === opt.value }"
      :aria-checked="model === opt.value"
      @click="model = opt.value"
    >
      {{ opt.label }}
    </button>
  </div>
</template>
