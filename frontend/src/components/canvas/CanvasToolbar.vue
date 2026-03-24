<script setup lang="ts">
/**
 * CanvasToolbar - Floating toolbar for canvas editing
 * Migrated from prototype MindGraphCanvasPage toolbar
 */
import { type ComputedRef, computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElTooltip } from 'element-plus'

import {
  ArrowDownUp,
  Brush,
  Camera,
  ChevronDown,
  Image as ImageIcon,
  Layers,
  LayoutGrid,
  Package,
  PenLine,
  Plus,
  RotateCcw,
  RotateCw,
  Sparkles,
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
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramNode } from '@/types'
import { type BorderStyleType, getBorderStyleProps } from '@/utils/borderStyleUtils'

const notify = useNotifications()

const { t } = useLanguage()
const { isGenerating: isAIGenerating, autoComplete, validateForAutoComplete } = useAutoComplete()

const props = withDefaults(
  defineProps<{
    /** When true, show exit fullscreen button */
    isPresentationMode?: boolean
  }>(),
  { isPresentationMode: false }
)

const emit = defineEmits<{
  (e: 'exitPresentation'): void
}>()

const diagramStore = useDiagramStore()
const uiStore = useUIStore()
const savedDiagramsStore = useSavedDiagramsStore()

const collabCanvas = inject<
  | {
      isDiagramOwner?: ComputedRef<boolean>
    }
  | undefined
>('collabCanvas', undefined)

const aiBlockedByCollab = computed(() => {
  if (!diagramStore.collabSessionActive) {
    return false
  }
  const own = collabCanvas?.isDiagramOwner
  if (!own) {
    return false
  }
  return !own.value
})

// Helper function to get timestamp for logging
function getTimestamp(): string {
  return new Date().toISOString()
}

// Computed property to check if current diagram is multi-flow map
const isMultiFlowMap = computed(() => diagramStore.type === 'multi_flow_map')

// Computed property to check if current diagram is bridge map
const isBridgeMap = computed(() => diagramStore.type === 'bridge_map')

// Concept map uses real-time relationship generation only (no multi-stage AI Generate).
// Default editing experience is "standard" mode; alternate concept-map modes are not wired yet.
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
    nameKey: string
    bgClass: string
    borderClass: string
  } & StylePresetColors
> = [
  {
    nameKey: 'canvas.toolbar.stylePresetSimple',
    bgClass: 'bg-blue-50',
    borderClass: 'border-blue-600',
    ...PRESET_SIMPLE,
  },
  {
    nameKey: 'canvas.toolbar.stylePresetCreative',
    bgClass: 'bg-purple-50',
    borderClass: 'border-purple-600',
    ...PRESET_CREATIVE,
  },
  {
    nameKey: 'canvas.toolbar.stylePresetBusiness',
    bgClass: 'bg-green-50',
    borderClass: 'border-green-600',
    ...PRESET_BUSINESS,
  },
  {
    nameKey: 'canvas.toolbar.stylePresetVibrant',
    bgClass: 'bg-yellow-50',
    borderClass: 'border-yellow-600',
    ...PRESET_VIBRANT,
  },
]

type MoreAppHandlerKey = 'concept_map_modes'

type MoreAppItem = {
  name: string
  icon: typeof LayoutGrid
  desc: string
  tag?: string
  iconBg: string
  iconColor: string
  handlerKey?: MoreAppHandlerKey
  appKey?: 'waterfall' | 'learning_sheet' | 'snapshot'
}

