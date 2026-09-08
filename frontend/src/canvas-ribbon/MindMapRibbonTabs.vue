<script setup lang="ts">
import type { Component } from 'vue'

import { GraduationCap, Folder, Palette, Users } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'

import MindMapRibbonAiMark from './MindMapRibbonAiMark.vue'
import { type MindMapRibbonTabId, MIND_MAP_RIBBON_TABS, MIND_MAP_RIBBON_TAB_LABEL_KEYS } from './mindMapRibbonTypes'
import './mindMapRibbonTabs.css'

defineProps<{
  activeTab: MindMapRibbonTabId
}>()

const emit = defineEmits<{
  'update:activeTab': [tab: MindMapRibbonTabId]
}>()

const { t } = useLanguage()

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
</script>

<template>
  <div
    class="mm-ribbon-tabs mm-ribbon-tabs--topbar"
    role="tablist"
    data-testid="mindmap-ribbon-tabs"
  >
    <button
      v-for="tab in MIND_MAP_RIBBON_TABS"
      :key="tab"
      type="button"
      class="mm-ribbon-tabs__tab"
      role="tab"
      :class="{ 'is-active': activeTab === tab, 'mm-ribbon-tabs__tab--ai': tab === 'ai' }"
      :aria-selected="activeTab === tab"
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
        <span class="mm-ribbon-tabs__label">{{ tabLabel(tab) }}</span>
      </span>
    </button>
  </div>
</template>
