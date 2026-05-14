<script setup lang="ts">
/**
 * Admin — Kitty LLMOps: module map and hub contract (read-only).
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiRequest } from '@/utils/apiClient'

interface LlmopsModule {
  id: string
  title: string
  paths: string[]
  role: string
  hub_calls: string[]
}

interface SpecialFlowRow {
  name: string
  channel: string
  hub_op: string | null
  notes: string
}

interface LlmopsManifest {
  version: number
  hub_mutation_ops: string[]
  diagram_voice_intents: string[]
  ui_and_special_voice_intents: string[]
  modules: LlmopsModule[]
  mermaid_flow: string
  special_flows?: SpecialFlowRow[]
}

const loading = ref(true)
const manifest = ref<LlmopsManifest | null>(null)
const flowText = ref('')

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await apiRequest('/api/auth/admin/kitty-llmops/architecture')
    if (!res.ok) {
      throw new Error('request failed')
    }
    const data = (await res.json()) as LlmopsManifest
    manifest.value = data
    flowText.value = data.mermaid_flow || ''
  } catch {
    ElMessage.error('Failed to load Kitty architecture manifest')
    manifest.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="kitty-llmops space-y-6">
    <p class="text-sm text-gray-600">
      Read-only map of Kitty modules and MindGraphAgentHub responsibilities. For operational details see
      <code class="text-xs bg-gray-100 px-1 rounded">services/agent_hub/README.md</code>.
    </p>

    <div v-loading="loading">
      <template v-if="manifest">
        <el-descriptions title="Hub mutation ops" :column="1" border class="mb-4">
          <el-descriptions-item label="MutationOp">
            {{ manifest.hub_mutation_ops.join(', ') }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="grid md:grid-cols-2 gap-4 mb-4">
          <el-card shadow="never">
            <template #header>Diagram voice intents</template>
            <ul class="list-disc pl-5 text-sm space-y-1">
              <li v-for="x in manifest.diagram_voice_intents" :key="x">{{ x }}</li>
            </ul>
          </el-card>
          <el-card shadow="never">
            <template #header>UI / special intents</template>
            <ul class="list-disc pl-5 text-sm space-y-1 max-h-60 overflow-y-auto">
              <li v-for="x in manifest.ui_and_special_voice_intents" :key="x">{{ x }}</li>
            </ul>
          </el-card>
        </div>

        <el-card v-if="manifest.special_flows?.length" shadow="never" class="mb-4">
          <template #header>Classifier / pipeline flows (non-action)</template>
          <el-table :data="manifest.special_flows" stripe size="small">
            <el-table-column prop="name" label="Flow" width="200" />
            <el-table-column prop="channel" label="Channel" width="120" />
            <el-table-column prop="hub_op" label="Hub op" width="200" />
            <el-table-column prop="notes" label="Notes" min-width="240" />
          </el-table>
        </el-card>

        <el-table :data="manifest.modules" stripe class="mb-4">
          <el-table-column prop="title" label="Module" width="180" />
          <el-table-column prop="role" label="Role" min-width="220" />
          <el-table-column label="Code paths" min-width="240">
            <template #default="{ row }">
              <code v-for="p in row.paths" :key="p" class="block text-xs text-gray-700">{{ p }}</code>
            </template>
          </el-table-column>
          <el-table-column label="Hub API" min-width="200">
            <template #default="{ row }">
              <span v-if="!row.hub_calls.length" class="text-gray-400 text-sm">—</span>
              <ul v-else class="list-disc pl-4 text-xs space-y-0.5">
                <li v-for="h in row.hub_calls" :key="h">{{ h }}</li>
              </ul>
            </template>
          </el-table-column>
        </el-table>

        <el-card shadow="never">
          <template #header>Flow (Mermaid source)</template>
          <pre class="text-xs bg-gray-900 text-green-100 p-4 rounded overflow-x-auto whitespace-pre-wrap">{{
            flowText
          }}</pre>
        </el-card>
      </template>
    </div>
  </div>
</template>
