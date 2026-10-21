<script setup lang="ts">
/**
 * 1:1-matching action bar under a finished MindMate seminar reply.
 */
import { computed } from 'vue'

import { ElButton, ElIcon } from 'element-plus'

import { CopyDocument, RefreshRight, Share } from '@element-plus/icons-vue'

import { CornerUpLeft, ThumbsDown, ThumbsUp } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import MindmateSoftIcon from '@/components/mindmate/MindmateSoftIcon.vue'
import { useLanguage } from '@/composables'
import type { CollabFeedbackRating } from '@/utils/mindmateCollabDisplay'

const props = withDefaults(
  defineProps<{
    canRegenerate: boolean
    regenerateDisabled: boolean
    feedback: CollabFeedbackRating | undefined
    showWordTemplateExport: boolean
    showConvertToDocument: boolean
    convertingDocument: boolean
    exportingWord: boolean
    showCanvas: boolean
    openingCanvas: boolean
    highlightState?: 'none' | 'mine' | 'other'
  }>(),
  {
    highlightState: 'none',
  }
)

const emit = defineEmits<{
  (e: 'copy'): void
  (e: 'regenerate'): void
  (e: 'feedback', rating: 'like' | 'dislike'): void
  (e: 'reply'): void
  (e: 'highlight'): void
  (e: 'multi'): void
  (e: 'exportWord'): void
  (e: 'convertDocument'): void
  (e: 'openCanvas'): void
}>()

const { t } = useLanguage()

const highlightKey = computed(() => {
  if (props.highlightState === 'mine') {
    return 'mindmate.highlights.cancelMine'
  }
  if (props.highlightState === 'other') {
    return 'mindmate.highlights.alreadySet'
  }
  return 'mindmate.highlights.pin'
})

function onHighlight(): void {
  if (props.highlightState === 'other') {
    return
  }
  emit('highlight')
}
</script>

<template>
  <div class="action-bar action-bar-visible mt-3 flex flex-wrap items-center gap-1">
    <I18nTooltip
      k="mindmate.tooltip.copy"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        @click="emit('copy')"
      >
        <ElIcon :size="18"><CopyDocument /></ElIcon>
      </ElButton>
    </I18nTooltip>

    <I18nTooltip
      v-if="canRegenerate"
      k="mindmate.tooltip.regenerate"
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
    </I18nTooltip>

    <I18nTooltip
      k="mindmate.tooltip.like"
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
    </I18nTooltip>

    <I18nTooltip
      k="mindmate.tooltip.dislike"
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
    </I18nTooltip>

    <I18nTooltip
      k="mindmate.bubble.reply"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        @click="emit('reply')"
      >
        <CornerUpLeft
          :size="16"
          :stroke-width="2"
        />
      </ElButton>
    </I18nTooltip>

    <I18nTooltip
      :k="highlightKey"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        :class="{ 'is-set': highlightState !== 'none' }"
        @click="onHighlight"
      >
        <MindmateSoftIcon
          name="highlights"
          :size="16"
        />
      </ElButton>
    </I18nTooltip>

    <I18nTooltip
      k="mindmate.tooltip.share"
      placement="top"
    >
      <ElButton
        text
        class="action-btn-lg"
        @click="emit('multi')"
      >
        <ElIcon :size="18"><Share /></ElIcon>
      </ElButton>
    </I18nTooltip>

    <button
      v-if="showConvertToDocument"
      type="button"
      class="mindmate-stone-btn action-bar-canvas-btn"
      :class="{ 'is-busy': convertingDocument }"
      :disabled="convertingDocument"
      :title="t('mindmate.tooltip.convertToDocument')"
      @click="emit('convertDocument')"
    >
      <span class="mindmate-stone-btn__label">
        <I18nText
          k="mindmate.convertToDocument"
          dense
        />
      </span>
    </button>

    <button
      v-if="showWordTemplateExport"
      type="button"
      class="mindmate-stone-btn action-bar-canvas-btn"
      :class="{ 'is-busy': exportingWord }"
      :disabled="exportingWord"
      :title="t('mindmate.tooltip.exportWordTemplate')"
      @click="emit('exportWord')"
    >
      <span class="mindmate-stone-btn__label">
        <I18nText
          k="mindmate.exportWordTemplate"
          dense
        />
      </span>
    </button>

    <ElButton
      v-if="showCanvas"
      size="small"
      class="mindmate-canvas-btn action-bar-canvas-btn"
      :loading="openingCanvas"
      @click="emit('openCanvas')"
    >
      <I18nText
        k="mindmate.openInCanvas"
        dense
      />
    </ElButton>
  </div>
</template>

<style scoped>
@import '../panels/mindmate/mindmate.css';

.action-btn-lg.is-set {
  background: #ececf1;
  color: #9c9aa8;
}

.action-btn-lg.is-set:hover {
  background: #e4e4ea;
  color: #6b6b76;
}
</style>
