<script setup lang="ts">
/**
 * Admin — MindBot: per-organization DingTalk + Dify (HTTP callback).
 */
import { computed, onMounted, ref } from 'vue'

import { DocumentCopy } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAuthStore } from '@/stores/auth'
import { apiRequest } from '@/utils/apiClient'

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { publicSiteUrl } = usePublicSiteUrl()
const { featureMindbot } = useFeatureFlags()

interface MindbotConfigRow {
  id: number
  organization_id: number
  dingtalk_robot_code: string
  dingtalk_client_id: string | null
  dify_api_base_url: string
  dify_timeout_seconds: number
  dify_inputs_json: string | null
  is_enabled: boolean
}

interface OrgOption {
  id: number
  name: string
  display_name?: string | null
}

const loading = ref(true)
const saving = ref(false)
const configs = ref<MindbotConfigRow[]>([])
const schools = ref<OrgOption[]>([])

const isAdmin = computed(() => authStore.isAdmin)
const isManager = computed(() => authStore.isManager)
const managerOrgId = computed(() => {
  const raw = authStore.user?.schoolId
  if (raw == null || raw === '') {
    return NaN
  }
  const n = Number(raw)
  return Number.isFinite(n) ? n : NaN
})

const apiMindbotBase = computed(() => {
  const origin = publicSiteUrl.value.replace(/\/$/, '')
  return `${origin}/api/mindbot`
})

function callbackShared(): string {
  return `${apiMindbotBase.value}/dingtalk/callback`
}

function callbackPerOrg(organizationId: number): string {
  return `${apiMindbotBase.value}/dingtalk/orgs/${organizationId}/callback`
}

const callbackPerOrgPattern = computed(
  () => `${apiMindbotBase.value}/dingtalk/orgs/{organization_id}/callback`,
)

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formOrgId = ref<number | null>(null)

const form = ref({
  dingtalk_robot_code: '',
  dingtalk_app_secret: '',
  dingtalk_client_id: '',
  dify_api_base_url: '',
  dify_api_key: '',
  dify_inputs_json: '',
  dify_timeout_seconds: 30,
  is_enabled: true,
})

function orgLabel(org: OrgOption): string {
  const display = org.display_name?.trim()
  if (display) {
    return display
  }
  return org.name
}

function orgNameById(organizationId: number): string {
  const o = schools.value.find((x) => x.id === organizationId)
  return o ? orgLabel(o) : String(organizationId)
}

function resetForm(): void {
  form.value = {
    dingtalk_robot_code: '',
    dingtalk_app_secret: '',
    dingtalk_client_id: '',
    dify_api_base_url: '',
    dify_api_key: '',
    dify_inputs_json: '',
    dify_timeout_seconds: 30,
    is_enabled: true,
  }
  formOrgId.value = null
}

function fillForm(row: MindbotConfigRow): void {
  form.value = {
    dingtalk_robot_code: row.dingtalk_robot_code,
    dingtalk_app_secret: '',
    dingtalk_client_id: row.dingtalk_client_id ?? '',
    dify_api_base_url: row.dify_api_base_url,
    dify_api_key: '',
    dify_inputs_json: row.dify_inputs_json ?? '',
    dify_timeout_seconds: row.dify_timeout_seconds,
    is_enabled: row.is_enabled,
  }
  formOrgId.value = row.organization_id
}