// More apps items (hide waterfall for concept_map — dedicated concept generation button)
const moreApps = computed((): MoreAppItem[] => {
  const conceptMapModesRow: MoreAppItem = {
    name: t('canvas.toolbar.moreAppConceptMapModes'),
    icon: Layers,
    desc: t('canvas.toolbar.moreAppConceptMapModesDesc'),
    tag: t('canvas.toolbar.tagSoon'),
    iconBg: 'bg-emerald-100',
    iconColor: 'text-emerald-600',
    handlerKey: 'concept_map_modes',
  }
  const apps: MoreAppItem[] = [
    {
      appKey: 'waterfall',
      name: t('canvas.toolbar.moreAppWaterfall'),
      icon: LayoutGrid,
      desc: t('canvas.toolbar.moreAppWaterfallDesc'),
      tag: t('canvas.toolbar.tagHot'),
      iconBg: 'bg-blue-100',
      iconColor: 'text-blue-600',
    },
    {
      appKey: 'learning_sheet',
      name: t('canvas.toolbar.moreAppLearningSheet'),
      icon: Package,
      desc: t('canvas.toolbar.moreAppLearningSheetDesc'),
      iconBg: 'bg-purple-100',
      iconColor: 'text-purple-600',
    },
    {
      appKey: 'snapshot',
      name: t('canvas.toolbar.moreAppSnapshot'),
      icon: Camera,
      desc: t('canvas.toolbar.moreAppSnapshotDesc'),
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-600',
    },
  ]
  const withoutWaterfall = isConceptMap.value
    ? apps.filter((a) => a.appKey !== 'waterfall')
    : apps
  if (isConceptMap.value) {
    return [conceptMapModesRow, ...withoutWaterfall]
  }
  return withoutWaterfall
})

function handleApplyStylePreset(preset: StylePresetColors) {
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }
  diagramStore.applyStylePreset(preset)
  notify.success(t('canvas.toolbar.styleApplied'))
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
    notify.warning(t('canvas.toolbar.selectNodesFirst'))
    return
  }
  diagramStore.pushHistory(t('canvas.toolbar.updateTextStyle'))
  ids.forEach((nodeId) => {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node) {
      const mergedStyle = { ...(node.style || {}), ...updates }
      diagramStore.updateNode(nodeId, { style: mergedStyle })
    }
  })
  notify.success(t('canvas.toolbar.applied'))
}

function applyBackgroundToSelected(color?: string) {
  const ids = diagramStore.selectedNodes
  if (!ids.length) {
    notify.warning(t('canvas.toolbar.selectNodesFirst'))
    return
  }
  const baseColor = color ?? backgroundColor.value
  backgroundColor.value = colorToHex(baseColor)
  const value = hexToRgba(colorToHex(baseColor), backgroundOpacity.value)
  diagramStore.pushHistory(t('canvas.toolbar.updateBackground'))
  ids.forEach((nodeId) => {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node) {
      const mergedStyle = { ...(node.style || {}), backgroundColor: value }
      diagramStore.updateNode(nodeId, { style: mergedStyle })
    }
  })
  notify.success(t('canvas.toolbar.applied'))
}

