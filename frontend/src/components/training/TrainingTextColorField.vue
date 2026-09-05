<script setup lang="ts">
import { FLOATING_TOOLBAR_COLORS } from '@/config/floatingToolbarColors'

defineProps<{
  label: string
  value: string
  open: boolean
  kind: 'ink' | 'stroke'
}>()

const emit = defineEmits<{
  toggle: []
  pick: [color: string]
}>()

function onCustom(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  emit('pick', target.value)
}
</script>

<template>
  <div class="text-color">
    <button
      type="button"
      class="text-color__btn"
      :class="{ 'is-on': open }"
      :title="label"
      :aria-label="label"
      :aria-expanded="open"
      @click="emit('toggle')"
    >
      <span
        v-if="kind === 'ink'"
        class="text-color__letter"
        :style="{ color: value }"
        >A</span
      >
      <span
        v-else
        class="text-color__ring"
        :style="{ borderColor: value }"
      />
    </button>
    <div
      v-if="open"
      class="text-color__panel"
    >
      <div class="text-color__grid">
        <button
          v-for="color in FLOATING_TOOLBAR_COLORS"
          :key="`${kind}-${color}`"
          type="button"
          class="text-color__swatch"
          :class="{ 'is-current': color === value }"
          :style="{ backgroundColor: color }"
          :aria-label="color"
          @click="emit('pick', color)"
        />
      </div>
      <input
        type="color"
        class="text-color__native"
        :value="value"
        :aria-label="label"
        @input="onCustom"
      />
    </div>
  </div>
</template>

<style scoped>
.text-color {
  position: relative;
}
.text-color__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  border: 0;
  border-radius: 0.3rem;
  background: transparent;
  cursor: pointer;
}
.text-color__btn:hover,
.text-color__btn.is-on {
  background: #fef3c7;
}
.text-color__letter {
  font-size: 0.78rem;
  font-weight: 800;
  line-height: 1;
}
.text-color__ring {
  width: 0.72rem;
  height: 0.72rem;
  border: 2px solid #1c1917;
  border-radius: 2px;
  background: #fffef8;
}
.text-color__panel {
  position: absolute;
  top: calc(100% + 0.28rem);
  right: 0;
  z-index: 6;
  width: 8.6rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.5rem;
  background: #fff;
  padding: 0.4rem;
  box-shadow: 0 8px 20px rgb(28 25 23 / 0.12);
}
.text-color__grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.22rem;
}
.text-color__swatch {
  width: 100%;
  aspect-ratio: 1;
  border: 1px solid #e7e5e4;
  border-radius: 2px;
  padding: 0;
  cursor: pointer;
}
.text-color__swatch.is-current {
  outline: 2px solid #ca8a04;
  outline-offset: 1px;
}
.text-color__native {
  display: block;
  width: 100%;
  height: 1.35rem;
  margin-top: 0.35rem;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
</style>
