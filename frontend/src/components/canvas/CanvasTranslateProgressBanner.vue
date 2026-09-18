<script setup lang="ts">
/**
 * Full-width slate banner (matches CanvasCollabOverlay session strip) while diagram translate streams.
 */
import I18nText from '@/components/common/I18nText.vue'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'

const ui = useDiagramTranslateUiStore()
</script>

<template>
  <div
    v-if="ui.bannerVisible"
    class="w-full shrink-0 flex flex-col border-b border-slate-600/60 pointer-events-none select-none"
    role="status"
  >
    <div
      class="flex items-center justify-center gap-2 px-3 py-1.5 text-xs text-white bg-slate-700/95"
    >
      <span class="inline-flex items-center gap-2 font-medium">
        <span
          class="w-1.5 h-1.5 rounded-full shrink-0 bg-sky-400 animate-pulse"
          aria-hidden="true"
        />
        <I18nText k="canvas.toolbar.translateLabelBannerTitle" />
      </span>
      <span class="opacity-40">·</span>
      <span class="opacity-90 tabular-nums font-mono tracking-tight">{{ ui.progressLabel }}</span>
    </div>
  </div>
</template>