const orgsWithoutConfig = computed(() => {
  const have = new Set(configs.value.map((c) => c.organization_id))
  return schools.value.filter((o) => !have.has(o.id))
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await apiRequest('/api/mindbot/admin/configs')
    if (!res.ok) {
      notify.error(t('admin.mindbot.loadError'))
      return
    }
    configs.value = (await res.json()) as MindbotConfigRow[]
    if (isAdmin.value) {
      const orgRes = await apiRequest('/api/auth/admin/organizations')
      if (orgRes.ok) {
        schools.value = (await orgRes.json()) as OrgOption[]
      } else {
        schools.value = []
      }
    }
    if (isManager.value && Number.isFinite(managerOrgId.value)) {
      const row = configs.value.find((c) => c.organization_id === managerOrgId.value)
      if (row) {
        fillForm(row)
      } else {
        resetForm()
        formOrgId.value = managerOrgId.value
      }
    }
  } catch {
    notify.error(t('admin.mindbot.loadError'))
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  dialogMode.value = 'create'
  resetForm()
  if (orgsWithoutConfig.value.length) {
    formOrgId.value = orgsWithoutConfig.value[0].id
  }
  dialogVisible.value = true
}

function openEdit(row: MindbotConfigRow): void {
  dialogMode.value = 'edit'
  fillForm(row)
  dialogVisible.value = true
}

async function save(): Promise<void> {
  const oid = formOrgId.value
  if (oid == null) {
    notify.error(t('admin.mindbot.saveError'))
    return
  }
  const isNew = !configs.value.some((c) => c.organization_id === oid)
  if (isNew) {
    if (!form.value.dingtalk_app_secret.trim() || !form.value.dify_api_key.trim()) {
      notify.error(t('admin.mindbot.saveError'))
      return
    }
  }
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      dingtalk_robot_code: form.value.dingtalk_robot_code.trim(),
      dingtalk_client_id: form.value.dingtalk_client_id.trim() || null,
      dify_api_base_url: form.value.dify_api_base_url.trim(),
      dify_timeout_seconds: form.value.dify_timeout_seconds,
      is_enabled: form.value.is_enabled,
    }
    const inputsRaw = form.value.dify_inputs_json.trim()
    if (inputsRaw) {
      payload.dify_inputs_json = inputsRaw
    } else if (!isNew) {
      payload.dify_inputs_json = null
    }
    const sec = form.value.dingtalk_app_secret.trim()
    const key = form.value.dify_api_key.trim()
    if (sec) {
      payload.dingtalk_app_secret = sec
    }
    if (key) {
      payload.dify_api_key = key
    }
    const res = await apiRequest(`/api/mindbot/admin/configs/${oid}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      notify.error(t('admin.mindbot.saveError'))
      return
    }
    notify.success(t('admin.mindbot.saved'))
    if (isAdmin.value) {
      dialogVisible.value = false
    }
    await load()
  } finally {
    saving.value = false
  }
}

async function removeRow(row: MindbotConfigRow): Promise<void> {
  try {
    await ElMessageBox.confirm(t('admin.mindbot.deleteConfirm'), {
      type: 'warning',
    })
  } catch {
    return
  }
  const res = await apiRequest(`/api/mindbot/admin/configs/${row.organization_id}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    notify.error(t('admin.mindbot.deleteError'))
    return
  }
  notify.success(t('admin.mindbot.deleted'))
  await load()
}