function applyBorderToSelected(updates: {
  borderColor?: string
  borderWidth?: number
  borderStyle?: import('@/types').NodeStyle['borderStyle']
}) {
  const ids = diagramStore.selectedNodes
  if (!ids.length) {
    notify.warning(t('canvas.toolbar.selectNodesFirst'))
    return
  }
  if (updates.borderColor !== undefined) borderColor.value = updates.borderColor
  if (updates.borderWidth !== undefined) borderWidth.value = updates.borderWidth
  if (updates.borderStyle !== undefined) borderStyle.value = updates.borderStyle
  diagramStore.pushHistory(t('canvas.toolbar.updateBorder'))
  ids.forEach((nodeId) => {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node) {
      const mergedStyle = { ...(node.style || {}), ...updates }
      diagramStore.updateNode(nodeId, { style: mergedStyle })
    }
  })
  notify.success(t('canvas.toolbar.applied'))
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
        textDecoration.value = s.textDecoration ?? 'none'
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
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }

  // For bubble maps, add a new attribute node (addNode recalculates layout and connections)
  if (diagramType === 'bubble_map') {
    const bubbleNodes = diagramStore.data.nodes.filter(
      (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
    )
    const newIndex = bubbleNodes.length

    diagramStore.addNode({
      id: `bubble-${newIndex}`,
      text: t('canvas.toolbar.newAttribute'),
      type: 'bubble',
      position: { x: 0, y: 0 },
    })

    diagramStore.pushHistory(t('canvas.toolbar.addAttributeHistory'))
    notify.success(t('canvas.toolbar.attributeAdded'))
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
      text: t('canvas.toolbar.newAssociation'),
      type: 'bubble',
      position: { x: 0, y: 0 }, // Will be recalculated
    })

    diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
    notify.success(t('canvas.toolbar.nodeAddedCircle'))
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
      text: t('canvas.toolbar.newItemA'),
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
      text: t('canvas.toolbar.newItemB'),
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

    diagramStore.pushHistory(t('canvas.toolbar.addAnalogyPairHistory'))
    notify.success(t('canvas.toolbar.analogyPairAdded'))
    return
  }

  // For mindmap/brace_map: add branch (Tab) or child (Enter) - handled by handleAddBranch/handleAddChild
  if (diagramType === 'mindmap' || diagramType === 'mind_map' || diagramType === 'brace_map') {
    handleAddBranch()
    return
  }

  // For flow map: add step or substep
  if (diagramType === 'flow_map') {
    const selectedId = diagramStore.selectedNodes[0]
    const selectedNode = selectedId
      ? diagramStore.data?.nodes?.find((n) => n.id === selectedId)
      : undefined
    const isStepSelected = selectedNode?.type === 'flow'
    if (isStepSelected && selectedNode?.text) {
      if (
        diagramStore.addFlowMapSubstep(selectedNode.text, t('canvas.toolbar.newSubstep'))
      ) {
        diagramStore.pushHistory(t('canvas.toolbar.addSubstepHistory'))
        notify.success(t('canvas.toolbar.substepAdded'))
      }
    } else {
      const stepCount = diagramStore.data?.nodes?.filter((n) => n.type === 'flow').length ?? 0
      const stepNum = stepCount + 1
      const defaultSubsteps: [string, string] = [
        t('canvas.toolbar.substepDefault1', { n: stepNum }),
        t('canvas.toolbar.substepDefault2', { n: stepNum }),
      ]
      if (diagramStore.addFlowMapStep(t('canvas.toolbar.newStep'), defaultSubsteps)) {
        diagramStore.pushHistory(t('canvas.toolbar.addStepHistory'))
        notify.success(t('canvas.toolbar.stepAdded'))
      }
    }
    return
  }

  // For double bubble map: user must select a similarity/difference node, then add to that group.
  // Similarity: adds one node (connects both topics). Difference: adds a PAIR (left + right).
  if (diagramType === 'double_bubble_map') {
    const selectedId = diagramStore.selectedNodes[0]
    const group = getDoubleBubbleGroupFromNodeId(selectedId)
    if (!group) {
      notify.warning(t('canvas.toolbar.selectSimilarityOrDifferenceFirst'))
      return
    }
    const spec = diagramStore.getDoubleBubbleSpecFromData()
    if (!spec) return
    const similarities = (spec.similarities as string[]) || []
    const leftDifferences = (spec.leftDifferences as string[]) || []
    const rightDifferences = (spec.rightDifferences as string[]) || []
    const simIndex = similarities.length + 1
    const newSimText = t('canvas.toolbar.similarityWithIndex', { n: simIndex })
    const pairIndex = Math.max(leftDifferences.length, rightDifferences.length) + 1
    const newLeftText = t('canvas.toolbar.differenceAWithIndex', { n: pairIndex })
    const newRightText = t('canvas.toolbar.differenceBWithIndex', { n: pairIndex })
    const text = group === 'similarity' ? newSimText : newLeftText
    const pairText = group === 'similarity' ? undefined : newRightText
    if (diagramStore.addDoubleBubbleMapNode(group, text, pairText)) {
      diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
      notify.success(
        group === 'similarity'
          ? t('canvas.toolbar.nodeAddedGeneric')
          : t('canvas.toolbar.differencePairAdded')
      )
    }
    return
  }

  // For other diagram types, show under development message
  notify.info(t('canvas.toolbar.addNodeInDevelopment'))
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
  if (diagramType === 'flow_map') {
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    const stepCount = diagramStore.data.nodes.filter((n) => n.type === 'flow').length
    const stepNum = stepCount + 1
    const defaultSubsteps: [string, string] = [
      t('canvas.toolbar.substepDefault1', { n: stepNum }),
      t('canvas.toolbar.substepDefault2', { n: stepNum }),
    ]
    if (diagramStore.addFlowMapStep(t('canvas.toolbar.newStep'), defaultSubsteps)) {
      diagramStore.pushHistory(t('canvas.toolbar.addStepHistory'))
      notify.success(t('canvas.toolbar.stepAdded'))
    }
    return
  }
  if (diagramType === 'brace_map') {
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    const targetIds = new Set(diagramStore.data.connections?.map((c) => c.target) ?? [])
    const rootId =
      diagramStore.data.nodes.find((n) => n.type === 'topic')?.id ??
      diagramStore.data.nodes.find((n) => !targetIds.has(n.id))?.id
    if (!rootId) return
    const text = t('canvas.toolbar.newPart')
    const subpartTexts: [string, string] = [
      t('canvas.toolbar.subpartLabel1'),
      t('canvas.toolbar.subpartLabel2'),
    ]
    if (diagramStore.addBraceMapPart(rootId, text, subpartTexts)) {
      notify.success(t('canvas.toolbar.partAdded'))
    }
    return
  }
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return
  if (!diagramStore.data?.nodes) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }

  const selectedId = diagramStore.selectedNodes[0]
  const side: 'left' | 'right' = selectedId?.startsWith('branch-l-') ? 'left' : 'right'
  const text = t('canvas.toolbar.newBranch')
  const childText = t('canvas.toolbar.newChild')

  if (diagramStore.addMindMapBranch(side, text, childText)) {
    notify.success(t('canvas.toolbar.branchAdded'))
  }
}

