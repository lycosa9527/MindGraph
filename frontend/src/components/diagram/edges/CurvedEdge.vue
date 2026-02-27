<script setup lang="ts">
/**
 * CurvedEdge - Curved connection edge for mind maps, tree maps, and concept maps
 * Uses bezier curves for smooth connections
 * Concept map: relationship labels are editable on double-click
 */
import { computed, inject, nextTick, ref, watch } from 'vue'

import { EdgeLabelRenderer, type EdgeProps, getBezierPath } from '@vue-flow/core'

import { CONCEPT_MAP_GENERATING_KEY } from '@/composables/useConceptMapRelationship'
import { eventBus } from '@/composables/useEventBus'
import { useLanguage } from '@/composables/useLanguage'
import { useTheme } from '@/composables/useTheme'
import { useDiagramStore } from '@/stores'
import type { DiagramType, MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

const generatingConnectionIds = inject<{ value: Set<string> }>(
  CONCEPT_MAP_GENERATING_KEY,
  ref(new Set<string>())
)

const diagramStore = useDiagramStore()
const { t } = useLanguage()


const relationshipPlaceholder = computed(() =>
  t('diagram.relationshipPlaceholder', '输入关系...')
)

const isConceptMap = computed(
  () => (props.data?.diagramType as DiagramType) === 'concept_map'
)

const { theme } = useTheme({
  diagramType: computed(() => props.data?.diagramType as DiagramType),
})

const relationshipColor = computed(() => {
  if (!isConceptMap.value) return undefined
  return theme.value?.relationshipColor || '#666666'
})

const isEditing = ref(false)
const editText = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.data?.label,
  (val) => {
    editText.value = val || ''
  },
  { immediate: true }
)

function startEditing() {
  if (!isConceptMap.value) return
  isEditing.value = true
  editText.value = props.data?.label || ''
  nextTick(() => inputRef.value?.focus())
}

function saveLabel() {
  if (!isConceptMap.value) return
  isEditing.value = false
  const trimmed = editText.value.trim()
  if (trimmed !== (props.data?.label || '')) {
    diagramStore.updateConnectionLabel(props.id, trimmed)
    diagramStore.pushHistory('Update relationship')
    if (trimmed === '') {
      eventBus.emit('concept_map:label_cleared', {
        connectionId: props.id,
        sourceId: props.source,
        targetId: props.target,
      })
    }
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    saveLabel()
  }
  if (event.key === 'Escape') {
    isEditing.value = false
    editText.value = props.data?.label || ''
  }
}

// Calculate bezier path
const path = computed(() => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
    curvature: 0.25,
  })
  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#94a3b8',
  strokeWidth: props.data?.style?.strokeWidth || 2,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))

const isGenerating = computed(() =>
  isConceptMap.value && generatingConnectionIds.value.has(props.id)
)
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path curved-edge"
    :d="path.edgePath"
    :style="edgeStyle"
    :marker-end="markerEnd"
  />

  <!-- Edge label: concept map = editable, others = static box -->
  <EdgeLabelRenderer v-if="data?.label !== undefined">
    <div
      class="edge-label absolute"
      :class="{
        'edge-label-concept-map': isConceptMap,
        'edge-label-box': !isConceptMap,
        'pointer-events-none': !isConceptMap,
        'nopan': isConceptMap,
        'cursor-text': isConceptMap && !isEditing,
      }"
      :style="{
        transform: `translate(-50%, -50%) translate(${path.labelX}px, ${path.labelY}px)`,
        color: isConceptMap ? relationshipColor : undefined,
        pointerEvents: isConceptMap ? 'auto' : undefined,
      }"
      @dblclick.stop="startEditing"
    >
      <input
        v-if="isConceptMap && isEditing"
        ref="inputRef"
        v-model="editText"
        type="text"
        class="edge-label-input"
        :placeholder="relationshipPlaceholder"
        @blur="saveLabel"
        @keydown="handleKeydown"
      />
      <span
        v-else
        :class="{ 'edge-label-placeholder': isConceptMap && !(data?.label?.trim()) && !isGenerating }"
      >
        {{
          isGenerating
            ? (t('diagram.aiGenerating', 'AI...') as string)
            : isConceptMap && !(data?.label?.trim())
              ? relationshipPlaceholder
              : (data?.label || '')
        }}
      </span>
    </div>
  </EdgeLabelRenderer>
</template>

<style scoped>
.curved-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.curved-edge:hover {
  stroke: #64748b;
}

.edge-label {
  font-size: 11px;
  white-space: nowrap;
}

.edge-label-box {
  background-color: white;
  padding: 4px 8px;
  border-radius: 4px;
  color: #4b5563;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.edge-label-placeholder {
  color: #9ca3af;
}

.dark .edge-label-placeholder {
  color: #6b7280;
}

.edge-label-concept-map {
  background: #f5f5f5;
  padding: 4px 8px;
  min-width: 28px;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  border-radius: 2px;
}

.dark .edge-label-concept-map {
  background: #1f2937;
}

.edge-label-input {
  width: 60px;
  min-width: 40px;
  max-width: 100px;
  padding: 2px 4px;
  font-size: 11px;
  border: 1px solid #94a3b8;
  border-radius: 2px;
  background: white;
  color: #333;
  outline: none;
}

.dark .edge-label-input {
  background: #374151;
  border-color: #6b7280;
  color: #e5e7eb;
}
</style>