async function copyUrl(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    notify.success(t('admin.mindbot.copied'))
  } catch {
    notify.error(t('admin.mindbot.saveError'))
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div
    v-if="!featureMindbot"
    class="text-sm text-gray-600"
  >
    {{ t('admin.feature.mindbotHint') }}
  </div>
  <div
    v-else
    v-loading="loading"
    class="admin-mindbot-tab space-y-6 max-w-4xl"
  >
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-1">{{ t('admin.mindbot.title') }}</h2>
      <p class="text-sm text-gray-600">{{ t('admin.mindbot.intro') }}</p>
    </div>

    <div class="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-2 text-sm">
      <div class="font-medium text-gray-800">{{ t('admin.mindbot.callbackShared') }}</div>
      <div class="flex flex-wrap items-center gap-2">
        <code class="text-xs break-all flex-1 min-w-0">{{ callbackShared() }}</code>
        <el-button
          size="small"
          :icon="DocumentCopy"
          @click="copyUrl(callbackShared())"
        >
          {{ t('admin.mindbot.copyUrl') }}
        </el-button>
      </div>
      <div class="pt-2">
        <div class="font-medium text-gray-800">{{ t('admin.mindbot.callbackPerOrg') }}</div>
        <div class="flex flex-wrap items-center gap-2 mt-1">
          <code class="text-xs break-all flex-1 min-w-0">{{ callbackPerOrgPattern }}</code>
          <el-button
            v-if="configs.length === 1"
            size="small"
            :icon="DocumentCopy"
            @click="copyUrl(callbackPerOrg(configs[0].organization_id))"
          >
            {{ t('admin.mindbot.copyUrl') }}
          </el-button>
        </div>
      </div>
    </div>

    <template v-if="isAdmin">
      <div class="flex justify-end">
        <el-button
          type="primary"
          :disabled="orgsWithoutConfig.length === 0"
          @click="openCreate"
        >
          {{ t('admin.mindbot.create') }}
        </el-button>
      </div>
      <el-table
        :data="configs"
        stripe
        style="width: 100%"
      >
        <el-table-column
          prop="organization_id"
          :label="t('admin.mindbot.colOrg')"
          min-width="160"
        >
          <template #default="{ row }">
            {{ orgNameById(row.organization_id) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="dingtalk_robot_code"
          :label="t('admin.mindbot.colRobot')"
          min-width="140"
        />
        <el-table-column
          prop="is_enabled"
          :label="t('admin.mindbot.colEnabled')"
          width="100"
        >
          <template #default="{ row }">
            <span>{{ row.is_enabled ? '✓' : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.library.colActions')"
          width="200"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              @click="openEdit(row)"
            >
              {{ t('admin.mindbot.edit') }}
            </el-button>
            <el-button
              link
              type="danger"
              @click="removeRow(row)"
            >
              {{ t('admin.mindbot.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-dialog
        v-model="dialogVisible"
        :title="dialogMode === 'create' ? t('admin.mindbot.create') : t('admin.mindbot.edit')"
        width="min(520px, 92vw)"
        destroy-on-close
        @closed="resetForm"
      >
        <el-form
          label-position="top"
          class="space-y-2"
        >
          <el-form-item
            v-if="dialogMode === 'create'"
            :label="t('admin.mindbot.orgSelect')"
          >
            <el-select
              v-model="formOrgId"
              class="w-full"
              filterable
            >
              <el-option
                v-for="o in orgsWithoutConfig"
                :key="o.id"
                :label="orgLabel(o)"
                :value="o.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.dingtalkRobotCode')">
            <el-input v-model="form.dingtalk_robot_code" />
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.dingtalkAppSecret')">
            <el-input
              v-model="form.dingtalk_app_secret"
              type="password"
              show-password
              autocomplete="new-password"
            />
            <div class="text-xs text-gray-500 mt-1">{{ t('admin.mindbot.dingtalkAppSecretHint') }}</div>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.dingtalkClientId')">
            <el-input v-model="form.dingtalk_client_id" />
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyBaseUrl')">
            <el-input v-model="form.dify_api_base_url" />
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyApiKey')">
            <el-input
              v-model="form.dify_api_key"
              type="password"
              show-password
              autocomplete="new-password"
            />
            <div class="text-xs text-gray-500 mt-1">{{ t('admin.mindbot.difyApiKeyHint') }}</div>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyInputsJson')">
            <el-input
              v-model="form.dify_inputs_json"
              type="textarea"
              :rows="3"
              class="font-mono text-sm"
            />
            <div class="text-xs text-gray-500 mt-1">{{ t('admin.mindbot.difyInputsJsonHint') }}</div>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyTimeout')">
            <el-input-number
              v-model="form.dify_timeout_seconds"
              :min="5"
              :max="120"
            />
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.enabled')">
            <el-switch v-model="form.is_enabled" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">{{ t('admin.cancel') }}</el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="save"
          >
            {{ t('admin.mindbot.save') }}
          </el-button>
        </template>
      </el-dialog>
    </template>

    <template v-else-if="isManager">
      <el-alert
        v-if="!Number.isFinite(managerOrgId)"
        type="warning"
        :closable="false"
        :title="t('admin.mindbot.managerNoOrg')"
      />
      <el-form
        v-else
        label-position="top"
        class="max-w-xl space-y-2"
      >
        <el-form-item :label="t('admin.mindbot.dingtalkRobotCode')">
          <el-input v-model="form.dingtalk_robot_code" />
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.dingtalkAppSecret')">
          <el-input
            v-model="form.dingtalk_app_secret"
            type="password"
            show-password
            autocomplete="new-password"
          />
          <div class="text-xs text-gray-500 mt-1">{{ t('admin.mindbot.dingtalkAppSecretHint') }}</div>
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.dingtalkClientId')">
          <el-input v-model="form.dingtalk_client_id" />
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.difyBaseUrl')">
          <el-input v-model="form.dify_api_base_url" />
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.difyApiKey')">
          <el-input
            v-model="form.dify_api_key"
            type="password"
            show-password
            autocomplete="new-password"
          />
          <div class="text-xs text-gray-500 mt-1">{{ t('admin.mindbot.difyApiKeyHint') }}</div>
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.difyInputsJson')">
          <el-input
            v-model="form.dify_inputs_json"
            type="textarea"
            :rows="3"
            class="font-mono text-sm"
          />
          <div class="text-xs text-gray-500 mt-1">{{ t('admin.mindbot.difyInputsJsonHint') }}</div>
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.difyTimeout')">
          <el-input-number
            v-model="form.dify_timeout_seconds"
            :min="5"
            :max="120"
          />
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.enabled')">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="saving"
            @click="save"
          >
            {{ t('admin.mindbot.save') }}
          </el-button>
        </el-form-item>
      </el-form>
    </template>
  </div>
</template>
