<script setup lang="ts">
import { computed } from 'vue'

import { LayoutTemplate, PanelRight, Pencil } from '@lucide/vue'

import MindMapNumberingControls from '@/components/canvas/MindMapNumberingControls.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  MIND_MAP_DIAGRAM_STYLES,
  type MindMapDiagramStyleId,
  resolveMindMapDiagramStyleId,
} from '@/config/mindMapDiagramStyles'
import {
  type MindMapThemeId,
  getMindMapCommonThemes,
  resolveMindMapThemeId,
} from '@/config/mindMapThemes'
import { MIND_MAP_RAINBOW_THEME_ID } from '@/config/mindMapVibrantThemes'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'

import V3RibbonCommand from './V3RibbonCommand.vue'
import V3RibbonGroup from './V3RibbonGroup.vue'
import { useV3RibbonActions } from './useV3RibbonActions'

const props = withDefaults(
  defineProps<{
    classic?: boolean
    disabled?: boolean
  }>(),
  { classic: false, disabled: false }
)

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramSession()
const actions = useV3RibbonActions()
const themes = getMindMapCommonThemes()

const themeId = computed(() =>
  resolveMindMapThemeId(diagramStore.data?._mindmap_theme as string | undefined)
)
const styleId = computed(() =>
  resolveMindMapDiagramStyleId(diagramStore.data?._mindmap_diagram_style as string | undefined)
)

function ensureDiagram(): boolean {
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return false
  }
  return true
}

function pickTheme(id: MindMapThemeId): void {
  if (props.disabled || !ensureDiagram()) return
  diagramStore.applyMindMapAppearance({ themeId: id, diagramStyleId: styleId.value })
}

function pickStyle(id: MindMapDiagramStyleId): void {
  if (props.disabled || !ensureDiagram()) return
  diagramStore.applyMindMapAppearance({ themeId: themeId.value, diagramStyleId: id })
}
</script>

<template>
  <V3RibbonGroup
    group="structure"
    :label="t('canvas.v3.ribbon.groupStructure')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.toolbar.mindMapStructureBalanced')"
      :icon="LayoutTemplate"
      variant="stacked"
      :active="actions.structureMode === 'balanced'"
      :disabled="disabled"
      @click="actions.setStructure('balanced')"
    />
    <V3RibbonCommand
      :label="t('canvas.toolbar.mindMapStructureRight')"
      :icon="PanelRight"
      variant="stacked"
      :active="actions.structureMode === 'right'"
      :disabled="disabled"
      @click="actions.setStructure('right')"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="theme"
    :label="t('canvas.v3.ribbon.groupTheme')"
    :classic="classic"
  >
    <button
      v-for="theme in themes"
      :key="theme.id"
      type="button"
      class="v3-ribbon-swatch"
      :class="{ 'is-active': themeId === theme.id }"
      :style="{ background: theme.topicBackgroundColor || theme.backgroundColor }"
      :title="t(theme.nameKey)"
      :disabled="disabled"
      @click="pickTheme(theme.id)"
    />
    <button
      type="button"
      class="v3-ribbon-swatch"
      :class="{ 'is-active': themeId === MIND_MAP_RAINBOW_THEME_ID }"
      style="background: linear-gradient(90deg, #f43f5e, #f59e0b, #10b981, #3b82f6)"
      :title="t('canvas.toolbar.mindMapThemeRainbow')"
      :disabled="disabled"
      @click="pickTheme(MIND_MAP_RAINBOW_THEME_ID)"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="style"
    :label="t('canvas.v3.ribbon.groupStyle')"
    :classic="classic"
  >
    <V3RibbonCommand
      v-for="style in MIND_MAP_DIAGRAM_STYLES"
      :key="style.id"
      :label="t(style.nameKey)"
      variant="stacked"
      :active="styleId === style.id"
      :disabled="disabled"
      @click="pickStyle(style.id)"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    v-if="classic"
    group="numbering"
    :label="t('canvas.v3.ribbon.groupNumbering')"
    :classic="classic"
  >
    <MindMapNumberingControls variant="button" />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="sketch"
    :label="t('canvas.v3.ribbon.groupSketch')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.v3.line')"
      :icon="Pencil"
      variant="stacked"
      :active="actions.lineModeOn"
      :disabled="disabled"
      @click="actions.toggleLineMode"
    />
  </V3RibbonGroup>
</template>
