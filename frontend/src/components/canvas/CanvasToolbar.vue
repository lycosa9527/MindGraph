<script setup lang="ts">
/**
 * CanvasToolbar - Floating toolbar for canvas editing
 * Migrated from prototype MindGraphCanvasPage toolbar
 */
import { computed, nextTick, ref } from 'vue'

import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElTooltip } from 'element-plus'
import { useVueFlow } from '@vue-flow/core'

import {
  ArrowDownUp,
  Brush,
  ChevronDown,
  Fish,
  Image as ImageIcon,
  LayoutGrid,
  Package,
  PenLine,
  Plus,
  RotateCcw,
  RotateCw,
  Square,
  Trash2,
  Type,
  Wand2,
} from 'lucide-vue-next'

import { useNotifications } from '@/composables'
import { useAutoComplete, useLanguage } from '@/composables'
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { useDiagramStore } from '@/stores'
import type { DiagramNode } from '@/types'

const notify = useNotifications()

const { isZh } = useLanguage()
const { isGenerating: isAIGenerating, autoComplete, validateForAutoComplete } = useAutoComplete()

const diagramStore = useDiagramStore()
const { updateNode: updateVueFlowNode } = useVueFlow()

// Helper function to get timestamp for logging
function getTimestamp(): string {
  return new Date().toISOString()
}

// Computed property to check if current diagram is multi-flow map
const isMultiFlowMap = computed(() => diagramStore.type === 'multi_flow_map')

// Computed property to check if current diagram is bridge map
const isBridgeMap = computed(() => diagramStore.type === 'bridge_map')

// Dropdown visibility (prefixed with _ to indicate intentionally unused - reserved for future)
const _showStyleDropdown = ref(false)
const _showTextDropdown = ref(false)
const _showBackgroundDropdown = ref(false)
const _showBorderDropdown = ref(false)
const _showMoreAppsDropdown = ref(false)

// Text style state
const fontFamily = ref('Arial')
const fontSize = ref(16)
const textColor = ref('#000000')

// Background state
const backgroundColors = ['#FFFFFF', '#F9FAFB', '#F3F4F6', '#E5E7EB', '#D1D5DB']
const backgroundOpacity = ref(100)

// Border state
const borderColor = ref('#000000')
const borderWidth = ref(1)
const borderStyle = ref('solid')

// Style presets
const stylePresets = [
  { name: '简约风格', bgClass: 'bg-blue-50', borderClass: 'border-blue-200' },
  { name: '创意风格', bgClass: 'bg-purple-50', borderClass: 'border-purple-200' },
  { name: '商务风格', bgClass: 'bg-green-50', borderClass: 'border-green-200' },
  { name: '活力风格', bgClass: 'bg-yellow-50', borderClass: 'border-yellow-200' },
]

// More apps items
const moreApps = [
  {
    name: '瀑布流',
    icon: LayoutGrid,
    desc: '在批量节点中选择，发散聚合思维显性化',
    tag: '热门',
    iconBg: 'bg-blue-100',
    iconColor: 'text-blue-600',
  },
  {
    name: '半成品图示',
    icon: Package,
    desc: '随机留空，学习复习好搭子',
    iconBg: 'bg-purple-100',
    iconColor: 'text-purple-600',
  },
  {
    name: '专家鱼骨图',
    icon: Fish,
    desc: '问题分析与原因追溯工具',
    iconBg: 'bg-green-100',
    iconColor: 'text-green-600',
  },
]

function handleUndo() {
  diagramStore.undo()
}

function handleRedo() {
  diagramStore.redo()
}

