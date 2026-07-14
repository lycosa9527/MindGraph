<script setup lang="ts">
import { computed, ref, type Component } from 'vue'

import { onClickOutside } from '@vueuse/core'

import { ChevronDown } from '@lucide/vue'

export interface ShowcaseFilterOption {
  value: string
  label: string
}

const props = withDefaults(
  defineProps<{
    label?: string
    modelValue: string
    options: ShowcaseFilterOption[]
    allLabel?: string
    prefixIcon?: Component
    /** labeled: "学科：全部" | plain: icon + current label only */
    variant?: 'labeled' | 'plain'
    /** When false, omit the "全部" option (e.g. sort dropdown). */
    includeAll?: boolean
    /** Sort panel uses w-40; filter dropdowns use w-48. */
    panelSize?: 'md' | 'sm'
    /** Stretch trigger to full container width (publish form). */
    block?: boolean
  }>(),
  {
    variant: 'labeled',
    allLabel: '全部',
    includeAll: true,
    panelSize: 'md',
    block: false,
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

const displayValue = computed(() => {
  if (!props.modelValue) return props.allLabel
  return props.options.find((o) => o.value === props.modelValue)?.label ?? props.modelValue
})

const allOptions = computed(() =>
  props.includeAll
    ? [{ value: '', label: props.allLabel }, ...props.options]
    : props.options
)

const panelWidthClass = computed(() => (props.panelSize === 'sm' ? 'w-40' : 'w-48'))

function select(value: string) {
  emit('update:modelValue', value)
  open.value = false
}

function isSelected(value: string): boolean {
  return props.modelValue === value
}

onClickOutside(rootRef, () => {
  open.value = false
})
</script>

<template>
  <div ref="rootRef" :class="['relative', block ? 'w-full' : '']">
    <button
      type="button"
      :class="['showcase-dropdown-trigger', block ? 'w-full justify-between' : '']"
      @click="open = !open"
    >
      <component
        :is="prefixIcon"
        v-if="prefixIcon"
        class="h-3.5 w-3.5 shrink-0 text-gray-500"
      />
      <template v-if="variant === 'labeled' && label">
        <span class="text-gray-500">{{ label }}：</span>
        <span class="font-medium text-gray-800">{{ displayValue }}</span>
      </template>
      <span v-else class="font-medium text-gray-800">{{ displayValue }}</span>
      <ChevronDown
        class="h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform"
        :class="open ? 'rotate-180' : ''"
      />
    </button>

    <div
      v-if="open"
      :class="['showcase-dropdown-panel', block ? 'w-full min-w-0' : panelWidthClass]"
    >
      <div class="showcase-dropdown-scroll max-h-64 overflow-y-auto py-1">
        <button
          v-for="opt in allOptions"
          :key="opt.value || '__all__'"
          type="button"
          class="showcase-dropdown-item"
          :class="isSelected(opt.value) ? 'showcase-dropdown-item--active' : ''"
          @click="select(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.showcase-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  height: 2.25rem;
  padding: 0 1rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: #374151;
  background: #fff;
  border: none;
  border-radius: 0.75rem;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  outline: none;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.showcase-dropdown-trigger:hover {
  background: #f9fafb;
}

.showcase-dropdown-trigger:focus,
.showcase-dropdown-trigger:focus-visible {
  outline: none;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
}

/* 无实线边框，靠柔和阴影浮起（参考图） */
.showcase-dropdown-panel {
  position: absolute;
  left: 0;
  top: calc(100% + 4px);
  z-index: 20;
  padding: 0.375rem;
  background: #fff;
  border: none;
  border-radius: 0.75rem;
  box-shadow:
    0 4px 6px -1px rgb(0 0 0 / 0.06),
    0 12px 24px -6px rgb(0 0 0 / 0.08);
}

.showcase-dropdown-item {
  display: block;
  width: 100%;
  margin: 0.125rem 0;
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: #4b5563;
  text-align: left;
  background: transparent;
  border: none;
  border-radius: 0.5rem;
  outline: none;
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.showcase-dropdown-item:hover {
  background: #f9fafb;
  color: #374151;
}

.showcase-dropdown-item:focus,
.showcase-dropdown-item:focus-visible {
  outline: none;
  box-shadow: none;
}

.showcase-dropdown-item--active {
  background: #f3f4f6;
  font-weight: 500;
  color: #111827;
}

.showcase-dropdown-scroll::-webkit-scrollbar {
  width: 5px;
}

.showcase-dropdown-scroll::-webkit-scrollbar-track {
  margin: 4px 0;
  background: transparent;
}

.showcase-dropdown-scroll::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 9999px;
}

.showcase-dropdown-scroll::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
