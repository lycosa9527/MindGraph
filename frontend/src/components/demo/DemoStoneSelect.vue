<script setup lang="ts">
/**
 * Stone list menu for demo mode. The native select menu is clipped by the dialog.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ChevronDown } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'

export interface DemoStoneOption {
  value: string
  label: string
  labelKey?: string
  fontFamily?: string
  swatch?: string
}

const model = defineModel<string>({ required: true })

const props = withDefaults(
  defineProps<{
    options: DemoStoneOption[]
    placeholder: string
    menuLabel: string
    compact?: boolean
    narrow?: boolean
    mid?: boolean
    preserveSelection?: boolean
  }>(),
  {
    compact: false,
    narrow: false,
    mid: false,
    preserveSelection: false,
  }
)

const open = ref(false)
const root = ref<HTMLElement | null>(null)

const currentOption = computed(() => props.options.find((option) => option.value === model.value))

const currentLabel = computed(() => currentOption.value?.label ?? props.placeholder)

const currentSwatch = computed(() => currentOption.value?.swatch ?? '')

function toggle(): void {
  open.value = !open.value
}

function pick(value: string): void {
  model.value = value
  open.value = false
}

function keepFocus(event: MouseEvent): void {
  if (props.preserveSelection) event.preventDefault()
}

function onPointerDown(event: PointerEvent): void {
  const node = root.value
  if (!node || !open.value) return
  if (event.target instanceof Node && node.contains(event.target)) return
  open.value = false
}

watch(open, (isOpen) => {
  if (isOpen) document.addEventListener('pointerdown', onPointerDown)
  else document.removeEventListener('pointerdown', onPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPointerDown)
})
</script>

<template>
  <div
    ref="root"
    class="demo-stone-select"
    :class="{ 'is-compact': compact, 'is-narrow': narrow, 'is-mid': mid, 'is-open': open }"
  >
    <button
      type="button"
      class="demo-stone-select__button"
      :aria-label="menuLabel"
      :aria-expanded="open"
      @mousedown="keepFocus"
      @click="toggle"
    >
      <span class="demo-stone-select__value">
        <span
          v-if="currentSwatch"
          class="demo-stone-select__swatch"
          :style="{ background: currentSwatch }"
        />
        <I18nText
          v-if="currentOption?.labelKey"
          :k="currentOption.labelKey"
        />
        <template v-else>{{ currentLabel }}</template>
      </span>
      <ChevronDown class="h-4 w-4" />
    </button>
    <ul
      v-if="open"
      class="demo-stone-select__menu"
      role="listbox"
    >
      <li
        v-for="option in options"
        :key="option.value"
      >
        <button
          type="button"
          role="option"
          :aria-selected="model === option.value"
          :class="{ 'is-on': model === option.value }"
          :style="option.fontFamily ? { fontFamily: option.fontFamily } : undefined"
          @mousedown="keepFocus"
          @click="pick(option.value)"
        >
          <span
            v-if="option.swatch"
            class="demo-stone-select__swatch"
            :style="{ background: option.swatch }"
          />
          <I18nText
            v-if="option.labelKey"
            :k="option.labelKey"
          />
          <template v-else>{{ option.label }}</template>
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.demo-stone-select {
  position: relative;
  z-index: 1;
  flex: 0 1 auto;
}

.demo-stone-select.is-open {
  z-index: 40;
}

.demo-stone-select__button {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  width: 13rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.7rem;
  padding: 0.5rem 0.75rem;
  background: #fff;
  color: #1c1917;
  font: inherit;
  font-size: 0.875rem;
  cursor: pointer;
}

.is-compact .demo-stone-select__button {
  width: 9.25rem;
  padding: 0.35rem 0.55rem;
}

.is-narrow .demo-stone-select__button {
  width: 4.6rem;
  padding: 0.35rem 0.4rem;
}

.is-mid .demo-stone-select__button {
  width: 6.4rem;
  padding: 0.35rem 0.45rem;
}

.demo-stone-select__value {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.demo-stone-select__swatch {
  flex: 0 0 auto;
  width: 0.7rem;
  height: 0.7rem;
  border: 1px solid #e7e5e4;
  border-radius: 999px;
}

.demo-stone-select__button:focus-visible,
.demo-stone-select__menu button:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 1px #1c1917;
}

.demo-stone-select__menu {
  position: absolute;
  z-index: 40;
  top: calc(100% + 0.3rem);
  left: 0;
  width: max(100%, 5.5rem);
  max-height: 14rem;
  margin: 0;
  padding: 0.3rem;
  overflow: auto;
  list-style: none;
  border: 1px solid #e7e5e4;
  border-radius: 0.8rem;
  background: #fff;
  box-shadow: 0 14px 32px rgb(28 25 23 / 0.1);
}

.demo-stone-select__menu button {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  width: 100%;
  border: 0;
  border-radius: 0.5rem;
  padding: 0.45rem 0.6rem;
  background: transparent;
  color: #1c1917;
  font: inherit;
  font-size: 0.875rem;
  text-align: left;
  cursor: pointer;
}

.demo-stone-select__menu button.is-on,
.demo-stone-select__menu button:hover {
  background: #f5f5f4;
}
</style>