function handleAddChild() {
  const diagramType = diagramStore.type
  if (diagramType === 'flow_map') {
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    const selectedId = diagramStore.selectedNodes[0]
    const selectedNode = selectedId
      ? diagramStore.data?.nodes?.find((n) => n.id === selectedId)
      : undefined
    if (selectedNode?.type !== 'flow' || !selectedNode?.text) {
      notify.warning(t('canvas.toolbar.selectStepForSubstep'))
      return
    }
    if (
      diagramStore.addFlowMapSubstep(selectedNode.text, t('canvas.toolbar.newSubstep'))
    ) {
      diagramStore.pushHistory(t('canvas.toolbar.addSubstepHistory'))
      notify.success(t('canvas.toolbar.substepAdded'))
    }
    return
  }
  if (diagramType === 'brace_map') {
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId) {
      notify.warning(t('canvas.toolbar.selectPartForSubpart'))
      return
    }
    const targetIds = new Set(diagramStore.data.connections?.map((c) => c.target) ?? [])
    const rootId =
      diagramStore.data.nodes.find((n) => n.type === 'topic')?.id ??
      diagramStore.data.nodes.find((n) => !targetIds.has(n.id))?.id
    if (selectedId === rootId || selectedId === 'dimension-label') {
      notify.warning(t('canvas.toolbar.selectPartThenEnter'))
      return
    }
    const text = t('canvas.toolbar.newSubpart')
    if (diagramStore.addBraceMapPart(selectedId, text)) {
      notify.success(t('canvas.toolbar.subpartAdded'))
    }
    return
  }
  if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return
  if (!diagramStore.data?.nodes) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }

  const selectedId = diagramStore.selectedNodes[0]
  if (!selectedId || selectedId === 'topic') {
    notify.warning(t('canvas.toolbar.selectBranchOrChild'))
    return
  }

  const text = t('canvas.toolbar.newChild')
  if (diagramStore.addMindMapChild(selectedId, text)) {
    notify.success(t('canvas.toolbar.childAdded'))
  } else {
    notify.warning(t('canvas.toolbar.cannotAddChild'))
  }
}

function handleAddCause() {
  const diagramType = diagramStore.type

  if (!diagramStore.data?.nodes) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }

  if (diagramType !== 'multi_flow_map') {
    return
  }

  // Add new cause node (layout will be recalculated automatically)
  diagramStore.addNode({
    id: 'cause-temp', // Temporary ID, will be re-indexed
    text: t('canvas.toolbar.newCause'),
    type: 'flow',
    position: { x: 0, y: 0 }, // Will be recalculated
    category: 'causes', // Pass category to addNode
  } as DiagramNode & { category?: string })

  diagramStore.pushHistory(t('canvas.toolbar.addCauseHistory'))
  notify.success(t('canvas.toolbar.causeAdded'))
}

function handleAddEffect() {
  const diagramType = diagramStore.type

  if (!diagramStore.data?.nodes) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }

  if (diagramType !== 'multi_flow_map') {
    return
  }

  // Add new effect node (layout will be recalculated automatically)
  diagramStore.addNode({
    id: 'effect-temp', // Temporary ID, will be re-indexed
    text: t('canvas.toolbar.newEffect'),
    type: 'flow',
    position: { x: 0, y: 0 }, // Will be recalculated
    category: 'effects', // Pass category to addNode
  } as DiagramNode & { category?: string })

  diagramStore.pushHistory(t('canvas.toolbar.addEffectHistory'))
  notify.success(t('canvas.toolbar.effectAdded'))
}

