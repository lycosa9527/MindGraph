<script setup lang="ts">
/**
 * Icon / image / link chrome on a v2 mind-map topic or branch node.
 */
import { computed, ref } from 'vue'

import { ExternalLink } from '@lucide/vue'

import { ImagePreviewModal } from '@/components/common'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  type MindMapAdornmentPart,
  readNodeAdornment,
  resolveMindMapAdornmentParts,
  sanitizeMindMapHref,
} from '@/utils/mindMapAdornments'
import { isMindMapSummaryNodeId } from '@/utils/mindMapSummary'

const props = withDefaults(
  defineProps<{
    nodeId: string
    part?: MindMapAdornmentPart
  }>(),
  { part: 'all' }
)

const { t } = useLanguage()
const diagramStore = useDiagramSession()
const previewOpen = ref(false)

const adornment = computed(() => {
  if (isMindMapSummaryNodeId(props.nodeId)) return null
  return readNodeAdornment(diagramStore.data, props.nodeId, diagramStore.data?.connections)
})

const href = computed(() => {
  const raw = adornment.value?.href
  return raw ? sanitizeMindMapHref(raw) : null
})

const visibleParts = computed(() =>
  resolveMindMapAdornmentParts(
    props.part,
    Boolean(adornment.value?.imageUrl),
    Boolean(adornment.value?.icon || href.value)
  )
)

const previewImageUrl = computed(() => adornment.value?.imageUrl ?? '')

function openLink(event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  if (!href.value) return
  window.open(href.value, '_blank', 'noopener,noreferrer')
}

function openImagePreview(event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  if (!previewImageUrl.value) return
  previewOpen.value = true
}
</script>

<template>
  <div
    v-if="visibleParts.image || visibleParts.inline"
    class="mm-adornments"
    :class="{ 'mm-adornments--inline': props.part === 'inline' }"
  >
    <button
      v-if="visibleParts.image && adornment?.imageUrl"
      type="button"
      class="mm-adornments__image-btn nodrag nopan"
      :title="t('canvas.ribbon.enlargeImage')"
      :aria-label="t('canvas.ribbon.enlargeImage')"
      @click="openImagePreview"
      @mousedown.stop
      @pointerdown.stop
    >
      <img
        class="mm-adornments__image"
        :src="adornment.imageUrl"
        alt=""
      />
    </button>
    <div
      v-if="visibleParts.inline"
      class="mm-adornments__row"
    >
      <span
        v-if="adornment?.icon"
        class="mm-adornments__icon"
        aria-hidden="true"
        >{{ adornment.icon }}</span
      >
      <button
        v-if="href"
        type="button"
        class="mm-adornments__link"
        :title="href || t('canvas.ribbon.openLink')"
        @click="openLink"
        @mousedown.stop
      >
        <ExternalLink :size="12" />
      </button>
    </div>
    <ImagePreviewModal
      v-if="visibleParts.image && previewImageUrl"
      v-model:visible="previewOpen"
      title=""
      :image-url="previewImageUrl"
    />
  </div>
</template>

<style scoped>
.mm-adornments {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  max-width: 100%;
}

.mm-adornments--inline {
  flex-direction: row;
  max-width: none;
  flex-shrink: 0;
}

.mm-adornments__image-btn {
  display: block;
  padding: 0;
  border: none;
  background: transparent;
  line-height: 0;
  cursor: zoom-in;
  border-radius: 4px;
}

.mm-adornments__image-btn:hover .mm-adornments__image,
.mm-adornments__image-btn:focus-visible .mm-adornments__image {
  outline: 2px solid rgba(37, 99, 235, 0.45);
  outline-offset: 1px;
}

.mm-adornments__image {
  display: block;
  max-width: 120px;
  max-height: 80px;
  object-fit: contain;
  border-radius: 4px;
  pointer-events: none;
}

.mm-adornments__row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.mm-adornments__icon {
  font-size: 16px;
  line-height: 1;
}

.mm-adornments__link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: #2563eb;
  cursor: pointer;
}
</style>
