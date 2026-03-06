<script setup lang="ts">
/**
 * CanvasToolbar - Floating toolbar for canvas editing
 * Migrated from prototype MindGraphCanvasPage toolbar
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElTooltip } from 'element-plus'

import {
  ArrowDownUp,
  Brush,
  ChevronDown,
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
  X,
} from 'lucide-vue-next'

import { eventBus, useNotifications } from '@/composables'
import { useAutoComplete, useLanguage } from '@/composables'
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import {
  PRESET_BUSINESS,
  PRESET_CREATIVE,
  PRESET_SIMPLE,
  PRESET_VIBRANT,
  type StylePresetColors,
} from '@/config/colorPalette'
import { useDiagramStore, useUIStore } from '@/stores'
import type { DiagramNode } from '@/types'
import {
  getBorderStyleProps,
  type BorderStyleType,
} from '@/utils/borderStyleUtils'

const notify = useNotifications()

const { isZh } = useLanguage()
const { isGenerating: isAIGenerating, autoComplete, validateForAutoComplete } = useAutoComplete()

const props = withDefaults(
  defineProps<{
    /** When true, show exit fullscreen button */
    isPresentationMode?: boolean
  }>(),
  { isPresentationMode: false }
)

const emit = defineEmits<{
  (e: 'exit-presentation'): void
}>()

const diagramStore = useDiagramStore()
const uiStore = useUIStore()
const { updateNode: updateVueFlowNode } = useVueFlow()

// Helper function to get timestamp for logging
function getTimestamp(): string {
  return new Date().toISOString()
}

// Computed property to check if current diagram is multi-flow map
const isMultiFlowMap = computed(() => diagramStore.type === 'multi_flow_map')

// Computed property to check if current diagram is bridge map
const isBridgeMap = computed(() => diagramStore.type === 'bridge_map')

// Concept map uses real-time relationship generation only (no multi-stage AI Generate)
const isConceptMap = computed(() => diagramStore.type === 'concept_map')

// Dropdown visibility (prefixed with _ to indicate intentionally unused - reserved for future)
const _showStyleDropdown = ref(false)
const _showTextDropdown = ref(false)
const _showBackgroundDropdown = ref(false)
const _showBorderDropdown = ref(false)
const _showMoreAppsDropdown = ref(false)

// Text style state
const fontFamily = ref('Inter')
const fontSize = ref(16)
const textColor = ref('#000000')
const fontWeight = ref<'normal' | 'bold'>('normal')
const fontStyle = ref<'normal' | 'italic'>('normal')
const textDecoration = ref<'none' | 'underline' | 'line-through' | 'underline line-through'>('none')

// Text color palette: grays first, then usual colors (red, blue, green, etc.)
const textColorPalette = [
  '#000000',
  '#374151',
  '#6b7280',
  '#9ca3af',
  '#4b5563',
  '#1f2937',
  '#dc2626',
  '#ea580c',
  '#ca8a04',
  '#16a34a',
  '#059669',
  '#0d9488',
  '#0284c7',
  '#2563eb',
  '#4f46e5',
  '#7c3aed',
  '#9333ea',
  '#c026d3',
  '#db2777',
  '#e11d48',
]

// Background state
const backgroundColors = ['#FFFFFF', '#F9FAFB', '#F3F4F6', '#E5E7EB', '#D1D5DB']
const backgroundColor = ref('#FFFFFF')
const backgroundOpacity = ref(100)

/** Convert hex to rgba with opacity (0-100) */
function hexToRgba(hex: string, opacityPercent: number): string {
  const alpha = Math.max(0, Math.min(100, opacityPercent)) / 100
  const match = hex.replace('#', '').match(/.{2}/g)
  if (!match || match.length < 3) return hex
  const [r, g, b] = match.map((x) => parseInt(x, 16))
  return `rgba(${r},${g},${b},${alpha})`
}

