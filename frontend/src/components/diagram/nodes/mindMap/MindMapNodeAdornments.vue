<script setup lang="ts">
/**
 * Icon / image / link chrome on a v2 mind-map topic or branch node.
 */
import { computed } from 'vue'

import { ExternalLink } from '@lucide/vue'

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

function openLink(event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  if (!href.value) return
  window.open(href.value, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <div
    v-if="visibleParts.image || visibleParts.inline"
    class="mm-adornments"
    :class="{ 'mm-adornments--inline': props.part === 'inline' }"
  >
    <img
      v-if="visibleParts.image && adornment?.imageUrl"
      class="mm-adornments__image"
      :src="adornment.imageUrl"
      alt=""
    />
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
        :title="t('canvas.ribbon.openLink')"
        @click="openLink"
        @mousedown.stop
      >
        <ExternalLink :size="12" />
      </button>
    </div>
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

.mm-adornments__image {
  display: block;
  max-width: 120px;
  max-height: 80px;
  object-fit: contain;
  border-radius: 4px;
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
