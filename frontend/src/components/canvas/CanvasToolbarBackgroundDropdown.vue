<script setup lang="ts">
import { ElButton, ElDropdown, ElDropdownMenu } from 'element-plus'

import { Image as ImageIcon } from 'lucide-vue-next'

defineProps<{
  bgMenuLabel: string
  bgColorLabel: string
  opacityLabel: string
  backgroundColors: string[]
  backgroundOpacity: number
}>()

const emit = defineEmits<{
  pickColor: [color: string]
  'update:backgroundOpacity': [opacity: number]
  applyBackground: []
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
      <ImageIcon class="w-4 h-4" />
      <span>{{ bgMenuLabel }}</span>
    </ElButton>
    <template #dropdown>
      <ElDropdownMenu>
        <div class="p-3 w-56">
          <div class="mb-3">
            <label class="text-xs text-gray-500 block mb-1">{{ bgColorLabel }}:</label>
            <div class="grid grid-cols-5 gap-1">
              <div
                v-for="color in backgroundColors"
                :key="color"
                class="w-6 h-6 rounded border border-gray-200 cursor-pointer hover:ring-2 hover:ring-blue-400 shrink-0"
                :style="{ backgroundColor: color }"
                @click="emit('pickColor', color)"
              />
            </div>
          </div>
          <div class="mb-2">
            <label class="text-xs text-gray-500 block mb-1">{{ opacityLabel }}:</label>
            <input
              :value="backgroundOpacity"
              type="range"
              min="0"
              max="100"
              class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
              @input="
                emit('update:backgroundOpacity', Number(($event.target as HTMLInputElement).value))
              "
              @change="emit('applyBackground')"
            />
            <div class="flex justify-between text-xs text-gray-500 mt-1">
              <span>0%</span>
              <span>100%</span>
            </div>
          </div>
        </div>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</template>