function handleAddNode() {
  const diagramType = diagramStore.type

  if (!diagramStore.data?.nodes) {
    notify.warning('请先创建图示')
    return
  }

  // For circle maps, add a new context node
  if (diagramType === 'circle_map') {
    // Find existing context nodes to determine next index
    const contextNodes = diagramStore.data.nodes.filter(
      (n) => n.type === 'bubble' && n.id.startsWith('context-')
    )
    const newIndex = contextNodes.length

    // Add new context node (layout will be recalculated automatically)
    diagramStore.addNode({
      id: `context-${newIndex}`,
      text: '新联想',
      type: 'bubble',
      position: { x: 0, y: 0 }, // Will be recalculated
    })

    diagramStore.pushHistory('添加节点')
    notify.success('已添加新节点')
    return
  }

  // For bridge maps, add a new analogy pair (left and right nodes)
  if (diagramType === 'bridge_map') {
    // Find all existing bridge map pair nodes (exclude dimension label)
    const pairNodes = diagramStore.data.nodes.filter(
      (n) =>
        n.data?.diagramType === 'bridge_map' &&
        n.data?.pairIndex !== undefined &&
        !n.data?.isDimensionLabel
    )

    // Find the highest pairIndex
    let maxPairIndex = -1
    pairNodes.forEach((node) => {
      const pairIndex = node.data?.pairIndex
      if (typeof pairIndex === 'number' && pairIndex > maxPairIndex) {
        maxPairIndex = pairIndex
      }
    })

    const newPairIndex = maxPairIndex + 1

    // Calculate position for new pair (following bridgeMap.ts loader logic)
    const centerY = DEFAULT_CENTER_Y
    const gapBetweenPairs = 50
    const verticalGap = 5
    const nodeWidth = DEFAULT_NODE_WIDTH
    const nodeHeight = BRANCH_NODE_HEIGHT
    const gapFromLabelRight = 10
    const estimatedLabelWidth = 100
    const startX = DEFAULT_PADDING + estimatedLabelWidth + gapFromLabelRight

    // Find the rightmost existing pair node to calculate next X position
    let nextX = startX
    if (pairNodes.length > 0) {
      // Find the rightmost node
      const rightmostNode = pairNodes.reduce((rightmost, node) => {
        if (!rightmost) return node
        const rightmostX = rightmost.position?.x || 0
        const nodeX = node.position?.x || 0
        return nodeX > rightmostX ? node : rightmost
      })

      // Calculate next X: rightmost node's X + node width + gap
      const rightmostX = rightmostNode.position?.x || startX
      nextX = rightmostX + nodeWidth + gapBetweenPairs
    }

    // Calculate Y positions (same as bridgeMap.ts loader)
    const leftNodeY = centerY - verticalGap - nodeHeight
    const rightNodeY = centerY + verticalGap

    // Create left node
    const leftNode: DiagramNode = {
      id: `pair-${newPairIndex}-left`,
      text: isZh.value ? '新事物A' : 'New Item A',
      type: 'branch',
      position: { x: nextX, y: leftNodeY },
      data: {
        pairIndex: newPairIndex,
        position: 'left',
        diagramType: 'bridge_map',
      },
    }

    // Create right node
    const rightNode: DiagramNode = {
      id: `pair-${newPairIndex}-right`,
      text: isZh.value ? '新事物B' : 'New Item B',
      type: 'branch',
      position: { x: nextX, y: rightNodeY },
      data: {
        pairIndex: newPairIndex,
        position: 'right',
        diagramType: 'bridge_map',
      },
    }

    // Add both nodes
    diagramStore.addNode(leftNode)
    diagramStore.addNode(rightNode)

    diagramStore.pushHistory(isZh.value ? '添加类比对' : 'Add Analogy Pair')
    notify.success(isZh.value ? '已添加类比对' : 'Analogy pair added')
    return
  }

  // For other diagram types, show under development message
  notify.info('增加节点功能开发中')
}

function handleAddCause() {
  const diagramType = diagramStore.type

  if (!diagramStore.data?.nodes) {
    notify.warning('请先创建图示')
    return
  }

  if (diagramType !== 'multi_flow_map') {
    return
  }

  // Add new cause node (layout will be recalculated automatically)
  diagramStore.addNode({
    id: 'cause-temp', // Temporary ID, will be re-indexed
    text: '新原因',
    type: 'flow',
    position: { x: 0, y: 0 }, // Will be recalculated
    category: 'causes', // Pass category to addNode
  } as DiagramNode & { category?: string })

  diagramStore.pushHistory('添加原因')
  notify.success('已添加原因节点')
}

