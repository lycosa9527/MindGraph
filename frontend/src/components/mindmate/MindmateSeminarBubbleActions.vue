<script setup lang="ts">
/**
 * Hover actions shared by every seminar bubble: copy, reply, highlight, multi-select.
 */
import { computed } from 'vue'

import { ElButton, ElIcon } from 'element-plus'

import { CopyDocument, Share } from '@element-plus/icons-vue'

import { CornerUpLeft } from '@lucide/vue'

import I18nTooltip from '@/components/common/I18nTooltip.vue'
import MindmateSoftIcon from '@/components/mindmate/MindmateSoftIcon.vue'
import { useLanguage } from '@/composables'

const props = withDefaults(
  defineProps<{
    /** True while the pointer is on the message row. */
    open?: boolean
    /** Right-align under the sender's own bubble. */
    inline?: boolean
    /** none = can pin; mine = I can cancel; other = already pinned by someone else. */
    highlightState?: 'none' | 'mine' | 'other'
  }>(),
  {
    open: false,
    inline: false,
    highlightState: 'none',
  }
)

const emit = defineEmits<{
  (e: 'copy'): void
  (e: 'reply'): void
  (e: 'highlight'): void
  (e: 'multi'): void
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
  <div
    class="mm-bubble-actions message-actions"
    :class="{ 'justify-end': inline, 'is-open': open }"
  >
    <I18nTooltip
      k="mindmate.tooltip.copy"
      placement="top"
      :disabled="!open"
      :enterable="false"
      :show-after="400"
      :hide-after="0"
    >
      <ElButton
        text
        circle
        :aria-label="t('mindmate.tooltip.copy')"
        @click.stop="emit('copy')"
      >
        <ElIcon :size="16"><CopyDocument /></ElIcon>
      </ElButton>
    </I18nTooltip>
    <I18nTooltip
      k="mindmate.bubble.reply"
      placement="top"
      :disabled="!open"
      :enterable="false"
      :show-after="400"
      :hide-after="0"
    >
      <ElButton
        text
        circle
        :aria-label="t('mindmate.bubble.reply')"
        @click.stop="emit('reply')"
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
      :disabled="!open"
      :enterable="false"
      :show-after="400"
      :hide-after="0"
    >
      <ElButton
        text
        circle
        :class="{ 'is-set': highlightState !== 'none' }"
        :aria-label="t(highlightKey)"
        @click.stop="onHighlight"
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
      :disabled="!open"
      :enterable="false"
      :show-after="400"
      :hide-after="0"
    >
      <ElButton
        text
        circle
        :aria-label="t('mindmate.tooltip.share')"
        @click.stop="emit('multi')"
      >
        <ElIcon :size="16"><Share /></ElIcon>
      </ElButton>
    </I18nTooltip>
  </div>
</template>

<style scoped>
.mm-bubble-actions {
  display: flex;
  visibility: hidden;
  pointer-events: none;
  align-items: center;
  gap: 0;
  width: fit-content;
  height: 26px;
  padding: 0;
}

.mm-bubble-actions.is-open {
  visibility: visible;
  pointer-events: auto;
}

.mm-bubble-actions :deep(.el-tooltip__trigger) {
  display: inline-flex;
  margin: 0;
  line-height: 0;
}

.mm-bubble-actions :deep(.el-button) {
  margin: 0;
}

.mm-bubble-actions :deep(.el-button.is-circle) {
  width: 26px;
  min-width: 26px;
  height: 26px;
  padding: 0;
}

.mm-bubble-actions :deep(.el-button.is-set) {
  --el-button-text-color: #6d5efc;
  color: #6d5efc;
}
</style>
