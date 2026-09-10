<script setup lang="ts">
/**
 * Global host for swissGlassConfirm / swissGlassConfirmHero.
 */
import { computed } from 'vue'

import { TriangleAlert } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import {
  getSwissGlassConfirmState,
  settleSwissGlassConfirm,
} from '@/composables/common/useSwissGlassConfirm'
import { useLanguage } from '@/composables/core/useLanguage'

const state = getSwissGlassConfirmState()
const { t } = useLanguage()

const ribbon = computed(() => state.ribbon || t('swissGlass.confirm.ribbon'))
const confirmLabel = computed(() => state.confirmLabel || t('common.confirm'))
const cancelLabel = computed(() => state.cancelLabel || t('common.cancel'))
const plateIcon = computed(() => state.icon ?? TriangleAlert)

function onConfirm(): void {
  settleSwissGlassConfirm(true)
}

function onCancel(): void {
  settleSwissGlassConfirm(false)
}
</script>

<template>
  <SwissGlassDialog
    v-model="state.open"
    :ribbon="ribbon"
    :title="state.title"
    :line1="state.line1"
    :line2="state.line2"
    :icon="plateIcon"
    width="min(440px, 92vw)"
    :close-on-click-modal="false"
    @close="onCancel"
  >
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="onCancel"
        >
          {{ cancelLabel }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn min-w-22"
          :class="
            state.danger ? 'mind-map-side-rail-btn--danger' : 'mind-map-side-rail-btn--primary'
          "
          @click="onConfirm"
        >
          {{ confirmLabel }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
