import { ref, shallowRef, watch, type Ref } from 'vue'

import {
  collectFormatBrushStyle,
  FORMAT_BRUSH_DOUBLE_CLICK_MS,
  formatBrushTargetsFromSelection,
  resolveFormatPainterClick,
} from '@/composables/canvasToolbar/formatBrushStyle'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { STYLE_PRESET_PALETTES, type StylePresetColors } from '@/config/colorPalette'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { syncMindMapConnectionStrokeColors } from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram, mindMapStyleFromTheme } from '@/config/mindMapThemes'
import type { NodeStyle } from '@/types'
import { type BorderStyleType, getBorderStyleProps } from '@/utils/borderStyleUtils'
import { colorToHex, hexToRgba, parseAlphaFromColor } from '@/utils/colorFormat'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'

export const formatBrushActive = ref(false)
export const formatBrushLocked = ref(false)
const formatBrushStyle = ref<NodeStyle | null>(null)
const formatBrushSourceIds = ref<string[]>([])
let lastFormatBrushClickAt = 0
let formatBrushActivateToastTimer: ReturnType<typeof setTimeout> | null = null

let formatBrushSelectionWatchBound = false
let formatBrushEscapeBound = false
let formatBrushPaneBound = false
let applyFormatBrushToIds: ((ids: string[]) => void) | null = null
let cancelFormatBrush: ((options?: { silent?: boolean }) => void) | null = null
let formatBrushDiagramStore = shallowRef<ReturnType<typeof useDiagramSession> | null>(null)

export function resetFormatBrushState(): void {
  formatBrushActive.value = false
  formatBrushLocked.value = false
  formatBrushStyle.value = null
  formatBrushSourceIds.value = []
  lastFormatBrushClickAt = 0
  if (formatBrushActivateToastTimer !== null) {
    clearTimeout(formatBrushActivateToastTimer)
    formatBrushActivateToastTimer = null
  }
  if (typeof document !== 'undefined') {
    document.documentElement.classList.remove('mg-format-brush-active')
  }
}

function syncFormatBrushCursor(active: boolean): void {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('mg-format-brush-active', active)
}

function onFormatBrushEscape(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !formatBrushActive.value) return
  cancelFormatBrush?.({ silent: false })
}