/** Parse alpha from rgba() or return 100 for hex */
function parseAlphaFromColor(color: string): number {
  const rgba = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/)
  if (rgba && rgba[4] !== undefined) return Math.round(parseFloat(rgba[4]) * 100)
  return 100
}

/** Extract base hex from rgba or return as-is for hex */
function colorToHex(color: string): string {
  const rgba = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (rgba) {
    const r = parseInt(rgba[1], 10).toString(16).padStart(2, '0')
    const g = parseInt(rgba[2], 10).toString(16).padStart(2, '0')
    const b = parseInt(rgba[3], 10).toString(16).padStart(2, '0')
    return `#${r}${g}${b}`
  }
  return color
}

// Border state
const borderColor = ref('#000000')
const borderColorPalette = [
  '#000000',
  '#374151',
  '#6b7280',
  '#9ca3af',
  '#dc2626',
  '#ea580c',
  '#16a34a',
  '#0284c7',
  '#2563eb',
  '#7c3aed',
  '#9333ea',
  '#db2777',
]
const borderWidth = ref(1)
const borderStyle = ref<BorderStyleType>('solid')

const borderStyleOptions: BorderStyleType[] = [
  'solid',
  'dashed',
  'dotted',
  'double',
  'dash-dot',
  'dash-dot-dot',
]

function getBorderPreviewStyle(style: BorderStyleType) {
  return getBorderStyleProps(borderColor.value, 2, style, {
    backgroundColor: '#f9fafb',
  })
}

// Style presets: WCAG AA contrast-compliant palettes (bg + text + border)
const stylePresets: Array<
  {
    name: string
    bgClass: string
    borderClass: string
  } & StylePresetColors
> = [
  {
    name: '简约风格',
    bgClass: 'bg-blue-50',
    borderClass: 'border-blue-600',
    ...PRESET_SIMPLE,
  },
  {
    name: '创意风格',
    bgClass: 'bg-purple-50',
    borderClass: 'border-purple-600',
    ...PRESET_CREATIVE,
  },
  {
    name: '商务风格',
    bgClass: 'bg-green-50',
    borderClass: 'border-green-600',
    ...PRESET_BUSINESS,
  },
  {
    name: '活力风格',
    bgClass: 'bg-yellow-50',
    borderClass: 'border-yellow-600',
    ...PRESET_VIBRANT,
  },
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
]

function handleApplyStylePreset(preset: StylePresetColors) {
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
    return
  }
  diagramStore.applyStylePreset(preset)
  notify.success(isZh.value ? '已应用样式' : 'Style applied')
}

function applyTextStyleToSelected(updates: {
  fontFamily?: string
  fontSize?: number
  textColor?: string
  fontWeight?: 'normal' | 'bold'
  fontStyle?: 'normal' | 'italic'
  textDecoration?: 'none' | 'underline' | 'line-through' | 'underline line-through'
}) {
  const ids = diagramStore.selectedNodes
  if (!ids.length) {
    notify.warning(isZh.value ? '请先选择节点' : 'Please select node(s) first')
    return
  }
  diagramStore.pushHistory(isZh.value ? '更新文本样式' : 'Update text style')
  ids.forEach((nodeId) => {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node) {
      const mergedStyle = { ...(node.style || {}), ...updates }
      diagramStore.updateNode(nodeId, { style: mergedStyle })
    }
  })
  notify.success(isZh.value ? '已应用' : 'Applied')
}

function applyBackgroundToSelected(color?: string) {
  const ids = diagramStore.selectedNodes
  if (!ids.length) {
    notify.warning(isZh.value ? '请先选择节点' : 'Please select node(s) first')
    return
  }
  const baseColor = color ?? backgroundColor.value
  backgroundColor.value = colorToHex(baseColor)
  const value = hexToRgba(colorToHex(baseColor), backgroundOpacity.value)
  diagramStore.pushHistory(isZh.value ? '更新背景' : 'Update background')
  ids.forEach((nodeId) => {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node) {
      const mergedStyle = { ...(node.style || {}), backgroundColor: value }
      diagramStore.updateNode(nodeId, { style: mergedStyle })
    }
  })
  notify.success(isZh.value ? '已应用' : 'Applied')
}

