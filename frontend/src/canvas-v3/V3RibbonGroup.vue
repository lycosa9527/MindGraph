<script setup lang="ts">
import { computed, useSlots } from 'vue'

const props = withDefaults(
  defineProps<{
    group: string
    label: string
    classic?: boolean
  }>(),
  { classic: false }
)

const slots = useSlots()
const hasLead = computed(() => Boolean(slots.lead))
</script>

<template>
  <div
    class="v3-ribbon-group"
    :class="{ 'is-classic': props.classic }"
    :data-group="group"
  >
    <div class="v3-ribbon-group__row">
      <div
        v-if="hasLead"
        class="v3-ribbon-group__lead"
      >
        <slot name="lead" />
      </div>
      <div
        class="v3-ribbon-group__body"
        :class="{ 'is-classic': props.classic }"
      >
        <slot />
      </div>
    </div>
    <span
      v-if="props.classic"
      class="v3-ribbon-group__label"
      >{{ label }}</span
    >
  </div>
</template>
