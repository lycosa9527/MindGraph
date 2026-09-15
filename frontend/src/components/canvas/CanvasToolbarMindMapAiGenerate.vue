<script setup lang="ts">
/**
 * Bottom-bar「AI生成图示」button — no 学段 caret.
 * New canvas uses 专业内容; classic generate is delegated to the parent.
 */
import { ElTooltip } from 'element-plus'

import { Sparkles } from '@lucide/vue'

import { useCollabGuestAiGate } from '@/composables/collab/useCollabGuestAiGate'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMindMapAudienceGenerate } from '@/composables/mindMap/audience/useMindMapAudienceGenerate'

const props = withDefaults(
  defineProps<{
    compact?: boolean
    tooltipPlacement?: 'top' | 'bottom'
    /** Classic / thinking-map generate — parent handles click. */
    delegateGenerate?: boolean
  }>(),
  { compact: false, tooltipPlacement: 'bottom', delegateGenerate: false }
)

const emit = defineEmits<{
  aiGenerate: []
}>()

const { t } = useLanguage()
const { isAIGenerating, handleMindMapAiGenerate } = useMindMapAudienceGenerate()
const { aiBlockedByCollab, notifyCollabGuestAiBlocked } = useCollabGuestAiGate()

function onGenerateClick(): void {
  if (aiBlockedByCollab.value) {
    notifyCollabGuestAiBlocked()
    return
  }
  if (props.delegateGenerate) {
    emit('aiGenerate')
    return
  }
  void handleMindMapAiGenerate()
}

const generateLabel = t('canvas.toolbar.aiGenerate')
const generatingLabel = t('canvas.toolbar.aiGenerating')
</script>

<template>
  <ElTooltip
    :content="
      aiBlockedByCollab
        ? t('canvas.toolbar.collabAiBlocked')
        : isAIGenerating
          ? generatingLabel
          : t('canvas.toolbar.aiGenerateTooltip')
    "
    :placement="props.tooltipPlacement"
    :disabled="!props.compact && !aiBlockedByCollab"
  >
    <button
      type="button"
      class="mm-ai-generate"
      :class="{
        'mm-ai-generate--compact': props.compact,
        'mm-ai-generate--busy': isAIGenerating,
        'mm-ai-generate--blocked': aiBlockedByCollab,
      }"
      :disabled="isAIGenerating"
      :aria-disabled="aiBlockedByCollab"
      :aria-label="
        aiBlockedByCollab
          ? t('canvas.toolbar.collabAiBlocked')
          : isAIGenerating
            ? generatingLabel
            : generateLabel
      "
      @click="onGenerateClick"
    >
      <Sparkles
        class="mm-ai-generate__icon h-4 w-4 shrink-0"
        aria-hidden="true"
      />
      <span
        v-if="!props.compact"
        class="mm-ai-generate__label"
        >{{ isAIGenerating ? generatingLabel : generateLabel }}</span
      >
    </button>
  </ElTooltip>
</template>

<style scoped>
.mm-ai-generate {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border: none;
  border-radius: 8px;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  box-shadow:
    0 1px 3px rgb(37 99 235 / 0.35),
    inset 0 1px 0 rgb(255 255 255 / 0.2);
  transition:
    background 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.mm-ai-generate--compact {
  padding: 0 10px;
}

.mm-ai-generate:hover:not(:disabled) {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
}

.mm-ai-generate:disabled,
.mm-ai-generate--blocked {
  cursor: not-allowed;
  opacity: 0.45;
  box-shadow: none;
}

.mm-ai-generate--blocked:hover {
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
}

.mm-ai-generate__label,
.mm-ai-generate__icon {
  color: #fff;
  white-space: nowrap;
}
</style>