function handleAddEffect() {
  const diagramType = diagramStore.type

  if (!diagramStore.data?.nodes) {
    notify.warning('请先创建图示')
    return
  }

  if (diagramType !== 'multi_flow_map') {
    return
  }

  // Add new effect node (layout will be recalculated automatically)
  diagramStore.addNode({
    id: 'effect-temp', // Temporary ID, will be re-indexed
    text: '新结果',
    type: 'flow',
    position: { x: 0, y: 0 }, // Will be recalculated
    category: 'effects', // Pass category to addNode
  } as DiagramNode & { category?: string })

  diagramStore.pushHistory('添加结果')
  notify.success('已添加结果节点')
}

function repositionBridgeMapPairs() {
  const startTime = getTimestamp()
  console.debug(`[CanvasToolbar] [${startTime}] repositionBridgeMapPairs() called`)

  if (!diagramStore.data) return

  const pairs = new Map<number, { left: DiagramNode; right: DiagramNode }>()

  for (const node of diagramStore.data.nodes) {
    if (
      node.data?.diagramType !== 'bridge_map' ||
      node.data?.pairIndex === undefined ||
      node.data?.isDimensionLabel
    ) {
      continue
    }

    const pairIndex = node.data.pairIndex as number
    const position = node.data.position as 'left' | 'right'
    
    if (!pairs.has(pairIndex)) {
      pairs.set(pairIndex, { left: null!, right: null! })
    }
    
    const pair = pairs.get(pairIndex)!
    if (position === 'left') {
      pair.left = node
    } else {
      pair.right = node
    }
  }

  const sortedPairs = Array.from(pairs.entries())
    .filter(([, pair]) => pair.left && pair.right)
    .sort(([a], [b]) => a - b)

  const gapBetweenPairs = 50
  const gapFromLabelRight = 10
  const estimatedLabelWidth = 100
  const startX = DEFAULT_PADDING + estimatedLabelWidth + gapFromLabelRight
  const verticalGap = 5
  const nodeHeight = BRANCH_NODE_HEIGHT
  const nodeWidth = DEFAULT_NODE_WIDTH
  const centerY = DEFAULT_CENTER_Y

  console.debug(`[CanvasToolbar] [${getTimestamp()}] Repositioning ${sortedPairs.length} pairs`)
  
  let currentX = startX
  for (const [, pair] of sortedPairs) {
    const leftNodeY = centerY - verticalGap - nodeHeight
    const rightNodeY = centerY + verticalGap

    console.debug(`[CanvasToolbar] [${getTimestamp()}] Updating pair ${pair.left.data?.pairIndex}:`, {
      leftNodeId: pair.left.id,
      rightNodeId: pair.right.id,
      newX: currentX,
      leftNodeY,
      rightNodeY,
    })

    updateVueFlowNode(pair.left.id, (node) => ({
      ...node,
      position: { x: currentX, y: leftNodeY },
    }))
    updateVueFlowNode(pair.right.id, (node) => ({
      ...node,
      position: { x: currentX, y: rightNodeY },
    }))

    diagramStore.updateNodePosition(pair.left.id, { x: currentX, y: leftNodeY }, false)
    diagramStore.updateNodePosition(pair.right.id, { x: currentX, y: rightNodeY }, false)

    currentX += nodeWidth + gapBetweenPairs
  }
  
  console.debug(`[CanvasToolbar] [${getTimestamp()}] repositionBridgeMapPairs() complete`)
}

