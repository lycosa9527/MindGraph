<script setup lang="ts">
/**
 * Mini mind-map skeleton icon — orthogonal bus lines + distinct node silhouettes.
 *
 * Shape rendering rules (must match canvas nodeShape):
 * - rectangle: sharp corners (rx=0)
 * - rounded: 圆角矩形 — small corner radius, NOT a pill
 * - oval: 气泡 — ellipse filling the node box
 * - underline: horizontal rule
 */
import { computed } from 'vue'

import type { MindMapDiagramStylePreset } from '@/config/mindMapDiagramStyles'
import type { NodeShape } from '@/utils/nodeShapeStyle'

const props = withDefaults(
  defineProps<{
    preset: MindMapDiagramStylePreset
    active?: boolean
  }>(),
  { active: false }
)

const W = 76
const H = 44

const TOPIC = { x: 2, y: 16, w: 14, h: 12 }
const SPINE_X = 19
const L1_TRUNK_X = 36

const L1 = [
  { x: 22, y: 4, w: 11, h: 6 },
  { x: 22, y: 17, w: 11, h: 6 },
  { x: 22, y: 30, w: 11, h: 6 },
] as const

const L2: ReadonlyArray<ReadonlyArray<{ x: number; y: number; w: number; h: number }>> = [
  [
    { x: 44, y: 2, w: 10, h: 5 },
    { x: 44, y: 9, w: 10, h: 5 },
  ],
  [
    { x: 44, y: 16, w: 10, h: 5 },
    { x: 44, y: 23, w: 10, h: 5 },
  ],
  [
    { x: 44, y: 30, w: 10, h: 5 },
    { x: 44, y: 37, w: 10, h: 5 },
  ],
]

const strokeColor = computed(() => (props.active ? '#3b82f6' : '#64748b'))
const lineColor = computed(() => (props.active ? '#60a5fa' : '#94a3b8'))
const fillColor = computed(() => (props.active ? '#eff6ff' : '#e8edf2'))

function centerY(box: { y: number; h: number }): number {
  return box.y + box.h / 2
}

function rightX(box: { x: number; w: number }): number {
  return box.x + box.w
}

function boxCenter(box: { x: number; y: number; w: number; h: number }): { cx: number; cy: number } {
  return { cx: box.x + box.w / 2, cy: box.y + box.h / 2 }
}

/** 圆角矩形 — slight corner radius (classic / soft L1). */
function roundedRectRx(h: number, soft = false): number {
  return soft ? Math.min(4, h * 0.42) : Math.min(2.5, h * 0.28)
}

function nodeFill(shape: NodeShape): string {
  if (shape === 'underline') return 'none'
  return fillColor.value
}

function nodeStroke(_shape: NodeShape): string {
  return strokeColor.value
}

const topicBusPaths = computed(() => {
  const topicRight = rightX(TOPIC)
  const topicCy = centerY(TOPIC)
  const l1Ys = L1.map(centerY)
  const spineTop = Math.min(...l1Ys, topicCy)
  const spineBottom = Math.max(...l1Ys, topicCy)

  const paths: string[] = [
    `M ${topicRight} ${topicCy} H ${SPINE_X}`,
    `M ${SPINE_X} ${spineTop} V ${spineBottom}`,
  ]
  for (const l1 of L1) {
    paths.push(`M ${SPINE_X} ${centerY(l1)} H ${l1.x}`)
  }
  return paths
})

const l2BusPaths = computed(() => {
  const paths: string[] = []
  L1.forEach((l1, gi) => {
    const l1Right = rightX(l1)
    const l1Cy = centerY(l1)
    const children = L2[gi]
    const childYs = children.map(centerY)
    const spineTop = Math.min(...childYs, l1Cy)
    const spineBottom = Math.max(...childYs, l1Cy)

    paths.push(`M ${l1Right} ${l1Cy} H ${L1_TRUNK_X}`)
    paths.push(`M ${L1_TRUNK_X} ${spineTop} V ${spineBottom}`)
    children.forEach((l2) => {
      paths.push(`M ${L1_TRUNK_X} ${centerY(l2)} H ${l2.x}`)
    })
  })
  return paths
})

const connectorPaths = computed(() => [...topicBusPaths.value, ...l2BusPaths.value])

const lineJoin = computed(() => (props.preset.id === 'formal' ? 'miter' : 'round'))
</script>

