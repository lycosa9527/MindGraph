<script setup lang="ts">
/**
 * Change-password card for hosts that are not the Settings dialog (mobile account).
 */
import { computed } from 'vue'

import { KeyRound } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables/core/useLanguage'

import ChangePasswordForm from './ChangePasswordForm.vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const { t } = useLanguage()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

function onSuccess() {
  isVisible.value = false
  emit('success')
}
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.password.ribbon')"
    ribbon-key="swissGlass.hero.password.ribbon"
    :title="t('swissGlass.hero.password.title')"
    title-key="swissGlass.hero.password.title"
    :line1="t('swissGlass.hero.password.line1')"
    line1-key="swissGlass.hero.password.line1"
    :icon="KeyRound"
  >
    <ChangePasswordForm
      :active="visible"
      @success="onSuccess"
    />
  </SwissGlassCard>
</template>
