<script setup lang="ts">
/**
 * Combined Terms of Use & Privacy Policy — opened from /auth footer link.
 */
import { computed } from 'vue'

import { ElScrollbar } from 'element-plus'

import { FileText } from '@lucide/vue'

import SoftwareAgreementDocument from '@/components/auth/SoftwareAgreementDocument.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables'
import { softwareAgreementForUiCode } from '@/content/authSoftwareAgreement'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t, currentLanguage } = useLanguage()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const agreement = computed(() => softwareAgreementForUiCode(currentLanguage.value))
</script>

<template>
  <SwissGlassDialog
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.agreement.ribbon')"
    :title="t('swissGlass.hero.agreement.title')"
    :line1="t('swissGlass.hero.agreement.line1')"
    :line2="t('auth.softwareAgreementUpdated', { date: agreement.updated })"
    :icon="FileText"
    width="min(640px, 94vw)"
  >
    <ElScrollbar
      class="sa-scrollbar"
      max-height="70vh"
    >
      <SoftwareAgreementDocument :agreement="agreement" />
    </ElScrollbar>
  </SwissGlassDialog>
</template>
