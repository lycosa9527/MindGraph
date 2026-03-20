<script setup lang="ts">
/**
 * LearningSheetOverlay - Draws dashed line and answer chips below diagram (半成品图示 mode)
 * Same style as bridge map alternative dimensions: dashed line, then blue chips
 */
import { computed } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { useLanguage } from '@/composables'
import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { useDiagramStore } from '@/stores'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'

const { viewport: vueFlowViewport, getViewport, getNodes } = useVueFlow()
const diagramStore = useDiagramStore()
const { isZh } = useLanguage()

const viewport = computed(() => vueFlowViewport.value ?? getViewport())

const isLearningSheet = computed(
  () => diagramStore.isLearningSheet && diagramStore.hiddenAnswers.length > 0
)

interface NodeWithDimensions {
  position?: { x: number; y: number }
  measured?: { width?: number; height?: number }
  dimensions?: { width?: number; height?: number }
}

const SEPARATOR_COLOR = '#1976d2'
const SEPARATOR_OPACITY = 0.4
const SEPARATOR_OFFSET_Y = 15
const SEPARATOR_DASHARRAY = '4,4'
const LINE_WIDTH = 2
const LABEL_OFFSET_Y = 15
const LABEL_FONT_SIZE = 13
const LABEL_CHIP_GAP = 8
const CHIP_FONT_SIZE = 12
const CHIP_COLOR = '#1976d2'
const CHIP_OPACITY = 0.8
const CHIP_SPACING = 8
const CHIP_PADDING_X = 8
const CHIP_PADDING_Y = 4
const CHIP_RADIUS = 4

const separatorLine = computed(() => {
  if (!isLearningSheet.value) return null

  const nodes = getNodes.value
  if (nodes.length === 0) return null

  const allBottomEdges: number[] = []
  const allXPositions: number[] = []

  nodes.forEach((node) => {
    const n = node as NodeWithDimensions
    const pos = n.position ?? { x: 0, y: 0 }
    const width = n.dimensions?.width ?? n.measured?.width ?? DEFAULT_NODE_WIDTH
    const height = n.dimensions?.height ?? n.measured?.height ?? DEFAULT_NODE_HEIGHT

    allBottomEdges.push(pos.y + height)
    allXPositions.push(pos.x)
    allXPositions.push(pos.x + width)
  })

  const lowestBottom = Math.max(...allBottomEdges)
  const separatorY = lowestBottom + SEPARATOR_OFFSET_Y
  const minX = Math.min(...allXPositions)
  const maxX = Math.max(...allXPositions)

  return { x1: minX, y1: separatorY, x2: maxX, y2: separatorY }
})

const answersLabel = computed(() => (isZh.value ? '参考答案:' : 'Answers:'))

const answerSectionPosition = computed(() => {
  if (!separatorLine.value) return null
  const labelY = separatorLine.value.y1 + LABEL_OFFSET_Y
  const chipsY = labelY + LABEL_FONT_SIZE + LABEL_CHIP_GAP
  const centerX = (separatorLine.value.x1 + separatorLine.value.x2) / 2
  return { labelY, chipsY, centerX }
})

const answerChips = computed(() => {
  const answers = diagramStore.hiddenAnswers
  if (answers.length === 0 || !answerSectionPosition.value) return []

  const { chipsY, centerX } = answerSectionPosition.value

  const chipWidths = answers.map(
    (ans) => CHIP_PADDING_X * 2 + measureTextWidth(ans ?? '', CHIP_FONT_SIZE)
  )
  const totalWidth = chipWidths.reduce((sum, w) => sum + w, 0) + CHIP_SPACING * (answers.length - 1)
  let currentX = centerX - totalWidth / 2

  return answers.map((text, index) => {
    const chipX = currentX + chipWidths[index] / 2
    currentX += chipWidths[index] + CHIP_SPACING
    return {
      text,
      x: chipX,
      y: chipsY,
      width: chipWidths[index],
    }
  })
})
</script>

<template>
  <svg
    v-if="isLearningSheet && separatorLine"
    class="learning-sheet-overlay absolute inset-0 w-full h-full pointer-events-none"
    style="z-index: 100"
  >
    <g :transform="`translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})`">
      <!-- Dashed separator line below diagram -->
      <line
        :x1="separatorLine.x1"
        :y1="separatorLine.y1"
        :x2="separatorLine.x2"
        :y2="separatorLine.y2"
        :stroke="SEPARATOR_COLOR"
        :stroke-width="LINE_WIDTH"
        :stroke-dasharray="SEPARATOR_DASHARRAY"
        :opacity="SEPARATOR_OPACITY"
        stroke-linecap="round"
      />

      <!-- Answers label + chips (same style as bridge map alternative dimensions) -->
      <g v-if="answerSectionPosition">
        <text
          :x="answerSectionPosition.centerX"
          :y="answerSectionPosition.labelY"
          :fill="CHIP_COLOR"
          :font-size="LABEL_FONT_SIZE"
          :opacity="CHIP_OPACITY"
          text-anchor="middle"
          dominant-baseline="middle"
        >
          {{ answersLabel }}
        </text>
      </g>
      <g
        v-for="(chip, index) in answerChips"
        :key="index"
      >
        <rect
          :x="chip.x - chip.width / 2"
          :y="chip.y - CHIP_PADDING_Y - CHIP_FONT_SIZE / 2"
          :width="chip.width"
          :height="CHIP_FONT_SIZE + CHIP_PADDING_Y * 2"
          :rx="CHIP_RADIUS"
          :fill="CHIP_COLOR"
          :opacity="CHIP_OPACITY"
        />
        <text
          :x="chip.x"
          :y="chip.y"
          fill="white"
          :font-size="CHIP_FONT_SIZE"
          text-anchor="middle"
          dominant-baseline="middle"
        >
          {{ chip.text }}
        </text>
      </g>
    </g>
  </svg>
</template>
