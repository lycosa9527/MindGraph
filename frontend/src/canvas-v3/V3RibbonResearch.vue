<script setup lang="ts">
import { Bot } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'

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
</script>

<template>
  <V3RibbonGroup
    group="collaborate"
    :label="t('canvas.v3.ribbon.groupCollaborate')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.v3.mindMate')"
      :icon="Bot"
      variant="stacked"
      :active="actions.isMindmateOpen"
      :disabled="disabled"
      @click="actions.toggleMindmate"
    />
  </V3RibbonGroup>
</template>
