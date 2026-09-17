<script setup lang="ts">
/**
 * 1:1-matching action bar under a finished MindMate seminar reply.
 */
import { ElButton, ElIcon, ElTooltip } from 'element-plus'

import { CopyDocument, RefreshRight, Share } from '@element-plus/icons-vue'

import { ThumbsDown, ThumbsUp } from '@lucide/vue'

import { useLanguage } from '@/composables'
import type { CollabFeedbackRating } from '@/utils/mindmateCollabDisplay'

defineProps<{
  isLastAssistant: boolean
  canRegenerate: boolean
  regenerateDisabled: boolean
  feedback: CollabFeedbackRating | undefined
  showWordTemplateExport: boolean
  exportingWord: boolean
  showCanvas: boolean
  openingCanvas: boolean
}>()

const emit = defineEmits<{
  (e: 'copy'): void
  (e: 'regenerate'): void
  (e: 'feedback', rating: 'like' | 'dislike'): void
  (e: 'share'): void
  (e: 'export-word'): void
  (e: 'open-canvas'): void
}>()

const { t } = useLanguage()
</script>

<template>
  <div
    class="action-bar mt-3 flex flex-wrap items-center gap-1"
    :class="{
      'action-bar-visible': isLastAssistant,
      'action-bar-hover': !isLastAssistant,
    }"
  >
    <ElTooltip
      :content="t('mindmate.tooltip.copy')"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        @click="emit('copy')"
      >
        <ElIcon :size="18"><CopyDocument /></ElIcon>
      </ElButton>
    </ElTooltip>

    <ElTooltip
      v-if="canRegenerate"
      :content="t('mindmate.tooltip.regenerate')"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        :disabled="regenerateDisabled"
        @click="emit('regenerate')"
      >
        <ElIcon :size="18"><RefreshRight /></ElIcon>
      </ElButton>
    </ElTooltip>

    <ElTooltip
      :content="t('mindmate.tooltip.like')"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        :class="{ 'is-active': feedback === 'like' }"
        @click="emit('feedback', 'like')"
      >
        <ThumbsUp :size="16" />
      </ElButton>
    </ElTooltip>

    <ElTooltip
      :content="t('mindmate.tooltip.dislike')"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        :class="{ 'is-active-dislike': feedback === 'dislike' }"
        @click="emit('feedback', 'dislike')"
      >
        <ThumbsDown :size="16" />
      </ElButton>
    </ElTooltip>

    <ElTooltip
      :content="t('mindmate.tooltip.share')"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        @click="emit('share')"
      >
        <ElIcon :size="18"><Share /></ElIcon>
      </ElButton>
    </ElTooltip>

    <button
      v-if="showWordTemplateExport"
      type="button"
      class="mindmate-stone-btn action-bar-canvas-btn"
      :class="{ 'is-busy': exportingWord }"
      :disabled="exportingWord"
      :title="t('mindmate.tooltip.exportWordTemplate')"
      @click="emit('export-word')"
    >
      <span class="mindmate-stone-btn__label">{{ t('mindmate.exportWordTemplate') }}</span>
    </button>

    <ElButton
      v-if="showCanvas"
      size="small"
      class="mindmate-canvas-btn action-bar-canvas-btn"
      :loading="openingCanvas"
      @click="emit('open-canvas')"
    >
      {{ t('mindmate.openInCanvas') }}
    </ElButton>
  </div>
</template>

<style scoped>
@import '../panels/mindmate/mindmate.css';
</style>
