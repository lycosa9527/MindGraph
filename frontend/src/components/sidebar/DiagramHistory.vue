<script setup lang="ts">
/**
 * DiagramHistory - Grouped list of saved diagrams
 * Design: Clean minimalist grouped by time periods
 * Shows max 20 items with "More" option
 */
import { computed, onMounted, ref, watch } from 'vue'

import {
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElMessageBox,
  ElScrollbar,
} from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { Edit3, FileImage, Lock, MoreHorizontal, Pin, Trash2 } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

const props = defineProps<{
  isBlurred?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', diagram: SavedDiagram): void
}>()

const { isZh } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()

// Show all or just 10
const showAll = ref(false)
const INITIAL_LIMIT = 10

// Computed
const diagrams = computed(() => savedDiagramsStore.diagrams)
const isLoading = computed(() => savedDiagramsStore.isLoading)
const currentDiagramId = computed(() => savedDiagramsStore.currentDiagramId)
const maxDiagrams = computed(() => savedDiagramsStore.maxDiagrams)
const _remainingSlots = computed(() => savedDiagramsStore.remainingSlots)

// Group diagrams by time period with pinned at top
interface GroupedDiagrams {
  pinned: SavedDiagram[]
  today: SavedDiagram[]
  yesterday: SavedDiagram[]
  week: SavedDiagram[]
  month: SavedDiagram[]
}

