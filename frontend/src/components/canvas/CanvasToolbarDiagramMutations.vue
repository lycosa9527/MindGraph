<script setup lang="ts">
/**
 * Edit-tab structure buttons for non-mind-map diagrams.
 * Each button calls the existing node action for that diagram type.
 */
import { computed } from 'vue'

import { ArrowDownUp, Plus } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import { useDiagramStore } from '@/stores'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const {
  handleAddNode,
  handleAddBranch,
  handleAddChild,
  handleAddCause,
  handleAddEffect,
  handleAddTreeCategory,
  handleAddTreeChild,
} = useNodeActions({ registerEventBusListeners: false })

const diagramType = computed(() => diagramStore.type)

const doubleBubbleGroup = computed(() => {
  const selectedId = diagramStore.selectedNodes[0]
  const node = diagramStore.data?.nodes?.find((item) => item.id === selectedId)
  return node ? readDoubleBubbleRole(node) : null
})

const doubleBubbleLabelKey = computed(() =>
  doubleBubbleGroup.value === 'leftDiff' || doubleBubbleGroup.value === 'rightDiff'
    ? 'canvas.toolbar.addDifferencePair'
    : 'canvas.toolbar.addSimilarity'
)

function toggleFlowOrientation(): void {
  diagramStore.toggleFlowMapOrientation()
  notify.success(t('canvas.toolbar.layoutDirectionToggled'))
}

function addConceptRelationship(): void {
  const ids = diagramStore.selectedNodes.filter((id, index, list) => list.indexOf(id) === index)
  if (ids.length !== 2) {
    notify.warning(t('canvas.toolbar.selectTwoConcepts'))
    return
  }
  const sourceId = ids[0]
  const targetId = ids[1]
  if (!sourceId || !targetId) return
  eventBus.emit('concept_map:link_drop', { sourceId, targetId })
}
</script>

<template>
  <div class="mm-btn-group">
    <I18nTooltip
      v-if="diagramType === 'circle_map'"
      k="canvas.toolbar.addAssociation"
      placement="bottom"
    >
      <button
        type="button"
        class="mm-btn"
        @click="handleAddNode"
      >
        <Plus class="w-4 h-4" />
        <span class="mm-btn__label"><I18nText k="canvas.toolbar.addAssociation" /></span>
      </button>
    </I18nTooltip>

    <I18nTooltip
      v-else-if="diagramType === 'bubble_map'"
      k="canvas.toolbar.addAttribute"
      placement="bottom"
    >
      <button
        type="button"
        class="mm-btn"
        @click="handleAddNode"
      >
        <Plus class="w-4 h-4" />
        <span class="mm-btn__label"><I18nText k="canvas.toolbar.addAttribute" /></span>
      </button>
    </I18nTooltip>

    <I18nTooltip
      v-else-if="diagramType === 'double_bubble_map'"
      :k="doubleBubbleLabelKey"
      placement="bottom"
    >
      <button
        type="button"
        class="mm-btn"
        :class="{ 'is-dimmed': !doubleBubbleGroup }"
        @click="handleAddNode"
      >
        <Plus class="w-4 h-4" />
        <span class="mm-btn__label"><I18nText :k="doubleBubbleLabelKey" /></span>
      </button>
    </I18nTooltip>

    <template v-else-if="diagramType === 'tree_map'">
      <I18nTooltip
        k="canvas.toolbar.addCategory"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddTreeCategory"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addCategory" /></span>
        </button>
      </I18nTooltip>
      <I18nTooltip
        k="canvas.toolbar.addTreeChild"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddTreeChild"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addTreeChild" /></span>
        </button>
      </I18nTooltip>
    </template>

    <template v-else-if="diagramType === 'brace_map'">
      <I18nTooltip
        k="canvas.toolbar.addPart"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddBranch"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addPart" /></span>
        </button>
      </I18nTooltip>
      <I18nTooltip
        k="canvas.toolbar.addSubpart"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddChild"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addSubpart" /></span>
        </button>
      </I18nTooltip>
    </template>

    <template v-else-if="diagramType === 'flow_map'">
      <I18nTooltip
        k="canvas.toolbar.addStep"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddBranch"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addStep" /></span>
        </button>
      </I18nTooltip>
      <I18nTooltip
        k="canvas.toolbar.addSubstep"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddChild"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addSubstep" /></span>
        </button>
      </I18nTooltip>
      <I18nTooltip
        k="canvas.toolbar.toggleDirection"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="toggleFlowOrientation"
        >
          <ArrowDownUp class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.directionLabel" /></span>
        </button>
      </I18nTooltip>
    </template>

    <template v-else-if="diagramType === 'multi_flow_map'">
      <I18nTooltip
        k="canvas.toolbar.addCause"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddCause"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addCause" /></span>
        </button>
      </I18nTooltip>
      <I18nTooltip
        k="canvas.toolbar.addEffect"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddEffect"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addEffect" /></span>
        </button>
      </I18nTooltip>
    </template>

    <I18nTooltip
      v-else-if="diagramType === 'bridge_map'"
      k="canvas.toolbar.addAnalogyPair"
      placement="bottom"
    >
      <button
        type="button"
        class="mm-btn"
        @click="handleAddNode"
      >
        <Plus class="w-4 h-4" />
        <span class="mm-btn__label"><I18nText k="canvas.toolbar.addAnalogyPair" /></span>
      </button>
    </I18nTooltip>

    <template v-else-if="diagramType === 'concept_map'">
      <I18nTooltip
        k="diagram.contextMenu.addConcept"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          @click="handleAddNode"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="diagram.contextMenu.addConcept" /></span>
        </button>
      </I18nTooltip>
      <I18nTooltip
        k="canvas.toolbar.addRelationship"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn"
          :class="{ 'is-dimmed': diagramStore.selectedNodes.length !== 2 }"
          @click="addConceptRelationship"
        >
          <Plus class="w-4 h-4" />
          <span class="mm-btn__label"><I18nText k="canvas.toolbar.addRelationship" /></span>
        </button>
      </I18nTooltip>
    </template>
  </div>
</template>
