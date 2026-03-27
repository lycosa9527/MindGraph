<script setup lang="ts">
import { ElButton, ElDropdown, ElDropdownMenu } from 'element-plus'

import { Square } from 'lucide-vue-next'

import type { BorderStyleType } from '@/utils/borderStyleUtils'

defineProps<{
  borderMenuLabel: string
  colorLabel: string
  borderWidthLabel: string
  borderStyleLabel: string
  borderColorPalette: string[]
  borderColor: string
  borderWidth: number
  borderStyle: BorderStyleType
  borderStyleOptions: BorderStyleType[]
  getBorderPreviewStyle: (style: BorderStyleType) => Record<string, string>
}>()

const emit = defineEmits<{
  applyBorder: [
    updates: { borderColor?: string; borderWidth?: number; borderStyle?: BorderStyleType },
  ]
}>()
</script>

<template>
  <ElDropdown
    trigger="hover"
    placement="bottom"
  >
    <ElButton
      text
      size="small"
    >
      <Square class="w-4 h-4" />
      <span>{{ borderMenuLabel }}</span>
    </ElButton>
    <template #dropdown>
      <ElDropdownMenu>
        <div class="p-3 w-56">
          <div class="mb-2">
            <label class="text-xs text-gray-500 block mb-1">{{ colorLabel }}:</label>
            <div class="grid grid-cols-5 gap-1">
              <div
                v-for="color in borderColorPalette"
                :key="color"
                class="w-6 h-6 rounded border border-gray-200 cursor-pointer hover:ring-2 hover:ring-blue-400 shrink-0"
                :class="{ 'ring-2 ring-blue-500': borderColor === color }"
                :style="{ backgroundColor: color }"
                @click="emit('applyBorder', { borderColor: color })"
              />
            </div>
          </div>
          <div class="mb-2">
            <label class="text-xs text-gray-500 block mb-1">{{ borderWidthLabel }}:</label>
            <input
              :value="borderWidth"
              type="number"
              min="1"
              max="10"
              class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              @change="
                emit('applyBorder', {
                  borderWidth: Number(($event.target as HTMLInputElement).value),
                })
              "
            />
          </div>
          <div class="mb-2">
            <label class="text-xs text-gray-500 block mb-1.5">{{ borderStyleLabel }}:</label>
            <div class="grid grid-cols-3 gap-1.5">
              <button
                v-for="style in borderStyleOptions"
                :key="style"
                type="button"
                class="border-style-option flex items-center justify-center rounded-md p-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-gray-600"
                :class="{
                  'bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-500': borderStyle === style,
                }"
                @click="emit('applyBorder', { borderStyle: style })"
              >
                <div
                  class="border-preview-pill h-5 w-14"
                  :style="{
                    borderRadius: '9999px',
                    backgroundColor: '#f9fafb',
                    ...getBorderPreviewStyle(style),
                  }"
                />
              </button>
            </div>
          </div>
        </div>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</template>
