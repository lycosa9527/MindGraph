<script setup lang="ts">
/**
 * Admin — Kitty LLMOps: devices, live sessions, defaults, module map.
 */
import { computed, ref } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  putAdminKittyDefaults,
  useAdminKittyDevices,
  useAdminKittyLlmopsArchitecture,
  useAdminKittySessions,
} from '@/composables/queries'

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

const { t } = useLanguage()
const notify = useNotifications()

const architectureQuery = useAdminKittyLlmopsArchitecture()
const devicesQuery = useAdminKittyDevices()
const sessionsQuery = useAdminKittySessions()

const loading = computed(() => architectureQuery.isFetching.value)
const manifest = computed(() => architectureQuery.data.value as LlmopsManifest | null | undefined)
const flowText = computed(() => manifest.value?.mermaid_flow ?? '')
const devices = computed(() => devicesQuery.data.value?.devices ?? [])
const sessions = computed(() => sessionsQuery.data.value?.sessions ?? [])

const defaultsUserId = ref('')
const defaultsListenMode = ref('manual')
const defaultsTts = ref(true)
const defaultsSaving = ref(false)

function formatSeen(epoch: number): string {
  if (!epoch) {
    return '—'
  }
  return new Date(epoch * 1000).toLocaleString()
}

async function saveDefaults(): Promise<void> {
  const userId = Number.parseInt(defaultsUserId.value, 10)
  if (!Number.isFinite(userId) || userId < 1) {
    return
  }
  defaultsSaving.value = true
  try {
    await putAdminKittyDefaults(userId, {
      listen_mode: defaultsListenMode.value,
      tts_enabled: defaultsTts.value,
    })
    notify.success(t('admin.kittyDefaultsSaved'))
  } catch {
    notify.warning(t('admin.featureSaveFailed'))
  } finally {
    defaultsSaving.value = false
  }
}
</script>

