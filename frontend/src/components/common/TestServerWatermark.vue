<script setup lang="ts">
/**
 * Light diagonal repeating watermark when FEATURE_TEST_SERVER_BANNER is on.
 * Companion to SwissWarningModal (@/components/common/SwissWarningModal.vue).
 * Stays under dialogs/modals (z-index) and never captures pointer events.
 */
import { useLanguage } from '@/composables/core/useLanguage'

const { t } = useLanguage()

/** Enough tiles to cover large viewports after 45° rotation. */
const TILE_COUNT = 72
</script>

<template>
  <div
    class="tsw-root"
    aria-hidden="true"
  >
    <div class="tsw-plane">
      <span
        v-for="index in TILE_COUNT"
        :key="index"
        class="tsw-tile"
      >
        {{ t('app.testServer.watermark') }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.tsw-root {
  /* Above page chrome, below Element Plus / LoginModal (~1000+) overlays. */
  position: fixed;
  inset: 0;
  z-index: 40;
  pointer-events: none;
  overflow: hidden;
}

.tsw-plane {
  position: absolute;
  top: 50%;
  left: 50%;
  display: grid;
  grid-template-columns: repeat(6, 220px);
  gap: 48px 64px;
  width: max-content;
  transform: translate(-50%, -50%) rotate(-45deg);
  opacity: 0.07;
  user-select: none;
}

.tsw-tile {
  display: block;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  white-space: nowrap;
  color: var(--swiss-ink, #1c1917);
  line-height: 1;
}

.dark .tsw-plane {
  opacity: 0.09;
}

.dark .tsw-tile {
  color: #fafaf9;
}

@media print {
  .tsw-root {
    display: none;
  }
}
</style>
