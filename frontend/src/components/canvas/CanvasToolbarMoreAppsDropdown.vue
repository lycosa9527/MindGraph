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
      >
        <ElButton
          size="small"
          class="more-apps-btn"
        >
          <LayoutGrid class="w-4 h-4 shrink-0 text-gray-500 dark:text-gray-400" />
          <span v-if="!compact">{{ moreAppsLabel }}</span>
          <ChevronDown class="w-3.5 h-3.5 shrink-0" />
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu class="more-apps-menu">
            <ElDropdownItem
              v-for="app in apps"
              :key="app.appKey ?? app.handlerKey ?? app.name"
              @click="emit('selectApp', app)"
            >
              <div class="flex items-start py-1">
                <div
                  class="rounded-full p-2 mr-3 shrink-0"
                  :class="app.iconBg"
                >
                  <component
                    :is="app.icon"
                    class="w-4 h-4"
                    :class="app.iconColor"
                  />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="font-medium mb-0.5 flex items-center gap-2">
                    {{ app.name }}
                    <span
                      v-if="app.tag"
                      class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full"
                      >{{ app.tag }}</span
                    >
                  </div>
                  <div class="text-xs text-gray-500">{{ app.desc }}</div>
                </div>
              </div>
            </ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </span>
  </ElTooltip>
</template>
