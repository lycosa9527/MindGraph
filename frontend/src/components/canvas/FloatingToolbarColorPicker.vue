<script setup lang="ts">
/**
 * Node color popup: compact document palette plus native well.
 * The well is `#rrggbb` so mobile browsers paint the node color, not black.
 */
import { computed } from 'vue'

import {
  FLOATING_TOOLBAR_COLORS,
  FLOATING_TOOLBAR_COLOR_COLUMNS,
  FLOATING_TOOLBAR_THEME_ROWS,
} from '@/config/floatingToolbarColors'
import { hexColorsEqual } from '@/utils/colorFormat'

const props = defineProps<{
  currentColor: string
  nativeColor: string
}>()

const emit = defineEmits<{
  pick: [color: string]
}>()

const THEME_SWATCH_COUNT = FLOATING_TOOLBAR_COLOR_COLUMNS * FLOATING_TOOLBAR_THEME_ROWS

const themeColors = computed(() => FLOATING_TOOLBAR_COLORS.slice(0, THEME_SWATCH_COUNT))
const extraColors = computed(() => FLOATING_TOOLBAR_COLORS.slice(THEME_SWATCH_COUNT))

function swatchIsActive(color: string): boolean {
  return hexColorsEqual(props.currentColor, color)
}

function onCustomColor(ev: Event): void {
  emit('pick', (ev.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="nft-color-picker">
    <div class="nft-color-grid">
      <button
        v-for="(color, index) in themeColors"
        :key="`theme-${index}-${color}`"
        type="button"
        class="nft-palette-swatch"
        :class="{
          'nft-palette-swatch--active': swatchIsActive(color),
          'nft-palette-swatch--light': color.toLowerCase() === '#ffffff',
        }"
        :style="{ backgroundColor: color }"
        :aria-pressed="swatchIsActive(color)"
        :title="color"
        @click="emit('pick', color)"
      />
    </div>
    <div
      v-if="extraColors.length"
      class="nft-color-grid nft-color-grid--extra"
    >
      <button
        v-for="(color, index) in extraColors"
        :key="`extra-${index}-${color}`"
        type="button"
        class="nft-palette-swatch"
        :class="{ 'nft-palette-swatch--active': swatchIsActive(color) }"
        :style="{ backgroundColor: color }"
        :aria-pressed="swatchIsActive(color)"
        :title="color"
        @click="emit('pick', color)"
      />
    </div>
    <input
      type="color"
      class="nft-native-color"
      :value="nativeColor"
      :style="{ backgroundColor: nativeColor }"
      @input="onCustomColor"
    />
  </div>
</template>

<style scoped>
.nft-color-picker {
  /* 8 × 18px swatches + 7 × 3px gaps */
  width: 165px;
  box-sizing: border-box;
}

.nft-color-grid {
  display: grid;
  grid-template-columns: repeat(8, 18px);
  grid-auto-rows: 18px;
  gap: 3px;
  justify-content: start;
  margin-bottom: 6px;
}

.nft-color-grid--extra {
  padding-top: 6px;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
}

.nft-palette-swatch {
  box-sizing: border-box;
  width: 18px;
  height: 18px;
  min-width: 18px;
  min-height: 18px;
  margin: 0;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  cursor: pointer;
  padding: 0;
  flex: none;
}

.nft-palette-swatch--light {
  border-color: rgba(15, 23, 42, 0.22);
}

.nft-palette-swatch:hover {
  transform: scale(1.1);
  z-index: 1;
}

.nft-palette-swatch--active {
  outline: 2px solid #2563eb;
  outline-offset: 1px;
}

.nft-native-color {
  display: block;
  width: 100%;
  height: 28px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 6px;
  padding: 0;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  overflow: hidden;
}

.nft-native-color::-webkit-color-swatch-wrapper {
  padding: 0;
}

.nft-native-color::-webkit-color-swatch {
  border: none;
  border-radius: 5px;
}

.nft-native-color::-moz-color-swatch {
  border: none;
  border-radius: 5px;
}
</style>
