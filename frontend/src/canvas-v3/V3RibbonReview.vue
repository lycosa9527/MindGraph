<script setup lang="ts">
import {
  BookOpen,
  GraduationCap,
  Keyboard,
  Languages,
  List,
  MonitorPlay,
  MousePointerClick,
  Shuffle,
} from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'

import V3RibbonCommand from './V3RibbonCommand.vue'
import V3RibbonGroup from './V3RibbonGroup.vue'
import { useV3RibbonActions } from './useV3RibbonActions'

withDefaults(
  defineProps<{
    classic?: boolean
    disabled?: boolean
    workshopCode?: string | null
    shortcutGuideOpen?: boolean
  }>(),
  { classic: false, disabled: false, workshopCode: null, shortcutGuideOpen: false }
)

const emit = defineEmits<{
  toggleShortcutGuide: []
}>()

const { t } = useLanguage()
const actions = useV3RibbonActions()
</script>

<template>
  <V3RibbonGroup
    group="learn"
    :label="t('canvas.v3.ribbon.groupLearn')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.v3.learn')"
      :icon="GraduationCap"
      variant="stacked"
      :active="actions.isLearningSheet"
      :disabled="disabled"
      @click="actions.toggleLearning"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.mindMapSideToolbar.learningSheet')"
      :icon="BookOpen"
      variant="stacked"
      :disabled="disabled"
      @click="actions.openSideTool('learning_sheet')"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.mindMapSideToolbar.learningSheetRandomTitle')"
      :icon="Shuffle"
      variant="stacked"
      :disabled="disabled"
      @click="actions.learningSheet.startRandomLearningSheet"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.mindMapSideToolbar.learningSheetCustomTitle')"
      :icon="MousePointerClick"
      variant="stacked"
      :disabled="disabled"
      @click="actions.learningSheet.activatePick"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="outline"
    :label="t('canvas.v3.ribbon.groupOutline')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.mindMapSideToolbar.outline')"
      :icon="List"
      variant="stacked"
      :disabled="disabled"
      @click="actions.openSideTool('outline')"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.shortcutGuide.title')"
      :icon="Keyboard"
      variant="stacked"
      :active="shortcutGuideOpen"
      @click="emit('toggleShortcutGuide')"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="language"
    :label="t('canvas.v3.ribbon.groupLanguage')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.toolbar.moreAppTranslateLabel')"
      :icon="Languages"
      variant="stacked"
      :disabled="disabled"
      @click="actions.runTranslate"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="present"
    :label="t('canvas.v3.ribbon.groupPresent')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.zoomControls.presentationMode')"
      :icon="MonitorPlay"
      variant="stacked"
      @click="actions.startPresentation"
    />
  </V3RibbonGroup>
</template>
