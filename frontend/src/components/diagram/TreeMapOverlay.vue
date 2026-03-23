<script setup lang="ts">
/**
 * TreeMapOverlay - Draws alternative dimensions at bottom for tree maps
 * Like archive tree-renderer.js lines 725-801
 */
import { computed } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { useLanguage } from '@/composables/useLanguage'
import { useDiagramStore } from '@/stores'

const { viewport: vueFlowViewport, getViewport, getNodes } = useVueFlow()
const diagramStore = useDiagramStore()
const { t } = useLanguage()

const viewport = computed(() => {
  if (vueFlowViewport.value) return vueFlowViewport.value
  return getViewport()
})

const isTreeMap = computed(() => diagramStore.type === 'tree_map')

interface NodeWithDimensions {
  measured?: { width?: number; height?: number }
  dimensions?: { width?: number; height?: number }
}

const SEPARATOR_OFFSET_Y = 15
const ALTERNATIVE_DIMENSIONS_OFFSET_Y = 15
const ALTERNATIVE_LABEL_FONT_SIZE = 13
const ALTERNATIVE_CHIP_COLOR = '#1976d2'

const alternativeDimensions = computed(() => {
  if (!isTreeMap.value) return []
  const diagramData = diagramStore.data
  if (diagramData && typeof diagramData === 'object' && 'alternative_dimensions' in diagramData) {
    const altDims = diagramData.alternative_dimensions
    if (Array.isArray(altDims)) {
      return altDims.filter((dim) => typeof dim === 'string' && dim.trim())
    }
  }
  return []
})

const alternativeDimensionsLabel = computed(() =>
  t('diagram.alternativeDimensions.treeMapTitle')
)

const alternativeDimensionsChipsText = computed(() =>
  alternativeDimensions.value.map((d) => `• ${d}`).join('  ')
)

const treeMapSeparatorLine = computed(() => {
  if (!isTreeMap.value) return null
  const nodes = getNodes.value
  const treeNodes = nodes.filter((n) => n.type !== 'label' && n.id !== 'dimension-label')
  if (treeNodes.length === 0) return null

  const getNodeDimensions = (node: (typeof nodes)[0] & NodeWithDimensions) => ({
    width: node.dimensions?.width ?? node.measured?.width ?? DEFAULT_NODE_WIDTH,
    height: node.dimensions?.height ?? node.measured?.height ?? DEFAULT_NODE_HEIGHT,
  })

  let lowestBottom = 0
  let minX = Infinity
  let maxX = -Infinity
  treeNodes.forEach((node) => {
    const dims = getNodeDimensions(node)
    const bottom = node.position.y + dims.height
    if (bottom > lowestBottom) lowestBottom = bottom
    if (node.position.x < minX) minX = node.position.x
    if (node.position.x + dims.width > maxX) maxX = node.position.x + dims.width
  })
  if (minX === Infinity || maxX === -Infinity) return null

  const separatorY = lowestBottom + SEPARATOR_OFFSET_Y
  return { x1: minX, y1: separatorY, x2: maxX, y2: separatorY }
})

const treeMapAlternativePosition = computed(() => {
  if (!treeMapSeparatorLine.value) return null
  const labelY = treeMapSeparatorLine.value.y1 + ALTERNATIVE_DIMENSIONS_OFFSET_Y
  const chipsY = labelY + ALTERNATIVE_LABEL_FONT_SIZE + 8
  const centerX = (treeMapSeparatorLine.value.x1 + treeMapSeparatorLine.value.x2) / 2
  return { labelY, chipsY, centerX }
})
</script>

<template>
  <svg
    v-if="
      isTreeMap &&
      alternativeDimensions.length > 0 &&
      treeMapSeparatorLine &&
      treeMapAlternativePosition
    "
    class="tree-map-overlay absolute inset-0 w-full h-full pointer-events-none"
    style="z-index: 0"
  >
    <g :transform="`translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})`">
      <line
        :x1="treeMapSeparatorLine.x1"
        :y1="treeMapSeparatorLine.y1"
        :x2="treeMapSeparatorLine.x2"
        :y2="treeMapSeparatorLine.y2"
        :stroke="ALTERNATIVE_CHIP_COLOR"
        stroke-width="1"
        stroke-dasharray="4,4"
        :opacity="0.4"
        stroke-linecap="round"
      />
      <text
        :x="treeMapAlternativePosition.centerX"
        :y="treeMapAlternativePosition.labelY"
        :fill="ALTERNATIVE_CHIP_COLOR"
        :font-size="ALTERNATIVE_LABEL_FONT_SIZE"
        text-anchor="middle"
        dominant-baseline="middle"
        :opacity="0.7"
      >
        {{ alternativeDimensionsLabel }}
      </text>
      <text
        :x="treeMapAlternativePosition.centerX"
        :y="treeMapAlternativePosition.chipsY"
        :fill="ALTERNATIVE_CHIP_COLOR"
        :font-size="ALTERNATIVE_LABEL_FONT_SIZE - 1"
        text-anchor="middle"
        dominant-baseline="middle"
        font-weight="600"
        :opacity="0.8"
      >
        {{ alternativeDimensionsChipsText }}
      </text>
    </g>
  </svg>
</template>

<style scoped>
.tree-map-overlay {
  overflow: visible;
}
</style>
