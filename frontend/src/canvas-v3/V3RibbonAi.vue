<script setup lang="ts">
import { FileSearch, GitBranch, Layers, MessageCircle, Sparkles } from '@lucide/vue'

import CanvasToolbarMindMapAudiencePicker from '@/components/canvas/CanvasToolbarMindMapAudiencePicker.vue'
import { useLanguage } from '@/composables/core/useLanguage'

import V3RibbonCommand from './V3RibbonCommand.vue'
import V3RibbonGroup from './V3RibbonGroup.vue'
import { useV3RibbonActions } from './useV3RibbonActions'

withDefaults(
  defineProps<{
    classic?: boolean
    disabled?: boolean
  }>(),
  { classic: false, disabled: false }
)

const { t } = useLanguage()
const actions = useV3RibbonActions()
</script>

<template>
  <V3RibbonGroup
    group="generate"
    :label="t('canvas.v3.ribbon.groupGenerate')"
    :classic="classic"
  >
    <template #lead>
      <V3RibbonCommand
        :label="t('canvas.v3.auto')"
        :icon="Sparkles"
        variant="stacked"
        primary
        :disabled="disabled"
        @click="actions.handleAIGenerate()"
      />
    </template>
    <CanvasToolbarMindMapAudiencePicker
      v-if="classic"
      :compact="!classic"
      anchor="bottom"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="model"
    :label="t('canvas.v3.ribbon.groupModel')"
    :classic="classic"
  >
    <V3RibbonCommand
      v-for="model in actions.llmModels"
      :key="model.id"
      :label="model.label"
      variant="stacked"
      :active="actions.selectedLlm === model.id"
      :disabled="disabled"
      @click="actions.selectLlm(model.id)"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    group="assist"
    :label="t('canvas.v3.ribbon.groupAssist')"
    :classic="classic"
  >
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.mindMapSideToolbar.waterfall')"
      :icon="Layers"
      variant="stacked"
      :disabled="disabled"
      @click="actions.openSideTool('waterfall')"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.mindMapSideToolbar.oneSentence')"
      :icon="MessageCircle"
      variant="stacked"
      :disabled="disabled"
      @click="actions.openSideTool('one_sentence')"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.mindMapSideToolbar.documentSummary')"
      :icon="FileSearch"
      variant="stacked"
      :disabled="disabled"
      @click="actions.openSideTool('document_summary')"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    v-if="classic"
    group="onnode"
    :label="t('canvas.v3.ribbon.groupOnNode')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.floatingToolbar.aiSubgraph')"
      :icon="GitBranch"
      variant="stacked"
      :disabled="disabled || !actions.hasSelection"
      @click="actions.requestAiSubgraph"
    />
  </V3RibbonGroup>
</template>
