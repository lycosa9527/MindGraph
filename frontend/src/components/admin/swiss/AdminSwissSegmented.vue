<script setup lang="ts" generic="T extends string | number">
/**
 * Stone segmented control — plain buttons with radiogroup semantics.
 * Styles: admin-swiss-segmented.css → .admin-swiss-segmented / .admin-swiss-segment
 * Reference: settings language on/off segmented control.
 */
export type AdminSwissSegmentOption<T extends string | number = string | number> = {
  /** Pre-translated text. Used when there is no message key. */
  label?: string
  /** Message key. Bilingual chrome when dual-language mode is on. */
  labelKey?: string
  labelParams?: Record<string, unknown>
  value: T
  /** Optional count badge (e.g. moderation queue totals). */
  count?: number
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
    /** Disable all segments (e.g. while a ZhiHui job is running). */
    disabled?: boolean
  }>(),
  {
    ariaLabel: undefined,
    block: false,
    equal: false,
    fit: false,
    disabled: false,
  }
)

const model = defineModel<T>({ required: true })

const emit = defineEmits<{
  /** Fires on every segment click, including re-selecting the active value. */
  select: [value: T]
}>()

function onSegmentClick(value: T): void {
  model.value = value
  emit('select', value)
}
</script>

<template>
  <div
    class="admin-swiss-segmented"
    :class="{
      'admin-swiss-segmented--block': block,
      'admin-swiss-segmented--equal': equal,
      'admin-swiss-segmented--fit': fit,
      'admin-swiss-segmented--disabled': disabled,
    }"
    role="radiogroup"
    :aria-label="ariaLabel"
    :aria-disabled="disabled || undefined"
  >
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      role="radio"
      class="admin-swiss-segment"
      :class="{ 'is-active': model === opt.value }"
      :aria-checked="model === opt.value"
      :disabled="disabled"
      @click="onSegmentClick(opt.value)"
    >
      <span class="admin-swiss-segment-label">
        <I18nText
          v-if="opt.labelKey"
          :k="opt.labelKey"
          :params="opt.labelParams"
        />
        <template v-else>{{ opt.label }}</template>
      </span>
      <span
        v-if="opt.count != null && opt.count > 0"
        class="admin-swiss-segment-badge"
      >
        {{ opt.count }}
      </span>
    </button>
  </div>
</template>

<style src="@/styles/admin-swiss-segmented.css"></style>