function applyBorderToSelected(updates: {
  borderColor?: string
  borderWidth?: number
  borderStyle?: import('@/types').NodeStyle['borderStyle']
}) {
  const ids = diagramStore.selectedNodes
  if (!ids.length) {
    notify.warning(isZh.value ? '请先选择节点' : 'Please select node(s) first')
    return
  }
  if (updates.borderColor !== undefined) borderColor.value = updates.borderColor
  if (updates.borderWidth !== undefined) borderWidth.value = updates.borderWidth
  if (updates.borderStyle !== undefined) borderStyle.value = updates.borderStyle
  diagramStore.pushHistory(isZh.value ? '更新边框' : 'Update border')
  ids.forEach((nodeId) => {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node) {
      const mergedStyle = { ...(node.style || {}), ...updates }
      diagramStore.updateNode(nodeId, { style: mergedStyle })
    }
  })
  notify.success(isZh.value ? '已应用' : 'Applied')
}

function handleToggleBold() {
  fontWeight.value = fontWeight.value === 'bold' ? 'normal' : 'bold'
  applyTextStyleToSelected({ fontWeight: fontWeight.value })
}

function handleToggleItalic() {
  fontStyle.value = fontStyle.value === 'italic' ? 'normal' : 'italic'
  applyTextStyleToSelected({ fontStyle: fontStyle.value })
}

function toggleTextDecorationPart(
  part: 'underline' | 'line-through'
): 'none' | 'underline' | 'line-through' | 'underline line-through' {
  const current = textDecoration.value || 'none'
  const parts = current.split(' ').filter(Boolean)
  const has = parts.includes(part)
  if (has) {
    const newParts = parts.filter((p) => p !== part)
    return (newParts.length ? newParts.join(' ') : 'none') as
      | 'none'
      | 'underline'
      | 'line-through'
      | 'underline line-through'
  }
  return [...parts, part].filter(Boolean).join(' ') as
    | 'none'
    | 'underline'
    | 'line-through'
    | 'underline line-through'
}

function handleToggleUnderline() {
  textDecoration.value = toggleTextDecorationPart('underline')
  applyTextStyleToSelected({ textDecoration: textDecoration.value })
}

function handleToggleStrikethrough() {
  textDecoration.value = toggleTextDecorationPart('line-through')
  applyTextStyleToSelected({ textDecoration: textDecoration.value })
}

function handleFontFamilyChange(ev: Event) {
  const val = (ev.target as HTMLSelectElement).value
  fontFamily.value = val
  applyTextStyleToSelected({ fontFamily: val })
}

function handleFontSizeInput(ev: Event) {
  const v = parseInt((ev.target as HTMLInputElement).value, 10)
  if (!Number.isNaN(v)) {
    fontSize.value = v
    applyTextStyleToSelected({ fontSize: v })
  }
}

function handleTextColorPick(color: string) {
  textColor.value = color
  applyTextStyleToSelected({ textColor: color })
}

