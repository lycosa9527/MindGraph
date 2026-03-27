<script setup lang="ts">
/**
 * Teacher Usage Page (教师使用度)
 * Admin-only analytics dashboard for teacher engagement classification.
 */
import { provide } from 'vue'

import { ArrowDown, ArrowUp, Loading } from '@element-plus/icons-vue'

import TeacherUsageDialogs from '@/components/teacher-usage/TeacherUsageDialogs.vue'
import type { Teacher } from '@/composables/teacherUsage/teacherUsageTypes'
import {
  teacherUsageInjectionKey,
  useTeacherUsagePage,
} from '@/composables/teacherUsage/useTeacherUsagePage'
import { formatUserNumber } from '@/utils/intlDisplay'

const page = useTeacherUsagePage()
provide(teacherUsageInjectionKey, page)

const {
  t,
  uiStore,
  isLoading,
  allUsersLoading,
  activeTab,
  stats,
  loadTeacherUsage,
  loadAllUsers,
  usersPage,
  formatNumber,
  TOP_LEVEL_GROUPS,
  SUB_GROUPS,
  teacherGroupName,
  teacherGroupDescription,
  groupStats,
  openTeachersModal,
  pieChartRef,
  barChartRef,
  groupChartRefs,
  toggleGroupExpanded,
  isGroupExpanded,
  allUsers,
  usersTotal,
  usersPageSize,
  onUsersPageChange,
  openUserDetailFromList,
} = page
</script>

