<script setup lang="ts">
/**
 * DiagramTemplateInput - Template-based input with fill-in slots
 * Migrated from prototype MindMateChatPage template system
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { ArrowRight, ChevronDown, X } from 'lucide-vue-next'

import { DIAGRAM_TEMPLATES, useUIStore } from '@/stores'

const uiStore = useUIStore()
const router = useRouter()

const chartTypes = [
  '选择图示',
  '圆圈图',
  '气泡图',
  '双气泡图',
  '树形图',
  '括号图',
  '流程图',
  '复流程图',
  '桥型图',
  '思维导图',
]

const selectedType = computed(() => uiStore.selectedChartType)
const templateSlots = computed(() => uiStore.templateSlots)
// freeInputValue reserved for v-model binding in future
const _freeInputValue = computed(() => uiStore.freeInputValue)

const currentTemplate = computed(() => {
  if (selectedType.value === '选择图示') return null
  return DIAGRAM_TEMPLATES[selectedType.value] || null
})

function handleTypeChange(type: string) {
  uiStore.setSelectedChartType(type)
}

function clearType() {
  uiStore.setSelectedChartType('选择图示')
}

function handleFreeInputChange(e: Event) {
  const target = e.target as HTMLElement
  uiStore.setFreeInputValue(target.textContent || '')
}

function handleSlotInput(slotName: string, e: Event) {
  const target = e.target as HTMLElement
  const placeholder = target.getAttribute('data-placeholder')
  const value = target.textContent === placeholder ? '' : target.textContent?.trim() || ''
  uiStore.setTemplateSlot(slotName, value)
}

function handleSlotFocus(e: FocusEvent) {
  const target = e.target as HTMLElement
  const placeholder = target.getAttribute('data-placeholder')
  if (placeholder && target.textContent === placeholder) {
    target.textContent = ''
    target.style.color = '#000'
  }
}

function handleSlotBlur(e: FocusEvent) {
  const target = e.target as HTMLElement
  const placeholder = target.getAttribute('data-placeholder')
  if (placeholder && !target.textContent?.trim()) {
    target.textContent = placeholder
    target.style.color = '#9CA3AF'
  }
}

function handleSubmit() {
  if (!uiStore.hasValidSlots()) return

  // Navigate to canvas with the generated request
  const requestText = uiStore.getTemplateText()
  router.push({
    path: '/canvas',
    query: { type: selectedType.value, prompt: requestText },
  })
}

// Parse template into parts with slots
function parseTemplate(template: string, slots: string[]) {
  const parts: Array<{ type: 'text'; content: string } | { type: 'slot'; name: string }> = []
  let remaining = template

  for (const slot of slots) {
    const marker = `【${slot}】`
    const index = remaining.indexOf(marker)
    if (index > 0) {
      parts.push({ type: 'text', content: remaining.substring(0, index) })
    }
    if (index >= 0) {
      parts.push({ type: 'slot', name: slot })
      remaining = remaining.substring(index + marker.length)
    }
  }

  if (remaining) {
    parts.push({ type: 'text', content: remaining })
  }

  return parts
}

const templateParts = computed(() => {
  if (!currentTemplate.value) return []
  return parseTemplate(currentTemplate.value.template, currentTemplate.value.slots)
})
</script>

<template>
  <div class="diagram-template-input rounded-xl border border-gray-200 p-5 bg-white shadow-sm">
    <!-- Input area -->
    <div class="mb-4">
      <!-- Free input mode -->
      <div
        v-if="selectedType === '选择图示'"
        id="mindgraph-free-input"
        class="w-full min-h-[40px] p-3 text-gray-800 focus:outline-none"
        contenteditable="true"
        data-placeholder="请输入绘图要求..."
        @input="handleFreeInputChange"
      />

      <!-- Template mode -->
      <div
        v-else
        class="flex items-center rounded-lg p-2"
      >
        <!-- Chart type tag -->
        <div class="relative mr-2">
          <span class="bg-blue-50 text-blue-600 px-2 py-1 rounded text-sm">
            {{ selectedType }}
          </span>
          <button
            class="absolute -top-1 -right-1 w-4 h-4 bg-red-100 rounded-full flex items-center justify-center text-red-500 text-xs hover:bg-red-200 transition-colors"
            @click.stop="clearType"
          >
            <X class="w-2.5 h-2.5" />
          </button>
        </div>

        <!-- Template with slots -->
        <div class="flex-1 flex flex-wrap items-center gap-1">
          <template
            v-for="(part, index) in templateParts"
            :key="index"
          >
            <span
              v-if="part.type === 'text'"
              class="text-gray-800"
              >{{ part.content }}</span
            >
            <span
              v-else
              class="inline-block border border-blue-200 rounded px-2 py-1 min-w-[60px] text-center cursor-text"
              contenteditable="true"
              :data-slot="part.name"
              :data-placeholder="part.name"
              :style="{ color: templateSlots[part.name] ? '#000' : '#9CA3AF' }"
              @input="handleSlotInput(part.name, $event)"
              @focus="handleSlotFocus"
              @blur="handleSlotBlur"
            >
              {{ templateSlots[part.name] || part.name }}
            </span>
          </template>
        </div>
      </div>
    </div>

    <!-- Controls -->
    <div class="flex items-center justify-between">
      <!-- Chart type selector -->
      <div class="relative w-1/4">
        <select
          :value="selectedType"
          class="w-full appearance-none bg-white border border-blue-500 rounded-md py-2 pl-3 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
          @change="handleTypeChange(($event.target as HTMLSelectElement).value)"
        >
          <option
            v-for="type in chartTypes"
            :key="type"
            :value="type"
          >
            {{ type }}
          </option>
        </select>
        <div class="absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none">
          <ChevronDown class="w-3.5 h-3.5 text-gray-400" />
        </div>
      </div>

      <!-- Submit button -->
      <button
        class="p-2.5 rounded-full text-white transition-colors"
        :class="
          uiStore.hasValidSlots()
            ? 'bg-blue-600 hover:bg-blue-700'
            : 'bg-gray-300 cursor-not-allowed'
        "
        :disabled="!uiStore.hasValidSlots()"
        @click="handleSubmit"
      >
        <ArrowRight class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>

<style scoped>
[data-placeholder]:empty:before {
  content: attr(data-placeholder);
  color: #9ca3af;
  pointer-events: none;
}

[data-slot]:focus,
#mindgraph-free-input:focus {
  outline: 2px solid #60a5fa;
  outline-offset: 1px;
  color: #000 !important;
}

#mindgraph-free-input:empty:before {
  content: attr(data-placeholder);
  color: #9ca3af;
  pointer-events: none;
}
</style>