watch(
  () => diagramStore.selectedNodeData,
  (nodes) => {
    if (nodes.length === 1) {
      const s = nodes[0]?.style
      if (s) {
        if (s.fontFamily) fontFamily.value = s.fontFamily
        if (s.fontSize) fontSize.value = s.fontSize
        if (s.textColor) textColor.value = s.textColor
        if (s.fontWeight) fontWeight.value = s.fontWeight
        if (s.fontStyle) fontStyle.value = s.fontStyle
        if (s.textDecoration) textDecoration.value = s.textDecoration
        if (s.borderColor) borderColor.value = s.borderColor
        if (s.borderWidth !== undefined) borderWidth.value = s.borderWidth
        if (s.borderStyle) borderStyle.value = s.borderStyle
        if (s.backgroundColor) {
          backgroundColor.value = colorToHex(s.backgroundColor)
          backgroundOpacity.value = parseAlphaFromColor(s.backgroundColor)
        }
      }
    }
  },
  { deep: true }
)

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

  // For bubble maps, add a new attribute node
  if (diagramType === 'bubble_map') {
    const bubbleNodes = diagramStore.data.nodes.filter(
      (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
    )
    const newIndex = bubbleNodes.length

    diagramStore.addNode({
      id: `bubble-${newIndex}`,
      text: isZh.value ? '新属性' : 'New Attribute',
      type: 'bubble',
      position: { x: 0, y: 0 },
    })

    diagramStore.data.connections.push({
      id: `edge-topic-bubble-${newIndex}`,
      source: 'topic',
      target: `bubble-${newIndex}`,
    })

    diagramStore.pushHistory(isZh.value ? '添加属性' : 'Add Attribute')
    notify.success(isZh.value ? '已添加新属性' : 'Attribute added')
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

  // For mindmap/brace_map: add branch (Tab) or child (Enter) - handled by handleAddBranch/handleAddChild
  if (diagramType === 'mindmap' || diagramType === 'mind_map' || diagramType === 'brace_map') {
    handleAddBranch()
    return
  }

  // For double bubble map: user must select a similarity/difference node, then add to that group.
  // Similarity: adds one node (connects both topics). Difference: adds a PAIR (left + right).
  if (diagramType === 'double_bubble_map') {
    const selectedId = diagramStore.selectedNodes[0]
    const group = getDoubleBubbleGroupFromNodeId(selectedId)
    if (!group) {
      notify.warning(
        isZh.value
          ? '请先选择相似点或不同点节点'
          : 'Please select a similarity or difference node first'
      )
      return
    }
    const spec = diagramStore.getDoubleBubbleSpecFromData()
    if (!spec) return
    const similarities = (spec.similarities as string[]) || []
    const leftDifferences = (spec.leftDifferences as string[]) || []
    const rightDifferences = (spec.rightDifferences as string[]) || []
    const newSimText = isZh.value ? `相似点 ${similarities.length + 1}` : `Similarity ${similarities.length + 1}`
    const pairIndex = Math.max(leftDifferences.length, rightDifferences.length) + 1
    const newLeftText = isZh.value ? `不同点A${pairIndex}` : `Difference A${pairIndex}`
    const newRightText = isZh.value ? `不同点B${pairIndex}` : `Difference B${pairIndex}`
    const text = group === 'similarity' ? newSimText : newLeftText
    const pairText = group === 'similarity' ? undefined : newRightText
    if (diagramStore.addDoubleBubbleMapNode(group, text, pairText)) {
      diagramStore.pushHistory(isZh.value ? '添加节点' : 'Add node')
      notify.success(
        group === 'similarity'
          ? isZh.value ? '已添加节点' : 'Node added'
          : isZh.value ? '已添加一对不同点' : 'Difference pair added'
      )
    }
    return
  }

  // For other diagram types, show under development message
  notify.info('增加节点功能开发中')
}

/** Resolve double bubble group from node id: similarity-*, left-diff-*, right-diff-* */
function getDoubleBubbleGroupFromNodeId(
  nodeId: string | undefined
): 'similarity' | 'leftDiff' | 'rightDiff' | null {
  if (!nodeId) return null
  if (/^similarity-\d+$/.test(nodeId)) return 'similarity'
  if (/^left-diff-\d+$/.test(nodeId)) return 'leftDiff'
  if (/^right-diff-\d+$/.test(nodeId)) return 'rightDiff'
  return null
}

function handleAddBranch() {
  const diagramType = diagramStore.type
  if (diagramType === 'brace_map') {
    if (!diagramStore.data?.nodes) {
      notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
      return
    }
    const targetIds = new Set(diagramStore.data.connections?.map((c) => c.target) ?? [])
    const rootId =
      diagramStore.data.nodes.find((n) => n.type === 'topic')?.id ??
      diagramStore.data.nodes.find((n) => !targetIds.has(n.id))?.id
    if (!rootId) return
    const text = isZh.value ? '新部分' : 'New Part'
    const subpartTexts: [string, string] = isZh.value
      ? ['子部分1', '子部分2']
      : ['Subpart 1', 'Subpart 2']
    if (diagramStore.addBraceMapPart(rootId, text, subpartTexts)) {
      notify.success(isZh.value ? '已添加部分' : 'Part added')
    }
    return
  }
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return
  if (!diagramStore.data?.nodes) {
    notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
    return
  }

  const selectedId = diagramStore.selectedNodes[0]
  const side: 'left' | 'right' =
    selectedId?.startsWith('branch-l-') ? 'left' : 'right'
  const text = isZh.value ? '新分支' : 'New Branch'
  const childText = isZh.value ? '新子项' : 'New Child'

  if (diagramStore.addMindMapBranch(side, text, childText)) {
    notify.success(isZh.value ? '已添加分支' : 'Branch added')
  }
}

function handleAddChild() {
  const diagramType = diagramStore.type
  if (diagramType === 'brace_map') {
    if (!diagramStore.data?.nodes) {
      notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
      return
    }
    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId) {
      notify.warning(
        isZh.value ? '请先选择要添加子部分的节点' : 'Please select a part to add subpart to'
      )
      return
    }
    const targetIds = new Set(diagramStore.data.connections?.map((c) => c.target) ?? [])
    const rootId =
      diagramStore.data.nodes.find((n) => n.type === 'topic')?.id ??
      diagramStore.data.nodes.find((n) => !targetIds.has(n.id))?.id
    if (selectedId === rootId || selectedId === 'dimension-label') {
      notify.warning(
        isZh.value ? '请选择部分节点后按 Enter 添加子部分' : 'Select a part node, then press Enter to add subpart'
      )
      return
    }
    const text = isZh.value ? '新子部分' : 'New Subpart'
    if (diagramStore.addBraceMapPart(selectedId, text)) {
      notify.success(isZh.value ? '已添加子部分' : 'Subpart added')
    }
    return
  }
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return
  if (!diagramStore.data?.nodes) {
    notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
    return
  }

  const selectedId = diagramStore.selectedNodes[0]
  if (!selectedId || selectedId === 'topic') {
    notify.warning(isZh.value ? '请先选择分支或子节点' : 'Please select a branch or child node')
    return
  }

  const text = isZh.value ? '新子项' : 'New Child'
  if (diagramStore.addMindMapChild(selectedId, text)) {
    notify.success(isZh.value ? '已添加子项' : 'Child added')
  } else {
    notify.warning(isZh.value ? '无法添加子项' : 'Cannot add child')
  }
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

    console.debug(
      `[CanvasToolbar] [${getTimestamp()}] Updating pair ${pair.left.data?.pairIndex}:`,
      {
        leftNodeId: pair.left.id,
        rightNodeId: pair.right.id,
        newX: currentX,
        leftNodeY,
        rightNodeY,
      }
    )

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

  // For bubble maps, delete selected attribute nodes (bulk remove + re-index)
  if (diagramType === 'bubble_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const deletedCount = diagramStore.removeBubbleMapNodes(selectedNodes)

    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(isZh.value ? '删除属性' : 'Delete Attribute')
      notify.success(
        isZh.value ? `已删除 ${deletedCount} 个属性` : `Deleted ${deletedCount} attribute(s)`
      )
    } else {
      notify.warning(isZh.value ? '无法删除主题节点' : 'Cannot delete topic node')
    }
    return
  }

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

  // For brace maps, delete selected part/subpart nodes (and descendants)
  if (diagramType === 'brace_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const deletedCount = diagramStore.removeBraceMapNodes(selectedNodes)

    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(isZh.value ? '删除节点' : 'Delete nodes')
      notify.success(
        isZh.value ? `已删除 ${deletedCount} 个节点` : `Deleted ${deletedCount} node(s)`
      )
    } else {
      notify.warning(isZh.value ? '无法删除主题节点' : 'Cannot delete topic node')
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

  // For mindmap: rebuild spec and remove selected branches/children
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const deletedCount = diagramStore.removeMindMapNodes(selectedNodes)

    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(isZh.value ? '删除节点' : 'Delete nodes')
      notify.success(`已删除 ${deletedCount} 个节点`)
    } else {
      notify.warning(isZh.value ? '无法删除主题节点' : 'Cannot delete topic node')
    }
    return
  }

  // For double bubble map: delete selected similarity/difference nodes (protect topics)
  if (diagramType === 'double_bubble_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const toDelete = selectedNodes.filter(
      (id) =>
        /^similarity-\d+$/.test(id) ||
        /^left-diff-\d+$/.test(id) ||
        /^right-diff-\d+$/.test(id)
    )
    if (toDelete.length === 0) {
      notify.warning(
        isZh.value
          ? '请选择相似点或不同点节点（主题节点不可删除）'
          : 'Please select similarity or difference nodes (topic nodes cannot be deleted)'
      )
      return
    }

    const deletedCount = diagramStore.removeDoubleBubbleMapNodes(toDelete)
    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(isZh.value ? '删除节点' : 'Delete nodes')
      notify.success(
        isZh.value ? `已删除 ${deletedCount} 个节点` : `Deleted ${deletedCount} node(s)`
      )
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
    console.debug(
      `[CanvasToolbar] [${deleteStartTime}] Starting deletion of ${pairIndicesToDelete.size} pair(s)`
    )

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

    console.debug(
      `[CanvasToolbar] [${getTimestamp()}] Deletion complete. Deleted ${deletedCount} nodes. Waiting for nextTick...`
    )

    if (deletedCount > 0) {
      await nextTick()
      const repositionStartTime = getTimestamp()
      console.debug(
        `[CanvasToolbar] [${repositionStartTime}] Starting repositioning after nextTick`
      )
      repositionBridgeMapPairs()
      console.debug(`[CanvasToolbar] [${getTimestamp()}] Repositioning complete`)
      diagramStore.clearSelection()
      const pairCount = pairIndicesToDelete.size
      diagramStore.pushHistory(isZh.value ? '删除类比对' : 'Delete Analogy Pair')
      notify.success(
        isZh.value
          ? `已删除 ${pairCount} 个类比对`
          : `Deleted ${pairCount} analogy pair${pairCount > 1 ? 's' : ''}`
      )
    } else {
      notify.warning(isZh.value ? '无法删除维度标签' : 'Cannot delete dimension label')
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

async function handleMoreApp(appName: string) {
  if (appName === '瀑布流') {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
      return
    }
    eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'toolbar' })
    return
  }
  if (appName === '半成品图示') {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
      return
    }
    if (diagramStore.isLearningSheet) {
      diagramStore.restoreFromLearningSheetMode()
      notify.success(isZh.value ? '已切换回普通模式' : 'Switched back to regular mode')
    } else if (diagramStore.hasPreservedLearningSheet()) {
      diagramStore.applyLearningSheetView()
      notify.success(isZh.value ? '已恢复学习单' : 'Learning sheet restored')
    } else {
      diagramStore.setLearningSheetMode(true)
      const spec = diagramStore.getSpecForSave()
      if (spec && diagramStore.type) {
        const enrichedSpec = {
          ...spec,
          is_learning_sheet: true,
          hidden_node_percentage: 0.2,
        }
        diagramStore.loadFromSpec(enrichedSpec, diagramStore.type)
        notify.success(isZh.value ? '已切换为半成品图示模式' : 'Switched to learning sheet mode')
      }
    }
    return
  }
  notify.info(`${appName}功能开发中`)
}

