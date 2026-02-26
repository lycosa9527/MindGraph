<template>
  <div class="smart-response-page">
    <el-card>
      <template #header>
        <div class="page-header">
          <h2>Smart Response 智回</h2>
          <el-button type="primary" @click="handleStartLearningMode" :disabled="!selectedDiagramId">
            Start Learning Mode
          </el-button>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="8">
          <el-card>
            <template #header>Diagram Selection</template>
            <el-select v-model="selectedDiagramId" placeholder="Select diagram" style="width: 100%">
              <el-option
                v-for="diagram in diagrams"
                :key="diagram.id"
                :label="diagram.name"
                :value="diagram.id"
              />
            </el-select>
          </el-card>
        </el-col>

        <el-col :span="16">
          <el-card>
            <template #header>
              <div class="watch-list-header">
                <span>Watches</span>
                <el-button size="small" @click="fetchWatches">Refresh</el-button>
              </div>
            </template>

            <el-table :data="watches" v-loading="isLoading">
              <el-table-column prop="watch_id" label="Watch ID" width="150" />
              <el-table-column prop="student_name" label="Student" width="120" />
              <el-table-column prop="status" label="Status" width="120">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)">
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="last_seen" label="Last Seen" width="180" />
              <el-table-column label="Actions" width="200">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === 'unassigned'"
                    size="small"
                    @click="showAssignModal(row)"
                  >
                    Assign
                  </el-button>
                  <el-button
                    v-else
                    size="small"
                    @click="showUnassignModal(row)"
                  >
                    Unassign
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <WatchAssignmentModal
      v-model="showAssignDialog"
      :watch-item="selectedWatch"
      @assigned="handleAssigned"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSmartResponseStore } from '@/stores/smartResponse'
import WatchAssignmentModal from '@/components/smart-response/WatchAssignmentModal.vue'

const store = useSmartResponseStore()
const watches = computed(() => store.watches)
const isLoading = computed(() => store.isLoading)

const selectedDiagramId = ref<string>('')
const diagrams = ref<Array<{ id: string; name: string }>>([])
const showAssignDialog = ref(false)
const selectedWatch = ref(null)

onMounted(async () => {
  await store.fetchWatches()
  // TODO: Load diagrams
})

onUnmounted(() => {
  store.reset()
})

function getStatusType(status: string) {
  const types: Record<string, string> = {
    unassigned: 'info',
    assigned: 'warning',
    connected: 'success',
    learning_mode: 'success',
    offline: 'danger',
  }
  return types[status] || 'info'
}

function showAssignModal(watch: any) {
  selectedWatch.value = watch
  showAssignDialog.value = true
}

function showUnassignModal(watch: any) {
  // TODO: Implement unassign
}

async function handleAssigned(watchId: string, studentId: number) {
  await store.assignWatch(watchId, studentId)
  showAssignDialog.value = false
}

async function handleStartLearningMode() {
  if (!selectedDiagramId.value) return
  const sessionId = await store.startLearningMode(selectedDiagramId.value)
  if (sessionId) {
    // TODO: Connect WebSocket and broadcast
  }
}

async function fetchWatches() {
  await store.fetchWatches()
}
</script>

<style scoped>
.smart-response-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.watch-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>