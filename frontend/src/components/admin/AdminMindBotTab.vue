<script setup lang="ts">
/**
 * Admin — MindBot: per-organization DingTalk HTTP robot + Dify.
 */
import { computed, onMounted, ref } from 'vue'

import { DocumentCopy, Plus } from '@element-plus/icons-vue'
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
  public_callback_token: string
  dingtalk_robot_code: string
  dingtalk_app_secret_masked: string
  dify_api_key_masked: string
  dingtalk_client_id: string | null
  dingtalk_event_token_set: boolean
  dingtalk_event_aes_key_set: boolean
  dingtalk_event_owner_key: string | null
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

function buildCallbackUrlByToken(token: string): string {
  const tok = token.trim()
  return `${apiMindbotBase.value}/dingtalk/callback/t/${encodeURIComponent(tok)}`
}

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formOrgId = ref<number | null>(null)
/** True when user chose to type a new DingTalk / Dify secret (edit mode). */
const dingtalkSecretReplaceMode = ref(false)
const difyApiKeyReplaceMode = ref(false)

const form = ref({
  dingtalk_robot_code: '',
  dingtalk_app_secret: '',
  dify_api_base_url: '',
  dify_api_key: '',
  dify_inputs_json: '',
  dify_timeout_seconds: 300,
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
    dify_api_base_url: '',
    dify_api_key: '',
    dify_inputs_json: '',
    dify_timeout_seconds: 300,
    is_enabled: true,
  }
  formOrgId.value = null
  dingtalkSecretReplaceMode.value = false
  difyApiKeyReplaceMode.value = false
}

function fillForm(row: MindbotConfigRow): void {
  form.value = {
    dingtalk_robot_code: row.dingtalk_robot_code,
    dingtalk_app_secret: '',
    dify_api_base_url: row.dify_api_base_url,
    dify_api_key: '',
    dify_inputs_json: row.dify_inputs_json ?? '',
    dify_timeout_seconds: row.dify_timeout_seconds,
    is_enabled: row.is_enabled,
  }
  formOrgId.value = row.organization_id
  dingtalkSecretReplaceMode.value = !row.dingtalk_app_secret_masked
  difyApiKeyReplaceMode.value = !row.dify_api_key_masked
}

function startReplaceDingtalkSecret(): void {
  dingtalkSecretReplaceMode.value = true
  form.value.dingtalk_app_secret = ''
}

function startReplaceDifyApiKey(): void {
  difyApiKeyReplaceMode.value = true
  form.value.dify_api_key = ''
}

const orgsWithoutConfig = computed(() => {
  const have = new Set(configs.value.map((c) => c.organization_id))
  return schools.value.filter((o) => !have.has(o.id))
})

const editingOrgRow = computed(() => {
  const oid = formOrgId.value
  if (oid == null) {
    return undefined
  }
  return configs.value.find((c) => c.organization_id === oid)
})

