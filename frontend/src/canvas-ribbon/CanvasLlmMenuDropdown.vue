<script setup lang="ts">
/**
 * Canvas model menu. Closed state is the current pick — Express with the
 * DeepSeek mark until the user chooses another model.
 */
import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Check, ChevronUp } from '@lucide/vue'

import LlmPhaseRing, {
  type LlmPhaseRingStreamingVariant,
} from '@/components/shared/LlmPhaseRing.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useCanvasLlmMenu } from '@/composables/llm/useCanvasLlmMenu'
import { useLLMResultsStore } from '@/stores/llmResults'

import CanvasLlmLogo from './CanvasLlmLogo.vue'
import './mindMapStatusBar.css'

withDefaults(
  defineProps<{
    /** Popper placement. Both canvas bars sit on the bottom edge. */
    placement?: 'top-start' | 'top' | 'bottom-start'
    testId?: string
    /** Taller tap target for the phone canvas bar. */
    touch?: boolean
  }>(),
  {
    placement: 'top-start',
    testId: 'mindmap-ribbon-llm-menu',
    touch: false,
  }
)

const { t } = useLanguage()
const { llmMenu, selectedLlm, selectedLlmRow, selectLlm } = useCanvasLlmMenu()
const llmResultsStore = useLLMResultsStore()

function onLlmCommand(command: string | number | object): void {
  if (typeof command === 'string') {
    selectLlm(command)
  }
}

function ringVariant(modelId: string): LlmPhaseRingStreamingVariant {
  if (modelId === 'doubao' || modelId === 'doubao21') {
    return 'doubao'
  }
  if (modelId.startsWith('qwen')) {
    return 'qwen'
  }
  if (modelId === 'deepseek') {
    return 'deepseek'
  }
  return 'primary'
}
</script>

<template>
  <ElDropdown
    trigger="click"
    :placement="placement"
    :popper-class="touch ? 'mm-llm-menu-popper mm-llm-menu-popper--touch' : 'mm-llm-menu-popper'"
    :data-testid="testId"
    @command="onLlmCommand"
  >
    <LlmPhaseRing
      :phase="llmResultsStore.modelPhases[selectedLlm]"
      :streaming-variant="ringVariant(selectedLlm)"
      border-radius="9999px"
    >
      <button
        type="button"
        class="mm-llm-menu-btn"
        :class="{ 'mm-llm-menu-btn--touch': touch }"
        :data-llm="selectedLlm"
        :aria-label="t('canvas.ribbon.aiModel')"
      >
        <CanvasLlmLogo
          v-if="selectedLlmRow"
          :name="selectedLlmRow.logo"
          :size="touch ? 18 : 16"
        />
        <span class="mm-llm-menu-btn__label">{{ selectedLlmRow?.label }}</span>
        <ChevronUp
          class="mm-llm-menu-btn__chevron h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
    </LlmPhaseRing>
    <template #dropdown>
      <ElDropdownMenu class="mm-llm-menu">
        <ElDropdownItem
          v-for="model in llmMenu"
          :key="model.id"
          :command="model.id"
          :class="{ 'is-active': selectedLlm === model.id }"
        >
          <span class="mm-llm-menu__row">
            <CanvasLlmLogo
              :name="model.logo"
              :size="touch ? 18 : 16"
            />
            <span class="mm-llm-menu__label">{{ model.label }}</span>
            <span
              v-if="model.model"
              class="mm-llm-menu__model"
              >{{ model.model }}</span
            >
            <Check
              v-if="selectedLlm === model.id"
              class="mm-llm-menu__check h-3.5 w-3.5"
              :stroke-width="2"
            />
          </span>
        </ElDropdownItem>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</template>
