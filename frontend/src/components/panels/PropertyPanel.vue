<script setup lang="ts">
/**
 * Property Panel - Node property editor
 */
import { computed, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { useDiagramStore } from '@/stores'
import type { DiagramNode } from '@/types'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const diagramStore = useDiagramStore()
const { t, isZh } = useLanguage()
const notify = useNotifications()

// Local form state
const formData = ref({
  text: '',
  fontSize: 14,
  fontWeight: 'normal' as 'normal' | 'bold',
  backgroundColor: '#ffffff',
  borderColor: '#409eff',
  textColor: '#303133',
  borderWidth: 2,
  borderRadius: 8,
})

// Selected node
const selectedNode = computed(() => {
  if (diagramStore.selectedNodes.length !== 1) return null
  return diagramStore.selectedNodeData[0] || null
})

const isMultiSelect = computed(() => diagramStore.selectedNodes.length > 1)

// Watch selected node and update form
watch(
  () => selectedNode.value,
  (node) => {
    if (node) {
      formData.value = {
        text: node.text || '',
        fontSize: node.style?.fontSize || 14,
        fontWeight: node.style?.fontWeight || 'normal',
        backgroundColor: node.style?.backgroundColor || '#ffffff',
        borderColor: node.style?.borderColor || '#409eff',
        textColor: node.style?.textColor || '#303133',
        borderWidth: node.style?.borderWidth || 2,
        borderRadius: node.style?.borderRadius || 8,
      }
    }
  },
  { immediate: true }
)

// Apply changes
function applyChanges() {
  if (!selectedNode.value) return

  const updates: Partial<DiagramNode> = {
    text: formData.value.text,
    style: {
      fontSize: formData.value.fontSize,
      fontWeight: formData.value.fontWeight,
      backgroundColor: formData.value.backgroundColor,
      borderColor: formData.value.borderColor,
      textColor: formData.value.textColor,
      borderWidth: formData.value.borderWidth,
      borderRadius: formData.value.borderRadius,
    },
  }

  diagramStore.pushHistory('Update node properties')
  diagramStore.updateNode(selectedNode.value.id, updates)
  notify.success(t('notification.saved'))
}

// Delete node
function deleteNode() {
  if (!selectedNode.value) return

  diagramStore.pushHistory('Delete node')
  diagramStore.removeNode(selectedNode.value.id)
  notify.success(t('notification.deleted'))
}

// Font weight options
const fontWeightOptions = [
  { label: isZh.value ? '正常' : 'Normal', value: 'normal' },
  { label: isZh.value ? '粗体' : 'Bold', value: 'bold' },
]
</script>

<template>
  <div
    class="property-panel bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-lg flex flex-col"
  >
    <!-- Header -->
    <div
      class="panel-header h-12 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700"
    >
      <h3 class="font-medium text-gray-800 dark:text-white">
        {{ t('panel.properties') }}
      </h3>
      <el-button
        text
        circle
        @click="emit('close')"
      >
        <el-icon><Close /></el-icon>
      </el-button>
    </div>

    <!-- Content -->
    <div class="panel-content flex-1 overflow-y-auto p-4">
      <!-- Multi-select message -->
      <div
        v-if="isMultiSelect"
        class="text-center py-8 text-gray-500"
      >
        <el-icon
          :size="32"
          class="mb-2"
          ><InfoFilled
        /></el-icon>
        <p>
          {{ diagramStore.selectedNodes.length }} {{ isZh ? '个节点已选择' : 'nodes selected' }}
        </p>
        <p class="text-sm mt-1">
          {{ isZh ? '选择单个节点以编辑属性' : 'Select a single node to edit properties' }}
        </p>
      </div>

      <!-- Property form -->
      <el-form
        v-else-if="selectedNode"
        label-position="top"
        size="small"
      >
        <!-- Text -->
        <el-form-item :label="isZh ? '文本' : 'Text'">
          <el-input
            v-model="formData.text"
            type="textarea"
            :rows="3"
            :placeholder="isZh ? '节点文本' : 'Node text'"
          />
        </el-form-item>

        <!-- Font Size -->
        <el-form-item :label="isZh ? '字体大小' : 'Font Size'">
          <el-slider
            v-model="formData.fontSize"
            :min="10"
            :max="32"
            :step="1"
            show-input
            input-size="small"
          />
        </el-form-item>

        <!-- Font Weight -->
        <el-form-item :label="isZh ? '字体粗细' : 'Font Weight'">
          <el-radio-group v-model="formData.fontWeight">
            <el-radio-button
              v-for="opt in fontWeightOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- Colors -->
        <div class="grid grid-cols-3 gap-3">
          <el-form-item :label="isZh ? '背景色' : 'Background'">
            <el-color-picker v-model="formData.backgroundColor" />
          </el-form-item>
          <el-form-item :label="isZh ? '边框色' : 'Border'">
            <el-color-picker v-model="formData.borderColor" />
          </el-form-item>
          <el-form-item :label="isZh ? '文字色' : 'Text'">
            <el-color-picker v-model="formData.textColor" />
          </el-form-item>
        </div>

        <!-- Border Width -->
        <el-form-item :label="isZh ? '边框宽度' : 'Border Width'">
          <el-slider
            v-model="formData.borderWidth"
            :min="0"
            :max="8"
            :step="1"
            show-input
            input-size="small"
          />
        </el-form-item>

        <!-- Border Radius -->
        <el-form-item :label="isZh ? '圆角' : 'Border Radius'">
          <el-slider
            v-model="formData.borderRadius"
            :min="0"
            :max="50"
            :step="2"
            show-input
            input-size="small"
          />
        </el-form-item>

        <!-- Actions -->
        <div class="flex gap-2 mt-6">
          <el-button
            type="primary"
            class="flex-1"
            @click="applyChanges"
          >
            {{ t('common.save') }}
          </el-button>
          <el-button
            type="danger"
            @click="deleteNode"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </el-form>

      <!-- No selection -->
      <div
        v-else
        class="text-center py-8 text-gray-500"
      >
        <el-icon
          :size="32"
          class="mb-2"
          ><Select
        /></el-icon>
        <p>{{ isZh ? '选择一个节点以编辑属性' : 'Select a node to edit properties' }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.property-panel {
  height: 100%;
}
</style>
