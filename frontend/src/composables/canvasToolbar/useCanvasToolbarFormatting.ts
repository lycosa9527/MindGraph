import { type Ref, computed, nextTick, ref, watch } from 'vue'

import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import {
  formatBrushActive,
  formatBrushLocked,
  handleFormatBrush,
  useCanvasFormatBrush,
} from '@/composables/canvasToolbar/useCanvasFormatBrush'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { STYLE_PRESET_PALETTES, type StylePresetColors } from '@/config/colorPalette'
import { FLOATING_TOOLBAR_FONT_SIZES } from '@/config/floatingToolbarColors'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { syncMindMapConnectionStrokeColors } from '@/config/mindMapGeometry'
import type { DiagramNode, NodeStyle } from '@/types'
import { type BorderStyleType, getBorderStyleProps } from '@/utils/borderStyleUtils'
import { colorToHex, hexToRgba, parseAlphaFromColor } from '@/utils/colorFormat'
import { displayedNodeFontSize, readPaintedNodeFontSizePx } from '@/utils/displayedNodeFontSize'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import { type NodeShape, defaultDisplayedNodeShape } from '@/utils/nodeShapeStyle'
import { thinkingMapColorsAreDefault, thinkingMapRoleChrome } from '@/utils/thinkingMapChrome'
import { thinkingMapDisplayedNodeColors } from '@/utils/thinkingMapNodePaint'

export {
  formatBrushActive,
  formatBrushLocked,
  resetFormatBrushState,
} from '@/composables/canvasToolbar/useCanvasFormatBrush'

