<script setup lang="ts">
/**
 * Bottom-bar AI cluster: generate left of 「AI模型」, v2 专业内容 right of LLM pills.
 */
import { computed } from 'vue'

import { useMediaQuery } from '@vueuse/core'

import AIModelSelector from '@/components/canvas/AIModelSelector.vue'
import CanvasToolbarMindMapAiGenerate from '@/components/canvas/CanvasToolbarMindMapAiGenerate.vue'
import CanvasToolbarMindMapAudiencePicker from '@/components/canvas/CanvasToolbarMindMapAudiencePicker.vue'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { useDiagramStore } from '@/stores'

const props = withDefaults(
  defineProps<{
    hostDisplayedLlmModel?: string | null
    isCollabGuest?: boolean
  }>(),
  {
    hostDisplayedLlmModel: null,
    isCollabGuest: false,
  }
)

const emit = defineEmits<{
  modelChange: [model: string]
}>()

const diagramStore = useDiagramStore()
const useMindMapV2 = useMindMapV2Chrome()
const { handleAIGenerate, isConceptMap } = useCanvasToolbarApps()
const compactBottomAi = useMediaQuery('(max-width: 767px)')

const showGenerate = computed(() => !isConceptMap.value && !diagramStore.collabSessionActive)
const showAudiencePicker = computed(() => useMindMapV2.value && !diagramStore.collabSessionActive)
</script>

<template>
  <AIModelSelector
    :host-displayed-llm-model="props.hostDisplayedLlmModel"
    :is-collab-guest="props.isCollabGuest"
    @model-change="emit('modelChange', $event)"
  >
    <template
      v-if="showGenerate"
      #before
    >
      <CanvasToolbarMindMapAiGenerate
        :compact="compactBottomAi"
        tooltip-placement="top"
        :delegate-generate="!useMindMapV2"
        @ai-generate="handleAIGenerate"
      />
    </template>
    <template
      v-if="showAudiencePicker"
      #after
    >
      <CanvasToolbarMindMapAudiencePicker
        :compact="compactBottomAi"
        anchor="bottom"
      />
    </template>
  </AIModelSelector>
</template>
