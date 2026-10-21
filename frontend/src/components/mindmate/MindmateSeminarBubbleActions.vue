<script setup lang="ts">
/**
 * Hover actions shared by every seminar bubble: copy, reply, highlight, multi-select.
 */
import { computed } from 'vue'

import { Copy, CornerUpLeft, Share2 } from '@lucide/vue'

import I18nTooltip from '@/components/common/I18nTooltip.vue'
import MindmateSoftIcon from '@/components/mindmate/MindmateSoftIcon.vue'
import { useLanguage } from '@/composables'

const props = withDefaults(
  defineProps<{
    /** Keep the cluster on the left of a persistent stamp row. */
    inline?: boolean
    /** none = can pin; mine = I can cancel; other = already pinned by someone else. */
    highlightState?: 'none' | 'mine' | 'other'
  }>(),
  {
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
    class="mm-bubble-actions"
    :class="{ 'is-inline': inline }"
  >
    <I18nTooltip
      k="mindmate.tooltip.copy"
      placement="top"
    >
      <button
        type="button"
        :aria-label="t('mindmate.tooltip.copy')"
        @click.stop="emit('copy')"
      >
        <Copy
          :size="15"
          :stroke-width="2"
        />
      </button>
    </I18nTooltip>
    <I18nTooltip
      k="mindmate.bubble.reply"
      placement="top"
    >
      <button
        type="button"
        :aria-label="t('mindmate.bubble.reply')"
        @click.stop="emit('reply')"
      >
        <CornerUpLeft
          :size="15"
          :stroke-width="2"
        />
      </button>
    </I18nTooltip>
    <I18nTooltip
      :k="highlightKey"
      placement="top"
    >
      <button
        type="button"
        class="mm-bubble-actions__pin"
        :class="{ 'is-set': highlightState !== 'none' }"
        :aria-label="t(highlightKey)"
        @click.stop="onHighlight"
      >
        <MindmateSoftIcon
          name="highlights"
          :size="15"
        />
      </button>
    </I18nTooltip>
    <I18nTooltip
      k="mindmate.tooltip.share"
      placement="top"
    >
      <button
        type="button"
        :aria-label="t('mindmate.tooltip.share')"
        @click.stop="emit('multi')"
      >
        <Share2
          :size="15"
          :stroke-width="2"
        />
      </button>
    </I18nTooltip>
  </div>
</template>

<style scoped>
.mm-bubble-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  width: fit-content;
  margin-top: 4px;
  padding: 2px;
  border: 1px solid #ece9f8;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 6px 16px rgba(28, 25, 23, 0.06);
  opacity: 0;
  pointer-events: none;
}

.mm-bubble-actions.is-inline {
  margin-top: 0;
  margin-left: 0;
}

.mm-bubble-actions button {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #57534e;
  cursor: pointer;
}

.mm-bubble-actions button:hover {
  background: #f5f3ff;
  color: #6d5efc;
}

.mm-bubble-actions button.is-set {
  background: #ececf1;
  color: #9c9aa8;
}

.mm-bubble-actions button.is-set:hover {
  background: #e4e4ea;
  color: #6b6b76;
}
</style>
