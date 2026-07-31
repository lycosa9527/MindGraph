<script setup lang="ts">
/**
 * MaiteModeNav — demo / inquiry / map Swiss stone segmented control.
 */
import { computed } from 'vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMaiteWorkspace } from '@/composables/maite/useMaiteWorkspace'

import type { MaiteMode } from '@/types/maite'

const { t } = useLanguage()
const { mode, setMode } = useMaiteWorkspace()

const modes: MaiteMode[] = ['demo', 'inquiry', 'map']

const options = computed(() =>
  modes.map((value) => ({
    label: t(`maite.mode.${value}`),
    value,
  }))
)

const modeModel = computed({
  get: () => mode.value,
  set: (value: MaiteMode) => {
    setMode(value)
  },
})
</script>

<template>
  <AdminSwissSegmented
    v-model="modeModel"
    :options="options"
    equal
    :aria-label="t('maite.title')"
  />
</template>