<template>
  <div class="teacher-usage-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header (same as Library, Gewe modules) -->
    <div
      class="teacher-usage-header h-14 px-4 flex items-center justify-between bg-white border-b border-stone-200"
    >
      <h1 class="text-sm font-semibold text-stone-900">
        {{ t('teacher.analytics.title') }}
      </h1>
      <el-button
        size="small"
        :loading="isLoading || allUsersLoading"
        @click="activeTab === 'overview' ? loadTeacherUsage() : loadAllUsers(usersPage)"
      >
        {{ t('common.refresh') }}
      </el-button>
    </div>

    <!-- Scrollable content -->
    <div class="teacher-usage-content flex-1 overflow-y-auto px-6 pt-6 pb-6">
      <el-tabs
        v-model="activeTab"
        class="teacher-usage-tabs"
      >
        <el-tab-pane
          :label="t('teacher.analytics.overview')"
          name="overview"
        >
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

          <div
            v-else
            class="max-w-7xl mx-auto"
          >
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('total')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.totalTeachers') }}
                </p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatUserNumber(stats.totalTeachers, uiStore.language) }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('unused')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.unused') }}
                </p>
                <p class="text-2xl font-bold text-gray-500 dark:text-gray-400">
                  {{ stats.unused }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('continuous')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.continuous') }}
                </p>
                <p class="text-2xl font-bold text-green-600 dark:text-green-400">
                  {{ stats.continuous }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('rejection')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.rejection') }}
                </p>
                <p class="text-2xl font-bold text-orange-600 dark:text-orange-400">
                  {{ stats.rejection }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('stopped')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.stopped') }}
                </p>
                <p class="text-2xl font-bold text-red-600 dark:text-red-400">
                  {{ stats.stopped }}
                </p>
              </el-card>
              <el-card
                shadow="hover"
                class="stat-card stat-card-clickable"
                @click="openTeachersModal('intermittent')"
              >
                <p class="text-xs text-gray-500 mb-1">
                  {{ t('teacher.analytics.modalTitle.intermittent') }}
                </p>
                <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {{ stats.intermittent }}
                </p>
              </el-card>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <el-card shadow="hover">
                <template #header>
                  <span class="font-medium">
                    {{ t('teacher.analytics.groupDistribution') }}
                  </span>
                </template>
                <div
                  ref="pieChartRef"
                  class="h-64"
                />
              </el-card>
              <el-card shadow="hover">
                <template #header>
                  <span class="font-medium">
                    {{ t('teacher.analytics.tokenByGroup') }}
                  </span>
                </template>
                <div
                  ref="barChartRef"
                  class="h-64"
                />
              </el-card>
            </div>

            <!-- Diagram cards: Total, 未使用, 持续使用, then 非持续使用 box with 3 sub-cards -->
            <div class="space-y-4">
              <!-- Total -->
              <el-card
                shadow="hover"
                class="group-card cursor-pointer transition-colors"
                :class="{ 'group-card-expanded': isGroupExpanded('total') }"
                @click="toggleGroupExpanded('total')"
              >
                <div class="flex items-center justify-between">
                  <div>
                    <span class="font-semibold text-stone-900">
                      {{ t('teacher.analytics.group.total.name') }}
                    </span>
                    <div class="text-xs text-stone-500 mt-0.5">
                      {{ t('teacher.analytics.group.total.description') }}
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <el-tag size="small">
                      {{ groupStats.total?.count ?? 0 }}
                      {{ t('teacher.analytics.teachersUnit') }}
                    </el-tag>
                    <el-icon
                      :size="18"
                      class="text-stone-400"
                    >
                      <ArrowDown v-if="!isGroupExpanded('total')" />
                      <ArrowUp v-else />
                    </el-icon>
                  </div>
                </div>
                <div
                  v-show="isGroupExpanded('total')"
                  class="mt-6 pt-6 border-t border-stone-200"
                  @click.stop
                >
                  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                      <el-table
                        :data="groupStats.total?.teachers ?? []"
                        stripe
                        size="small"
                      >
                        <el-table-column
                          prop="username"
                          :label="t('teacher.analytics.colTeacher')"
                          width="140"
                        />
                        <el-table-column
                          prop="diagrams"
                          :label="t('teacher.analytics.colAutocompleteCount')"
                          width="80"
                        />
                        <el-table-column
                          prop="conceptGen"
                          :label="t('teacher.analytics.colConceptGen')"
                          width="80"
                        />
                        <el-table-column
                          prop="relationshipLabels"
                          :label="t('teacher.analytics.colRelLabels')"
                          width="80"
                        />
                        <el-table-column
                          prop="tokens"
                          :label="t('teacher.analytics.colTokens')"
                          width="100"
                        >
                          <template #default="{ row }">
                            {{ formatNumber(row.tokens) }}
                          </template>
                        </el-table-column>
                        <el-table-column
                          prop="lastActive"
                          :label="t('teacher.analytics.colLastActive')"
                        />
                      </el-table>
                    </div>
                    <div>
                      <div
                        :ref="
                          (el) => {
                            if (el) groupChartRefs['total'] = el as HTMLDivElement
                          }
                        "
                        class="h-48"
                      />
                    </div>
                  </div>
                </div>
              </el-card>

              <!-- 未使用, 持续使用 -->
              <el-card
                v-for="group in TOP_LEVEL_GROUPS"
                :key="group.id"
                shadow="hover"
                class="group-card cursor-pointer transition-colors"
                :class="{ 'group-card-expanded': isGroupExpanded(group.id) }"
                @click="toggleGroupExpanded(group.id)"
              >
                <div class="flex items-center justify-between">
                  <div>
                    <span class="font-semibold text-stone-900">
                      {{ teacherGroupName(group.id) }}
                    </span>
                    <div class="text-xs text-stone-500 mt-0.5">
                      {{ teacherGroupDescription(group.id) }}
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <el-tag size="small">
                      {{ groupStats[group.id]?.count ?? 0 }}
                      {{ t('teacher.analytics.teachersUnit') }}
                    </el-tag>
                    <el-icon
                      :size="18"
                      class="text-stone-400"
                    >
                      <ArrowDown v-if="!isGroupExpanded(group.id)" />
                      <ArrowUp v-else />
                    </el-icon>
                  </div>
                </div>
                <div
                  v-show="isGroupExpanded(group.id)"
                  class="mt-6 pt-6 border-t border-stone-200"
                  @click.stop
                >
                  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                      <el-table
                        :data="groupStats[group.id]?.teachers ?? []"
                        stripe
                        size="small"
                      >
                        <el-table-column
                          prop="username"
                          :label="t('teacher.analytics.colTeacher')"
                          width="140"
                        />
                        <el-table-column
                          prop="diagrams"
                          :label="t('teacher.analytics.colAutocompleteCount')"
                          width="80"
                        />
                        <el-table-column
                          prop="conceptGen"
                          :label="t('teacher.analytics.colConceptGen')"
                          width="80"
                        />
                        <el-table-column
                          prop="relationshipLabels"
                          :label="t('teacher.analytics.colRelLabels')"
                          width="80"
                        />
                        <el-table-column
                          prop="tokens"
                          :label="t('teacher.analytics.colTokens')"
                          width="100"
                        >
                          <template #default="{ row }">
                            {{ formatNumber(row.tokens) }}
                          </template>
                        </el-table-column>
                        <el-table-column
                          prop="lastActive"
                          :label="t('teacher.analytics.colLastActive')"
                        />
                      </el-table>
                    </div>
                    <div>
                      <div
                        :ref="
                          (el) => {
                            if (el) groupChartRefs[group.id] = el as HTMLDivElement
                          }
                        "
                        class="h-48"
                      />
                    </div>
                  </div>
                </div>
              </el-card>

              <!-- 非持续使用: 拒绝使用, 停止使用, 间歇式使用 in a visual box -->
              <div
                class="sub-groups-box rounded-lg border-2 border-stone-300 bg-stone-100/50 p-4 dark:border-stone-600 dark:bg-stone-800/30"
              >
                <div class="text-sm font-semibold text-stone-700 dark:text-stone-300 mb-4">
                  {{ t('teacher.analytics.nonContinuous') }}
                </div>
                <div class="space-y-4">
                  <el-card
                    v-for="group in SUB_GROUPS"
                    :key="group.id"
                    shadow="hover"
                    class="group-card group-card-nested cursor-pointer transition-colors"
                    :class="{ 'group-card-expanded': isGroupExpanded(group.id) }"
                    @click="toggleGroupExpanded(group.id)"
                  >
                    <div class="flex items-center justify-between">
                      <div>
                        <span class="font-semibold text-stone-900">
                          {{ teacherGroupName(group.id) }}
                        </span>
                        <div class="text-xs text-stone-500 mt-0.5">
                          {{ teacherGroupDescription(group.id) }}
                        </div>
                      </div>
                      <div class="flex items-center gap-2">
                        <el-tag size="small">
                          {{ groupStats[group.id]?.count ?? 0 }}
                          {{ t('teacher.analytics.teachersUnit') }}
                        </el-tag>
                        <el-icon
                          :size="18"
                          class="text-stone-400"
                        >
                          <ArrowDown v-if="!isGroupExpanded(group.id)" />
                          <ArrowUp v-else />
                        </el-icon>
                      </div>
                    </div>
                    <div
                      v-show="isGroupExpanded(group.id)"
                      class="mt-6 pt-6 border-t border-stone-200"
                      @click.stop
                    >
                      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div>
                          <el-table
                            :data="groupStats[group.id]?.teachers ?? []"
                            stripe
                            size="small"
                          >
                            <el-table-column
                              prop="username"
                              :label="t('teacher.analytics.colTeacher')"
                              width="140"
                            />
                            <el-table-column
                              prop="diagrams"
                              :label="t('teacher.analytics.colAutocompleteCount')"
                              width="80"
                            />
                            <el-table-column
                              prop="conceptGen"
                              :label="t('teacher.analytics.colConceptGen')"
                              width="80"
                            />
                            <el-table-column
                              prop="relationshipLabels"
                              :label="t('teacher.analytics.colRelLabels')"
                              width="80"
                            />
                            <el-table-column
                              prop="tokens"
                              :label="t('teacher.analytics.colTokens')"
                              width="100"
                            >
                              <template #default="{ row }">
                                {{ formatNumber(row.tokens) }}
                              </template>
                            </el-table-column>
                            <el-table-column
                              prop="lastActive"
                              :label="t('teacher.analytics.colLastActive')"
                            />
                          </el-table>
                        </div>
                        <div>
                          <div
                            :ref="
                              (el) => {
                                if (el) groupChartRefs[group.id] = el as HTMLDivElement
                              }
                            "
                            class="h-48"
                          />
                        </div>
                      </div>
                    </div>
                  </el-card>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane
          :label="t('teacher.analytics.teachersTab')"
          name="teachers"
        >
          <div
            v-if="allUsersLoading"
            class="flex items-center justify-center py-20"
          >
            <el-icon
              class="is-loading"
              :size="32"
              ><Loading
            /></el-icon>
          </div>
          <div
            v-else
            class="max-w-5xl"
          >
            <el-table
              :data="allUsers"
              stripe
              size="small"
              class="teachers-list-table"
              @row-click="(row: Teacher) => openUserDetailFromList(row)"
            >
              <el-table-column
                prop="username"
                :label="t('teacher.analytics.colTeacher')"
                width="180"
              />
              <el-table-column
                prop="diagrams"
                :label="t('teacher.analytics.colAutocomplete')"
                width="100"
              />
              <el-table-column
                prop="conceptGen"
                :label="t('teacher.analytics.colConceptGen')"
                width="100"
              />
              <el-table-column
                prop="relationshipLabels"
                :label="t('teacher.analytics.colRelLabels')"
                width="100"
              />
              <el-table-column
                prop="tokens"
                :label="t('teacher.analytics.colTokens')"
                width="120"
              >
                <template #default="{ row }">
                  {{ formatNumber(row.tokens) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="lastActive"
                :label="t('teacher.analytics.colLastActive')"
              />
            </el-table>
            <div class="mt-4 flex justify-end">
              <el-pagination
                v-model:current-page="usersPage"
                :page-size="usersPageSize"
                :total="usersTotal"
                layout="prev, pager, next, total"
                @current-change="onUsersPageChange"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <TeacherUsageDialogs />
  </div>
</template>

<style scoped>
.teacher-usage-page {
  min-height: 0;
}

.teacher-usage-content {
  min-height: 0;
}

.stat-card {
  min-width: 0;
}

.stat-card-clickable {
  cursor: pointer;
}

.stat-card-clickable:hover {
  background-color: rgb(250 250 249);
}

.teachers-table-clickable :deep(.el-table__row) {
  cursor: pointer;
}

.teachers-table-clickable :deep(.el-table__row:hover) {
  background-color: rgb(245 245 244) !important;
}

.teachers-list-table :deep(.el-table__row) {
  cursor: pointer;
}

.teachers-list-table :deep(.el-table__row:hover) {
  background-color: rgb(245 245 244) !important;
}

:global(.dark) .stat-card-clickable:hover {
  background-color: rgb(41 37 36);
}

.group-card:hover {
  background-color: rgb(250 250 249);
}

:global(.dark) .group-card:hover {
  background-color: rgb(41 37 36);
}

.group-card-expanded:hover {
  background-color: transparent;
}

.group-card :deep(.el-card__body) {
  padding: 1rem 1.25rem;
}

.group-card-nested :deep(.el-card__body) {
  padding: 0.75rem 1rem;
}
</style>
