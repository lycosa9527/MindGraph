<script setup lang="ts">
/**
 * Public Dashboard Page - Public statistics view
 */
import { onMounted, ref } from 'vue'

import { useLanguage, useNotifications } from '@/composables'

const { isZh } = useLanguage()
const notify = useNotifications()

const isLoading = ref(true)
const stats = ref({
  totalDiagrams: 0,
  totalUsers: 0,
  diagramsToday: 0,
  popularTypes: [] as Array<{ type: string; count: number }>,
})

async function loadPublicStats() {
  isLoading.value = true
  try {
    // TODO: Fetch from /api/public/dashboard/stats
    stats.value = {
      totalDiagrams: 25680,
      totalUsers: 3420,
      diagramsToday: 156,
      popularTypes: [
        { type: 'Mind Map', count: 8540 },
        { type: 'Concept Map', count: 5230 },
        { type: 'Flow Map', count: 4120 },
        { type: 'Tree Map', count: 3890 },
        { type: 'Bubble Map', count: 2100 },
      ],
    }
  } catch {
    notify.error(
      isZh.value ? '网络错误，加载仪表盘失败' : 'Network error, failed to load dashboard'
    )
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadPublicStats()
})
</script>

<template>
  <div class="public-dashboard-page p-6 max-w-6xl mx-auto">
    <!-- Header -->
    <div class="text-center mb-12">
      <h1 class="text-3xl font-bold text-gray-800 dark:text-white mb-3">MindGraph Statistics</h1>
      <p class="text-gray-500 dark:text-gray-400">
        Real-time insights into diagram creation activity
      </p>
    </div>

    <!-- Loading State -->
    <div
      v-if="isLoading"
      class="flex items-center justify-center py-20"
    >
      <el-icon
        class="is-loading"
        :size="32"
        ><Loading
      /></el-icon>
    </div>

    <!-- Stats Grid -->
    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        <!-- Total Diagrams -->
        <el-card
          shadow="hover"
          class="stat-card text-center"
        >
          <div class="py-4">
            <el-icon
              :size="40"
              class="text-primary-500 mb-4"
              ><Document
            /></el-icon>
            <p class="text-4xl font-bold text-gray-800 dark:text-white mb-2">
              {{ stats.totalDiagrams.toLocaleString() }}
            </p>
            <p class="text-gray-500 dark:text-gray-400">Total Diagrams Created</p>
          </div>
        </el-card>

        <!-- Total Users -->
        <el-card
          shadow="hover"
          class="stat-card text-center"
        >
          <div class="py-4">
            <el-icon
              :size="40"
              class="text-green-500 mb-4"
              ><User
            /></el-icon>
            <p class="text-4xl font-bold text-gray-800 dark:text-white mb-2">
              {{ stats.totalUsers.toLocaleString() }}
            </p>
            <p class="text-gray-500 dark:text-gray-400">Registered Users</p>
          </div>
        </el-card>

        <!-- Diagrams Today -->
        <el-card
          shadow="hover"
          class="stat-card text-center"
        >
          <div class="py-4">
            <el-icon
              :size="40"
              class="text-orange-500 mb-4"
              ><TrendCharts
            /></el-icon>
            <p class="text-4xl font-bold text-gray-800 dark:text-white mb-2">
              {{ stats.diagramsToday.toLocaleString() }}
            </p>
            <p class="text-gray-500 dark:text-gray-400">Diagrams Today</p>
          </div>
        </el-card>
      </div>

      <!-- Popular Diagram Types -->
      <el-card shadow="hover">
        <template #header>
          <h2 class="text-lg font-medium">Popular Diagram Types</h2>
        </template>
        <div class="space-y-4">
          <div
            v-for="(item, index) in stats.popularTypes"
            :key="item.type"
            class="flex items-center gap-4"
          >
            <span class="w-6 text-center text-gray-400 font-medium">{{ index + 1 }}</span>
            <div class="flex-1">
              <div class="flex items-center justify-between mb-1">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ item.type }}</span>
                <span class="text-sm text-gray-500">{{ item.count.toLocaleString() }}</span>
              </div>
              <el-progress
                :percentage="(item.count / stats.popularTypes[0].count) * 100"
                :show-text="false"
                :stroke-width="6"
              />
            </div>
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.public-dashboard-page {
  min-height: calc(100vh - 112px);
}

.stat-card :deep(.el-card__body) {
  padding: 24px;
}
</style>
