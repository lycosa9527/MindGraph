<script setup lang="ts" generic="T extends string | number">
/**
 * Stone segmented control — plain buttons with radiogroup semantics.
 * Styles: admin-swiss-segmented.css → .admin-swiss-segmented / .admin-swiss-segment
 * Reference: LanguageSettingsModal canvas mode toggle (classic / new).
 */
export type AdminSwissSegmentOption<T extends string | number = string | number> = {
  label: string
  value: T
}

withDefaults(
  defineProps<{
    options: AdminSwissSegmentOption<T>[]
    ariaLabel?: string
    /** Full-width equal segments (long labels). */
    block?: boolean
    /** Equal-width inline segments (short labels). */
    equal?: boolean
    /** Width follows label text (no equal flex columns). */
    fit?: boolean
  }>(),
  {
    ariaLabel: undefined,
    block: false,
    equal: false,
    fit: false,
  }
)

const model = defineModel<T>({ required: true })
</script>

<template>
  <div
    class="admin-swiss-segmented"
    :class="{
      'admin-swiss-segmented--block': block,
      'admin-swiss-segmented--equal': equal,
      'admin-swiss-segmented--fit': fit,
    }"
    role="radiogroup"
    :aria-label="ariaLabel"
  >
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      role="radio"
      class="admin-swiss-segment"
      :class="{ 'is-active': model === opt.value }"
      :aria-checked="model === opt.value"
      @click="model = opt.value"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<style src="@/styles/admin-swiss-segmented.css"></style>
