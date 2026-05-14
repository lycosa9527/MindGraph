<script setup lang="ts">
import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElTooltip } from 'element-plus'

import { ChevronDown, LayoutGrid } from 'lucide-vue-next'

import type { MoreAppItem } from '@/composables/canvasToolbar'

withDefaults(
  defineProps<{
    compact?: boolean
    moreAppsLabel: string
    apps: MoreAppItem[]
  }>(),
  { compact: false }
)

const emit = defineEmits<{
  selectApp: [app: MoreAppItem]
}>()
</script>

<template>
  <ElTooltip
    :content="moreAppsLabel"
    placement="bottom"
    :disabled="!compact"
  >
    <span class="inline-flex">
      <ElDropdown
        trigger="hover"
        placement="bottom-end"
        popper-class="canvas-more-apps-popper"
      >
        <ElButton
          size="small"
          class="more-apps-btn canvas-more-apps-trigger"
        >
          <LayoutGrid class="canvas-more-apps-trigger__icon w-4 h-4 shrink-0" />
          <span
            v-if="!compact"
            class="canvas-more-apps-trigger__label"
            >{{ moreAppsLabel }}</span
          >
          <ChevronDown class="canvas-more-apps-trigger__chevron w-3.5 h-3.5 shrink-0" />
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu class="canvas-more-apps-menu max-h-[min(420px,70vh)] overflow-y-auto">
            <ElDropdownItem
              v-for="app in apps"
              :key="app.appKey ?? app.handlerKey ?? app.name"
              class="canvas-more-apps-menu__item"
              @click="emit('selectApp', app)"
            >
              <div class="canvas-more-apps__row flex items-start">
                <div
                  class="canvas-more-apps__icon-wrap rounded-full p-2 mr-3 shrink-0"
                  :class="app.iconBg"
                >
                  <component
                    :is="app.icon"
                    class="w-4 h-4"
                    :class="app.iconColor"
                  />
                </div>
                <div class="flex-1 min-w-0">
                  <div
                    class="canvas-more-apps__title mb-0.5 flex flex-wrap items-center gap-2 font-medium"
                  >
                    {{ app.name }}
                    <span
                      v-if="app.tag"
                      class="canvas-more-apps__tag text-xs px-2 py-0.5 rounded-full"
                      >{{ app.tag }}</span
                    >
                  </div>
                  <div class="canvas-more-apps__desc text-xs">{{ app.desc }}</div>
                </div>
              </div>
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </span>
  </ElTooltip>
</template>

<style scoped>
/**
 * Trigger — matches MindGraphLanguageSwitcher header Swiss stone pill
 * (see .mindgraph-lang-switcher.mindgraph-lang-switcher--header).
 */
.canvas-more-apps-trigger.canvas-more-apps-trigger {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

.canvas-more-apps-trigger__icon {
  color: #57534e;
}

.canvas-more-apps-trigger__label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #1c1917;
}

.canvas-more-apps-trigger__chevron {
  color: #57534e;
}

.dark .canvas-more-apps-trigger.canvas-more-apps-trigger {
  --el-button-bg-color: #374151;
  --el-button-border-color: #4b5563;
  --el-button-hover-bg-color: #4b5563;
  --el-button-hover-border-color: #6b7280;
  --el-button-active-bg-color: #6b7280;
  --el-button-text-color: #f9fafb;
}

.dark .canvas-more-apps-trigger__icon,
.dark .canvas-more-apps-trigger__chevron {
  color: #d6d3d1;
}

.dark .canvas-more-apps-trigger__label {
  color: #f9fafb;
}
</style>

<!-- Teleported popper — must mirror .mindgraph-lang-switcher-popper -->
<style>
.canvas-more-apps-popper.el-popper {
  width: min(320px, calc(100vw - 24px)) !important;
  max-width: min(320px, calc(100vw - 24px)) !important;
  box-sizing: border-box !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

.dark .canvas-more-apps-popper.el-popper {
  border-color: #374151 !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.25),
    0 2px 4px -2px rgba(0, 0, 0, 0.18) !important;
}

.canvas-more-apps-popper .canvas-more-apps-menu.el-dropdown-menu {
  width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  scrollbar-gutter: stable;
}

.canvas-more-apps-popper .canvas-more-apps-menu__item.el-dropdown-menu__item {
  box-sizing: border-box;
  width: 100%;
  padding: 0 !important;
  border-radius: 6px;
  transition:
    background 0.12s,
    color 0.12s;
}

.canvas-more-apps-popper .canvas-more-apps-menu__item.el-dropdown-menu__item:hover,
.canvas-more-apps-popper .canvas-more-apps-menu__item.el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
}

.canvas-more-apps-popper .canvas-more-apps-menu__item.el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

.dark .canvas-more-apps-popper .canvas-more-apps-menu__item.el-dropdown-menu__item:hover,
.dark .canvas-more-apps-popper .canvas-more-apps-menu__item.el-dropdown-menu__item:focus {
  background: #374151 !important;
}

.dark .canvas-more-apps-popper .canvas-more-apps-menu__item.el-dropdown-menu__item:active {
  background: #4b5563 !important;
}

.canvas-more-apps-popper .canvas-more-apps__row {
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: #44403c;
}

.canvas-more-apps-popper .canvas-more-apps__title {
  color: #1c1917;
}

.canvas-more-apps-popper .canvas-more-apps__desc {
  color: #78716c;
  font-weight: 400;
  letter-spacing: 0;
}

.canvas-more-apps-popper .canvas-more-apps__tag {
  background: #f5f5f4;
  color: #57534e;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.dark .canvas-more-apps-popper .canvas-more-apps__row {
  color: #d6d3d1;
}

.dark .canvas-more-apps-popper .canvas-more-apps__title {
  color: #f9fafb;
}

.dark .canvas-more-apps-popper .canvas-more-apps__desc {
  color: #a8a29e;
}

.dark .canvas-more-apps-popper .canvas-more-apps__tag {
  background: #374151;
  color: #e7e5e4;
}

.canvas-more-apps-popper
  .canvas-more-apps-menu__item.el-dropdown-menu__item:hover
  .canvas-more-apps__title,
.canvas-more-apps-popper
  .canvas-more-apps-menu__item.el-dropdown-menu__item:focus
  .canvas-more-apps__title {
  color: #1c1917;
}

.dark
  .canvas-more-apps-popper
  .canvas-more-apps-menu__item.el-dropdown-menu__item:hover
  .canvas-more-apps__title,
.dark
  .canvas-more-apps-popper
  .canvas-more-apps-menu__item.el-dropdown-menu__item:focus
  .canvas-more-apps__title {
  color: #f9fafb;
}
</style>