function repositionBridgeMapPairs() {
  const startTime = getTimestamp()
  console.debug(`[CanvasToolbar] [${startTime}] repositionBridgeMapPairs() called`)

  if (!diagramStore.data) return

  const pairs = new Map<number, { left: DiagramNode | null; right: DiagramNode | null }>()

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
      pairs.set(pairIndex, { left: null, right: null })
    }

    const pair = pairs.get(pairIndex)
    if (!pair) {
      continue
    }
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
    const left = pair.left
    const right = pair.right
    if (!left || !right) {
      continue
    }

    const leftNodeY = centerY - verticalGap - nodeHeight
    const rightNodeY = centerY + verticalGap

    console.debug(
      `[CanvasToolbar] [${getTimestamp()}] Updating pair ${left.data?.pairIndex}:`,
      {
        leftNodeId: left.id,
        rightNodeId: right.id,
        newX: currentX,
        leftNodeY,
        rightNodeY,
      }
    )

    diagramStore.updateNodePosition(left.id, { x: currentX, y: leftNodeY }, false)
    diagramStore.updateNodePosition(right.id, { x: currentX, y: rightNodeY }, false)

    currentX += nodeWidth + gapBetweenPairs
  }

  console.debug(`[CanvasToolbar] [${getTimestamp()}] repositionBridgeMapPairs() complete`)
}

