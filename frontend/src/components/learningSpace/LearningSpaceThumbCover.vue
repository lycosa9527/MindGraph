<script setup lang="ts">
/**
 * Assignment-wall thumbnail. Still image only; the opened review is the live canvas.
 */
defineProps<{
  thumbnailUrl?: string | null
}>()
</script>

<template>
  <div class="ls-thumb-card__cover-inner">
    <img
      v-if="thumbnailUrl"
      :src="thumbnailUrl"
      alt=""
      loading="lazy"
    />
    <div
      v-else
      class="ls-thumb-card__ph"
    >
      <I18nText k="learningSpace.noPreview" />
    </div>
  </div>
</template>
