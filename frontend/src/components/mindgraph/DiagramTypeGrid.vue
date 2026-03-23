<script setup lang="ts">
/**
 * DiagramTypeGrid - Grid of diagram type cards with SVG previews and animations
 * SVG previews from archive/templates/editor.html diagram gallery
 */
import { useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { useUIStore } from '@/stores'
import type { DiagramType } from '@/types'

import DiagramPreviewSvg from './DiagramPreviewSvg.vue'

const uiStore = useUIStore()
const router = useRouter()
const { t } = useLanguage()

/** Store keeps Chinese diagram names; map from DiagramType for setSelectedChartType */
const TYPE_TO_ZH_NAME: Record<DiagramType, string> = {
  circle_map: '圆圈图',
  bubble_map: '气泡图',
  double_bubble_map: '双气泡图',
  tree_map: '树形图',
  brace_map: '括号图',
  flow_map: '流程图',
  multi_flow_map: '复流程图',
  bridge_map: '桥形图',
  mindmap: '思维导图',
  mind_map: '思维导图',
  concept_map: '概念图',
  diagram: '图表',
}

// All 10 diagram types (8 Thinking Maps + 2 extra), displayed in 2 rows of 5
const allDiagramTypes: Array<{ titleKey: string; descKey: string; type: DiagramType }> = [
  { titleKey: 'landing.diagramGrid.circle_map.title', descKey: 'landing.diagramGrid.circle_map.desc', type: 'circle_map' },
  { titleKey: 'landing.diagramGrid.bubble_map.title', descKey: 'landing.diagramGrid.bubble_map.desc', type: 'bubble_map' },
  { titleKey: 'landing.diagramGrid.double_bubble_map.title', descKey: 'landing.diagramGrid.double_bubble_map.desc', type: 'double_bubble_map' },
  { titleKey: 'landing.diagramGrid.tree_map.title', descKey: 'landing.diagramGrid.tree_map.desc', type: 'tree_map' },
  { titleKey: 'landing.diagramGrid.brace_map.title', descKey: 'landing.diagramGrid.brace_map.desc', type: 'brace_map' },
  { titleKey: 'landing.diagramGrid.flow_map.title', descKey: 'landing.diagramGrid.flow_map.desc', type: 'flow_map' },
  { titleKey: 'landing.diagramGrid.multi_flow_map.title', descKey: 'landing.diagramGrid.multi_flow_map.desc', type: 'multi_flow_map' },
  { titleKey: 'landing.diagramGrid.bridge_map.title', descKey: 'landing.diagramGrid.bridge_map.desc', type: 'bridge_map' },
  { titleKey: 'landing.diagramGrid.mindmap.title', descKey: 'landing.diagramGrid.mindmap.desc', type: 'mindmap' },
  { titleKey: 'landing.diagramGrid.concept_map.title', descKey: 'landing.diagramGrid.concept_map.desc', type: 'concept_map' },
]

function handleNewCanvas(item: { type: DiagramType }) {
  const zhName = TYPE_TO_ZH_NAME[item.type]
  if (zhName) {
    uiStore.setSelectedChartType(zhName)
  }
  router.push({
    path: '/canvas',
    query: { type: item.type },
  })
}
</script>

<template>
  <div class="diagram-type-grid">
    <!-- Section title -->
    <div class="text-left text-sm font-semibold text-stone-500 mb-4">
      {{ t('landing.diagramGrid.sectionTitle') }}
    </div>

    <!-- 2 rows of 5 diagram cards with SVG previews -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <div
        v-for="item in allDiagramTypes"
        :key="item.type"
        class="diagram-card group flex flex-col items-center p-3 border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-md transition-all cursor-pointer"
        @click="handleNewCanvas(item)"
      >
        <!-- SVG diagram preview (animated) -->
        <div class="diagram-preview-wrapper mb-2">
          <DiagramPreviewSvg :type="item.type" />
        </div>
        <div class="text-sm font-medium text-gray-800 mb-1 text-center leading-snug">
          {{ t(item.titleKey) }}
        </div>
        <div class="text-xs text-gray-500 text-center leading-snug">
          {{ t(item.descKey) }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagram-preview-wrapper {
  width: 100%;
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Archive-style animation: only on hover, from demo-login.html */
.diagram-card.group:hover :deep(.diagram-svg .anim-node) {
  transform-origin: center;
  animation: diagramAddNode 3.5s linear infinite;
}

.diagram-card.group:hover :deep(.diagram-svg .anim-line) {
  animation: diagramDrawLine 3.5s linear infinite;
}

/* Stagger: circle/rect by nth-of-type (archive style) */
.diagram-card.group:hover :deep(.diagram-svg circle.anim-node:nth-of-type(1)),
.diagram-card.group:hover :deep(.diagram-svg rect.anim-node:nth-of-type(1)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-node:nth-of-type(1)) {
  animation-delay: 0s;
}
.diagram-card.group:hover :deep(.diagram-svg circle.anim-node:nth-of-type(2)),
.diagram-card.group:hover :deep(.diagram-svg rect.anim-node:nth-of-type(2)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-node:nth-of-type(2)) {
  animation-delay: 0.3s;
}
.diagram-card.group:hover :deep(.diagram-svg circle.anim-node:nth-of-type(3)),
.diagram-card.group:hover :deep(.diagram-svg rect.anim-node:nth-of-type(3)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-node:nth-of-type(3)) {
  animation-delay: 0.6s;
}
.diagram-card.group:hover :deep(.diagram-svg circle.anim-node:nth-of-type(4)),
.diagram-card.group:hover :deep(.diagram-svg rect.anim-node:nth-of-type(4)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-node:nth-of-type(4)) {
  animation-delay: 0.9s;
}
.diagram-card.group:hover :deep(.diagram-svg circle.anim-node:nth-of-type(5)),
.diagram-card.group:hover :deep(.diagram-svg rect.anim-node:nth-of-type(5)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-node:nth-of-type(5)) {
  animation-delay: 1.2s;
}
.diagram-card.group:hover :deep(.diagram-svg circle.anim-node:nth-of-type(n + 6)),
.diagram-card.group:hover :deep(.diagram-svg rect.anim-node:nth-of-type(n + 6)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-node:nth-of-type(n + 6)) {
  animation-delay: 1.5s;
}

.diagram-card.group:hover :deep(.diagram-svg line.anim-line:nth-of-type(1)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-line:nth-of-type(1)),
.diagram-card.group:hover :deep(.diagram-svg circle.anim-line:nth-of-type(1)) {
  animation-delay: 0.15s;
}
.diagram-card.group:hover :deep(.diagram-svg line.anim-line:nth-of-type(2)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-line:nth-of-type(2)),
.diagram-card.group:hover :deep(.diagram-svg circle.anim-line:nth-of-type(2)) {
  animation-delay: 0.45s;
}
.diagram-card.group:hover :deep(.diagram-svg line.anim-line:nth-of-type(3)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-line:nth-of-type(3)),
.diagram-card.group:hover :deep(.diagram-svg circle.anim-line:nth-of-type(3)) {
  animation-delay: 0.75s;
}
.diagram-card.group:hover :deep(.diagram-svg line.anim-line:nth-of-type(4)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-line:nth-of-type(4)),
.diagram-card.group:hover :deep(.diagram-svg circle.anim-line:nth-of-type(4)) {
  animation-delay: 1.05s;
}
.diagram-card.group:hover :deep(.diagram-svg line.anim-line:nth-of-type(5)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-line:nth-of-type(5)),
.diagram-card.group:hover :deep(.diagram-svg circle.anim-line:nth-of-type(5)) {
  animation-delay: 1.35s;
}
.diagram-card.group:hover :deep(.diagram-svg line.anim-line:nth-of-type(n + 6)),
.diagram-card.group:hover :deep(.diagram-svg path.anim-line:nth-of-type(n + 6)),
.diagram-card.group:hover :deep(.diagram-svg circle.anim-line:nth-of-type(n + 6)) {
  animation-delay: 1.65s;
}

@keyframes diagramAddNode {
  0%,
  100% {
    opacity: 0;
    transform: scale(0.8);
  }
  15%,
  85% {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes diagramDrawLine {
  0%,
  100% {
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dashoffset: 100;
  }
}
</style>