async function handleDeleteNode() {
  const diagramType = diagramStore.type

  if (!diagramStore.data?.nodes) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
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
    notify.warning(t('canvas.toolbar.selectNodesToDelete'))
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
      diagramStore.pushHistory(t('canvas.toolbar.deleteAttributeHistory'))
      notify.success(t('canvas.toolbar.deletedAttributes', { count: deletedCount }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
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
      diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
      notify.success(t('canvas.toolbar.deletedNodes', { count: deletedCount }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
    }
    return
  }

  // For brace maps, delete selected part/subpart nodes (and descendants)
  if (diagramType === 'brace_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const deletedCount = diagramStore.removeBraceMapNodes(selectedNodes)

    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
      notify.success(t('canvas.toolbar.deletedNodes', { count: deletedCount }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
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
      diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
      notify.success(t('canvas.toolbar.deletedNodes', { count: deletedCount }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteEvent'))
    }
    return
  }

  // For mindmap: rebuild spec and remove selected branches/children
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const deletedCount = diagramStore.removeMindMapNodes(selectedNodes)

    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
      notify.success(t('canvas.toolbar.deletedNodes', { count: deletedCount }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
    }
    return
  }

  // For double bubble map: delete selected similarity/difference nodes (protect topics)
  if (diagramType === 'double_bubble_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const toDelete = selectedNodes.filter(
      (id) =>
        /^similarity-\d+$/.test(id) || /^left-diff-\d+$/.test(id) || /^right-diff-\d+$/.test(id)
    )
    if (toDelete.length === 0) {
      notify.warning(t('canvas.toolbar.selectSimilarityOrDifferenceDelete'))
      return
    }

    const deletedCount = diagramStore.removeDoubleBubbleMapNodes(toDelete)
    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
      notify.success(t('canvas.toolbar.deletedNodes', { count: deletedCount }))
    }
    return
  }

  // For tree maps, delete selected category/leaf nodes (category deletion includes children)
  if (diagramType === 'tree_map') {
    const selectedNodes = [...diagramStore.selectedNodes]
    const toDelete = selectedNodes.filter(
      (id) => /^tree-cat-\d+$/.test(id) || /^tree-leaf-\d+-\d+$/.test(id)
    )
    if (toDelete.length === 0) {
      notify.warning(t('canvas.toolbar.selectCategoryOrLeafDelete'))
      return
    }

    const deletedCount = diagramStore.removeTreeMapNodes(toDelete)
    if (deletedCount > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
      notify.success(t('canvas.toolbar.deletedNodes', { count: deletedCount }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteTopicGeneric'))
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
      diagramStore.pushHistory(t('canvas.toolbar.deleteAnalogyPairHistory'))
      notify.success(t('canvas.toolbar.deletedAnalogyPairs', { count: pairCount }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteDimension'))
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
    diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
    notify.success(t('canvas.toolbar.deletedNodes', { count: deletedCount }))
  } else {
    notify.warning(t('canvas.toolbar.cannotDeleteSelected'))
  }
}

function handleFormatBrush() {
  notify.info(t('canvas.toolbar.formatBrushDev'))
}

/**
 * Handle AI Generate button click
 * Uses the useAutoComplete composable which mirrors the old JS "Auto" button behavior
 */
async function handleAIGenerate() {
  if (aiBlockedByCollab.value) {
    notify.warning(t('canvas.toolbar.collabAiBlocked'))
    return
  }
  // Validate before generating
  const validation = validateForAutoComplete()
  if (!validation.valid) {
    notify.warning(validation.error || t('canvas.toolbar.cannotGenerate'))
    return
  }

  // Use the composable's autoComplete method
  const result = await autoComplete({
    promptSuffix: diagramStore.isLearningSheet ? ' 半成品' : undefined,
  })
  if (!result.success && result.error) {
    // Error is already shown by the composable, but we can show it again if needed
    console.error('Auto-complete failed:', result.error)
  }
}

function handleConceptGeneration() {
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }
  const options: Record<string, unknown> = {}
  if (isConceptMap.value && diagramStore.selectedNodes.length === 1) {
    const nodeId = diagramStore.selectedNodes[0]
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    const topicNode = diagramStore.data?.nodes?.find(
      (n) => n.type === 'topic' || n.type === 'center' || n.id === 'root'
    )
    if (node && node.id !== topicNode?.id && node.text?.trim()) {
      options.conceptMapNodeId = node.id
      options.conceptMapNodeText = (node.text ?? '').trim()
    }
  }
  eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'toolbar', options })
}

function handleMoreAppItem(app: MoreAppItem) {
  if (app.handlerKey === 'concept_map_modes') {
    notify.info(t('canvas.toolbar.conceptMapModesDev'))
    return
  }
  void handleMoreApp(app)
}

async function handleMoreApp(app: MoreAppItem) {
  if (app.appKey === 'waterfall') {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'toolbar' })
    return
  }
  if (app.appKey === 'learning_sheet') {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    if (diagramStore.isLearningSheet) {
      diagramStore.restoreFromLearningSheetMode()
      notify.success(t('canvas.toolbar.switchedToRegular'))
    } else if (diagramStore.hasPreservedLearningSheet()) {
      diagramStore.applyLearningSheetView()
      notify.success(t('canvas.toolbar.learningSheetRestored'))
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
        notify.success(t('canvas.toolbar.switchedLearningSheetMode'))
      }
    }
    return
  }
  if (app.appKey === 'snapshot') {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    if (!savedDiagramsStore.activeDiagramId) {
      notify.warning(t('canvas.toolbar.snapshotSaveFirst'))
      return
    }
    eventBus.emit('snapshot:requested', {})
    return
  }
  notify.info(t('canvas.toolbar.featureInDevelopment', { name: app.name }))
}

// Flow map orientation toggle (only visible for flow_map)
const isFlowMap = computed(() => diagramStore.type === 'flow_map')

function handleToggleOrientation() {
  diagramStore.toggleFlowMapOrientation()
  notify.success(t('canvas.toolbar.layoutDirectionToggled'))
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
        <!-- Exit fullscreen (canvas chrome hidden) -->
        <template v-if="props.isPresentationMode">
          <ElTooltip
            :content="t('canvas.toolbar.exitFullscreen')"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              class="text-red-600 hover:text-red-700 dark:text-red-400"
              @click="emit('exitPresentation')"
            >
              <X class="w-4 h-4" />
              <span>{{ t('canvas.toolbar.exit') }}</span>
            </ElButton>
          </ElTooltip>
          <div class="divider" />
        </template>

        <!-- Undo/Redo -->
        <ElTooltip
          :content="t('canvas.toolbar.undo')"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            :disabled="!diagramStore.canUndo"
            @click="handleUndo"
          >
            <RotateCw class="w-4 h-4" />
          </ElButton>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.redo')"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            :disabled="!diagramStore.canRedo"
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
            :content="t('canvas.toolbar.addCause')"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              @click="handleAddCause"
            >
              <Plus class="w-4 h-4" />
              <span>{{ t('canvas.toolbar.addCause') }}</span>
            </ElButton>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.toolbar.addEffect')"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              @click="handleAddEffect"
            >
              <Plus class="w-4 h-4" />
              <span>{{ t('canvas.toolbar.addEffect') }}</span>
            </ElButton>
          </ElTooltip>
        </template>

        <!-- For bridge maps, show "Add Analogy Pair" button -->
        <template v-else-if="isBridgeMap">
          <ElTooltip
            :content="t('canvas.toolbar.addAnalogyPair')"
            placement="bottom"
          >
            <ElButton
              text
              size="small"
              @click="handleAddNode"
            >
              <Plus class="w-4 h-4" />
              <span>{{ t('canvas.toolbar.addPairShort') }}</span>
            </ElButton>
          </ElTooltip>
        </template>

        <!-- For other diagram types, show simple button -->
        <ElTooltip
          v-else
          :content="t('canvas.toolbar.addNode')"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleAddNode"
          >
            <Plus class="w-4 h-4" />
            <span>{{ t('canvas.toolbar.addShort') }}</span>
          </ElButton>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.deleteNode')"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleDeleteNode"
          >
            <Trash2 class="w-4 h-4" />
            <span>{{ t('canvas.toolbar.deleteShort') }}</span>
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <!-- Format brush -->
        <ElTooltip
          :content="t('canvas.toolbar.formatPainter')"
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
          :content="t('canvas.toolbar.toggleDirection')"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleToggleOrientation"
          >
            <ArrowDownUp class="w-4 h-4 text-blue-500" />
            <span>{{ t('canvas.toolbar.directionLabel') }}</span>
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
            <span>{{ t('canvas.toolbar.styleMenu') }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-48">
                <div class="text-xs font-medium text-gray-500 mb-2">
                  {{ t('canvas.toolbar.presetsLabel') }}
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <ElDropdownItem
                    v-for="preset in stylePresets"
                    :key="preset.nameKey"
                    class="p-2! rounded border text-xs text-center"
                    :class="[preset.bgClass, preset.borderClass]"
                    @click="handleApplyStylePreset(preset)"
                  >
                    {{ t(preset.nameKey) }}
                  </ElDropdownItem>
                </div>
                <div class="border-t border-gray-200 my-2" />
                <ElDropdownItem
                  :class="{ 'bg-blue-50': uiStore.wireframeMode }"
                  @click="uiStore.toggleWireframe()"
                >
                  <PenLine class="w-3 h-3 mr-2 text-gray-500" />
                  {{ t('canvas.toolbar.wireframe') }}
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
            <span>{{ t('canvas.toolbar.textStyleMenu') }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-2.5 w-48 text-style-dropdown">
                <!-- Format buttons: B I U S -->
                <div class="mb-2">
                  <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                    {{ t('canvas.toolbar.formatLabel') }}
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
                    {{ t('canvas.toolbar.fontLabel') }}
                  </div>
                  <div class="grid grid-cols-2 gap-1.5">
                    <select
                      :value="fontFamily"
                      class="w-full border border-gray-200 rounded py-1.5 px-2 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500/40 focus:border-blue-400"
                      @change="handleFontFamilyChange"
                    >
                      <optgroup :label="t('canvas.toolbar.fontGroupChinese')">
                        <option value="Microsoft YaHei">微软雅黑</option>
                        <option value="SimSun">宋体</option>
                        <option value="SimHei">黑体</option>
                        <option value="KaiTi">楷体</option>
                        <option value="FangSong">仿宋</option>
                      </optgroup>
                      <optgroup :label="t('canvas.toolbar.fontGroupEnglish')">
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
                    {{ t('canvas.toolbar.colorLabel') }}
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
            <span>{{ t('canvas.toolbar.bgMenu') }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-3">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ t('canvas.toolbar.bgColorLabel') }}:</label
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
                    >{{ t('canvas.toolbar.opacityLabel') }}:</label
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
            <span>{{ t('canvas.toolbar.borderMenu') }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1"
                    >{{ t('canvas.toolbar.colorLabel') }}:</label
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
                    >{{ t('canvas.toolbar.borderWidthLabel') }}:</label
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
                    >{{ t('canvas.toolbar.borderStyleLabel') }}:</label
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
                        applyBorderToSelected({ borderStyle: style })
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

        <template v-if="isConceptMap">
          <div class="divider" />
          <!-- Concept Generation: opens node palette (drag concepts onto canvas) -->
          <ElButton
            type="primary"
            size="small"
            class="ai-btn"
            @click="handleConceptGeneration"
          >
            <Sparkles class="w-4 h-4" />
            <span>{{ t('canvas.toolbar.conceptGeneration') }}</span>
          </ElButton>
        </template>
        <template v-else>
          <div class="divider" />
          <!-- AI Generate button (hidden for concept_map) -->
          <ElButton
            type="primary"
            size="small"
            class="ai-btn"
            :class="{ 'ai-btn--generating': isAIGenerating }"
            :disabled="isAIGenerating || aiBlockedByCollab"
            @click="handleAIGenerate"
          >
            <Wand2
              class="w-4 h-4 shrink-0"
              :class="isAIGenerating ? 'opacity-30' : ''"
              aria-hidden="true"
            />
            <span>{{
              isAIGenerating
                ? t('canvas.toolbar.aiGenerating')
                : t('canvas.toolbar.aiGenerate')
            }}</span>
          </ElButton>
        </template>

        <div class="divider" />

        <!-- More apps dropdown -->
        <ElDropdown
          trigger="hover"
          placement="bottom-end"
        >
          <ElButton
            size="small"
            class="more-apps-btn"
          >
            <span>{{ t('canvas.toolbar.moreApps') }}</span>
            <ChevronDown class="w-3.5 h-3.5" />
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu class="more-apps-menu">
              <ElDropdownItem
                v-for="app in moreApps"
                :key="app.appKey ?? app.handlerKey ?? app.name"
                @click="handleMoreAppItem(app)"
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
                    <div class="font-medium mb-0.5 flex items-center gap-2">
                      {{ app.name }}
                      <span
                        v-if="app.tag"
                        class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full"
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
  box-sizing: border-box !important;
}

:deep(.ai-btn:hover) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

:deep(.ai-btn span) {
  color: white !important;
}

@property --ai-toolbar-ring-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

/* AI Generate: traveling border while generating (no Element Plus spinner) */
:deep(.ai-btn--generating) {
  position: relative !important;
  background: transparent !important;
  box-shadow: none !important;
  /* Outer 2px + inner padding matches idle 6px 16px so size stays stable */
  padding: 2px !important;
}

:deep(.ai-btn--generating:hover) {
  transform: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

:deep(.ai-btn--generating::before) {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  padding: 2px;
  --ai-toolbar-ring-angle: 0deg;
  pointer-events: none;
  z-index: 0;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: ai-toolbar-ring-spin 2.5s linear infinite;
  background: conic-gradient(
    from var(--ai-toolbar-ring-angle) at 50% 50%,
    rgba(59, 130, 246, 0.35) 0deg,
    rgba(255, 255, 255, 0.75) 52deg,
    #93c5fd 130deg,
    #3b82f6 180deg,
    #60a5fa 228deg,
    rgba(255, 255, 255, 0.75) 308deg,
    rgba(59, 130, 246, 0.35) 360deg
  );
}

:deep(.ai-btn--generating .el-button__inner),
:deep(.ai-btn--generating > span) {
  position: relative;
  z-index: 1;
  box-sizing: border-box !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border-radius: 4px !important;
  /* 4px + 2px ring = 6px vertical; 14px + 2px = 16px horizontal (matches idle 6px 16px) */
  padding: 4px 14px !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 6px !important;
}

:deep(.dark .ai-btn--generating::before) {
  background: conic-gradient(
    from var(--ai-toolbar-ring-angle) at 50% 50%,
    rgba(59, 130, 246, 0.4) 0deg,
    rgba(31, 41, 55, 0.92) 52deg,
    #60a5fa 130deg,
    #2563eb 180deg,
    #38bdf8 228deg,
    rgba(31, 41, 55, 0.92) 308deg,
    rgba(59, 130, 246, 0.4) 360deg
  );
}

@keyframes ai-toolbar-ring-spin {
  to {
    --ai-toolbar-ring-angle: 360deg;
  }
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