/** Manager create dialog: prefer profile school name (schools list may be empty). */
const managerSchoolDisplayName = computed(() => {
  const fromProfile = authStore.user?.schoolName?.trim()
  if (fromProfile) {
    return fromProfile
  }
  if (Number.isFinite(managerOrgId.value)) {
    return orgNameById(managerOrgId.value)
  }
  return '—'
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

function openManagerMindbotDialog(): void {
  if (!Number.isFinite(managerOrgId.value)) {
    return
  }
  const row = configs.value.find((c) => c.organization_id === managerOrgId.value)
  if (row) {
    dialogMode.value = 'edit'
    fillForm(row)
  } else {
    dialogMode.value = 'create'
    resetForm()
    formOrgId.value = managerOrgId.value
  }
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
    if (isNew) {
      const sec = form.value.dingtalk_app_secret.trim()
      const key = form.value.dify_api_key.trim()
      if (sec) {
        payload.dingtalk_app_secret = sec
      }
      if (key) {
        payload.dify_api_key = key
      }
    } else {
      if (dingtalkSecretReplaceMode.value) {
        const sec = form.value.dingtalk_app_secret.trim()
        if (sec) {
          payload.dingtalk_app_secret = sec
        }
      }
      if (difyApiKeyReplaceMode.value) {
        const key = form.value.dify_api_key.trim()
        if (key) {
          payload.dify_api_key = key
        }
      }
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
    dialogVisible.value = false
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
    class="text-sm text-gray-600 dark:text-gray-400"
  >
    {{ t('admin.feature.mindbotHint') }}
  </div>
  <div
    v-else
    v-loading="loading"
    class="admin-mindbot-tab pt-4 max-w-4xl"
  >
    <template v-if="isAdmin">
      <el-card
        shadow="never"
        class="border border-gray-200 dark:border-gray-700"
      >
        <template #header>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0 space-y-1">
              <span class="text-sm font-medium text-gray-900 dark:text-gray-100">
                {{ t('admin.mindbot.title') }}
              </span>
              <p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400 font-normal">
                {{ t('admin.mindbot.introHttpOnly') }}
              </p>
            </div>
            <el-button
              type="primary"
              size="small"
              class="shrink-0 self-start"
              :disabled="orgsWithoutConfig.length === 0"
              @click="openCreate"
            >
              <el-icon class="mr-1"><Plus /></el-icon>
              {{ t('admin.mindbot.create') }}
            </el-button>
          </div>
        </template>

        <div
          v-if="!loading && configs.length === 0"
          class="rounded-md border border-dashed border-gray-200 dark:border-gray-600 py-14 px-4 text-center"
        >
          <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
            {{ t('admin.mindbot.emptyState') }}
          </p>
          <el-button
            type="primary"
            size="small"
            :disabled="orgsWithoutConfig.length === 0"
            @click="openCreate"
          >
            <el-icon class="mr-1"><Plus /></el-icon>
            {{ t('admin.mindbot.create') }}
          </el-button>
        </div>
        <el-table
          v-else-if="configs.length > 0"
          :data="configs"
          stripe
          size="small"
          class="w-full"
        >
          <el-table-column
            prop="organization_id"
            :label="t('admin.mindbot.colOrg')"
            min-width="160"
          >
            <template #default="{ row }">
              <span class="text-gray-900 dark:text-gray-100">{{ orgNameById(row.organization_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="dingtalk_robot_code"
            :label="t('admin.mindbot.colRobot')"
            min-width="140"
          >
            <template #default="{ row }">
              <code class="text-xs font-mono text-gray-800 dark:text-gray-200">{{ row.dingtalk_robot_code }}</code>
            </template>
          </el-table-column>
          <el-table-column
            prop="is_enabled"
            :label="t('admin.mindbot.colEnabled')"
            width="110"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.is_enabled ? 'success' : 'info'"
                size="small"
                effect="plain"
              >
                {{ row.is_enabled ? t('admin.enabled') : t('admin.disabled') }}
              </el-tag>
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
                size="small"
                @click="openEdit(row)"
              >
                {{ t('admin.mindbot.edit') }}
              </el-button>
              <el-button
                link
                type="danger"
                size="small"
                @click="removeRow(row)"
              >
                {{ t('admin.mindbot.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <template v-else-if="isManager">
      <el-card
        shadow="never"
        class="border border-gray-200 dark:border-gray-700"
      >
        <template #header>
          <span class="text-sm font-medium text-gray-900 dark:text-gray-100">
            {{ t('admin.mindbot.title') }}
          </span>
        </template>
        <el-alert
          v-if="!Number.isFinite(managerOrgId)"
          type="warning"
          :closable="false"
          :title="t('admin.mindbot.managerNoOrg')"
          class="!items-start"
        />
        <div
          v-else
          class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <p class="text-sm text-gray-600 dark:text-gray-400 max-w-xl leading-relaxed">
            {{ t('admin.mindbot.managerIntro') }}
          </p>
          <el-button
            type="primary"
            size="small"
            class="shrink-0"
            @click="openManagerMindbotDialog"
          >
            {{ t('admin.mindbot.openSettings') }}
          </el-button>
        </div>
      </el-card>
    </template>

    <el-dialog
      v-if="isAdmin || isManager"
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? t('admin.mindbot.create') : t('admin.mindbot.edit')"
      width="min(520px, 94vw)"
      destroy-on-close
      append-to-body
      align-center
      @closed="resetForm"
    >
      <el-form
        label-position="top"
        class="space-y-1"
      >
        <div
          v-if="dialogMode === 'edit' && editingOrgRow?.public_callback_token"
          class="mb-5 rounded-md border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-700 dark:bg-neutral-900/40"
        >
          <div class="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">
            {{ t('admin.mindbot.schoolCallbackUrl') }}
          </div>
          <p class="text-xs text-gray-600 dark:text-gray-400 mb-3 leading-relaxed">
            {{ t('admin.mindbot.schoolCallbackUrlHint') }}
          </p>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
            <code
              class="block flex-1 min-w-0 break-all rounded border border-neutral-200 bg-white px-2.5 py-2 text-xs font-mono text-gray-900 dark:border-neutral-600 dark:bg-neutral-950 dark:text-neutral-100"
            >{{ buildCallbackUrlByToken(editingOrgRow.public_callback_token) }}</code>
            <el-button
              size="small"
              class="shrink-0"
              :icon="DocumentCopy"
              @click="copyUrl(buildCallbackUrlByToken(editingOrgRow.public_callback_token))"
            >
              {{ t('admin.mindbot.copyUrl') }}
            </el-button>
          </div>
        </div>
        <div
          v-else-if="dialogMode === 'create'"
          class="mb-5 rounded-md border border-amber-200/80 bg-amber-50/80 px-3 py-2.5 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100/90 leading-relaxed"
        >
          {{ t('admin.mindbot.callbackUrlAfterSave') }}
        </div>

        <el-form-item
          v-if="dialogMode === 'create' && isAdmin"
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

        <div class="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2 mt-1">
          {{ t('admin.mindbot.sectionDingTalk') }}
        </div>
        <el-form-item
          v-if="dialogMode === 'create' && !isAdmin"
          class="!mb-2"
        >
          <template #label>
            <span class="text-sm font-normal text-gray-700 dark:text-gray-300">{{ t('admin.mindbot.orgSelect') }}</span>
          </template>
          <span class="text-sm text-gray-900 dark:text-gray-100">{{ managerSchoolDisplayName }}</span>
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.dingtalkRobotCode')">
          <el-input
            v-model="form.dingtalk_robot_code"
            clearable
          />
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.dingtalkAppSecret')">
          <div
            v-if="
              dialogMode === 'edit'
                && editingOrgRow?.dingtalk_app_secret_masked
                && !dingtalkSecretReplaceMode
            "
            class="flex flex-col gap-2 sm:flex-row sm:items-stretch sm:gap-2"
          >
            <el-input
              :model-value="editingOrgRow.dingtalk_app_secret_masked"
              type="text"
              readonly
              class="font-mono text-sm flex-1 min-w-0"
            />
            <el-button
              class="shrink-0"
              size="small"
              @click="startReplaceDingtalkSecret"
            >
              {{ t('admin.mindbot.replaceSecret') }}
            </el-button>
          </div>
          <el-input
            v-else
            v-model="form.dingtalk_app_secret"
            type="password"
            show-password
            autocomplete="new-password"
            clearable
          />
          <div class="text-xs text-gray-500 dark:text-gray-400 mt-1.5 leading-relaxed">
            <template v-if="dialogMode === 'create'">
              {{ t('admin.mindbot.dingtalkAppSecretHint') }}
            </template>
            <template
              v-else-if="
                editingOrgRow?.dingtalk_app_secret_masked && !dingtalkSecretReplaceMode
              "
            >
              {{ t('admin.mindbot.dingtalkAppSecretMaskedHint') }}
            </template>
            <template v-else>
              {{ t('admin.mindbot.dingtalkAppSecretReplaceHint') }}
            </template>
          </div>
        </el-form-item>

        <el-divider class="!my-5" />

        <div class="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
          {{ t('admin.mindbot.sectionDify') }}
        </div>
        <el-form-item :label="t('admin.mindbot.difyBaseUrl')">
          <el-input
            v-model="form.dify_api_base_url"
            clearable
          />
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.difyApiKey')">
          <div
            v-if="
              dialogMode === 'edit'
                && editingOrgRow?.dify_api_key_masked
                && !difyApiKeyReplaceMode
            "
            class="flex flex-col gap-2 sm:flex-row sm:items-stretch sm:gap-2"
          >
            <el-input
              :model-value="editingOrgRow.dify_api_key_masked"
              type="text"
              readonly
              class="font-mono text-sm flex-1 min-w-0"
            />
            <el-button
              class="shrink-0"
              size="small"
              @click="startReplaceDifyApiKey"
            >
              {{ t('admin.mindbot.replaceSecret') }}
            </el-button>
          </div>
          <el-input
            v-else
            v-model="form.dify_api_key"
            type="password"
            show-password
            autocomplete="new-password"
            clearable
          />
          <div class="text-xs text-gray-500 dark:text-gray-400 mt-1.5 leading-relaxed">
            <template v-if="dialogMode === 'create'">
              {{ t('admin.mindbot.difyApiKeyHint') }}
            </template>
            <template
              v-else-if="editingOrgRow?.dify_api_key_masked && !difyApiKeyReplaceMode"
            >
              {{ t('admin.mindbot.difyApiKeyMaskedHint') }}
            </template>
            <template v-else>
              {{ t('admin.mindbot.difyApiKeyReplaceHint') }}
            </template>
          </div>
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.difyInputsJson')">
          <el-input
            v-model="form.dify_inputs_json"
            type="textarea"
            :rows="3"
            class="font-mono text-sm"
          />
          <div class="text-xs text-gray-500 dark:text-gray-400 mt-1.5 leading-relaxed">
            {{ t('admin.mindbot.difyInputsJsonHint') }}
          </div>
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.difyTimeout')">
          <el-input-number
            v-model="form.dify_timeout_seconds"
            :min="5"
            :max="600"
            class="w-full sm:w-40"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item :label="t('admin.mindbot.enabled')">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <el-button @click="dialogVisible = false">{{ t('admin.cancel') }}</el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="save"
          >
            {{ t('admin.mindbot.save') }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
