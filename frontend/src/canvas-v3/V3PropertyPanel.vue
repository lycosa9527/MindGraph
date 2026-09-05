<script setup lang="ts">
/**
 * V3 bubble-style property dock — text, font, colors, stroke (old editor panel).
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { DiagramNode, NodeStyle } from '@/types'

import './v3Chrome.css'

const { t } = useLanguage()
const diagramStore = useDiagramSession()

const open = ref(true)

const stopPropertyOpen = eventBus.on('panel:open_requested', ({ panel }) => {
  if (panel === 'property') {
    open.value = true
  }
})
onUnmounted(stopPropertyOpen)

const selectedNode = computed(() => {
  if (diagramStore.selectedNodes.length !== 1) return null
  return diagramStore.selectedNodeData[0] ?? null
})

const draft = ref({
  text: '',
  fontFamily: 'Inter, sans-serif',
  fontSize: 14,
  fontWeight: 'normal' as 'normal' | 'bold',
  fontStyle: 'normal' as 'normal' | 'italic',
  underline: false,
  strike: false,
  textColor: '#334155',
  fill: '#ffffff',
  stroke: '#2563eb',
  strokeWidth: 1.5,
})

watch(
  selectedNode,
  (node) => {
    if (!node) return
    open.value = true
    const decoration = node.style?.textDecoration ?? 'none'
    draft.value = {
      text: node.text || '',
      fontFamily: node.style?.fontFamily || 'Inter, sans-serif',
      fontSize: node.style?.fontSize || 14,
      fontWeight: node.style?.fontWeight || 'normal',
      fontStyle: node.style?.fontStyle || 'normal',
      underline: decoration.includes('underline'),
      strike: decoration.includes('line-through'),
      textColor: node.style?.textColor || '#334155',
      fill: node.style?.backgroundColor || '#ffffff',
      stroke: node.style?.borderColor || '#2563eb',
      strokeWidth: node.style?.borderWidth ?? 1.5,
    }
  },
  { immediate: true }
)

function decorationValue(): NodeStyle['textDecoration'] {
  if (draft.value.underline && draft.value.strike) return 'underline line-through'
  if (draft.value.underline) return 'underline'
  if (draft.value.strike) return 'line-through'
  return 'none'
}

function applyStyle(partial: Partial<NodeStyle>): void {
  const node = selectedNode.value
  if (!node) return
  diagramStore.updateNode(node.id, { style: partial })
}

function applyText(): void {
  const node = selectedNode.value
  if (!node) return
  const updates: Partial<DiagramNode> = { text: draft.value.text }
  diagramStore.updateNode(node.id, updates)
}

function resetStyles(): void {
  const node = selectedNode.value
  if (!node) return
  diagramStore.clearNodeStyle(node.id)
}

function toggleBold(): void {
  draft.value.fontWeight = draft.value.fontWeight === 'bold' ? 'normal' : 'bold'
  applyStyle({ fontWeight: draft.value.fontWeight })
}

function toggleItalic(): void {
  draft.value.fontStyle = draft.value.fontStyle === 'italic' ? 'normal' : 'italic'
  applyStyle({ fontStyle: draft.value.fontStyle })
}

function toggleUnderline(): void {
  draft.value.underline = !draft.value.underline
  applyStyle({ textDecoration: decorationValue() })
}

function toggleStrike(): void {
  draft.value.strike = !draft.value.strike
  applyStyle({ textDecoration: decorationValue() })
}

const showPanel = computed(() => open.value && selectedNode.value !== null)
</script>

<template>
  <aside
    v-if="showPanel"
    class="v3-property"
    data-testid="mindmap-v3-property-panel"
  >
    <div class="v3-property__header">
      <span>{{ t('panel.properties') }}</span>
      <button
        type="button"
        class="v3-property__close"
        @click="open = false"
      >
        ×
      </button>
    </div>
    <div class="v3-property__body">
      <div class="v3-property__group">
        <label>{{ t('panels.property.text') }}</label>
        <textarea
          v-model="draft.text"
          rows="3"
        />
        <button
          type="button"
          class="v3-property__apply"
          @click="applyText"
        >
          {{ t('canvas.v3.apply') }}
        </button>
      </div>
      <div class="v3-property__group">
        <label>{{ t('canvas.v3.fontFamily') }}</label>
        <select
          v-model="draft.fontFamily"
          @change="applyStyle({ fontFamily: draft.fontFamily })"
        >
          <option value="'Noto Sans SC', sans-serif">思源黑体</option>
          <option value="Inter, sans-serif">Inter</option>
          <option value="Arial, sans-serif">Arial</option>
          <option value="Georgia, serif">Georgia</option>
        </select>
      </div>
      <div class="v3-property__group">
        <label>{{ t('canvas.v3.fontSize') }}</label>
        <input
          v-model.number="draft.fontSize"
          type="number"
          min="8"
          max="72"
          @change="applyStyle({ fontSize: draft.fontSize })"
        />
      </div>
      <div class="v3-property__group">
        <label>{{ t('canvas.v3.textStyle') }}</label>
        <div class="v3-property__toggles">
          <button
            type="button"
            class="v3-toggle"
            :class="{ 'is-active': draft.fontWeight === 'bold' }"
            @click="toggleBold"
          >
            <strong>B</strong>
          </button>
          <button
            type="button"
            class="v3-toggle"
            :class="{ 'is-active': draft.fontStyle === 'italic' }"
            @click="toggleItalic"
          >
            <em>I</em>
          </button>
          <button
            type="button"
            class="v3-toggle"
            :class="{ 'is-active': draft.underline }"
            @click="toggleUnderline"
          >
            <u>U</u>
          </button>
          <button
            type="button"
            class="v3-toggle"
            :class="{ 'is-active': draft.strike }"
            @click="toggleStrike"
          >
            <s>S</s>
          </button>
        </div>
      </div>
      <div class="v3-property__group">
        <label>{{ t('canvas.toolbar.colorLabel') }}</label>
        <div class="v3-property__colors">
          <label class="v3-color-btn">
            <span>{{ t('canvas.v3.colorText') }}</span>
            <input
              v-model="draft.textColor"
              type="color"
              @change="applyStyle({ textColor: draft.textColor })"
            />
          </label>
          <label class="v3-color-btn">
            <span>{{ t('canvas.v3.colorFill') }}</span>
            <input
              v-model="draft.fill"
              type="color"
              @change="applyStyle({ backgroundColor: draft.fill })"
            />
          </label>
          <label class="v3-color-btn">
            <span>{{ t('canvas.v3.colorStroke') }}</span>
            <input
              v-model="draft.stroke"
              type="color"
              @change="applyStyle({ borderColor: draft.stroke })"
            />
          </label>
        </div>
      </div>
      <div class="v3-property__group">
        <label>{{ t('panels.property.borderWidth') }}</label>
        <input
          v-model.number="draft.strokeWidth"
          type="range"
          min="0"
          max="10"
          step="0.5"
          @change="applyStyle({ borderWidth: draft.strokeWidth })"
        />
      </div>
      <button
        type="button"
        class="v3-property__reset"
        @click="resetStyles"
      >
        {{ t('canvas.v3.resetStyles') }}
      </button>
    </div>
  </aside>
</template>
