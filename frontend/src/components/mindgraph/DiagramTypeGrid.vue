<script setup lang="ts">
/**
 * DiagramTypeGrid - Grid of diagram type cards with SVG previews and animations
 * SVG previews from archive/templates/editor.html diagram gallery
 */
import { useRouter } from 'vue-router'

import { useUIStore } from '@/stores'
import type { DiagramType } from '@/types'

import DiagramPreviewSvg from './DiagramPreviewSvg.vue'

const uiStore = useUIStore()
const router = useRouter()

// All 10 diagram types (8 Thinking Maps + 2 extra), displayed in 2 rows of 5
const allDiagramTypes: Array<{ name: string; desc: string; type: DiagramType }> = [
  { name: '圆圈图', desc: '联想 脑暴', type: 'circle_map' },
  { name: '气泡图', desc: '描述特性', type: 'bubble_map' },
  { name: '双气泡图', desc: '比较与对比', type: 'double_bubble_map' },
  { name: '树形图', desc: '分类与归纳', type: 'tree_map' },
  { name: '括号图', desc: '整体与部分', type: 'brace_map' },
  { name: '流程图', desc: '顺序与步骤', type: 'flow_map' },
  { name: '复流程图', desc: '因果分析', type: 'multi_flow_map' },
  { name: '桥形图', desc: '类比推理', type: 'bridge_map' },
  { name: '思维导图', desc: '概念梳理', type: 'mindmap' },
  { name: '概念图', desc: '概念关系', type: 'concept_map' },
]

function handleNewCanvas(item: { name: string; type: DiagramType }) {
  uiStore.setSelectedChartType(item.name)
  router.push({
    path: '/canvas',
    query: { type: item.type },
  })
}
</script>

<template>
  <div class="diagram-type-grid">
    <!-- Section title -->
    <div class="text-left text-sm font-semibold text-stone-500 mb-4">在画布中创建</div>

    <!-- 2 rows of 5 diagram cards with SVG previews -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <div
        v-for="item in allDiagramTypes"
        :key="item.name"
        class="diagram-card group flex flex-col items-center p-3 border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-md transition-all cursor-pointer"
        @click="handleNewCanvas(item)"
      >
        <!-- SVG diagram preview (animated) -->
        <div class="diagram-preview-wrapper mb-2">
          <DiagramPreviewSvg :type="item.type" />
        </div>
        <div class="text-sm font-medium text-gray-800 mb-1">
          {{ item.name }}
        </div>
        <div class="text-xs text-gray-500 text-center">
          {{ item.desc }}
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
