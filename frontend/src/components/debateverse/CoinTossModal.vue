<script setup lang="ts">
/**
 * CoinTossModal - Modal explaining the coin toss stage
 */
import { Coins } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { t } = useLanguage()

function handleClose() {
  emit('update:visible', false)
  emit('close')
}
</script>

<template>
  <SwissGlassDialog
    :model-value="visible"
    :ribbon="t('swissGlass.hero.coinToss.ribbon')"
    :title="t('swissGlass.hero.coinToss.title')"
    :line1="t('swissGlass.hero.coinToss.line1')"
    :icon="Coins"
    width="min(500px, 92vw)"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <p class="text-center text-[var(--swiss-body,#44403c)] mb-2">
      {{ t('debateverse.coinTossModalBody') }}
    </p>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="handleClose"
        >
          {{ t('debateverse.coinTossGotIt') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