async function handleDeleteNode() {
  const diagramType = diagramStore.type

  if (!diagramStore.data?.nodes) {
    notify.warning('请先创建图示')
    return
  }

  // Check if any nodes are selected
  const selectedNodesArray = [...diagramStore.selectedNodes]
  if (selectedNodesArray.length === 0) {
    console.debug(`[CanvasToolbar] [${getTimestamp()}] No nodes selected:`, {
      selectedNodes: diagramStore.selectedNodes,
      selectedNodesArray,
      selectedNodesLength: diagramStore.selectedNodes.length,
      diagramType: diagramStore.type,
      totalNodes: diagramStore.data?.nodes?.length || 0,
    })
    notify.warning('请先选择要删除的节点')
    return
  }
  
  console.log(`[CanvasToolbar] [${getTimestamp()}] ========== DELETE REQUESTED ==========`)
  console.log(`[CanvasToolbar] [${getTimestamp()}] Delete nodes:`, {
    selectedNodes: [...diagramStore.selectedNodes],
    selectedNodesArray: [...diagramStore.selectedNodes],
    selectedNodesLength: diagramStore.selectedNodes.length,
    diagramType: diagramStore.type,
    totalNodesInDiagram: diagramStore.data?.nodes?.length || 0,
  })
  console.log(`[CanvasToolbar] [${getTimestamp()}] ======================================`)

  // For circle maps, delete selected context nodes
  if (diagramType === 'circle_map') {
    let deletedCount = 0

    // Delete each selected node (skip topic/boundary)
    for (const nodeId of diagramStore.selectedNodes) {
      if (nodeId.startsWith('context-')) {
        if (diagramStore.removeNode(nodeId)) {
          deletedCount++
        }
      }
    }

    if (deletedCount > 0) {
      // Re-index remaining context nodes
      const contextNodes = diagramStore.data.nodes.filter(
        (n) => n.type === 'bubble' && n.id.startsWith('context-')
      )
      contextNodes.forEach((node, index) => {
        node.id = `context-${index}`
      })

      diagramStore.clearSelection()
      diagramStore.pushHistory('删除节点')
      notify.success(`已删除 ${deletedCount} 个节点`)
    } else {
      notify.warning('无法删除主题节点')
    }
    return
  }

  // For multi-flow maps, delete selected cause/effect nodes
  if (diagramType === 'multi_flow_map') {
    let deletedCount = 0
    const selectedNodes = [...diagramStore.selectedNodes]

    // Delete each selected node (skip event/topic node)
    for (const nodeId of selectedNodes) {
      // Protect event node from deletion
      if (nodeId === 'event') {
        continue
      }
      if (diagramStore.removeNode(nodeId)) {
        deletedCount++
      }
    }

    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory('删除节点')
      notify.success(`已删除 ${deletedCount} 个节点`)
    } else {
      notify.warning('无法删除事件节点')
    }
    return
  }

  // For bridge maps, delete entire analogy pairs
  if (diagramType === 'bridge_map') {
    if (!diagramStore.data?.nodes) {
      return
    }

    // Collect pair indices from selected nodes
    const pairIndicesToDelete = new Set<number>()
    const selectedNodes = [...diagramStore.selectedNodes]
    
    console.debug(`[CanvasToolbar] [${getTimestamp()}] Bridge map delete - Selected nodes:`, {
      selectedNodeIds: selectedNodes,
      selectedNodesCount: selectedNodes.length,
      allNodes: diagramStore.data.nodes.map((n) => ({
        id: n.id,
        text: n.text,
        pairIndex: n.data?.pairIndex,
        position: n.data?.position,
      })),
    })

    for (const nodeId of selectedNodes) {
      // Protect dimension label from deletion
      if (nodeId === 'dimension-label') {
        console.debug(`[CanvasToolbar] [${getTimestamp()}] Skipping dimension-label deletion`)
        continue
      }

      // Find the node and get its pairIndex
      const node = diagramStore.data.nodes.find((n) => n.id === nodeId)
      console.debug(`[CanvasToolbar] [${getTimestamp()}] Processing node for deletion:`, {
        nodeId,
        nodeFound: !!node,
        pairIndex: node?.data?.pairIndex,
        position: node?.data?.position,
        nodeText: node?.text,
      })
      
      if (node && node.data?.pairIndex !== undefined) {
        const pairIndex = node.data.pairIndex
        if (typeof pairIndex === 'number') {
          pairIndicesToDelete.add(pairIndex)
          console.debug(`[CanvasToolbar] [${getTimestamp()}] Added pair to delete:`, {
            pairIndex,
            willDelete: [`pair-${pairIndex}-left`, `pair-${pairIndex}-right`],
          })
        }
      }
    }
    
    console.debug(`[CanvasToolbar] [${getTimestamp()}] Pairs to delete:`, {
      pairIndices: Array.from(pairIndicesToDelete),
      totalPairs: pairIndicesToDelete.size,
    })

    // Delete both left and right nodes for each pair index
    let deletedCount = 0
    const deleteStartTime = getTimestamp()
    console.debug(`[CanvasToolbar] [${deleteStartTime}] Starting deletion of ${pairIndicesToDelete.size} pair(s)`)
    
    for (const pairIndex of pairIndicesToDelete) {
      const leftNodeId = `pair-${pairIndex}-left`
      const rightNodeId = `pair-${pairIndex}-right`

      console.debug(`[CanvasToolbar] [${getTimestamp()}] Removing nodes:`, {
        pairIndex,
        leftNodeId,
        rightNodeId,
      })

      if (diagramStore.removeNode(leftNodeId)) {
        deletedCount++
        console.debug(`[CanvasToolbar] [${getTimestamp()}] Removed left node: ${leftNodeId}`)
      }
      if (diagramStore.removeNode(rightNodeId)) {
        deletedCount++
        console.debug(`[CanvasToolbar] [${getTimestamp()}] Removed right node: ${rightNodeId}`)
      }
    }

    console.debug(`[CanvasToolbar] [${getTimestamp()}] Deletion complete. Deleted ${deletedCount} nodes. Waiting for nextTick...`)

    if (deletedCount > 0) {
      await nextTick()
      const repositionStartTime = getTimestamp()
      console.debug(`[CanvasToolbar] [${repositionStartTime}] Starting repositioning after nextTick`)
      repositionBridgeMapPairs()
      console.debug(`[CanvasToolbar] [${getTimestamp()}] Repositioning complete`)
      diagramStore.clearSelection()
      const pairCount = pairIndicesToDelete.size
      diagramStore.pushHistory(
        isZh.value ? '删除类比对' : 'Delete Analogy Pair'
      )
      notify.success(
        isZh.value
          ? `已删除 ${pairCount} 个类比对`
          : `Deleted ${pairCount} analogy pair${pairCount > 1 ? 's' : ''}`
      )
    } else {
      notify.warning(
        isZh.value ? '无法删除维度标签' : 'Cannot delete dimension label'
      )
    }
    return
  }

  // For other diagram types, delete selected nodes
  let deletedCount = 0
  const selectedNodes = [...diagramStore.selectedNodes]

  for (const nodeId of selectedNodes) {
    if (diagramStore.removeNode(nodeId)) {
      deletedCount++
    }
  }

  if (deletedCount > 0) {
    diagramStore.clearSelection()
    diagramStore.pushHistory('删除节点')
    notify.success(`已删除 ${deletedCount} 个节点`)
  } else {
    notify.warning('无法删除选中的节点')
  }
}