function onFormatBrushPaneClick(): void {
  if (!formatBrushActive.value) return
  cancelFormatBrush?.({ silent: false })
  if (formatBrushActive.value) resetFormatBrushState()
}

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

  const fontFamily = ref('Inter')
  const fontSize = ref(14)
  const textColor = ref('#000000')
  const fontWeight = ref<'normal' | 'bold'>('normal')
  const fontStyle = ref<'normal' | 'italic'>('normal')
  const textDecoration = ref<'none' | 'underline' | 'line-through' | 'underline line-through'>(
    'none'
  )
  const textAlign = ref<'left' | 'center' | 'right'>('center')
  const nodeShape = ref<import('@/utils/nodeShapeStyle').NodeShape>('rounded')

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
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    diagramStore.applyStylePreset(preset)
    notify.success(t('canvas.toolbar.styleApplied'))
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
    if (!options?.silent && notifyOnApply) notify.success(t('canvas.toolbar.applied'))
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
      if (!options?.silent) notify.warning(t('canvas.toolbar.selectNodesFirst'))
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
    if (!options?.silent && notifyOnApply) notify.success(t('canvas.toolbar.applied'))
  }

  function applyBackgroundToSelected(color?: string, options?: { silent?: boolean }) {
    const ids = getTargetNodeIds()
    if (!ids.length) {
      if (!options?.silent) notify.warning(t('canvas.toolbar.selectNodesFirst'))
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
    if (!options?.silent && notifyOnApply) notify.success(t('canvas.toolbar.applied'))
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
      if (!options?.silent) notify.warning(t('canvas.toolbar.selectNodesFirst'))
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
    if (!options?.silent && notifyOnApply) notify.success(t('canvas.toolbar.applied'))
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
        | 'none'
        | 'underline'
        | 'line-through'
        | 'underline line-through'
    }
    return [...parts, part].join(' ') as
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
      fontSize.value = v
      applyTextStyleToSelected({ fontSize: v })
    }
  }

  function handleFontSizePick(size: number) {
    fontSize.value = size
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
          if (s.fontSize) fontSize.value = s.fontSize
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
          if (s.nodeShape) nodeShape.value = s.nodeShape
        }
      }
    },
    { deep: true }
  )

  function snapshotFormatBrushStyle(nodeId: string): NodeStyle | null {
    const sourceNode = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (!sourceNode) return null
    const persisted = diagramStore.getNodeStyle(nodeId)
    const isMindMap = diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
    const themeFallback = isMindMap
      ? mindMapStyleFromTheme(
          sourceNode,
          getMindMapThemeForDiagram(diagramStore.data),
          diagramStore.data?._mindmap_diagram_style,
          diagramStore.data?.connections
        )
      : undefined
    const copied = collectFormatBrushStyle(sourceNode.style, persisted, themeFallback)
    if (!copied.nodeShape && isMindMap) {
      copied.nodeShape = resolveMindMapNodeShape(
        {
          id: sourceNode.id,
          type: sourceNode.type,
          style: { ...themeFallback, ...persisted, ...sourceNode.style },
        },
        diagramStore.data?._mindmap_diagram_style
      )
    }
    return copied
  }

  function applyCopiedFormatBrush(ids: string[]): void {
    const style = formatBrushStyle.value
    if (!style || ids.length === 0) return
    diagramStore.pushHistory(t('canvas.toolbar.formatPainter'))
    ids.forEach((nodeId) => {
      const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
      if (node) {
        diagramStore.updateNode(nodeId, { style: { ...(node.style || {}), ...style } })
      }
    })
    const keepActive = formatBrushLocked.value
    const count = ids.length
    if (keepActive) {
      formatBrushSourceIds.value = [...formatBrushSourceIds.value, ...ids]
      return
    }
    resetFormatBrushState()
    if (notifyOnApply) notify.success(t('canvas.toolbar.formatBrushApplied', { count }))
  }

  function cancelCopiedFormatBrush(options?: { silent?: boolean }): void {
    if (!formatBrushActive.value) return
    resetFormatBrushState()
    if (!options?.silent) notify.info(t('canvas.toolbar.formatBrushCancelled'))
  }

  applyFormatBrushToIds = applyCopiedFormatBrush
  cancelFormatBrush = cancelCopiedFormatBrush
  formatBrushDiagramStore.value = diagramStore

  if (!formatBrushSelectionWatchBound) {
    formatBrushSelectionWatchBound = true
    watch(
      () => formatBrushDiagramStore.value?.selectedNodes.join('\0') ?? '',
      (joined) => {
        if (!formatBrushActive.value || !formatBrushStyle.value) return
        const ids = joined ? joined.split('\0') : []
        const targets = formatBrushTargetsFromSelection(ids, formatBrushSourceIds.value)
        if (!targets.length) return
        applyFormatBrushToIds?.(targets)
      }
    )
  }

  if (!formatBrushEscapeBound && typeof document !== 'undefined') {
    formatBrushEscapeBound = true
    document.addEventListener('keydown', onFormatBrushEscape)
  }

  if (!formatBrushPaneBound) {
    formatBrushPaneBound = true
    eventBus.on('canvas:pane_clicked', onFormatBrushPaneClick)
  }

  watch(formatBrushActive, (active) => {
    syncFormatBrushCursor(active)
  })

  function pickupFormatBrush(lock: boolean): boolean {
    const sourceIds = diagramStore.selectedNodes
    const sourceId = sourceIds[0]
    if (!sourceId) {
      notify.warning(t('canvas.toolbar.formatBrushSelectSource'))
      return false
    }
    const copiedStyle = snapshotFormatBrushStyle(sourceId)
    if (!copiedStyle || Object.keys(copiedStyle).length === 0) return false
    formatBrushStyle.value = copiedStyle
    formatBrushSourceIds.value = [...sourceIds]
    formatBrushActive.value = true
    formatBrushLocked.value = lock
    syncFormatBrushCursor(true)
    return true
  }

  function announceFormatBrushMode(lock: boolean): void {
    if (!notifyOnApply) return
    if (formatBrushActivateToastTimer !== null) {
      clearTimeout(formatBrushActivateToastTimer)
      formatBrushActivateToastTimer = null
    }
    if (lock) {
      notify.success(t('canvas.toolbar.formatBrushActivated'))
      return
    }
    formatBrushActivateToastTimer = setTimeout(() => {
      formatBrushActivateToastTimer = null
      if (formatBrushActive.value && !formatBrushLocked.value) {
        notify.success(t('canvas.toolbar.formatBrushActivated'))
      }
    }, FORMAT_BRUSH_DOUBLE_CLICK_MS)
  }

  function handleFormatBrush(options?: { lock?: boolean }): void {
    const now = Date.now()
    const action = resolveFormatPainterClick({
      active: formatBrushActive.value,
      locked: formatBrushLocked.value,
      lockRequested: Boolean(options?.lock),
      elapsedMs: now - lastFormatBrushClickAt,
    })
    lastFormatBrushClickAt = now

    if (action === 'noop') return
    if (action === 'cancel') {
      cancelCopiedFormatBrush()
      return
    }

    if (action === 'activate') {
      if (!pickupFormatBrush(false)) return
      announceFormatBrushMode(false)
      return
    }

    if (!formatBrushActive.value) {
      if (!pickupFormatBrush(true)) return
    } else {
      formatBrushLocked.value = true
    }
    announceFormatBrushMode(true)
  }

  return {
    formatBrushActive,
    formatBrushLocked,
    stylePresets,
    fontFamily,
    fontSize,
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
