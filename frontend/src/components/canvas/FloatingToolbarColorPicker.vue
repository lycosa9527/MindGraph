<script setup lang="ts">
/**
 * Node color popup: palette plus native well.
 * The well is `#rrggbb` so mobile browsers paint the node color, not black.
 */
import { FLOATING_TOOLBAR_COLORS } from '@/config/floatingToolbarColors'
import { hexColorsEqual } from '@/utils/colorFormat'

const props = defineProps<{
  currentColor: string
  nativeColor: string
}>()

const emit = defineEmits<{
  pick: [color: string]
}>()

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
        v-for="color in FLOATING_TOOLBAR_COLORS"
        :key="color"
        type="button"
        class="nft-palette-swatch"
        :class="{ 'nft-palette-swatch--active': swatchIsActive(color) }"
        :style="{ backgroundColor: color }"
        :aria-pressed="swatchIsActive(color)"
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
.nft-color-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
  margin-bottom: 6px;
}

.nft-palette-swatch {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  cursor: pointer;
  padding: 0;
}

.nft-palette-swatch:hover {
  transform: scale(1.08);
}

.nft-palette-swatch--active {
  outline: 2px solid #2563eb;
  outline-offset: 1px;
}

.nft-native-color {
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
