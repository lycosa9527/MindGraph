<script setup lang="ts">
/**
 * DiagramSlotFullModal - Modal shown when diagram slots are full
 * Allows user to delete an existing diagram to make space for saving
 *
 * Design: Swiss Design style matching other modals in the app
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElRadio, ElRadioGroup } from 'element-plus'

import { AlertTriangle, Loader2, Trash2 } from 'lucide-vue-next'

import { useNotifications } from '@/composables'
import { useLanguage } from '@/composables'
import { useSavedDiagramsStore } from '@/stores'

const notify = useNotifications()

const props = defineProps<{
  visible: boolean
  /** Title of the diagram to save */
  pendingTitle: string
  /** Type of the diagram to save */
  pendingDiagramType: string
  /** Spec of the diagram to save */
  pendingSpec: Record<string, unknown>
  /** Language of the diagram */
  pendingLanguage?: string
  /** Thumbnail of the diagram */
  pendingThumbnail?: string | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success', diagramId: string): void
  (e: 'cancel'): void
}>()

const savedDiagramsStore = useSavedDiagramsStore()
const { isZh } = useLanguage()

// State - use empty string instead of null for ElRadioGroup compatibility
const selectedDiagramId = ref<string>('')
const isDeleting = ref(false)

// Computed
const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const diagrams = computed(() => savedDiagramsStore.diagrams)
const maxDiagrams = computed(() => savedDiagramsStore.maxDiagrams)

// Watch for visibility changes to reset state
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      selectedDiagramId.value = ''
      isDeleting.value = false
      // Fetch latest diagrams
      savedDiagramsStore.fetchDiagrams()
    }
  }
)

// Get diagram type display name
function getDiagramTypeName(type: string): string {
  const typeMap: Record<string, string> = {
    circle_map: isZh.value ? '圆圈图' : 'Circle Map',
    bubble_map: isZh.value ? '气泡图' : 'Bubble Map',
    double_bubble_map: isZh.value ? '双气泡图' : 'Double Bubble',
    tree_map: isZh.value ? '树形图' : 'Tree Map',
    brace_map: isZh.value ? '括号图' : 'Brace Map',
    flow_map: isZh.value ? '流程图' : 'Flow Map',
    multi_flow_map: isZh.value ? '复流程图' : 'Multi-Flow Map',
    bridge_map: isZh.value ? '桥形图' : 'Bridge Map',
    mindmap: isZh.value ? '思维导图' : 'Mind Map',
    mind_map: isZh.value ? '思维导图' : 'Mind Map',
    concept_map: isZh.value ? '概念图' : 'Concept Map',
  }
  return typeMap[type] || type
}

// Format date
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return isZh.value ? '今天' : 'Today'
  } else if (diffDays === 1) {
    return isZh.value ? '昨天' : 'Yesterday'
  } else if (diffDays < 7) {
    return isZh.value ? `${diffDays}天前` : `${diffDays} days ago`
  } else {
    return date.toLocaleDateString(isZh.value ? 'zh-CN' : 'en-US', {
      month: 'short',
      day: 'numeric',
    })
  }
}

// Close modal
function closeModal(): void {
  isVisible.value = false
  emit('cancel')
}

