<script setup lang="ts">
import type { Component } from 'vue'

withDefaults(
  defineProps<{
    label: string
    icon?: Component
    variant?: 'label' | 'icon' | 'stacked'
    disabled?: boolean
    active?: boolean
    danger?: boolean
    primary?: boolean
    shortcut?: string
  }>(),
  {
    icon: undefined,
    variant: 'label',
    disabled: false,
    active: false,
    danger: false,
    primary: false,
    shortcut: '',
  }
)

const emit = defineEmits<{
  click: []
}>()
</script>

<template>
  <button
    type="button"
    class="v3-ribbon-cmd"
    :class="{
      'is-active': active,
      'is-danger': danger,
      'is-primary': primary,
      'is-icon': variant === 'icon',
      'is-stacked': variant === 'stacked' || (primary && Boolean(icon)),
    }"
    :disabled="disabled"
    :title="shortcut ? `${label} (${shortcut})` : label"
    @click="emit('click')"
  >
    <component
      :is="icon"
      v-if="icon"
      class="v3-ribbon-cmd__icon"
      :size="variant === 'icon' ? 16 : 18"
      :stroke-width="2.25"
    />
    <span
      v-if="variant !== 'icon'"
      class="v3-ribbon-cmd__label"
      >{{ label }}</span
    >
    <kbd
      v-if="shortcut && variant !== 'icon'"
      class="v3-ribbon-cmd__kbd"
      >{{ shortcut }}</kbd
    >
  </button>
</template>
