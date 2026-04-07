<script setup lang="ts">
import { ElButton, ElDropdown, ElDropdownMenu, ElTooltip } from 'element-plus'

import { AlignCenter, AlignLeft, AlignRight, Sigma, Type } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    compact?: boolean
    textStyleMenuLabel: string
    formatLabel: string
    alignLabel: string
    fontLabel: string
    fontGroupChinese: string
    fontGroupEnglish: string
    colorLabel: string
    insertEquationLabel: string
    insertEquationTooltip: string
    insertEquationEnabled: boolean
    fontFamily: string
    fontSize: number
    fontWeight: 'normal' | 'bold'
    fontStyle: 'normal' | 'italic'
    textDecoration: string
    textAlign: 'left' | 'center' | 'right'
    textColor: string
    textColorPalette: string[]
  }>(),
  { compact: false }
)

const emit = defineEmits<{
  toggleBold: []
  toggleItalic: []
  toggleUnderline: []
  toggleStrikethrough: []
  setTextAlign: [align: 'left' | 'center' | 'right']
  fontFamilyChange: [ev: Event]
  fontSizeInput: [ev: Event]
  textColorPick: [color: string]
  openMathInsert: []
}>()
</script>

<template>
  <ElTooltip
    :content="textStyleMenuLabel"
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
          <Type class="w-4 h-4" />
          <span v-if="!compact">{{ textStyleMenuLabel }}</span>
        </ElButton>
        <template #dropdown>
          <ElDropdownMenu>
            <div class="p-2.5 w-48 text-style-dropdown">
              <div class="mb-2">
                <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                  {{ formatLabel }}
                </div>
                <div class="grid grid-cols-4 gap-1.5">
                  <button
                    type="button"
                    class="format-btn min-w-[1.75rem] h-7 rounded border text-sm font-bold transition-all"
                    :class="[
                      fontWeight === 'bold'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                    ]"
                    @click="emit('toggleBold')"
                  >
                    B
                  </button>
                  <button
                    type="button"
                    class="format-btn min-w-[1.75rem] h-7 rounded border italic text-sm transition-all"
                    :class="[
                      fontStyle === 'italic'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                    ]"
                    @click="emit('toggleItalic')"
                  >
                    I
                  </button>
                  <button
                    type="button"
                    class="format-btn min-w-[1.75rem] h-7 rounded border underline text-sm transition-all"
                    :class="[
                      textDecoration?.includes('underline')
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                    ]"
                    @click="emit('toggleUnderline')"
                  >
                    U
                  </button>
                  <button
                    type="button"
                    class="format-btn min-w-[1.75rem] h-7 rounded border line-through text-sm transition-all"
                    :class="[
                      textDecoration?.includes('line-through')
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                    ]"
                    @click="emit('toggleStrikethrough')"
                  >
                    S
                  </button>
                </div>
                <div class="mt-2">
                  <ElTooltip
                    :content="insertEquationTooltip"
                    placement="right"
                    :disabled="!insertEquationEnabled"
                  >
                    <span class="block w-full">
                      <button
                        type="button"
                        class="format-btn w-full h-8 rounded border text-xs flex items-center justify-center gap-1 transition-all"
                        :class="[
                          insertEquationEnabled
                            ? 'border-gray-200 bg-gray-50 text-gray-700 hover:border-gray-300 hover:bg-gray-100'
                            : 'border-gray-100 bg-gray-50/50 text-gray-400 cursor-not-allowed',
                        ]"
                        :disabled="!insertEquationEnabled"
                        @click="emit('openMathInsert')"
                      >
                        <Sigma :size="14" />
                        {{ insertEquationLabel }}
                      </button>
                    </span>
                  </ElTooltip>
                </div>
                <div
                  class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mt-2 mb-1.5"
                >
                  {{ alignLabel }}
                </div>
                <div class="grid grid-cols-3 gap-1.5">
                  <button
                    type="button"
                    class="format-btn min-w-[1.75rem] h-7 rounded border text-sm transition-all flex items-center justify-center"
                    :class="[
                      textAlign === 'left'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                    ]"
                    @click="emit('setTextAlign', 'left')"
                  >
                    <AlignLeft :size="14" />
                  </button>
                  <button
                    type="button"
                    class="format-btn min-w-[1.75rem] h-7 rounded border text-sm transition-all flex items-center justify-center"
                    :class="[
                      textAlign === 'center'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                    ]"
                    @click="emit('setTextAlign', 'center')"
                  >
                    <AlignCenter :size="14" />
                  </button>
                  <button
                    type="button"
                    class="format-btn min-w-[1.75rem] h-7 rounded border text-sm transition-all flex items-center justify-center"
                    :class="[
                      textAlign === 'right'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100',
                    ]"
                    @click="emit('setTextAlign', 'right')"
                  >
                    <AlignRight :size="14" />
                  </button>
                </div>
              </div>

              <div class="border-t border-gray-100 my-2" />

              <div class="mb-2">
                <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                  {{ fontLabel }}
                </div>
                <div class="grid grid-cols-2 gap-1.5">
                  <select
                    :value="fontFamily"
                    class="w-full border border-gray-200 rounded py-1.5 px-2 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500/40 focus:border-blue-400"
                    @change="emit('fontFamilyChange', $event)"
                  >
                    <optgroup :label="fontGroupChinese">
                      <option value="Microsoft YaHei">微软雅黑</option>
                      <option value="SimSun">宋体</option>
                      <option value="SimHei">黑体</option>
                      <option value="KaiTi">楷体</option>
                      <option value="FangSong">仿宋</option>
                    </optgroup>
                    <optgroup :label="fontGroupEnglish">
                      <option value="Arial">Arial</option>
                      <option value="Inter">Inter</option>
                      <option value="Georgia">Georgia</option>
                      <option value="Courier New">Courier New</option>
                    </optgroup>
                  </select>
                  <input
                    :value="fontSize"
                    type="number"
                    min="8"
                    max="72"
                    class="w-full border border-gray-200 rounded py-1.5 px-2 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500/40 focus:border-blue-400"
                    @input="emit('fontSizeInput', $event)"
                  />
                </div>
              </div>

              <div class="border-t border-gray-100 my-2" />

              <div>
                <div class="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1.5">
                  {{ colorLabel }}
                </div>
                <div class="grid grid-cols-6 gap-1">
                  <div
                    v-for="color in textColorPalette"
                    :key="color"
                    class="w-5 h-5 rounded border cursor-pointer transition-all hover:scale-105"
                    :class="[
                      textColor === color
                        ? 'border-blue-500 ring-1 ring-blue-200'
                        : 'border-gray-200 hover:border-gray-300',
                    ]"
                    :style="{ backgroundColor: color }"
                    @click="emit('textColorPick', color)"
                  />
                </div>
              </div>
            </div>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </span>
  </ElTooltip>
</template>

<style scoped>
.text-style-dropdown .format-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