// Handle delete and save
async function handleDeleteAndSave(): Promise<void> {
  if (!selectedDiagramId.value) {
    notify.warning(isZh.value ? '请选择要删除的图示' : 'Please select a diagram to delete')
    return
  }

  isDeleting.value = true

  try {
    const result = await savedDiagramsStore.deleteAndSave(
      selectedDiagramId.value,
      props.pendingTitle,
      props.pendingDiagramType,
      props.pendingSpec,
      props.pendingLanguage || 'zh',
      props.pendingThumbnail || null
    )

    if (result.success && result.diagramId) {
      notify.success(isZh.value ? '图示保存成功' : 'Diagram saved successfully')
      isVisible.value = false
      emit('success', result.diagramId)
    } else {
      notify.error(result.error || (isZh.value ? '保存失败' : 'Save failed'))
    }
  } catch (error) {
    console.error('Delete and save error:', error)
    notify.error(isZh.value ? '网络错误，操作失败' : 'Network error, operation failed')
  } finally {
    isDeleting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="isVisible"
        class="modal-overlay"
        @click.self="closeModal"
      >
        <div class="modal-container">
          <!-- Header -->
          <div class="modal-header">
            <div class="header-icon">
              <AlertTriangle class="w-6 h-6 text-amber-500" />
            </div>
            <h2 class="modal-title">
              {{ isZh ? '图库已满' : 'Gallery Full' }}
            </h2>
            <p class="modal-subtitle">
              {{
                isZh
                  ? `您已保存 ${maxDiagrams} 个图示，请删除一个以保存新图示`
                  : `You have ${maxDiagrams} saved diagrams. Delete one to save new diagram`
              }}
            </p>
          </div>

          <!-- Diagram list -->
          <div class="diagram-list">
            <ElRadioGroup
              v-model="selectedDiagramId"
              class="w-full"
            >
              <div
                v-for="diagram in diagrams"
                :key="diagram.id"
                class="diagram-item"
                :class="{ 'is-selected': selectedDiagramId === diagram.id }"
                @click="selectedDiagramId = diagram.id"
              >
                <ElRadio
                  :value="diagram.id"
                  class="diagram-radio"
                >
                  <div class="diagram-content">
                    <!-- Thumbnail -->
                    <div class="diagram-thumbnail">
                      <img
                        v-if="diagram.thumbnail"
                        :src="diagram.thumbnail"
                        :alt="diagram.title"
                        class="thumbnail-image"
                      />
                      <div
                        v-else
                        class="thumbnail-placeholder"
                      >
                        <span class="text-stone-400 text-xs">
                          {{ getDiagramTypeName(diagram.diagram_type).charAt(0) }}
                        </span>
                      </div>
                    </div>

                    <!-- Info -->
                    <div class="diagram-info">
                      <div class="diagram-title">{{ diagram.title }}</div>
                      <div class="diagram-meta">
                        <span class="diagram-type">{{
                          getDiagramTypeName(diagram.diagram_type)
                        }}</span>
                        <span class="meta-dot" />
                        <span class="diagram-date">{{ formatDate(diagram.updated_at) }}</span>
                      </div>
                    </div>
                  </div>
                </ElRadio>
              </div>
            </ElRadioGroup>
          </div>

          <!-- Footer -->
          <div class="modal-footer">
            <ElButton
              class="cancel-btn"
              @click="closeModal"
            >
              {{ isZh ? '取消' : 'Cancel' }}
            </ElButton>
            <ElButton
              type="danger"
              class="delete-btn"
              :disabled="!selectedDiagramId || isDeleting"
              @click="handleDeleteAndSave"
            >
              <Loader2
                v-if="isDeleting"
                class="w-4 h-4 mr-2 animate-spin"
              />
              <Trash2
                v-else
                class="w-4 h-4 mr-2"
              />
              {{ isZh ? '删除并保存' : 'Delete & Save' }}
            </ElButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.modal-container {
  background: white;
  border-radius: 16px;
  width: 100%;
  max-width: 480px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.modal-header {
  padding: 24px 24px 16px;
  text-align: center;
  border-bottom: 1px solid #e7e5e4;
}

.header-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 12px;
  background: #fef3c7;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  color: #1c1917;
  margin: 0 0 8px;
}

.modal-subtitle {
  font-size: 14px;
  color: #78716c;
  margin: 0;
}

.diagram-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  max-height: 400px;
}

.diagram-item {
  padding: 12px;
  border: 2px solid transparent;
  border-radius: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fafaf9;
}

.diagram-item:hover {
  background: #f5f5f4;
  border-color: #d6d3d1;
}

.diagram-item.is-selected {
  background: #fef2f2;
  border-color: #ef4444;
}

.diagram-radio {
  width: 100%;
  display: flex;
  align-items: center;
}

.diagram-radio :deep(.el-radio__label) {
  flex: 1;
  padding-left: 12px;
}

.diagram-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.diagram-thumbnail {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: #e7e5e4;
}

.thumbnail-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  color: #a8a29e;
}

.diagram-info {
  flex: 1;
  min-width: 0;
}

.diagram-title {
  font-size: 14px;
  font-weight: 500;
  color: #1c1917;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.diagram-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #78716c;
}

.meta-dot {
  width: 3px;
  height: 3px;
  background: #a8a29e;
  border-radius: 50%;
}

.diagram-type {
  color: #57534e;
}

.diagram-date {
  color: #a8a29e;
}

.modal-footer {
  padding: 16px 24px 24px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid #e7e5e4;
}

.cancel-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
}

.delete-btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  display: flex;
  align-items: center;
}

/* Transition animations */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-active .modal-container,
.modal-fade-leave-active .modal-container {
  transition:
    transform 0.2s ease,
    opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .modal-container,
.modal-fade-leave-to .modal-container {
  transform: scale(0.95);
  opacity: 0;
}
</style>