function handleFormatBrush() {
  notify.info('格式刷功能开发中')
}

/**
 * Handle AI Generate button click
 * Uses the useAutoComplete composable which mirrors the old JS "Auto" button behavior
 */
async function handleAIGenerate() {
  // Validate before generating
  const validation = validateForAutoComplete()
  if (!validation.valid) {
    notify.warning(validation.error || (isZh.value ? '无法生成' : 'Cannot generate'))
    return
  }

  // Use the composable's autoComplete method
  const result = await autoComplete()
  if (!result.success && result.error) {
    // Error is already shown by the composable, but we can show it again if needed
    console.error('Auto-complete failed:', result.error)
  }
}

function handleMoreApp(appName: string) {
  notify.info(`${appName}功能开发中`)
}

// Flow map orientation toggle (only visible for flow_map)
const isFlowMap = computed(() => diagramStore.type === 'flow_map')

function handleToggleOrientation() {
  diagramStore.toggleFlowMapOrientation()
  notify.success(isZh.value ? '已切换布局方向' : 'Layout direction toggled')
}
</script>

<template>
  <div class="canvas-toolbar absolute top-[60px] left-1/2 transform -translate-x-1/2 z-10">
    <div
      class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 border-t-0 rounded-b-xl shadow-lg p-1.5 flex items-center justify-center"
    >
      <div
        class="toolbar-content flex items-center bg-gray-50 dark:bg-gray-700/50 rounded-lg p-1 gap-0.5"
      >
        <!-- Undo/Redo -->
        <ElTooltip
          :content="isZh ? '撤销' : 'Undo'"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleUndo"
          >
            <RotateCw class="w-4 h-4" />
          </ElButton>
        </ElTooltip>
        <ElTooltip
          :content="isZh ? '重做' : 'Redo'"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleRedo"
          >
            <RotateCcw class="w-4 h-4" />
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <!-- Add/Delete node -->
        <!-- For multi-flow maps, show two separate buttons: Add Cause and Add Effect -->
        <template v-if="isMultiFlowMap">
          <ElTooltip
            :content="isZh ? '添加原因' : 'Add Cause'"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              @click="handleAddCause"
            >
              <Plus class="w-4 h-4" />
              <span>{{ isZh ? '添加原因' : 'Add Cause' }}</span>
            </ElButton>
          </ElTooltip>
          <ElTooltip
            :content="isZh ? '添加结果' : 'Add Effect'"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              @click="handleAddEffect"
            >
              <Plus class="w-4 h-4" />
              <span>{{ isZh ? '添加结果' : 'Add Effect' }}</span>
            </ElButton>
          </ElTooltip>
        </template>

        <!-- For bridge maps, show "Add Analogy Pair" button -->
        <template v-else-if="isBridgeMap">
          <ElTooltip
            :content="isZh ? '添加类比对' : 'Add Analogy Pair'"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              @click="handleAddNode"
            >
              <Plus class="w-4 h-4" />
              <span>{{ isZh ? '添加类比对' : 'Add Pair' }}</span>
            </ElButton>
          </ElTooltip>
        </template>

        <!-- For other diagram types, show simple button -->
        <ElTooltip
          v-else
          :content="isZh ? '增加节点' : 'Add Node'"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleAddNode"
          >
            <Plus class="w-4 h-4" />
            <span>{{ isZh ? '增加节点' : 'Add' }}</span>
          </ElButton>
        </ElTooltip>
        <ElTooltip
          :content="isZh ? '删除节点' : 'Delete Node'"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleDeleteNode"
          >
            <Trash2 class="w-4 h-4" />
            <span>{{ isZh ? '删除节点' : 'Delete' }}</span>
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <!-- Format brush -->
        <ElTooltip
          :content="isZh ? '格式刷' : 'Format Painter'"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleFormatBrush"
          >
            <PenLine class="w-4 h-4 text-purple-500" />
          </ElButton>
        </ElTooltip>

        <!-- Flow Map Direction Toggle (only for flow_map) -->
        <ElTooltip
          v-if="isFlowMap"
          :content="isZh ? '切换布局方向' : 'Toggle Direction'"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleToggleOrientation"
          >
            <ArrowDownUp class="w-4 h-4 text-blue-500" />
            <span>{{ isZh ? '方向' : 'Direction' }}</span>
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <!-- Style dropdown -->
        <ElDropdown
          trigger="hover"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
          >
            <Brush class="w-4 h-4" />
            <span>{{ isZh ? '风格' : 'Style' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-48">
                <div class="text-xs font-medium text-gray-500 mb-2">
                  {{ isZh ? '预设样式' : 'Presets' }}
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <ElDropdownItem
                    v-for="preset in stylePresets"
                    :key="preset.name"
                    class="p-2! rounded border text-xs text-center"
                    :class="[preset.bgClass, preset.borderClass]"
                  >
                    {{ preset.name }}
                  </ElDropdownItem>
                </div>
                <div class="border-t border-gray-200 my-2" />
                <ElDropdownItem>
                  <PenLine class="w-3 h-3 mr-2 text-gray-500" />
                  {{ isZh ? '线稿模式' : 'Wireframe' }}
                </ElDropdownItem>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Text style dropdown -->
        <ElDropdown
          trigger="hover"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
          >
            <Type class="w-4 h-4" />
            <span>{{ isZh ? '文本样式' : 'Text' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '字体' : 'Font' }}:</label
                  >
                  <select
                    v-model="fontFamily"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="Arial">Arial</option>
                    <option value="Microsoft YaHei">微软雅黑</option>
                    <option value="SimSun">宋体</option>
                    <option value="SimHei">黑体</option>
                  </select>
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '字号' : 'Size' }}:</label
                  >
                  <input
                    v-model.number="fontSize"
                    type="number"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '颜色' : 'Color' }}:</label
                  >
                  <div
                    class="w-10 h-10 border border-gray-300 rounded-md cursor-pointer"
                    :style="{ backgroundColor: textColor }"
                  />
                </div>
                <div class="flex gap-2 mt-2">
                  <button
                    class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 font-bold"
                  >
                    B
                  </button>
                  <button
                    class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 italic"
                  >
                    I
                  </button>
                  <button
                    class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 underline"
                  >
                    U
                  </button>
                  <button
                    class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 line-through"
                  >
                    S
                  </button>
                </div>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Background dropdown -->
        <ElDropdown
          trigger="hover"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
          >
            <ImageIcon class="w-4 h-4" />
            <span>{{ isZh ? '背景' : 'BG' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-3">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '背景颜色' : 'Background Color' }}:</label
                  >
                  <div class="grid grid-cols-5 gap-1">
                    <div
                      v-for="color in backgroundColors"
                      :key="color"
                      class="w-6 h-6 rounded border border-gray-200 cursor-pointer hover:ring-2 hover:ring-blue-400"
                      :style="{ backgroundColor: color }"
                    />
                  </div>
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '透明度' : 'Opacity' }}:</label
                  >
                  <input
                    v-model.number="backgroundOpacity"
                    type="range"
                    min="0"
                    max="100"
                    class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                  />
                  <div class="flex justify-between text-xs text-gray-500 mt-1">
                    <span>0%</span>
                    <span>100%</span>
                  </div>
                </div>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Border dropdown -->
        <ElDropdown
          trigger="hover"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
          >
            <Square class="w-4 h-4" />
            <span>{{ isZh ? '边框' : 'Border' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '颜色' : 'Color' }}:</label
                  >
                  <div
                    class="w-10 h-10 border border-gray-300 rounded-md cursor-pointer"
                    :style="{ backgroundColor: borderColor }"
                  />
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '粗细' : 'Width' }}:</label
                  >
                  <input
                    v-model.number="borderWidth"
                    type="number"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '样式' : 'Style' }}:</label
                  >
                  <select
                    v-model="borderStyle"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="solid">{{ isZh ? '实线' : 'Solid' }}</option>
                    <option value="dashed">{{ isZh ? '虚线' : 'Dashed' }}</option>
                    <option value="dotted">{{ isZh ? '点线' : 'Dotted' }}</option>
                  </select>
                </div>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <div class="divider" />

        <!-- AI Generate button -->
        <ElButton
          type="primary"
          size="small"
          class="ai-btn"
          :loading="isAIGenerating"
          @click="handleAIGenerate"
        >
          <Wand2
            v-if="!isAIGenerating"
            class="w-4 h-4"
          />
          <span>{{
            isAIGenerating
              ? isZh
                ? '生成中...'
                : 'Generating...'
              : isZh
                ? 'AI生成图示'
                : 'AI Generate'
          }}</span>
        </ElButton>

        <!-- More apps dropdown -->
        <ElDropdown
          trigger="hover"
          placement="bottom-end"
        >
          <ElButton
            size="small"
            class="more-apps-btn"
          >
            <span>{{ isZh ? '更多应用' : 'More Apps' }}</span>
            <ChevronDown class="w-3.5 h-3.5" />
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu class="more-apps-menu">
              <ElDropdownItem
                v-for="app in moreApps"
                :key="app.name"
                @click="handleMoreApp(app.name)"
              >
                <div class="flex items-start py-1">
                  <div
                    class="rounded-full p-2 mr-3 shrink-0"
                    :class="app.iconBg"
                  >
                    <component
                      :is="app.icon"
                      class="w-4 h-4"
                      :class="app.iconColor"
                    />
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="font-medium mb-0.5 flex items-center">
                      {{ app.name }}
                      <span
                        v-if="app.tag"
                        class="ml-2 text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full"
                        >{{ app.tag }}</span
                      >
                    </div>
                    <div class="text-xs text-gray-500">{{ app.desc }}</div>
                  </div>
                </div>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Divider between button groups */
