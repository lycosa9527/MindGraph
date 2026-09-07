<script setup lang="ts">
import { Lightbulb, School } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useMindClassroomStore } from '@/stores'

import V3RibbonCommand from './V3RibbonCommand.vue'
import V3RibbonGroup from './V3RibbonGroup.vue'
import { useV3RibbonActions } from './useV3RibbonActions'

withDefaults(
  defineProps<{
    classic?: boolean
    disabled?: boolean
  }>(),
  { classic: false, disabled: false }
)

const { t } = useLanguage()
const actions = useV3RibbonActions()
const classroomStore = useMindClassroomStore()
</script>

<template>
  <V3RibbonGroup
    group="learn"
    :label="t('canvas.v3.ribbon.tabLearn')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.floatingToolbar.explain')"
      :icon="Lightbulb"
      variant="stacked"
      :disabled="disabled || !actions.hasSelection"
      @click="actions.requestExplainNode"
    />
    <V3RibbonCommand
      :label="t('canvas.mindMapSideToolbar.mindClassroom')"
      :icon="School"
      variant="stacked"
      :disabled="disabled"
      @click="classroomStore.openModal()"
    />
  </V3RibbonGroup>
</template>