<template>
  <svg
    class="mm-style-preview-svg"
    :class="{ 'is-active': active }"
    :viewBox="`0 0 ${W} ${H}`"
    width="100%"
    height="100%"
    aria-hidden="true"
  >
    <g
      fill="none"
      :stroke="lineColor"
      stroke-width="1"
      stroke-linecap="round"
      :stroke-linejoin="lineJoin"
    >
      <path
        v-for="(d, i) in connectorPaths"
        :key="`c-${i}`"
        :d="d"
      />
    </g>

    <!-- Topic -->
    <template v-if="preset.topicShape === 'underline'">
      <line
        :x1="TOPIC.x"
        :y1="TOPIC.y + TOPIC.h - 1"
        :x2="TOPIC.x + TOPIC.w"
        :y2="TOPIC.y + TOPIC.h - 1"
        :stroke="strokeColor"
        stroke-width="1.25"
        stroke-linecap="round"
      />
    </template>
    <ellipse
      v-else-if="preset.topicShape === 'oval'"
      :cx="boxCenter(TOPIC).cx"
      :cy="boxCenter(TOPIC).cy"
      :rx="TOPIC.w / 2"
      :ry="TOPIC.h / 2"
      :fill="nodeFill('oval')"
      :stroke="nodeStroke('oval')"
      stroke-width="1"
    />
    <rect
      v-else
      :x="TOPIC.x"
      :y="TOPIC.y"
      :width="TOPIC.w"
      :height="TOPIC.h"
      :rx="preset.topicShape === 'rounded' ? roundedRectRx(TOPIC.h, true) : 0"
      :fill="nodeFill(preset.topicShape)"
      :stroke="nodeStroke(preset.topicShape)"
      stroke-width="1"
    />

    <!-- Level 1 -->
    <template
      v-for="(box, i) in L1"
      :key="`l1-${i}`"
    >
      <line
        v-if="preset.branchDepth1Shape === 'underline'"
        :x1="box.x"
        :y1="box.y + box.h - 1"
        :x2="box.x + box.w"
        :y2="box.y + box.h - 1"
        :stroke="strokeColor"
        stroke-width="1.25"
        stroke-linecap="round"
      />
      <ellipse
        v-else-if="preset.branchDepth1Shape === 'oval'"
        :cx="boxCenter(box).cx"
        :cy="boxCenter(box).cy"
        :rx="box.w / 2"
        :ry="box.h / 2"
        :fill="nodeFill('oval')"
        :stroke="nodeStroke('oval')"
        stroke-width="1"
      />
      <rect
        v-else
        :x="box.x"
        :y="box.y"
        :width="box.w"
        :height="box.h"
        :rx="
          preset.branchDepth1Shape === 'rounded'
            ? roundedRectRx(box.h, preset.id === 'soft')
            : 0
        "
        :fill="nodeFill(preset.branchDepth1Shape)"
        :stroke="nodeStroke(preset.branchDepth1Shape)"
        stroke-width="1"
      />
    </template>

    <!-- Level 2 -->
    <template
      v-for="(group, gi) in L2"
      :key="`l2g-${gi}`"
    >
      <template
        v-for="(box, bi) in group"
        :key="`l2-${gi}-${bi}`"
      >
        <line
          v-if="preset.branchDepth2Shape === 'underline'"
          :x1="box.x"
          :y1="box.y + box.h - 1"
          :x2="box.x + box.w"
          :y2="box.y + box.h - 1"
          :stroke="strokeColor"
          stroke-width="1.1"
          stroke-linecap="round"
        />
        <ellipse
          v-else-if="preset.branchDepth2Shape === 'oval'"
          :cx="boxCenter(box).cx"
          :cy="boxCenter(box).cy"
          :rx="box.w / 2"
          :ry="box.h / 2"
          :fill="nodeFill('oval')"
          :stroke="nodeStroke('oval')"
          stroke-width="1"
        />
        <rect
          v-else
          :x="box.x"
          :y="box.y"
          :width="box.w"
          :height="box.h"
          :rx="preset.branchDepth2Shape === 'rounded' ? roundedRectRx(box.h, false) : 0"
          :fill="nodeFill(preset.branchDepth2Shape)"
          :stroke="nodeStroke(preset.branchDepth2Shape)"
          stroke-width="1"
        />
      </template>
    </template>
  </svg>
</template>

<style scoped>
.mm-style-preview-svg {
  display: block;
  width: 100%;
  max-width: 84px;
  height: auto;
  aspect-ratio: 76 / 44;
  margin: 0 auto;
}
</style>
