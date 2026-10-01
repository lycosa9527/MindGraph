<script setup lang="ts">
/**
 * Assignment-wall thumbnail — live diagram preview (Showcase path) with PNG fallback.
 */
import ShowcaseInlineDiagramPreview from '@/components/showcase/ShowcaseInlineDiagramPreview.vue'
import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  previewSpec?: Record<string, unknown> | null
  previewDiagramType?: string | null
  thumbnailUrl?: string | null
}>()

const { t } = useLanguage()
</script>

<template>
  <div class="ls-thumb-card__cover-inner">
    <ShowcaseInlineDiagramPreview
      v-if="props.previewSpec"
      :spec="props.previewSpec"
      :diagram-type="props.previewDiagramType"
      :thumbnail-url="props.thumbnailUrl"
      empty-label-key="learningSpace.noPreview"
    />
    <img
      v-else-if="props.thumbnailUrl"
      :src="props.thumbnailUrl"
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
