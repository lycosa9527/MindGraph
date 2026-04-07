<script setup lang="ts">
import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElTooltip } from 'element-plus'

import { Brush, PenLine } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import type { StylePresetColors } from '@/config/colorPalette'

const { t } = useLanguage()

withDefaults(
  defineProps<{
    compact?: boolean
    styleMenuLabel: string
    presetsLabel: string
    wireframeLabel: string
    wireframeMode: boolean
    stylePresets: Array<
      {
        nameKey: string
        bgClass: string
        borderClass: string
      } & StylePresetColors
    >
  }>(),
  { compact: false }
)

const emit = defineEmits<{
  applyPreset: [preset: StylePresetColors]
  toggleWireframe: []
}>()
</script>

<template>
  <ElTooltip
    :content="styleMenuLabel"
    placement="bottom"
    :disabled="!compact"
  >
    <span class="inline-flex">
      <ElDropdown
        trigger="hover"
        placement="bottom"
      >
        <ElButton
          text
          size="small"
        >
          <Brush class="w-4 h-4" />
          <span v-if="!compact">{{ styleMenuLabel }}</span>
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <div class="p-3 w-48">
              <div class="text-xs font-medium text-gray-500 mb-2">
                {{ presetsLabel }}
              </div>
              <div class="grid grid-cols-2 gap-2">
                <ElDropdownItem
                  v-for="preset in stylePresets"
                  :key="preset.nameKey"
                  class="p-2! rounded border text-xs text-center"
                  :class="[preset.bgClass, preset.borderClass]"
                  @click="emit('applyPreset', preset)"
                >
                  {{ t(preset.nameKey) }}
                </ElDropdownItem>
              </div>
              <div class="border-t border-gray-200 my-2" />
              <ElDropdownItem
                :class="{ 'bg-blue-50': wireframeMode }"
                @click="emit('toggleWireframe')"
              >
                <PenLine class="w-3 h-3 mr-2 text-gray-500" />
                {{ wireframeLabel }}
              </ElDropdownItem>
            </div>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </span>
  </ElTooltip>
</template>
