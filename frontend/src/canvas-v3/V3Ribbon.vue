<script setup lang="ts">
import { ref } from 'vue'

import { ChevronUp } from '@lucide/vue'

import CanvasMindMapShortcutGuide from '@/components/canvas/CanvasMindMapShortcutGuide.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type { SnapshotMetadata } from '@/composables/editor/useSnapshotHistory'

import V3RibbonAi from './V3RibbonAi.vue'
import V3RibbonDesign from './V3RibbonDesign.vue'
import V3RibbonFile from './V3RibbonFile.vue'
import V3RibbonHome from './V3RibbonHome.vue'
import V3RibbonReview from './V3RibbonReview.vue'
import './v3Ribbon.css'
import { type V3RibbonTabId, V3_RIBBON_TABS, V3_RIBBON_TAB_LABEL_KEYS } from './v3RibbonTypes'

withDefaults(
  defineProps<{
    activeTab: V3RibbonTabId
    disabled?: boolean
    snapshots?: SnapshotMetadata[]
    activeSnapshotVersion?: number | null
    recallingSnapshotVersion?: number | null
    isCollabGuest?: boolean
    workshopCode?: string | null
  }>(),
  {
    disabled: false,
    snapshots: () => [],
    activeSnapshotVersion: null,
    recallingSnapshotVersion: null,
    isCollabGuest: false,
    workshopCode: null,
  }
)

const emit = defineEmits<{
  'update:activeTab': [tab: V3RibbonTabId]
  toggleClassic: []
}>()

const { t } = useLanguage()
const shortcutGuideOpen = ref(false)

function toggleShortcutGuide(): void {
  shortcutGuideOpen.value = !shortcutGuideOpen.value
}

function tabLabel(tab: V3RibbonTabId): string {
  return t(V3_RIBBON_TAB_LABEL_KEYS[tab])
}
</script>

<template>
  <div
    class="v3-ribbon"
    :data-tab="activeTab"
    data-testid="mindmap-v3-ribbon"
  >
    <div
      class="v3-ribbon__tabs"
      role="tablist"
    >
      <button
        v-for="tab in V3_RIBBON_TABS"
        :key="tab"
        type="button"
        class="v3-ribbon__tab"
        role="tab"
        :class="{ 'is-active': activeTab === tab }"
        :aria-selected="activeTab === tab"
        :data-testid="`mindmap-v3-ribbon-tab-${tab}`"
        @click="emit('update:activeTab', tab)"
      >
        {{ tabLabel(tab) }}
      </button>
    </div>
    <div class="v3-ribbon__body">
      <div
        class="v3-ribbon__scroll is-classic"
        role="tabpanel"
      >
        <V3RibbonFile
          v-if="activeTab === 'file'"
          classic
          :disabled="disabled"
          :snapshots="snapshots"
          :active-snapshot-version="activeSnapshotVersion"
          :recalling-snapshot-version="recallingSnapshotVersion"
          :is-collab-guest="isCollabGuest"
        />
        <V3RibbonHome
          v-else-if="activeTab === 'home'"
          classic
          :disabled="disabled"
        />
        <V3RibbonDesign
          v-else-if="activeTab === 'design'"
          classic
          :disabled="disabled"
        />
        <V3RibbonReview
          v-else-if="activeTab === 'review'"
          classic
          :disabled="disabled"
          :workshop-code="workshopCode"
          :shortcut-guide-open="shortcutGuideOpen"
          @toggle-shortcut-guide="toggleShortcutGuide"
        />
        <V3RibbonAi
          v-else
          classic
          :disabled="disabled"
        />
      </div>
      <div class="v3-ribbon__chevron">
        <button
          type="button"
          class="v3-ribbon__chevron-btn"
          data-testid="mindmap-v3-ribbon-chevron"
          :aria-expanded="true"
          :aria-label="t('canvas.v3.ribbon.collapse')"
          @click="emit('toggleClassic')"
        >
          <ChevronUp
            :size="16"
            :stroke-width="2.25"
          />
        </button>
      </div>
    </div>
    <Teleport to="body">
      <div
        v-if="shortcutGuideOpen"
        class="v3-shortcut-guide-float"
      >
        <CanvasMindMapShortcutGuide />
      </div>
    </Teleport>
  </div>
</template>
