<script setup lang="ts">
/**
 * Original V3 pill toolbar — shown while the Word ribbon is collapsed.
 */
import { useLanguage } from '@/composables/core/useLanguage'

import { useV3RibbonActions } from './useV3RibbonActions'

withDefaults(
  defineProps<{
    disabled?: boolean
  }>(),
  { disabled: false }
)

const { t } = useLanguage()
const actions = useV3RibbonActions()
</script>

<template>
  <div class="v3-toolbar__row">
    <div class="v3-toolbar__section">
    <button
      type="button"
      class="v3-tool-btn v3-tool-btn--back"
      @click="actions.goBack"
    >
      {{ t('canvas.v3.backToGallery') }}
    </button>
    <div class="v3-toolbar__group">
      <span class="v3-toolbar__label">{{ t('canvas.v3.file') }}</span>
      <button
        type="button"
        class="v3-tool-btn v3-tool-btn--export"
        :disabled="disabled"
        :title="t('canvas.topBar.exportPng')"
        @click="actions.exportPng"
      >
        {{ t('canvas.v3.exportImage') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn v3-tool-btn--file"
        :disabled="disabled"
        :title="`${t('canvas.v3.saveMg')} (${t('canvas.toolbar.saveShortcut')})`"
        @click="actions.saveMg"
      >
        {{ t('canvas.v3.saveMg') }}
      </button>
    </div>
    <div class="v3-toolbar__group">
      <span class="v3-toolbar__label">{{ t('canvas.v3.nodes') }}</span>
      <button
        type="button"
        class="v3-tool-btn"
        :disabled="disabled"
        @click="actions.handleAddNode"
      >
        {{ t('canvas.toolbar.addShort') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn"
        :disabled="disabled"
        @click="actions.handleDeleteNode"
      >
        {{ t('canvas.toolbar.deleteShort') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn v3-tool-btn--auto"
        :disabled="disabled"
        @click="actions.handleAIGenerate()"
      >
        {{ t('canvas.v3.auto') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn v3-tool-btn--line"
        :class="{ 'is-active': actions.lineModeOn }"
        :disabled="disabled"
        @click="actions.toggleLineMode"
      >
        {{ t('canvas.v3.line') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn v3-tool-btn--learn"
        :class="{ 'is-active': actions.isLearningSheet }"
        :disabled="disabled"
        @click="actions.toggleLearning"
      >
        {{ t('canvas.v3.learn') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn v3-tool-btn--palette"
        :class="{ 'is-active': actions.isNodePaletteOpen }"
        :disabled="disabled"
        @click="actions.openNodePalette"
      >
        {{ t('canvas.v3.palette') }}
      </button>
    </div>
    <div class="v3-toolbar__group">
      <span class="v3-toolbar__label">{{ t('canvas.v3.tools') }}</span>
      <button
        type="button"
        class="v3-tool-btn"
        :disabled="disabled"
        @click="actions.emptySelected"
      >
        {{ t('canvas.v3.empty') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn"
        :disabled="!actions.canUndo || disabled"
        :title="`${t('canvas.toolbar.undo')} (${t('canvas.toolbar.undoShortcut')})`"
        @click="actions.undo"
      >
        {{ t('canvas.toolbar.undo') }}
      </button>
      <button
        type="button"
        class="v3-tool-btn"
        :disabled="!actions.canRedo || disabled"
        :title="`${t('canvas.toolbar.redo')} (${t('canvas.toolbar.redoShortcut')})`"
        @click="actions.redo"
      >
        {{ t('canvas.toolbar.redo') }}
      </button>
    </div>
    </div>
    <button
      type="button"
      class="v3-mindmate-btn"
      :class="{ 'is-active': actions.isMindmateOpen }"
      :disabled="disabled"
      @click="actions.toggleMindmate"
    >
      {{ t('canvas.v3.mindMate') }}
    </button>
  </div>
</template>
