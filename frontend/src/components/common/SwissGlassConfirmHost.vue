<script setup lang="ts">
/**
 * Global host for swissGlassConfirm / swissGlassConfirmHero.
 */
import { computed } from 'vue'

import { TriangleAlert } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
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
    :ribbon-key="state.ribbonKey || 'swissGlass.confirm.ribbon'"
    :title="state.title"
    :title-key="state.titleKey"
    :line1="state.line1"
    :line1-key="state.line1Key"
    :line2="state.line2"
    :line2-key="state.line2Key"
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
          <I18nText
            v-if="!state.cancelLabel || state.cancelLabelKey"
            :k="state.cancelLabelKey || 'common.cancel'"
          />
          <template v-else>{{ cancelLabel }}</template>
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn min-w-22"
          :class="
            state.danger ? 'mind-map-side-rail-btn--danger' : 'mind-map-side-rail-btn--primary'
          "
          @click="onConfirm"
        >
          <I18nText
            v-if="!state.confirmLabel || state.confirmLabelKey"
            :k="state.confirmLabelKey || 'common.confirm'"
          />
          <template v-else>{{ confirmLabel }}</template>
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
