<script setup lang="ts">
/**
 * ChunkTestHistory - Grouped list of recent chunk tests
 * Design: Clean minimalist grouped by time periods
 * Shows max 10 items initially with "Show more" option
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElMessage,
  ElMessageBox,
  ElScrollbar,
  ElTag,
} from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { Lock, MoreHorizontal, TestTube, Trash2 } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { useChunkTestHistory, useDeleteChunkTest, type ChunkTestHistoryItem } from '@/composables/queries/useChunkTestQueries'

const props = defineProps<{
  isBlurred?: boolean
}>()

const { isZh } = useLanguage()
const router = useRouter()

// Show all or just 10
const showAll = ref(false)
const INITIAL_LIMIT = 10

// Vue Query queries
const { data: historyData, isLoading: isLoadingHistory } = useChunkTestHistory(50)
const deleteTestMutation = useDeleteChunkTest()

// Computed - get tests from query data
const tests = computed(() => {
  if (!historyData.value) return []
  return historyData.value.results || []
})

const isLoading = computed(() => isLoadingHistory.value)

// Group tests by time period
interface GroupedTests {
  today: ChunkTestHistoryItem[]
  yesterday: ChunkTestHistoryItem[]
  week: ChunkTestHistoryItem[]
  month: ChunkTestHistoryItem[]
}

const groupedTests = computed((): GroupedTests => {
  const groups: GroupedTests = {
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  // Limit to 10 unless showAll
  const items = showAll.value ? tests.value : tests.value.slice(0, INITIAL_LIMIT)

  items.forEach((test) => {
    const testTime = new Date(test.created_at).getTime()

    if (testTime >= todayStart) {
      groups.today.push(test)
    } else if (testTime >= yesterdayStart) {
      groups.yesterday.push(test)
    } else if (testTime >= weekStart) {
      groups.week.push(test)
    } else {
      groups.month.push(test)
    }
  })

  return groups
})

// Check if there are more tests to show
const hasMore = computed(() => tests.value.length > INITIAL_LIMIT && !showAll.value)
const remainingCount = computed(() => tests.value.length - INITIAL_LIMIT)

// Group labels
const groupLabels = computed(() => ({
  today: isZh.value ? '今天' : 'Today',
  yesterday: isZh.value ? '昨天' : 'Yesterday',
  week: isZh.value ? '上周' : 'Past Week',
  month: isZh.value ? '上月' : 'Past Month',
}))

// Status labels and colors
type TagType = 'success' | 'warning' | 'info' | 'primary' | 'danger'
const statusConfig = computed(() => ({
  pending: { label: isZh.value ? '等待中' : 'Pending', color: 'info' as TagType },
  processing: { label: isZh.value ? '处理中' : 'Processing', color: 'primary' as TagType },
  completed: { label: isZh.value ? '已完成' : 'Completed', color: 'success' as TagType },
  failed: { label: isZh.value ? '失败' : 'Failed', color: 'danger' as TagType },
}))

// Get tag type for status
function getTagType(status: string): TagType {
  return statusConfig.value[status as keyof typeof statusConfig.value]?.color || 'info'
}

// Get test display name
function getTestName(test: ChunkTestHistoryItem): string {
  if (test.dataset_name && test.dataset_name !== 'user_documents') {
    return test.dataset_name
  }
  if (test.document_ids && test.document_ids.length > 0) {
    return isZh.value ? `用户文档 (${test.document_ids.length})` : `User Documents (${test.document_ids.length})`
  }
  return isZh.value ? '未命名测试' : 'Untitled Test'
}

// Handle test click
function handleTestClick(testId: number): void {
  router.push(`/chunk-test/results/${testId}`)
}

// Handle delete test
async function handleDeleteTest(testId: number): Promise<void> {
  try {
    await ElMessageBox.confirm(
      isZh.value
        ? '确定要删除这个测试记录吗？此操作不可撤销。'
        : 'Are you sure you want to delete this test? This cannot be undone.',
      isZh.value ? '删除测试' : 'Delete Test',
      {
        confirmButtonText: isZh.value ? '删除' : 'Delete',
        cancelButtonText: isZh.value ? '取消' : 'Cancel',
        type: 'warning',
      }
    )

    await deleteTestMutation.mutateAsync(testId)
    ElMessage.success(
      isZh.value ? '测试记录已删除' : 'Test deleted successfully'
    )
  } catch (error) {
    if (error instanceof Error && error.message !== 'cancel') {
      ElMessage.error(
        error.message || (isZh.value ? '删除失败' : 'Failed to delete test')
      )
    }
    // User cancelled - do nothing
  }
}

// Toggle show all
function toggleShowAll(): void {
  showAll.value = !showAll.value
}
</script>

<template>
  <div class="chunk-test-history flex flex-col border-t border-stone-200 relative overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ isZh ? '测试历史' : 'Test History' }}
      </div>
    </div>

    <!-- Scrollable test list -->
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
          v-else-if="tests.length === 0"
          class="text-center py-8"
        >
          <TestTube class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ isZh ? '暂无测试记录' : 'No tests yet' }}
          </p>
        </div>

        <!-- Grouped Test List -->
        <template v-else>
          <!-- Today -->
          <div
            v-if="groupedTests.today.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.today }}</div>
            <div
              v-for="test in groupedTests.today"
              :key="test.test_id"
              class="test-item"
              @click="handleTestClick(test.test_id)"
            >
              <div class="flex-1 min-w-0">
                <div class="test-name">
                  {{ getTestName(test) }}
                </div>
                <div class="test-meta">
                  <ElTag
                    :type="getTagType(test.status)"
                    size="small"
                    effect="plain"
                  >
                    {{ statusConfig[test.status as keyof typeof statusConfig]?.label || test.status }}
                  </ElTag>
                  <span class="test-id">#{{ test.test_id }}</span>
                </div>
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
                    <ElDropdownItem
                      divided
                      @click="handleDeleteTest(test.test_id)"
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
            v-if="groupedTests.yesterday.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.yesterday }}</div>
            <div
              v-for="test in groupedTests.yesterday"
              :key="test.test_id"
              class="test-item"
              @click="handleTestClick(test.test_id)"
            >
              <div class="flex-1 min-w-0">
                <div class="test-name">
                  {{ getTestName(test) }}
                </div>
                <div class="test-meta">
                  <ElTag
                    :type="getTagType(test.status)"
                    size="small"
                    effect="plain"
                  >
                    {{ statusConfig[test.status as keyof typeof statusConfig]?.label || test.status }}
                  </ElTag>
                  <span class="test-id">#{{ test.test_id }}</span>
                </div>
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
                    <ElDropdownItem
                      divided
                      @click="handleDeleteTest(test.test_id)"
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
            v-if="groupedTests.week.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.week }}</div>
            <div
              v-for="test in groupedTests.week"
              :key="test.test_id"
              class="test-item"
              @click="handleTestClick(test.test_id)"
            >
              <div class="flex-1 min-w-0">
                <div class="test-name">
                  {{ getTestName(test) }}
                </div>
                <div class="test-meta">
                  <ElTag
                    :type="getTagType(test.status)"
                    size="small"
                    effect="plain"
                  >
                    {{ statusConfig[test.status as keyof typeof statusConfig]?.label || test.status }}
                  </ElTag>
                  <span class="test-id">#{{ test.test_id }}</span>
                </div>
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
                    <ElDropdownItem
                      divided
                      @click="handleDeleteTest(test.test_id)"
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
            v-if="groupedTests.month.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.month }}</div>
            <div
              v-for="test in groupedTests.month"
              :key="test.test_id"
              class="test-item"
              @click="handleTestClick(test.test_id)"
            >
              <div class="flex-1 min-w-0">
                <div class="test-name">
                  {{ getTestName(test) }}
                </div>
                <div class="test-meta">
                  <ElTag
                    :type="getTagType(test.status)"
                    size="small"
                    effect="plain"
                  >
                    {{ statusConfig[test.status as keyof typeof statusConfig]?.label || test.status }}
                  </ElTag>
                  <span class="test-id">#{{ test.test_id }}</span>
                </div>
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
                    <ElDropdownItem
                      divided
                      @click="handleDeleteTest(test.test_id)"
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
            v-if="showAll && tests.length > INITIAL_LIMIT"
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
          {{ isZh ? '登录后查看测试历史' : 'Login to view history' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chunk-test-history {
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

.test-item {
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

.test-item:hover {
  background-color: #f5f5f4;
}

.test-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  font-weight: 500;
  margin-bottom: 2px;
}

.test-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #78716c;
}

.test-id {
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

.test-item:hover .more-btn {
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
