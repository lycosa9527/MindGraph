<script setup lang="ts">
import { computed, type Component } from 'vue'

import { Folder, GraduationCap, Palette, Users } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores'

import MindMapRibbonAiMark from './MindMapRibbonAiMark.vue'
import './mindMapRibbonTabs.css'
import {
  MIND_MAP_RIBBON_TABS,
  MIND_MAP_RIBBON_TAB_LABEL_KEYS,
  MIND_MAP_RIBBON_TOOLS_ID,
  type MindMapRibbonTabId,
} from './mindMapRibbonTypes'

const props = withDefaults(
  defineProps<{
    activeTab: MindMapRibbonTabId
    expanded?: boolean
  }>(),
  { expanded: true }
)

const emit = defineEmits<{
  'update:activeTab': [tab: MindMapRibbonTabId]
}>()

const { t } = useLanguage()
const authStore = useAuthStore()

const visibleTabs = computed(() => {
  if (authStore.user?.role === 'student') {
    return MIND_MAP_RIBBON_TABS.filter((tab) => tab !== 'research')
  }
  return MIND_MAP_RIBBON_TABS
})

const TAB_ICONS: Record<Exclude<MindMapRibbonTabId, 'ai'>, Component> = {
  file: Folder,
  edit: Palette,
  teaching: GraduationCap,
  research: Users,
}

function tabLabel(tab: MindMapRibbonTabId): string {
  return t(MIND_MAP_RIBBON_TAB_LABEL_KEYS[tab])
}

function lucideTabIcon(tab: MindMapRibbonTabId): Component | undefined {
  return tab === 'ai' ? undefined : TAB_ICONS[tab]
}

function tabTitle(tab: MindMapRibbonTabId): string {
  if (!props.expanded) {
    return t('canvas.ribbon.expand')
  }
  if (props.activeTab === tab) {
    return t('canvas.ribbon.collapse')
  }
  return tabLabel(tab)
}
</script>

<template>
  <div
    class="mm-ribbon-tabs mm-ribbon-tabs--topbar"
    :class="{ 'mm-ribbon-tabs--collapsed': !expanded }"
    role="tablist"
    data-testid="mindmap-ribbon-tabs"
  >
    <button
      v-for="tab in visibleTabs"
      :key="tab"
      type="button"
      class="mm-ribbon-tabs__tab"
      role="tab"
      :class="{ 'is-active': activeTab === tab, 'mm-ribbon-tabs__tab--ai': tab === 'ai' }"
      :aria-selected="activeTab === tab"
      :aria-controls="MIND_MAP_RIBBON_TOOLS_ID"
      :aria-expanded="activeTab === tab ? expanded : undefined"
      :title="tabTitle(tab)"
      :data-testid="`mindmap-ribbon-tab-${tab}`"
      @click="emit('update:activeTab', tab)"
    >
      <span class="mm-ribbon-tabs__inner">
        <span
          class="mm-ribbon-tabs__glyph"
          :class="`mm-ribbon-tabs__glyph--${tab}`"
          aria-hidden="true"
        >
          <MindMapRibbonAiMark v-if="tab === 'ai'" />
          <component
            :is="lucideTabIcon(tab)"
            v-else
            class="mm-ribbon-tabs__glyph-icon"
            :stroke-width="2.4"
          />
        </span>
        <span class="mm-ribbon-tabs__label">
          <I18nText :k="MIND_MAP_RIBBON_TAB_LABEL_KEYS[tab]" />
        </span>
      </span>
    </button>
  </div>
</template>
