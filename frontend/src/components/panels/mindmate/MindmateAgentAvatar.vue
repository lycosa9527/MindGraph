<script setup lang="ts">
/**
 * MindMate assistant avatar: school upload when set, else bundled default; falls back on load error.
 * Optional loadPhase shows the same traveling ring as canvas LLM model buttons.
 */
import { computed, ref, watch } from 'vue'

import { ElAvatar } from 'element-plus'

import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import { isActiveLlmPhaseRing } from '@/utils/llmLoadPhase'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import type { ModelLoadPhase } from '@/stores/llmResults'

const props = withDefaults(
  defineProps<{
    size?: number
    avatarClass?: string
    brandingSize?: 'md' | 'lg'
    phase?: ModelLoadPhase
  }>(),
  {
    size: 40,
    avatarClass: '',
    brandingSize: 'md',
    phase: 'idle',
  }
)

const { avatarUrl, defaultAvatar, displayName } = useMindMateBranding(props.brandingSize)
const displaySrc = ref(avatarUrl.value)

watch(avatarUrl, (url) => {
  displaySrc.value = url
})

function onAvatarError() {
  if (displaySrc.value !== defaultAvatar) {
    displaySrc.value = defaultAvatar
  }
}

const showPhaseRing = computed(() => isActiveLlmPhaseRing(props.phase))
</script>

<template>
  <LlmPhaseRing
    :phase="phase"
    :active="showPhaseRing"
    border-radius="50%"
    streaming-variant="primary"
    class="mindmate-agent-avatar-ring"
  >
    <ElAvatar
      :src="displaySrc"
      :alt="displayName"
      :size="size"
      :class="avatarClass"
      @error="onAvatarError"
    />
  </LlmPhaseRing>
</template>

<style scoped>
.mindmate-agent-avatar-ring {
  flex-shrink: 0;
}
</style>
