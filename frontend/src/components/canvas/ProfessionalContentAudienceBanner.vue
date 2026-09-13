<script setup lang="ts">
/**
 * Shows current AI audience level from the status-bar「专业内容」preference.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { GraduationCap } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useAiContentLevelStore } from '@/stores'

withDefaults(
  defineProps<{
    appearance?: 'boxed' | 'hero'
  }>(),
  { appearance: 'boxed' }
)

const { t } = useLanguage()
const { level } = storeToRefs(useAiContentLevelStore())

const audienceTitle = computed(() =>
  t(`canvas.toolbar.professionalContent.level.${level.value}.title`)
)
</script>

<template>
  <div
    class="pc-audience-banner"
    :class="`pc-audience-banner--${appearance}`"
  >
    <GraduationCap
      class="pc-audience-banner__icon"
      :stroke-width="2"
      aria-hidden="true"
    />
    <span>
      {{ t('canvas.toolbar.professionalContent.audienceLine', { level: audienceTitle }) }}
    </span>
  </div>
</template>

<style scoped>
.pc-audience-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  line-height: 1.35;
  color: #64748b;
}

.pc-audience-banner--boxed {
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8fafc;
}

.pc-audience-banner--hero {
  margin: 0;
  padding: 0;
  background: transparent;
  font-size: inherit;
  font-weight: inherit;
  line-height: inherit;
  color: inherit;
}

.pc-audience-banner__icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  opacity: 0.75;
}

.pc-audience-banner--hero .pc-audience-banner__icon {
  width: 13px;
  height: 13px;
}

:global(.dark) .pc-audience-banner--boxed {
  background: rgb(30 41 59 / 0.85);
  color: #94a3b8;
}

:global(.dark) .pc-audience-banner--hero {
  color: var(--ai-muted, #94a3b8);
}
</style>