// Flow map orientation toggle (only visible for flow_map)
const isFlowMap = computed(() => diagramStore.type === 'flow_map')

function handleToggleOrientation() {
  diagramStore.toggleFlowMapOrientation()
  notify.success(isZh.value ? '已切换布局方向' : 'Layout direction toggled')
}

onMounted(() => {
  eventBus.on('diagram:delete_selected_requested', handleDeleteNode)
  eventBus.on('diagram:add_node_requested', handleAddNode)
  eventBus.on('diagram:add_branch_requested', handleAddBranch)
  eventBus.on('diagram:add_child_requested', handleAddChild)
})

onUnmounted(() => {
  eventBus.off('diagram:delete_selected_requested', handleDeleteNode)
  eventBus.off('diagram:add_node_requested', handleAddNode)
  eventBus.off('diagram:add_branch_requested', handleAddBranch)
  eventBus.off('diagram:add_child_requested', handleAddChild)
})
</script>

<template>
  <div
    :class="[
      'canvas-toolbar absolute left-1/2 transform -translate-x-1/2 z-10',
      props.isPresentationMode ? 'top-4' : 'top-[60px]',
    ]"
  >
    <div
      class="rounded-xl shadow-lg p-1.5 flex items-center justify-center border border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md"
    >
      <div
        class="toolbar-content flex items-center bg-gray-50 dark:bg-gray-700/50 rounded-lg p-1 gap-0.5"
      >
        <!-- Exit fullscreen (presentation mode only) -->
        <template v-if="props.isPresentationMode">
          <ElTooltip
            :content="isZh ? '退出全屏' : 'Exit Fullscreen'"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              class="text-red-600 hover:text-red-700 dark:text-red-400"
              @click="emit('exit-presentation')"
            >
              <X class="w-4 h-4" />
              <span>{{ isZh ? '退出' : 'Exit' }}</span>
            </ElButton>
          </ElTooltip>
          <div class="divider" />
        </template>

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
                    @click="handleApplyStylePreset(preset)"
                  >
                    {{ preset.name }}
                  </ElDropdownItem>
                </div>
                <div class="border-t border-gray-200 my-2" />
                <ElDropdownItem
                  :class="{ 'bg-blue-50': uiStore.wireframeMode }"
                  @click="uiStore.toggleWireframe()"
                >
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
              <div class="p-2.5 w-48 text-style-dropdown">
                <!-- Format buttons: B I U S -->
                <div class="mb-2">
                  <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                    {{ isZh ? '格式' : 'Format' }}
                  </div>
                  <div class="grid grid-cols-4 gap-1.5">
                    <button
                      type="button"
                      class="format-btn min-w-[1.75rem] h-7 rounded border text-sm font-bold transition-all"
                      :class="[
                        fontWeight === 'bold'
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                      ]"
                      @click="handleToggleBold"
                    >
                      B
                    </button>
                    <button
                      type="button"
                      class="format-btn min-w-[1.75rem] h-7 rounded border italic text-sm transition-all"
                      :class="[
                        fontStyle === 'italic'
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                      ]"
                      @click="handleToggleItalic"
                    >
                      I
                    </button>
                    <button
                      type="button"
                      class="format-btn min-w-[1.75rem] h-7 rounded border underline text-sm transition-all"
                      :class="[
                        textDecoration?.includes('underline')
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                      ]"
                      @click="handleToggleUnderline"
                    >
                      U
                    </button>
                    <button
                      type="button"
                      class="format-btn min-w-[1.75rem] h-7 rounded border line-through text-sm transition-all"
                      :class="[
                        textDecoration?.includes('line-through')
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                      ]"
                      @click="handleToggleStrikethrough"
                    >
                      S
                    </button>
                  </div>
                </div>

                <div class="border-t border-gray-100 my-2" />

                <!-- Font & Size -->
                <div class="mb-2">
                  <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                    {{ isZh ? '字体' : 'Font' }}
                  </div>
                  <div class="grid grid-cols-2 gap-1.5">
                    <select
                      :value="fontFamily"
                      class="w-full border border-gray-200 rounded py-1.5 px-2 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500/40 focus:border-blue-400"
                      @change="handleFontFamilyChange"
                    >
                      <optgroup :label="isZh ? '中文字体' : 'Chinese'">
                        <option value="Microsoft YaHei">微软雅黑</option>
                        <option value="SimSun">宋体</option>
                        <option value="SimHei">黑体</option>
                        <option value="KaiTi">楷体</option>
                        <option value="FangSong">仿宋</option>
                      </optgroup>
                      <optgroup :label="isZh ? '英文字体' : 'English'">
                        <option value="Arial">Arial</option>
                        <option value="Inter">Inter</option>
                        <option value="Georgia">Georgia</option>
                        <option value="Courier New">Courier New</option>
                      </optgroup>
                    </select>
                    <input
                      :value="fontSize"
                      type="number"
                      min="8"
                      max="72"
                      class="w-full border border-gray-200 rounded py-1.5 px-2 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500/40 focus:border-blue-400"
                      @input="handleFontSizeInput"
                    />
                  </div>
                </div>

                <div class="border-t border-gray-100 my-2" />

                <!-- Color -->
                <div>
                  <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                    {{ isZh ? '颜色' : 'Color' }}
                  </div>
                  <div class="grid grid-cols-6 gap-1">
                    <div
                      v-for="color in textColorPalette"
                      :key="color"
                      class="w-5 h-5 rounded border cursor-pointer transition-all hover:scale-105"
                      :class="[
                        textColor === color
                          ? 'border-blue-500 ring-1 ring-blue-200'
                          : 'border-gray-200 hover:border-gray-300',
                      ]"
                      :style="{ backgroundColor: color }"
                      @click="handleTextColorPick(color)"
                    />
                  </div>
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
                      class="w-6 h-6 rounded border border-gray-200 cursor-pointer hover:ring-2 hover:ring-blue-400 shrink-0"
                      :style="{ backgroundColor: color }"
                      @click="applyBackgroundToSelected(color)"
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
                    @change="applyBackgroundToSelected()"
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
                  <div class="grid grid-cols-5 gap-1">
                    <div
                      v-for="color in borderColorPalette"
                      :key="color"
                      class="w-6 h-6 rounded border border-gray-200 cursor-pointer hover:ring-2 hover:ring-blue-400 shrink-0"
                      :class="{ 'ring-2 ring-blue-500': borderColor === color }"
                      :style="{ backgroundColor: color }"
                      @click="applyBorderToSelected({ borderColor: color })"
                    />
                  </div>
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ isZh ? '粗细' : 'Width' }}:</label
                  >
                  <input
                    v-model.number="borderWidth"
                    type="number"
                    min="1"
                    max="10"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    @change="applyBorderToSelected({ borderWidth: borderWidth })"
                  />
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1.5"
                    >{{ isZh ? '样式' : 'Style' }}:</label
                  >
                  <div class="grid grid-cols-3 gap-1.5">
                    <button
                      v-for="style in borderStyleOptions"
                      :key="style"
                      type="button"
                      class="border-style-option flex items-center justify-center rounded-md p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-gray-600"
                      :class="{
                        'bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-500':
                          borderStyle === style,
                      }"
                      @click="
                        borderStyle = style;
                        applyBorderToSelected({ borderStyle: style });
                      "
                    >
                      <div
                        class="border-preview-pill h-5 w-14"
                        :style="{
                          borderRadius: '9999px',
                          backgroundColor: '#f9fafb',
                          ...getBorderPreviewStyle(style),
                        }"
                      />
                    </button>
                  </div>
                </div>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <template v-if="!isConceptMap">
          <div class="divider" />
          <!-- AI Generate button (hidden for concept_map - uses real-time relationship generation) -->
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
        </template>

        <div
          v-if="!isConceptMap"
          class="divider"
        />

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
  margin-left: 12px !important;
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

/* Text style dropdown - format buttons */
.text-style-dropdown .format-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
