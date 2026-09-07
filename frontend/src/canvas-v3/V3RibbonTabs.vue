<script setup lang="ts">
import type { Component } from 'vue'

import { GraduationCap, Folder, Palette, Users } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'

import V3RibbonAiMark from './V3RibbonAiMark.vue'
import { type V3RibbonTabId, V3_RIBBON_TABS, V3_RIBBON_TAB_LABEL_KEYS } from './v3RibbonTypes'
import './v3Ribbon.css'
import './v3RibbonTabs.css'

withDefaults(
  defineProps<{
    activeTab: V3RibbonTabId
    variant?: 'v3' | 'topbar'
  }>(),
  { variant: 'v3' }
)

const emit = defineEmits<{
  'update:activeTab': [tab: V3RibbonTabId]
}>()

const { t } = useLanguage()

const TAB_ICONS: Record<Exclude<V3RibbonTabId, 'ai'>, Component> = {
  file: Folder,
  edit: Palette,
  teaching: GraduationCap,
  research: Users,
}

function tabLabel(tab: V3RibbonTabId): string {
  return t(V3_RIBBON_TAB_LABEL_KEYS[tab])
}

function lucideTabIcon(tab: V3RibbonTabId): Component | undefined {
  return tab === 'ai' ? undefined : TAB_ICONS[tab]
}
</script>

<template>
  <div
    class="v3-ribbon-tabs"
    :class="variant === 'topbar' ? 'v3-ribbon-tabs--topbar' : 'v3-ribbon-tabs--v3'"
    role="tablist"
    data-testid="mindmap-ribbon-tabs"
  >
    <button
      v-for="tab in V3_RIBBON_TABS"
      :key="tab"
      type="button"
      class="v3-ribbon-tabs__tab"
      role="tab"
      :class="{ 'is-active': activeTab === tab, 'v3-ribbon-tabs__tab--ai': tab === 'ai' }"
      :aria-selected="activeTab === tab"
      :data-testid="`mindmap-v3-ribbon-tab-${tab}`"
      @click="emit('update:activeTab', tab)"
    >
      <span class="v3-ribbon-tabs__inner">
        <span
          class="v3-ribbon-tabs__glyph"
          :class="`v3-ribbon-tabs__glyph--${tab}`"
          aria-hidden="true"
        >
          <V3RibbonAiMark v-if="tab === 'ai'" />
          <component
            :is="lucideTabIcon(tab)"
            v-else
            class="v3-ribbon-tabs__glyph-icon"
            :stroke-width="2.4"
          />
        </span>
        <span class="v3-ribbon-tabs__label">{{ tabLabel(tab) }}</span>
      </span>
    </button>
  </div>
</template>