<template>
  <div class="kitty-llmops space-y-6">
    <el-card shadow="never">
      <template #header>{{ t('admin.kittyDevicesTitle') }}</template>
      <el-table
        v-if="devices.length"
        :data="devices"
        stripe
        size="small"
      >
        <el-table-column
          prop="user_id"
          :label="t('admin.kittyDeviceUser')"
          width="90"
        />
        <el-table-column
          prop="device_id"
          :label="t('admin.kittyDeviceId')"
          min-width="140"
        />
        <el-table-column
          prop="firmware"
          :label="t('admin.kittyDeviceFirmware')"
          width="120"
        />
        <el-table-column
          prop="listen_mode"
          :label="t('admin.kittyDeviceListenMode')"
          width="120"
        />
        <el-table-column
          :label="t('admin.kittyDeviceLastSeen')"
          width="180"
        >
          <template #default="{ row }">
            {{ formatSeen(row.last_seen) }}
          </template>
        </el-table-column>
      </el-table>
      <p
        v-else
        class="text-sm text-gray-500"
      >
        {{ t('admin.kittyDevicesEmpty') }}
      </p>
    </el-card>

    <el-card shadow="never">
      <template #header>{{ t('admin.kittySessionsTitle') }}</template>
      <el-table
        v-if="sessions.length"
        :data="sessions"
        stripe
        size="small"
      >
        <el-table-column
          prop="user_id"
          :label="t('admin.kittyDeviceUser')"
          width="90"
        />
        <el-table-column
          prop="lane"
          label="Lane"
          width="100"
        />
        <el-table-column
          prop="voice_phase"
          :label="t('admin.kittySessionPhase')"
          width="120"
        />
        <el-table-column
          prop="listen_mode"
          :label="t('admin.kittyDeviceListenMode')"
          width="120"
        />
        <el-table-column
          prop="scope"
          label="Scope"
          min-width="160"
        />
      </el-table>
      <p
        v-else
        class="text-sm text-gray-500"
      >
        {{ t('admin.kittySessionsEmpty') }}
      </p>
    </el-card>

    <el-card shadow="never">
      <template #header>{{ t('admin.kittyDefaultsTitle') }}</template>
      <div class="flex flex-wrap gap-3 items-end">
        <el-input
          v-model="defaultsUserId"
          :placeholder="t('admin.kittyDefaultsUserId')"
          class="w-36"
        />
        <el-select
          v-model="defaultsListenMode"
          class="w-40"
        >
          <el-option
            label="manual"
            value="manual"
          />
          <el-option
            label="auto"
            value="auto"
          />
        </el-select>
        <el-switch
          v-model="defaultsTts"
          :active-text="t('admin.kittyDefaultsTts')"
        />
        <el-button
          type="primary"
          :loading="defaultsSaving"
          @click="saveDefaults"
        >
          {{ t('admin.kittyDefaultsSave') }}
        </el-button>
      </div>
    </el-card>

    <p class="text-sm text-gray-600">
      Read-only map of Kitty modules and MindGraphAgentHub responsibilities. For operational details
      see
      <code class="text-xs bg-gray-100 px-1 rounded">services/agent_hub/README.md</code>.
    </p>

    <div v-loading="loading">
      <template v-if="manifest">
        <el-descriptions
          title="Hub mutation ops"
          :column="1"
          border
          class="mb-4"
        >
          <el-descriptions-item label="MutationOp">
            {{ manifest.hub_mutation_ops.join(', ') }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="grid md:grid-cols-2 gap-4 mb-4">
          <el-card shadow="never">
            <template #header>Diagram voice intents</template>
            <ul class="list-disc pl-5 text-sm space-y-1">
              <li
                v-for="x in manifest.diagram_voice_intents"
                :key="x"
              >
                {{ x }}
              </li>
            </ul>
          </el-card>
          <el-card shadow="never">
            <template #header>UI / special intents</template>
            <ul class="list-disc pl-5 text-sm space-y-1 max-h-60 overflow-y-auto">
              <li
                v-for="x in manifest.ui_and_special_voice_intents"
                :key="x"
              >
                {{ x }}
              </li>
            </ul>
          </el-card>
        </div>

        <el-card
          v-if="manifest.special_flows?.length"
          shadow="never"
          class="mb-4"
        >
          <template #header>Classifier / pipeline flows (non-action)</template>
          <el-table
            :data="manifest.special_flows"
            stripe
            size="small"
          >
            <el-table-column
              prop="name"
              label="Flow"
              width="200"
            />
            <el-table-column
              prop="channel"
              label="Channel"
              width="120"
            />
            <el-table-column
              prop="hub_op"
              label="Hub op"
              width="200"
            />
            <el-table-column
              prop="notes"
              label="Notes"
              min-width="240"
            />
          </el-table>
        </el-card>

        <el-table
          :data="manifest.modules"
          stripe
          class="mb-4"
        >
          <el-table-column
            prop="title"
            label="Module"
            width="180"
          />
          <el-table-column
            prop="role"
            label="Role"
            min-width="220"
          />
          <el-table-column
            label="Code paths"
            min-width="240"
          >
            <template #default="{ row }">
              <code
                v-for="p in row.paths"
                :key="p"
                class="block text-xs text-gray-700"
                >{{ p }}</code
              >
            </template>
          </el-table-column>
          <el-table-column
            label="Hub API"
            min-width="200"
          >
            <template #default="{ row }">
              <span
                v-if="!row.hub_calls.length"
                class="text-gray-400 text-sm"
                >—</span
              >
              <ul
                v-else
                class="list-disc pl-4 text-xs space-y-0.5"
              >
                <li
                  v-for="h in row.hub_calls"
                  :key="h"
                >
                  {{ h }}
                </li>
              </ul>
            </template>
          </el-table-column>
        </el-table>

        <el-card shadow="never">
          <template #header>Flow (Mermaid source)</template>
          <pre
            class="text-xs bg-gray-900 text-green-100 p-4 rounded overflow-x-auto whitespace-pre-wrap"
            >{{ flowText }}</pre
          >
        </el-card>
      </template>
    </div>
  </div>
</template>
