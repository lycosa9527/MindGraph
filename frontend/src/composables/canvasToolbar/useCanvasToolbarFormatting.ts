import { ref, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { STYLE_PRESET_PALETTES, type StylePresetColors } from '@/config/colorPalette'
import { useDiagramStore } from '@/stores'
import { type BorderStyleType, getBorderStyleProps } from '@/utils/borderStyleUtils'
import { colorToHex, hexToRgba, parseAlphaFromColor } from '@/utils/colorFormat'

export function useCanvasToolbarFormatting() {
  const diagramStore = useDiagramStore()
  const { t } = useLanguage()
  const notify = useNotifications()

  const formatBrushActive = ref(false)
  const formatBrushStyle = ref<import('@/types').NodeStyle | null>(null)

  const fontFamily = ref('Inter')
  const fontSize = ref(16)
  const textColor = ref('#000000')
  const fontWeight = ref<'normal' | 'bold'>('normal')
  const fontStyle = ref<'normal' | 'italic'>('normal')
  const textDecoration = ref<'none' | 'underline' | 'line-through' | 'underline line-through'>(
    'none'
  )
  const textAlign = ref<'left' | 'center' | 'right'>('center')

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

  function applyTextStyleToSelected(updates: {
    fontFamily?: string
    fontSize?: number
    textColor?: string
    fontWeight?: 'normal' | 'bold'
    fontStyle?: 'normal' | 'italic'
    textDecoration?: 'none' | 'underline' | 'line-through' | 'underline line-through'
    textAlign?: 'left' | 'center' | 'right'
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
          textAlign.value = s.textAlign ?? 'center'
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

  function handleFormatBrush() {
    const styleKeys: (keyof import('@/types').NodeStyle)[] = [
      'backgroundColor',
      'borderColor',
      'textColor',
      'fontSize',
      'fontFamily',
      'fontWeight',
      'fontStyle',
      'textDecoration',
      'textAlign',
      'borderWidth',
      'borderStyle',
      'borderRadius',
    ]

    if (!formatBrushActive.value) {
      const sourceId = diagramStore.selectedNodes[0]
      if (!sourceId) {
        notify.warning(t('canvas.toolbar.formatBrushSelectSource'))
        return
      }
      const sourceNode = diagramStore.data?.nodes?.find((n) => n.id === sourceId)
      if (!sourceNode) return

      const copiedStyle: import('@/types').NodeStyle = {}
      for (const key of styleKeys) {
        if (sourceNode.style?.[key] !== undefined) {
          ;(copiedStyle as Record<string, unknown>)[key] = sourceNode.style[key]
        }
      }
      formatBrushStyle.value = copiedStyle
      formatBrushActive.value = true
      notify.success(t('canvas.toolbar.formatBrushActivated'))
      return
    }

    const targetIds = diagramStore.selectedNodes
    if (!targetIds.length) {
      formatBrushActive.value = false
      formatBrushStyle.value = null
      notify.info(t('canvas.toolbar.formatBrushCancelled'))
      return
    }

    const style = formatBrushStyle.value
    if (!style) return

    diagramStore.pushHistory(t('canvas.toolbar.formatPainter'))
    targetIds.forEach((nodeId) => {
      const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
      if (node) {
        diagramStore.updateNode(nodeId, { style: { ...(node.style || {}), ...style } })
      }
    })

    formatBrushActive.value = false
    formatBrushStyle.value = null
    notify.success(t('canvas.toolbar.formatBrushApplied', { count: targetIds.length }))
  }

  return {
    formatBrushActive,
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
    handleTextColorPick,
    handleFormatBrush,
  }
}