export function useCanvasToolbarFormatting(options?: {
  silentUpdates?: boolean
  /** When set, formatting applies to this node even if canvas selection was cleared (floating toolbar). */
  pinnedNodeId?: Ref<string | null | undefined>
}) {
  const diagramStore = useDiagramSession()
  const { t } = useLanguage()
  const notify = useNotifications()
  const notifyOnApply = !options?.silentUpdates
  const pinnedNodeId = options?.pinnedNodeId

  function getTargetNodeIds(): string[] {
    const selected = diagramStore.selectedNodes
    if (selected.length > 0) return selected
    const pinned = pinnedNodeId?.value
    return pinned ? [pinned] : []
  }

  function currentFormattingNode(): DiagramNode | undefined {
    const nodes = diagramStore.data?.nodes
    if (!nodes?.length) return undefined
    const pinned = pinnedNodeId?.value
    if (pinned) return nodes.find((node) => node.id === pinned)
    const selected = diagramStore.selectedNodes
    if (selected.length !== 1) return undefined
    return nodes.find((node) => node.id === selected[0])
  }

  function mergedNodeStyle(node: DiagramNode): NodeStyle {
    const persisted = diagramStore.getNodeStyle(node.id)
    const flow = diagramStore.vueFlowNodes.find((item) => item.id === node.id)
    const flowStyle = flow?.data?.style
    const painted = flowStyle && typeof flowStyle === 'object' ? flowStyle : undefined
    return { ...(persisted || {}), ...(node.style || {}), ...(painted || {}) }
  }

  function modelFontSize(node: DiagramNode): number {
    return displayedNodeFontSize(
      diagramStore.type,
      node,
      mergedNodeStyle(node),
      diagramStore.data?.connections
    )
  }

  const lastFontSize = ref(14)
  const paintedFontSize = ref<{ nodeId: string; size: number } | null>(null)
  /** Size just written by the toolbar. A stale DOM read must not put the old size back. */
  const appliedFontSize = ref<{ nodeId: string; size: number } | null>(null)
  let paintMeasureGeneration = 0

  function roundToolbarFontSize(value: number): number {
    const rounded = Math.round(value)
    return rounded > 0 ? rounded : lastFontSize.value
  }

  function rememberAppliedFontSize(size: number): void {
    const node = currentFormattingNode()
    if (!node) return
    appliedFontSize.value = { nodeId: node.id, size }
    paintedFontSize.value = { nodeId: node.id, size }
  }

  function schedulePaintedFontSizeRead(nodeId: string, attempt = 0): void {
    const generation = ++paintMeasureGeneration
    void nextTick(() => {
      if (generation !== paintMeasureGeneration) return
      const size = readPaintedNodeFontSizePx(nodeId)
      if (generation !== paintMeasureGeneration) return
      const applied = appliedFontSize.value
      const pending = applied?.nodeId === nodeId ? applied.size : null
      if (pending != null && size !== pending && attempt < 2) {
        schedulePaintedFontSizeRead(nodeId, attempt + 1)
        return
      }
      if (pending != null && size !== pending) {
        paintedFontSize.value = { nodeId, size: pending }
        return
      }
      appliedFontSize.value = null
      paintedFontSize.value = size == null ? null : { nodeId, size }
    })
  }

  const fontSize = computed(() => {
    const node = currentFormattingNode()
    if (!node) return lastFontSize.value
    const painted = paintedFontSize.value
    if (painted?.nodeId === node.id) return roundToolbarFontSize(painted.size)
    return roundToolbarFontSize(modelFontSize(node))
  })

  const fontSizeChoices = computed(() => {
    const sizes = new Set<number>(FLOATING_TOOLBAR_FONT_SIZES)
    const current = fontSize.value
    if (Number.isFinite(current) && current > 0) sizes.add(Math.round(current))
    return [...sizes].sort((left, right) => left - right)
  })

  const fontFamily = ref('Inter')
  const textColor = ref('#000000')
  const fontWeight = ref<'normal' | 'bold'>('normal')
  const fontStyle = ref<'normal' | 'italic'>('normal')
  const textDecoration = ref<'none' | 'underline' | 'line-through' | 'underline line-through'>(
    'none'
  )
  const textAlign = ref<'left' | 'center' | 'right'>('center')
  const nodeShape = ref<NodeShape | null>('rounded')

  function toolbarDisplayedNodeShape(node: DiagramNode, style: NodeStyle): NodeShape | null {
    const diagramType = diagramStore.type
    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      return resolveMindMapNodeShape(
        { id: node.id, type: node.type, style },
        diagramStore.data?._mindmap_diagram_style
      )
    }
    if (style.nodeShape) return style.nodeShape
    return defaultDisplayedNodeShape(diagramType, node.type)
  }

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

  const backgroundColors = ['#FFFFFF', '#F9FAFB', '#F3F4F6', '#E5E7EB', '#D1D5DB']
  const backgroundColor = ref('#FFFFFF')
  const backgroundOpacity = ref(100)

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

  const stylePresetUiMeta = [
    {
      nameKey: 'canvas.toolbar.stylePresetSimple',
      bgClass: 'bg-blue-50',
      borderClass: 'border-blue-600',
    },
    {
      nameKey: 'canvas.toolbar.stylePresetCreative',
      bgClass: 'bg-purple-50',
      borderClass: 'border-purple-600',
    },
    {
      nameKey: 'canvas.toolbar.stylePresetBusiness',
      bgClass: 'bg-green-50',
      borderClass: 'border-green-600',
    },
    {
      nameKey: 'canvas.toolbar.stylePresetVibrant',
      bgClass: 'bg-yellow-50',
      borderClass: 'border-yellow-600',
    },
  ] as const

  if (stylePresetUiMeta.length !== STYLE_PRESET_PALETTES.length) {
    throw new Error('Style preset UI metadata must match STYLE_PRESET_PALETTES in colorPalette')
  }

  const stylePresets: Array<
    {
      nameKey: string
      bgClass: string
      borderClass: string
    } & StylePresetColors
  > = stylePresetUiMeta.map((meta, index) => ({
    ...meta,
    ...STYLE_PRESET_PALETTES[index],
  }))

  function getBorderPreviewStyle(style: BorderStyleType) {
    return getBorderStyleProps(borderColor.value, 2, style, {
      backgroundColor: '#f9fafb',
    })
  }

  function handleApplyStylePreset(preset: StylePresetColors) {
    if (!diagramStore.data?.nodes?.length) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }
    diagramStore.applyStylePreset(preset)
    notify.successKey('canvas.toolbar.styleApplied')
  }

  function applyNodeShapeToSelected(
    shape: import('@/utils/nodeShapeStyle').NodeShape,
    options?: { silent?: boolean }
  ) {
    const ids = getTargetNodeIds()
    if (!ids.length) return
    diagramStore.pushHistory(t('canvas.toolbar.updateTextStyle'))
    ids.forEach((nodeId) => {
      const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
      if (node) {
        diagramStore.updateNode(nodeId, {
          style: { ...(node.style || {}), nodeShape: shape },
        })
      }
    })
    if (!options?.silent && notifyOnApply) notify.successKey('canvas.toolbar.applied')
  }

  function applyTextStyleToSelected(
    updates: {
      fontFamily?: string
      fontSize?: number
      textColor?: string
      fontWeight?: 'normal' | 'bold'
      fontStyle?: 'normal' | 'italic'
      textDecoration?: 'none' | 'underline' | 'line-through' | 'underline line-through'
      textAlign?: 'left' | 'center' | 'right'
    },
    options?: { silent?: boolean }
  ) {
    const ids = getTargetNodeIds()
    if (!ids.length) {
      if (!options?.silent) notify.warningKey('canvas.toolbar.selectNodesFirst')
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
    if (!options?.silent && notifyOnApply) notify.successKey('canvas.toolbar.applied')
  }

  function applyBackgroundToSelected(color?: string, options?: { silent?: boolean }) {
    const ids = getTargetNodeIds()
    if (!ids.length) {
      if (!options?.silent) notify.warningKey('canvas.toolbar.selectNodesFirst')
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
    if (!options?.silent && notifyOnApply) notify.successKey('canvas.toolbar.applied')
  }

  function applyBorderToSelected(
    updates: {
      borderColor?: string
      borderWidth?: number
      borderStyle?: import('@/types').NodeStyle['borderStyle']
    },
    options?: { silent?: boolean }
  ) {
    const ids = getTargetNodeIds()
    if (!ids.length) {
      if (!options?.silent) notify.warningKey('canvas.toolbar.selectNodesFirst')
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
    const diagramType = diagramStore.type
    if (
      isSessionMindMapV2VisualDesignActive(diagramStore.mindMapCanvasMode) &&
      updates.borderColor &&
      (diagramType === 'mindmap' || diagramType === 'mind_map') &&
      ids.includes('topic') &&
      diagramStore.data?.connections
    ) {
      syncMindMapConnectionStrokeColors(diagramStore.data.connections, updates.borderColor)
    }
    if (
      updates.borderColor &&
      isThinkingMapDiagramType(diagramType) &&
      diagramStore.data?.connections
    ) {
      const picked = updates.borderColor
      const touched = new Set(ids)
      for (const connection of diagramStore.data.connections) {
        if (!touched.has(connection.source) && !touched.has(connection.target)) continue
        connection.style = { ...(connection.style || {}), strokeColor: picked }
      }
    }
    if (!options?.silent && notifyOnApply) notify.successKey('canvas.toolbar.applied')
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
    const parts =
      current === 'none' ? [] : current.split(' ').filter((p) => p !== 'none' && Boolean(p))
    const has = parts.includes(part)
    if (has) {
      const newParts = parts.filter((p) => p !== part)
      return (newParts.length ? newParts.join(' ') : 'none') as
        'none' | 'underline' | 'line-through' | 'underline line-through'
    }
    return [...parts, part].join(' ') as
      'none' | 'underline' | 'line-through' | 'underline line-through'
  }

  function handleToggleUnderline() {
    textDecoration.value = toggleTextDecorationPart('underline')
    applyTextStyleToSelected({ textDecoration: textDecoration.value })
  }

  function handleToggleStrikethrough() {
    textDecoration.value = toggleTextDecorationPart('line-through')
    applyTextStyleToSelected({ textDecoration: textDecoration.value })
  }

  function handleTextAlign(align: 'left' | 'center' | 'right') {
    textAlign.value = align
    applyTextStyleToSelected({ textAlign: align })
  }

  function handleFontFamilyChange(ev: Event) {
    const val = (ev.target as HTMLSelectElement).value
    fontFamily.value = val
    applyTextStyleToSelected({ fontFamily: val })
  }

  function handleFontSizeInput(ev: Event) {
    const v = parseInt((ev.target as HTMLInputElement).value, 10)
    if (!Number.isNaN(v)) {
      rememberAppliedFontSize(v)
      applyTextStyleToSelected({ fontSize: v })
    }
  }

  function handleFontSizePick(size: number) {
    rememberAppliedFontSize(size)
    applyTextStyleToSelected({ fontSize: size }, { silent: true })
  }

  function handleTextColorPick(color: string) {
    textColor.value = color
    applyTextStyleToSelected({ textColor: color }, { silent: true })
  }

  function handleFillColorPick(color: string) {
    applyBackgroundToSelected(color, { silent: true })
  }

  function handleBorderColorPick(color: string) {
    applyBorderToSelected({ borderColor: color }, { silent: true })
  }

  function handleNodeShapePick(shape: import('@/utils/nodeShapeStyle').NodeShape) {
    nodeShape.value = shape
    applyNodeShapeToSelected(shape, { silent: true })
  }

  watch(
    () => {
      const node = currentFormattingNode()
      if (!node) return ''
      const flow = diagramStore.vueFlowNodes.find((item) => item.id === node.id)
      const flowSize = flow?.data?.style?.fontSize
      return `${node.id}:${node.style?.fontSize ?? ''}:${flowSize ?? ''}:${diagramStore.type ?? ''}`
    },
    () => {
      const node = currentFormattingNode()
      if (!node) return
      const model = roundToolbarFontSize(modelFontSize(node))
      lastFontSize.value = model
      const applied = appliedFontSize.value
      if (applied && (applied.nodeId !== node.id || applied.size !== model)) {
        appliedFontSize.value = null
      }
      schedulePaintedFontSizeRead(node.id)
    },
    { immediate: true }
  )

  watch(
    () => {
      const pinned = pinnedNodeId?.value
      const nodes = diagramStore.selectedNodeData
      if (nodes.length === 1) return nodes[0]
      if (pinned) return diagramStore.data?.nodes?.find((n) => n.id === pinned)
      return undefined
    },
    (node) => {
      if (node) {
        const persisted = diagramStore.getNodeStyle(node.id)
        const s = { ...(persisted || {}), ...(node.style || {}) }
        if (Object.keys(s).length > 0) {
          if (s.fontFamily) fontFamily.value = s.fontFamily
          if (s.textColor) textColor.value = s.textColor
          if (s.fontWeight) fontWeight.value = s.fontWeight
          if (s.fontStyle) fontStyle.value = s.fontStyle
          textDecoration.value = s.textDecoration ?? 'none'
          textAlign.value = s.textAlign ?? 'center'
          if (s.borderColor) borderColor.value = s.borderColor
          if (s.borderWidth !== undefined) borderWidth.value = s.borderWidth
          if (s.borderStyle) borderStyle.value = s.borderStyle
          if (s.backgroundColor) {
            backgroundColor.value = colorToHex(s.backgroundColor)
            backgroundOpacity.value = parseAlphaFromColor(s.backgroundColor)
          }
        }
        nodeShape.value = toolbarDisplayedNodeShape(node, s)
        if (isThinkingMapDiagramType(diagramStore.type)) {
          const chrome = thinkingMapRoleChrome(
            diagramStore.type,
            node,
            diagramStore.data?.connections
          )
          const paint = thinkingMapDisplayedNodeColors(
            diagramStore.type,
            diagramStore.data?._mindmap_theme,
            node,
            s,
            diagramStore.data?.connections
          )
          const showRolePaint = Boolean(paint && chrome && thinkingMapColorsAreDefault(s, chrome))
          if (showRolePaint && paint) {
            backgroundColor.value = colorToHex(paint.backgroundColor)
            textColor.value = paint.textColor
            borderColor.value = paint.borderColor
          }
        }
      }
    },
    { deep: true }
  )

  useCanvasFormatBrush()

  return {
    formatBrushActive,
    formatBrushLocked,
    stylePresets,
    fontFamily,
    fontSize,
    fontSizeChoices,
    textColor,
    fontWeight,
    fontStyle,
    textDecoration,
    textAlign,
    textColorPalette,
    backgroundColors,
    backgroundColor,
    backgroundOpacity,
    borderColor,
    borderColorPalette,
    borderWidth,
    borderStyle,
    borderStyleOptions,
    nodeShape,
    getBorderPreviewStyle,
    handleApplyStylePreset,
    applyBackgroundToSelected,
    applyBorderToSelected,
    handleToggleBold,
    handleToggleItalic,
    handleToggleUnderline,
    handleToggleStrikethrough,
    handleTextAlign,
    handleFontFamilyChange,
    handleFontSizeInput,
    handleFontSizePick,
    handleTextColorPick,
    handleFillColorPick,
    handleBorderColorPick,
    handleNodeShapePick,
    handleFormatBrush,
    applyNodeShapeToSelected,
  }
}