const groupedDiagrams = computed((): GroupedDiagrams => {
  const groups: GroupedDiagrams = {
    pinned: [],
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  // Limit unless showAll
  const items = showAll.value ? diagrams.value : diagrams.value.slice(0, INITIAL_LIMIT)

  items.forEach((diagram) => {
    // Pinned items go to the top group
    if (diagram.is_pinned) {
      groups.pinned.push(diagram)
      return
    }

    const diagramTime = new Date(diagram.updated_at).getTime()

    if (diagramTime >= todayStart) {
      groups.today.push(diagram)
    } else if (diagramTime >= yesterdayStart) {
      groups.yesterday.push(diagram)
    } else if (diagramTime >= weekStart) {
      groups.week.push(diagram)
    } else {
      // Everything older goes to Past Month
      groups.month.push(diagram)
    }
  })

  return groups
})

// Check if there are more diagrams to show
const hasMore = computed(() => diagrams.value.length > INITIAL_LIMIT && !showAll.value)
const remainingCount = computed(() => diagrams.value.length - INITIAL_LIMIT)

// Group labels
const groupLabels = computed(() => ({
  pinned: isZh.value ? '置顶' : 'Pinned',
  today: isZh.value ? '今天' : 'Today',
  yesterday: isZh.value ? '昨天' : 'Yesterday',
  week: isZh.value ? '上周' : 'Past Week',
  month: isZh.value ? '上月' : 'Past Month',
}))

// Diagram type labels
const diagramTypeLabels: Record<string, { zh: string; en: string }> = {
  mind_map: { zh: '思维导图', en: 'Mind Map' },
  mindmap: { zh: '思维导图', en: 'Mind Map' },
  concept_map: { zh: '概念图', en: 'Concept Map' },
  bubble_map: { zh: '气泡图', en: 'Bubble Map' },
  double_bubble_map: { zh: '双气泡图', en: 'Double Bubble Map' },
  tree_map: { zh: '树形图', en: 'Tree Map' },
  circle_map: { zh: '圆圈图', en: 'Circle Map' },
  flow_map: { zh: '流程图', en: 'Flow Map' },
  brace_map: { zh: '括号图', en: 'Brace Map' },
  multi_flow_map: { zh: '复流图', en: 'Multi-flow Map' },
  bridge_map: { zh: '桥形图', en: 'Bridge Map' },
}

function getDiagramTypeLabel(type: string): string {
  const labels = diagramTypeLabels[type]
  if (labels) {
    return isZh.value ? labels.zh : labels.en
  }
  return type
}

// Fetch diagrams on mount if authenticated
onMounted(() => {
  if (authStore.isAuthenticated && !props.isBlurred) {
    savedDiagramsStore.fetchDiagrams()
  }
})

// Re-fetch when authentication changes
watch(
  () => authStore.isAuthenticated,
  (isAuth) => {
    if (isAuth) {
      savedDiagramsStore.fetchDiagrams()
    } else {
      savedDiagramsStore.reset()
    }
  }
)

// Handle diagram click
function handleDiagramClick(diagram: SavedDiagram): void {
  savedDiagramsStore.setCurrentDiagram(diagram.id)
  emit('select', diagram)
}

// Handle rename diagram
async function handleRenameDiagram(diagramId: string): Promise<void> {
  const diagram = diagrams.value.find((d) => d.id === diagramId)
  const currentName = diagram?.title || ''

  try {
    const result = await ElMessageBox.prompt(
      isZh.value ? '请输入新的图示名称' : 'Enter a new name for this diagram',
      isZh.value ? '重命名图示' : 'Rename Diagram',
      {
        confirmButtonText: isZh.value ? '确定' : 'OK',
        cancelButtonText: isZh.value ? '取消' : 'Cancel',
        inputValue: currentName,
        inputPattern: /\S+/,
        inputErrorMessage: isZh.value ? '名称不能为空' : 'Name cannot be empty',
      }
    )

    const value =
      typeof result === 'object' && result !== null && 'value' in result
        ? (result as { value: string }).value
        : undefined
    if (value && value.trim() !== currentName) {
      await savedDiagramsStore.updateDiagram(diagramId, { title: value.trim() })
    }
  } catch {
    // User cancelled
  }
}

// Handle delete diagram - delete immediately
async function handleDeleteDiagram(diagramId: string): Promise<void> {
  try {
    const success = await savedDiagramsStore.deleteDiagram(diagramId)
    if (success) {
      notify.success(isZh.value ? '图示已删除' : 'Diagram deleted')
    } else {
      notify.error(isZh.value ? '删除失败' : 'Failed to delete diagram')
    }
  } catch (error) {
    console.error('[DiagramHistory] Delete error:', error)
    notify.error(isZh.value ? '删除失败' : 'Failed to delete diagram')
  }
}

// Handle pin/unpin diagram
async function handlePinDiagram(diagramId: string): Promise<void> {
  const diagram = diagrams.value.find((d) => d.id === diagramId)
  if (!diagram) return

  const newPinned = !diagram.is_pinned
  await savedDiagramsStore.pinDiagram(diagramId, newPinned)
}

// Toggle show all
function toggleShowAll(): void {
  showAll.value = !showAll.value
}
</script>

<template>
  <div class="diagram-history flex flex-col border-t border-stone-200 relative overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3 flex items-center justify-between">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ isZh ? '历史图示' : 'Diagrams' }}
      </div>
      <div
        v-if="!isBlurred && diagrams.length > 0"
        class="text-xs text-stone-400"
      >
        {{ diagrams.length }}/{{ maxDiagrams }}
      </div>
    </div>

    <!-- Scrollable diagram list -->
    <ElScrollbar class="flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <!-- Loading State -->
        <div
          v-if="isLoading"
          class="flex items-center justify-center py-8"
        >
          <ElIcon class="animate-spin text-stone-400">
            <Loading />
          </ElIcon>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="diagrams.length === 0"
          class="text-center py-8"
        >
          <FileImage class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ isZh ? '暂无保存的图示' : 'No saved diagrams' }}
          </p>
          <p class="text-xs text-stone-300 mt-1">
            {{ isZh ? `可保存 ${maxDiagrams} 个图示` : `Can save up to ${maxDiagrams} diagrams` }}
          </p>
        </div>

        <!-- Grouped Diagram List -->
        <template v-else>
          <!-- Top (Pinned) -->
          <div
            v-if="groupedDiagrams.pinned.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.pinned }}</div>
            <div
              v-for="diagram in groupedDiagrams.pinned"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  <Pin class="w-3 h-3 inline-block mr-1 text-amber-500" />
                  {{ diagram.title || (isZh ? '未命名' : 'Untitled') }}
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <ElDropdown
                trigger="click"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <Pin class="w-4 h-4 mr-2 text-amber-500 rotate-45" />
                      {{ isZh ? '取消置顶' : 'Unpin' }}
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Today -->
          <div
            v-if="groupedDiagrams.today.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.today }}</div>
            <div
              v-for="diagram in groupedDiagrams.today"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || (isZh ? '未命名' : 'Untitled') }}
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <ElDropdown
                trigger="click"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Yesterday -->
          <div
            v-if="groupedDiagrams.yesterday.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.yesterday }}</div>
            <div
              v-for="diagram in groupedDiagrams.yesterday"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || (isZh ? '未命名' : 'Untitled') }}
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <ElDropdown
                trigger="click"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Past Week -->
          <div
            v-if="groupedDiagrams.week.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.week }}</div>
            <div
              v-for="diagram in groupedDiagrams.week"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || (isZh ? '未命名' : 'Untitled') }}
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <ElDropdown
                trigger="click"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Past Month -->
          <div
            v-if="groupedDiagrams.month.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.month }}</div>
            <div
              v-for="diagram in groupedDiagrams.month"
              :key="diagram.id"
              class="diagram-item"
              :class="{ active: currentDiagramId === diagram.id }"
              @click="handleDiagramClick(diagram)"
            >
              <div class="diagram-info">
                <span class="diagram-name">
                  {{ diagram.title || (isZh ? '未命名' : 'Untitled') }}
                </span>
                <span class="diagram-type">
                  {{ getDiagramTypeLabel(diagram.diagram_type) }}
                </span>
              </div>
              <ElDropdown
                trigger="click"
                class="more-dropdown"
                @click.stop
              >
                <button
                  class="more-btn"
                  @click.stop
                >
                  <MoreHorizontal class="w-4 h-4" />
                </button>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem @click="handlePinDiagram(diagram.id)">
                      <Pin class="w-4 h-4 mr-2" />
                      {{ isZh ? '置顶' : 'Pin to Top' }}
                    </ElDropdownItem>
                    <ElDropdownItem @click="handleRenameDiagram(diagram.id)">
                      <Edit3 class="w-4 h-4 mr-2" />
                      {{ isZh ? '重命名' : 'Rename' }}
                    </ElDropdownItem>
                    <ElDropdownItem
                      divided
                      @click="handleDeleteDiagram(diagram.id)"
                    >
                      <span class="delete-option">
                        <Trash2 class="w-4 h-4 mr-2" />
                        {{ isZh ? '删除' : 'Delete' }}
                      </span>
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </div>

          <!-- Show More button -->
          <button
            v-if="hasMore"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ isZh ? `显示更多 (${remainingCount})` : `Show more (${remainingCount})` }}
          </button>

          <!-- Show Less button -->
          <button
            v-if="showAll && diagrams.length > INITIAL_LIMIT"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ isZh ? '收起' : 'Show less' }}
          </button>
        </template>
      </div>
    </ElScrollbar>

    <!-- Login overlay when blurred -->
    <div
      v-if="isBlurred"
      class="absolute inset-0 flex items-center justify-center bg-stone-50/60 backdrop-blur-[2px]"
    >
      <div class="text-center px-4">
        <div
          class="w-10 h-10 rounded-full bg-stone-100 flex items-center justify-center mx-auto mb-2"
        >
          <Lock class="w-5 h-5 text-stone-400" />
        </div>
        <p class="text-xs text-stone-500">
          {{ isZh ? '登录后查看历史图示' : 'Login to view diagrams' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagram-history {
  min-height: 120px;
}

.group-section {
  margin-bottom: 12px;
}

.group-section:last-child {
  margin-bottom: 0;
}

.group-label {
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  margin-bottom: 4px;
  padding-left: 2px;
}

.diagram-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  transition: background-color 0.15s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.diagram-item:hover {
  background-color: #f5f5f4;
}

.diagram-item.active {
  background-color: #e7e5e4;
  color: #1c1917;
}

.diagram-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.diagram-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diagram-type {
  font-size: 10px;
  color: #a8a29e;
}

.more-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  opacity: 0;
  color: #78716c;
  transition: all 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
}

.diagram-item:hover .more-btn {
  opacity: 1;
}

.more-btn:hover {
  background-color: #e7e5e4;
  color: #1c1917;
}

/* Dropdown menu styling */
.more-dropdown :deep(.el-dropdown-menu) {
  padding: 4px;
  border-radius: 8px;
  min-width: 140px;
}

.more-dropdown :deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  font-size: 13px;
  border-radius: 4px;
  color: #57534e;
}

.more-dropdown :deep(.el-dropdown-menu__item:hover) {
  background-color: #f5f5f4;
  color: #1c1917;
}

.more-dropdown :deep(.el-dropdown-menu__item.is-divided) {
  margin-top: 4px;
  border-top: 1px solid #e7e5e4;
  padding-top: 8px;
}

.delete-option {
  display: flex;
  align-items: center;
  color: #dc2626;
}

.show-more-btn {
  display: block;
  width: 100%;
  padding: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: #78716c;
  text-align: center;
  background: transparent;
  border: 1px dashed #d6d3d1;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.show-more-btn:hover {
  background-color: #fafaf9;
  border-color: #a8a29e;
  color: #57534e;
}
</style>