.divider {
  height: 20px;
  width: 1px;
  background-color: #d1d5db;
  margin: 0 6px;
}

/* Ensure toolbar doesn't wrap */
.toolbar-content {
  flex-wrap: nowrap;
  white-space: nowrap;
}

/* Reset Element Plus button styles to match prototype exactly */
/* Prototype uses: p-2 rounded hover:bg-gray-200 transition-colors */
:deep(.toolbar-content .el-button) {
  --el-button-hover-bg-color: transparent;
  --el-button-hover-text-color: inherit;
  padding: 8px !important; /* p-2 = 8px */
  margin: 0 !important;
  min-height: auto !important;
  height: auto !important;
  border-radius: 4px !important; /* rounded = 4px */
  transition: all 0.15s ease !important;
  border: none !important;
  font-size: 12px !important; /* text-xs = 12px */
}

:deep(.toolbar-content .el-button--text) {
  color: #4b5563 !important; /* gray-600 */
  background: transparent !important;
}

:deep(.toolbar-content .el-button--text:hover) {
  background-color: #d1d5db !important; /* gray-300 for visibility */
  color: #374151 !important; /* gray-700 */
}

:deep(.toolbar-content .el-button--text:active) {
  background-color: #9ca3af !important; /* gray-400 */
}

:deep(.toolbar-content .el-button--text span) {
  margin-left: 0 !important;
}

