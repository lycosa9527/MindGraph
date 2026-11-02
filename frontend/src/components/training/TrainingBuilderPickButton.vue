<script setup lang="ts">
/**
 * Ribbon choice button. The current label sits on the button; the menu matches
 * the gallery language picker (centered rows, check on the selected item).
 */
import { computed, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Check, ChevronDown } from '@lucide/vue'

import '@/components/mindgraph/mindgraphLangSwitcher.css'

const props = defineProps<{
  modelValue: string
  options: readonly { value: string; label: string }[]
  ariaLabel: string
}>()

const emit = defineEmits<{
  change: [value: string]
}>()

const open = ref(false)

const currentLabel = computed(() => {
  const match = props.options.find((row) => row.value === props.modelValue)
  return match?.label || props.ariaLabel
})

function onCommand(value: string | number | object): void {
  if (typeof value !== 'string') return
  emit('change', value)
}
</script>

<template>
  <ElDropdown
    trigger="click"
    popper-class="builder-pick-popper mindgraph-lang-switcher-popper"
    @command="onCommand"
    @visible-change="open = $event"
  >
    <button
      type="button"
      class="builder-pick"
      :class="{ 'is-open': open }"
      :title="currentLabel"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      aria-haspopup="listbox"
    >
      <slot name="icon" />
      <span class="builder-pick__label">{{ currentLabel }}</span>
      <ChevronDown
        class="builder-pick__chevron"
        :class="{ 'is-open': open }"
        :size="12"
        aria-hidden="true"
      />
    </button>
    <template #dropdown>
      <ElDropdownMenu class="mindgraph-lang-switcher__menu">
        <ElDropdownItem
          v-for="row in options"
          :key="row.value || 'none'"
          :command="row.value"
        >
          <span class="mindgraph-lang-switcher__row">
            <span class="mindgraph-lang-switcher__label">{{ row.label }}</span>
            <Check
              v-if="row.value === modelValue"
              class="mindgraph-lang-switcher__check"
              :size="16"
              aria-hidden="true"
            />
          </span>
        </ElDropdownItem>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</template>

<style scoped>
.builder-pick {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: min(24rem, 46vw);
  min-height: 28px;
  padding: 3px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #4b5563;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  cursor: pointer;
}
.builder-pick:hover,
.builder-pick.is-open {
  background: #e5e7eb;
  color: #1f2937;
}
.builder-pick__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.builder-pick__chevron {
  flex-shrink: 0;
  transition: transform 0.12s ease;
}
.builder-pick__chevron.is-open {
  transform: rotate(180deg);
}
:global(.dark) .builder-pick {
  color: #d1d5db;
}
:global(.dark) .builder-pick:hover,
:global(.dark) .builder-pick.is-open {
  background: #374151;
  color: #f9fafb;
}

/* Size the menu to the longest label. The language picker stays a fixed width. */
:global(.builder-pick-popper.mindgraph-lang-switcher-popper.el-popper) {
  width: max-content !important;
  min-width: max-content !important;
  max-width: min(32rem, calc(100vw - 24px)) !important;
}

:global(.builder-pick-popper.mindgraph-lang-switcher-popper .el-dropdown-menu) {
  width: max-content !important;
  min-width: max-content !important;
  max-width: none !important;
}

:global(.builder-pick-popper.mindgraph-lang-switcher-popper .mindgraph-lang-switcher__row) {
  width: max-content;
  max-width: none;
}

:global(.builder-pick-popper .mindgraph-lang-switcher__label) {
  width: auto;
  max-width: min(30rem, calc(100vw - 72px));
  white-space: nowrap;
  word-break: normal;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
