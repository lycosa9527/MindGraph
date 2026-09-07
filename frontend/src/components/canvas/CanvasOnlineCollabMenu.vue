<script setup lang="ts">
/**
 * Global canvas collab entry — school / shared-code / stop.
 */
import { computed } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { useV3RibbonActions } from '@/canvas-v3/useV3RibbonActions'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramStore } from '@/stores'

import CanvasCollabDrawIcon from './CanvasCollabDrawIcon.vue'

const props = withDefaults(
  defineProps<{
    workshopCode?: string | null
    isCollabGuest?: boolean
    isViewer?: boolean
  }>(),
  {
    workshopCode: null,
    isCollabGuest: false,
    isViewer: false,
  }
)

const { t } = useLanguage()
const { canUseOnlineCollab } = useSchoolTierFeatures()
const diagramStore = useDiagramStore()
const actions = useV3RibbonActions()

const sessionLive = computed(
  () => Boolean(props.workshopCode) || diagramStore.collabSessionActive
)

const showMenu = computed(
  () =>
    !props.isViewer &&
    !props.isCollabGuest &&
    (canUseOnlineCollab.value || sessionLive.value)
)
</script>

<template>
  <ElDropdown
    v-if="showMenu"
    trigger="click"
    placement="bottom-end"
    popper-class="canvas-collab-dropdown-popper"
    @command="(cmd: string) => actions.openCollab(cmd as 'organization' | 'network' | 'stop')"
  >
    <button
      type="button"
      class="canvas-title-collab"
      :class="{ 'is-live': sessionLive }"
      data-testid="canvas-title-collab"
      :aria-label="t('canvas.zoomControls.collaborate')"
      :title="t('canvas.topBar.collabTooltip')"
    >
      <CanvasCollabDrawIcon class="canvas-title-collab__icon" />
      <span class="canvas-title-collab__label">{{ t('canvas.zoomControls.collaborate') }}</span>
    </button>
    <template #dropdown>
      <ElDropdownMenu>
        <ElDropdownItem
          v-if="canUseOnlineCollab"
          command="organization"
        >
          {{ t('canvas.zoomControls.collabWithinOrg') }}
        </ElDropdownItem>
        <ElDropdownItem
          v-if="canUseOnlineCollab"
          command="network"
        >
          {{ t('canvas.zoomControls.collabCrossOrg') }}
        </ElDropdownItem>
        <ElDropdownItem
          v-if="sessionLive"
          :divided="canUseOnlineCollab"
          command="stop"
        >
          {{ t('canvas.zoomControls.collabTurnOff') }}
        </ElDropdownItem>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</template>

<style scoped>
.canvas-title-collab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #7c3aed;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
}

.canvas-title-collab:hover {
  background: #fff;
}

.canvas-title-collab__icon {
  flex-shrink: 0;
}

.canvas-title-collab__label {
  max-width: 7.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