/* Icon-only buttons should be square */
:deep(.toolbar-content .el-button--text:not(:has(span))) {
  padding: 8px !important;
}

/* Buttons with text: icon + gap-1 + text */
:deep(.toolbar-content .el-button:has(span)) {
  display: inline-flex !important;
  align-items: center !important;
  gap: 4px !important; /* gap-1 = 4px */
}

/* Dark mode text buttons */
:deep(.dark .toolbar-content .el-button--text) {
  color: #d1d5db !important; /* gray-300 */
}

:deep(.dark .toolbar-content .el-button--text:hover) {
  background-color: #4b5563 !important; /* gray-600 */
  color: #f3f4f6 !important; /* gray-100 */
}

:deep(.dark .toolbar-content .el-button--text:active) {
  background-color: #374151 !important; /* gray-700 */
}

/* AI Generate button styling */
:deep(.ai-btn) {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border: none !important;
  padding: 6px 16px !important;
  margin-left: 8px !important;
  gap: 6px !important;
}

:deep(.ai-btn:hover) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

:deep(.ai-btn span) {
  color: white !important;
}

/* More apps button styling */
:deep(.more-apps-btn) {
  background: white !important;
  border: 1px solid #e5e7eb !important;
  color: #374151 !important;
  padding: 6px 12px !important;
  margin-left: 8px !important;
  gap: 4px !important;
}

:deep(.more-apps-btn:hover) {
  background: #f9fafb !important;
  border-color: #d1d5db !important;
}

:deep(.more-apps-btn span) {
  color: #374151 !important;
}

/* More apps dropdown menu */
:deep(.more-apps-menu) {
  width: 280px !important;
}

:deep(.more-apps-menu .el-dropdown-menu__item) {
  padding: 8px 12px !important;
  line-height: 1.4 !important;
}

/* Dark mode support */
:deep(.dark) .divider {
  background-color: #4b5563;
}

:deep(.dark) .more-apps-btn {
  background: #374151 !important;
  border-color: #4b5563 !important;
  color: #e5e7eb !important;
}
</style>
