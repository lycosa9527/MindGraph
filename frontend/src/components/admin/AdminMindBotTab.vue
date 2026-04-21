<script setup lang="ts">
/**
 * Admin — MindBot: per-organization DingTalk HTTP robot + Dify.
 */
import { computed, onMounted, ref } from 'vue'

import { ElMessageBox } from 'element-plus'

import AdminMindBotConfigDialog from '@/components/admin/AdminMindBotConfigDialog.vue'
import type {
  MindbotConfigFormState,
  MindbotConfigRow,
  OrgOption,
} from '@/components/admin/mindbotConfigTypes'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAuthStore } from '@/stores/auth'
import { apiRequest } from '@/utils/apiClient'
import { maskSensitiveDisplay } from '@/utils/sensitiveMask'

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { publicSiteUrl } = usePublicSiteUrl()
const { featureMindbot } = useFeatureFlags()

const BOT_CAP = 5

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
const rotating = ref(false)
const moveDialogVisible = ref(false)
const moveSourceRow = ref<MindbotConfigRow | null>(null)
const moveTargetOrgId = ref<number | null>(null)
const moveSubmitting = ref(false)
const formOrgId = ref<number | null>(null)
/** Config PK of the row being edited; null when creating a new bot. */
const editingConfigId = ref<number | null>(null)
/** True when user chose to type a new DingTalk / Dify secret (edit mode). */
const dingtalkSecretReplaceMode = ref(false)
const difyApiKeyReplaceMode = ref(false)

const form = ref<MindbotConfigFormState>({
  bot_label: '',
  dingtalk_robot_code: '',
  dingtalk_client_id: '',
  dingtalk_app_secret: '',
  dify_api_base_url: '',
  dify_api_key: '',
  dify_inputs_json: '',
  dify_timeout_seconds: 300,
  show_chain_of_thought: false,
  chain_of_thought_max_chars: 4000,
  dingtalk_ai_card_template_id: '',
  dingtalk_ai_card_param_key: '',
  dingtalk_ai_card_streaming_max_chars: 6500,
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

/** Organizations that can receive this bot (under per-school cap, excluding source). */
function getValidMoveTargets(sourceOrgId: number): OrgOption[] {
  const counts = new Map<number, number>()
  for (const c of configs.value) {
    counts.set(c.organization_id, (counts.get(c.organization_id) ?? 0) + 1)
  }
  return schools.value.filter((o) => {
    if (o.id === sourceOrgId) {
      return false
    }
    return (counts.get(o.id) ?? 0) < BOT_CAP
  })
}

function canMoveBot(row: MindbotConfigRow): boolean {
  return getValidMoveTargets(row.organization_id).length > 0
}

const moveTargetOptions = computed(() => {
  const r = moveSourceRow.value
  if (r == null) {
    return []
  }
  return getValidMoveTargets(r.organization_id)
})

function openMoveDialog(row: MindbotConfigRow): void {
  moveSourceRow.value = row
  const opts = getValidMoveTargets(row.organization_id)
  moveTargetOrgId.value = opts[0]?.id ?? null
  moveDialogVisible.value = true
}

function onMoveDialogClosed(): void {
  moveSourceRow.value = null
  moveTargetOrgId.value = null
}

async function confirmMoveBot(): Promise<void> {
  const row = moveSourceRow.value
  const oid = moveTargetOrgId.value
  if (row == null || oid == null) {
    notify.error(t('admin.mindbot.moveError'))
    return
  }
  moveSubmitting.value = true
  try {
    const res = await apiRequest(`/api/mindbot/admin/configs/${row.id}/move`, {
      method: 'POST',
      body: JSON.stringify({ organization_id: oid }),
    })
    if (!res.ok) {
      notify.error(t('admin.mindbot.moveError'))
      return
    }
    notify.success(t('admin.mindbot.moveSuccess'))
    moveDialogVisible.value = false
    await load()
  } finally {
    moveSubmitting.value = false
  }
}

function resetForm(): void {
  form.value = {
    bot_label: '',
    dingtalk_robot_code: '',
    dingtalk_client_id: '',
    dingtalk_app_secret: '',
    dify_api_base_url: '',
    dify_api_key: '',
    dify_inputs_json: '',
    dify_timeout_seconds: 300,
    show_chain_of_thought: false,
    chain_of_thought_max_chars: 4000,
    dingtalk_ai_card_template_id: '',
    dingtalk_ai_card_param_key: '',
    dingtalk_ai_card_streaming_max_chars: 6500,
    is_enabled: true,
  }
  formOrgId.value = null
  editingConfigId.value = null
  dingtalkSecretReplaceMode.value = false
  difyApiKeyReplaceMode.value = false
}

function fillForm(row: MindbotConfigRow): void {
  form.value = {
    bot_label: row.bot_label ?? '',
    dingtalk_robot_code: row.dingtalk_robot_code,
    dingtalk_client_id: row.dingtalk_client_id ?? '',
    dingtalk_app_secret: '',
    dify_api_base_url: row.dify_api_base_url,
    dify_api_key: '',
    dify_inputs_json: row.dify_inputs_json ?? '',
    dify_timeout_seconds: row.dify_timeout_seconds,
    show_chain_of_thought:
      Boolean(row.show_chain_of_thought_oto) ||
      Boolean(row.show_chain_of_thought_internal_group) ||
      Boolean(row.show_chain_of_thought_cross_org_group),
    chain_of_thought_max_chars: row.chain_of_thought_max_chars,
    dingtalk_ai_card_template_id: row.dingtalk_ai_card_template_id ?? '',
    dingtalk_ai_card_param_key: row.dingtalk_ai_card_param_key ?? '',
    dingtalk_ai_card_streaming_max_chars: row.dingtalk_ai_card_streaming_max_chars,
    is_enabled: row.is_enabled,
  }
  formOrgId.value = row.organization_id
  editingConfigId.value = row.id
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

/** Schools that have not yet reached the 5-bot cap. */
const orgsUnderLimit = computed(() => {
  const counts = new Map<number, number>()
  for (const c of configs.value) {
    counts.set(c.organization_id, (counts.get(c.organization_id) ?? 0) + 1)
  }
  return schools.value.filter((o) => (counts.get(o.id) ?? 0) < BOT_CAP)
})

const editingRow = computed(() => {
  const cid = editingConfigId.value
  if (cid == null) {
    return undefined
  }
  return configs.value.find((c) => c.id === cid)
})

const canLoadUsage = computed(() => dialogMode.value === 'edit' && editingConfigId.value != null)

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

/** School name for the MindBot dialog header (钉钉机器人【name】). */
const mindbotDialogSchoolDisplayName = computed(() => {
  const oid = formOrgId.value
  if (oid == null) {
    return ''
  }
  const match = schools.value.find((x) => x.id === oid)
  if (match) {
    return orgLabel(match)
  }
  if (!isAdmin.value) {
    const m = managerSchoolDisplayName.value.trim()
    if (m && m !== '—') {
      return m
    }
  }
  return String(oid)
})

async function loadAllConfigs(): Promise<MindbotConfigRow[]> {
  const PAGE_SIZE = 200
  const all: MindbotConfigRow[] = []
  let afterId: number | null = null
  for (;;) {
    const url =
      afterId == null
        ? `/api/mindbot/admin/configs?limit=${PAGE_SIZE}`
        : `/api/mindbot/admin/configs?limit=${PAGE_SIZE}&after_id=${afterId}`
    const res = await apiRequest(url)
    if (!res.ok) {
      throw new Error('configs_fetch_failed')
    }
    const page = (await res.json()) as MindbotConfigRow[]
    all.push(...page)
    if (page.length < PAGE_SIZE) {
      break
    }
    afterId = page[page.length - 1].id
  }
  return all
}

async function load(): Promise<void> {
  loading.value = true
  try {
    configs.value = await loadAllConfigs()
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
  if (orgsUnderLimit.value.length) {
    formOrgId.value = orgsUnderLimit.value[0].id
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

async function createConfig(): Promise<void> {
  const oid = formOrgId.value
  if (oid == null) {
    notify.error(t('admin.mindbot.saveError'))
    return
  }
  if (!form.value.dingtalk_app_secret.trim() || !form.value.dify_api_key.trim()) {
    notify.error(t('admin.mindbot.saveError'))
    return
  }
  saving.value = true
  try {
    const inputsRaw = form.value.dify_inputs_json.trim()
    const payload: Record<string, unknown> = {
      organization_id: oid,
      bot_label: form.value.bot_label.trim() || null,
      dingtalk_robot_code: form.value.dingtalk_robot_code.trim(),
      dingtalk_client_id: form.value.dingtalk_client_id.trim() || null,
      dingtalk_app_secret: form.value.dingtalk_app_secret.trim(),
      dify_api_base_url: form.value.dify_api_base_url.trim(),
      dify_api_key: form.value.dify_api_key.trim(),
      dify_inputs_json: inputsRaw || null,
      dify_timeout_seconds: form.value.dify_timeout_seconds,
      show_chain_of_thought_oto: form.value.show_chain_of_thought,
      show_chain_of_thought_internal_group: form.value.show_chain_of_thought,
      show_chain_of_thought_cross_org_group: form.value.show_chain_of_thought,
      chain_of_thought_max_chars: form.value.chain_of_thought_max_chars,
      dingtalk_ai_card_template_id: form.value.dingtalk_ai_card_template_id.trim() || null,
      dingtalk_ai_card_param_key: form.value.dingtalk_ai_card_param_key.trim() || null,
      dingtalk_ai_card_streaming_max_chars: form.value.dingtalk_ai_card_streaming_max_chars,
      is_enabled: form.value.is_enabled,
    }
    const res = await apiRequest('/api/mindbot/admin/configs', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      notify.error(t('admin.mindbot.saveError'))
      return
    }
    const saved = (await res.json()) as MindbotConfigRow
    notify.success(t('admin.mindbot.saved'))
    await load()
    const row = configs.value.find((c) => c.id === saved.id) ?? saved
    fillForm(row)
    dialogMode.value = 'edit'
  } finally {
    saving.value = false
  }
}

async function updateConfig(): Promise<void> {
  const cid = editingConfigId.value
  if (cid == null) {
    notify.error(t('admin.mindbot.saveError'))
    return
  }
  saving.value = true
  try {
    const inputsRaw = form.value.dify_inputs_json.trim()
    const payload: Record<string, unknown> = {
      bot_label: form.value.bot_label.trim() || null,
      dingtalk_robot_code: form.value.dingtalk_robot_code.trim(),
      dingtalk_client_id: form.value.dingtalk_client_id.trim() || null,
      dify_api_base_url: form.value.dify_api_base_url.trim(),
      dify_inputs_json: inputsRaw || null,
      dify_timeout_seconds: form.value.dify_timeout_seconds,
      show_chain_of_thought_oto: form.value.show_chain_of_thought,
      show_chain_of_thought_internal_group: form.value.show_chain_of_thought,
      show_chain_of_thought_cross_org_group: form.value.show_chain_of_thought,
      chain_of_thought_max_chars: form.value.chain_of_thought_max_chars,
      dingtalk_ai_card_template_id: form.value.dingtalk_ai_card_template_id.trim() || null,
      dingtalk_ai_card_param_key: form.value.dingtalk_ai_card_param_key.trim() || null,
      dingtalk_ai_card_streaming_max_chars: form.value.dingtalk_ai_card_streaming_max_chars,
      is_enabled: form.value.is_enabled,
    }
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
    const res = await apiRequest(`/api/mindbot/admin/configs/${cid}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      notify.error(t('admin.mindbot.saveError'))
      return
    }
    const saved = (await res.json()) as MindbotConfigRow
    notify.success(t('admin.mindbot.saved'))
    await load()
    const row = configs.value.find((c) => c.id === saved.id) ?? saved
    fillForm(row)
    dialogMode.value = 'edit'
  } finally {
    saving.value = false
  }
}

async function save(): Promise<void> {
  if (dialogMode.value === 'create') {
    await createConfig()
  } else {
    await updateConfig()
  }
}

async function rotateCallbackUrl(): Promise<void> {
  const cid = editingConfigId.value
  if (cid == null) {
    return
  }
  try {
    await ElMessageBox.confirm(t('admin.mindbot.rotateConfirm'), t('admin.mindbot.rotateConfirmTitle'), {
      type: 'warning',
      customClass: 'mindbot-swiss-message-box mindbot-swiss-msg--rotate',
      modalClass: 'mindbot-swiss-backdrop',
      cancelButtonClass: 'mindbot-pill mindbot-pill--footer-cancel',
      showClose: true,
    })
  } catch {
    return
  }
  rotating.value = true
  try {
    const res = await apiRequest(`/api/mindbot/admin/configs/${cid}/rotate-callback-token`, {
      method: 'POST',
    })
    if (!res.ok) {
      notify.error(t('admin.mindbot.loadError'))
      return
    }
    const row = (await res.json()) as MindbotConfigRow
    const idx = configs.value.findIndex((c) => c.id === cid)
    if (idx >= 0) {
      configs.value[idx] = row
    }
    fillForm(row)
    notify.success(t('admin.mindbot.callbackRotated'))
  } finally {
    rotating.value = false
  }
}

async function removeRow(row: MindbotConfigRow): Promise<void> {
  try {
    await ElMessageBox.confirm(t('admin.mindbot.deleteConfirm'), t('admin.mindbot.deleteConfirmTitle'), {
      type: 'warning',
      customClass: 'mindbot-swiss-message-box mindbot-swiss-msg--delete',
      modalClass: 'mindbot-swiss-backdrop',
      cancelButtonClass: 'mindbot-pill mindbot-pill--footer-cancel',
      showClose: true,
    })
  } catch {
    return
  }
  const res = await apiRequest(`/api/mindbot/admin/configs/${row.id}`, {
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

const isAddBotDisabled = computed(() => loading.value || orgsUnderLimit.value.length === 0)

defineExpose({
  openCreate,
  isAddSchoolDisabled: isAddBotDisabled,
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
          <div class="min-w-0 space-y-1">
            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">
              {{ t('admin.mindbot.title') }}
            </span>
            <p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400 font-normal">
              {{ t('admin.mindbot.introHttpOnly') }}
            </p>
          </div>
        </template>

        <div
          v-if="!loading && configs.length === 0"
          class="rounded-md border border-dashed border-gray-200 dark:border-gray-600 py-14 px-4 text-center"
        >
          <p class="text-sm text-gray-500 dark:text-gray-400">
            {{ t('admin.mindbot.emptyState') }}
          </p>
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
            min-width="140"
          >
            <template #default="{ row }">
              <span class="text-gray-900 dark:text-gray-100">{{
                orgNameById(row.organization_id)
              }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="bot_label"
            :label="t('admin.mindbot.colBotLabel')"
            min-width="120"
          >
            <template #default="{ row }">
              <span class="text-gray-700 dark:text-gray-300">{{
                row.bot_label || '—'
              }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="dingtalk_robot_code"
            :label="t('admin.mindbot.colRobot')"
            min-width="130"
          >
            <template #default="{ row }">
              <code class="text-xs font-mono text-gray-800 dark:text-gray-200">{{
                maskSensitiveDisplay(row.dingtalk_robot_code)
              }}</code>
            </template>
          </el-table-column>
          <el-table-column
            prop="is_enabled"
            :label="t('admin.mindbot.colEnabled')"
            width="100"
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
            width="300"
            fixed="right"
          >
            <template #default="{ row }">
              <div class="flex flex-wrap items-center gap-2">
                <el-button
                  type="primary"
                  size="small"
                  plain
                  class="mindbot-pill mindbot-pill--table-edit"
                  @click="openEdit(row)"
                >
                  {{ t('admin.mindbot.edit') }}
                </el-button>
                <el-tooltip
                  :disabled="canMoveBot(row)"
                  :content="t('admin.mindbot.moveNoTargets')"
                  placement="top"
                >
                  <span class="inline-block">
                    <el-button
                      type="warning"
                      size="small"
                      plain
                      class="mindbot-pill mindbot-pill--table-move"
                      :disabled="!canMoveBot(row)"
                      @click="openMoveDialog(row)"
                    >
                      {{ t('admin.mindbot.move') }}
                    </el-button>
                  </span>
                </el-tooltip>
                <el-button
                  type="danger"
                  size="small"
                  plain
                  class="mindbot-pill mindbot-pill--table-delete"
                  @click="removeRow(row)"
                >
                  {{ t('admin.mindbot.delete') }}
                </el-button>
              </div>
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
          <div class="min-w-0 space-y-1">
            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">
              {{ t('admin.mindbot.title') }}
            </span>
            <p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400 font-normal">
              {{ t('admin.mindbot.managerReadOnlyIntro') }}
            </p>
          </div>
        </template>
        <el-alert
          v-if="!Number.isFinite(managerOrgId)"
          type="warning"
          :closable="false"
          :title="t('admin.mindbot.managerNoOrg')"
          class="!items-start"
        />
        <template v-else>
          <div
            v-if="!loading && configs.length === 0"
            class="rounded-md border border-dashed border-gray-200 dark:border-gray-600 py-14 px-4 text-center"
          >
            <p class="text-sm text-gray-500 dark:text-gray-400">
              {{ t('admin.mindbot.managerNoConfig') }}
            </p>
          </div>
          <el-table
            v-else-if="configs.length > 0"
            :data="configs"
            stripe
            size="small"
            class="w-full"
          >
            <el-table-column
              prop="bot_label"
              :label="t('admin.mindbot.colBotLabel')"
              min-width="120"
            >
              <template #default="{ row }">
                <span class="text-gray-700 dark:text-gray-300">{{ row.bot_label || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column
              prop="dingtalk_robot_code"
              :label="t('admin.mindbot.colRobot')"
              min-width="130"
            >
              <template #default="{ row }">
                <code class="text-xs font-mono text-gray-800 dark:text-gray-200">{{
                  maskSensitiveDisplay(row.dingtalk_robot_code)
                }}</code>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('admin.mindbot.schoolCallbackUrl')"
              min-width="260"
            >
              <template #default="{ row }">
                <div class="flex items-center gap-2 min-w-0">
                  <code class="text-xs font-mono text-gray-600 dark:text-gray-400 truncate">
                    {{ buildCallbackUrlByToken(row.public_callback_token) }}
                  </code>
                  <el-button
                    size="small"
                    plain
                    class="mindbot-pill shrink-0"
                    @click="copyUrl(buildCallbackUrlByToken(row.public_callback_token))"
                  >
                    {{ t('admin.mindbot.copyUrl') }}
                  </el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              prop="is_enabled"
              :label="t('admin.mindbot.colEnabled')"
              width="100"
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
          </el-table>
        </template>
      </el-card>
    </template>

    <el-dialog
      v-model="moveDialogVisible"
      class="mindbot-settings-dialog mindbot-swiss-dialog mindbot-move-dialog"
      width="min(480px, 94vw)"
      destroy-on-close
      append-to-body
      align-center
      modal-class="mindbot-swiss-backdrop"
      :show-close="true"
      @closed="onMoveDialogClosed"
    >
      <template #header>
        <div class="mindbot-swiss-header mindbot-config-header">
          <span class="mindbot-swiss-header__glyph">◇</span>
          <span class="mindbot-swiss-header__title">{{ t('admin.mindbot.move') }}</span>
          <span
            class="mindbot-swiss-header__divider"
            aria-hidden="true"
            >·</span
          >
          <span class="mindbot-swiss-header__note">{{ t('admin.mindbot.moveTitle') }}</span>
        </div>
      </template>
      <div class="mindbot-config-body">
        <div
          class="mindbot-config-scanlines"
          aria-hidden="true"
        />
        <div class="mindbot-swiss-form-wrap">
          <p class="mindbot-swiss-hint text-xs mb-4 leading-relaxed">
            {{ t('admin.mindbot.moveIntro') }}
          </p>
          <div class="flex flex-col gap-2">
            <span
              class="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--mindbot-swiss-muted)]"
              >{{ t('admin.mindbot.moveTarget') }}</span
            >
            <el-select
              v-model="moveTargetOrgId"
              class="mindbot-swiss-select w-full"
              filterable
              :placeholder="t('admin.mindbot.orgSelect')"
            >
              <el-option
                v-for="o in moveTargetOptions"
                :key="o.id"
                :label="orgLabel(o)"
                :value="o.id"
              />
            </el-select>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="mindbot-dialog-footer flex w-full justify-end gap-2">
          <el-button
            class="mindbot-pill mindbot-pill--footer-cancel"
            @click="moveDialogVisible = false"
          >
            {{ t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            class="mindbot-pill mindbot-pill--footer-save"
            :loading="moveSubmitting"
            :disabled="moveTargetOrgId == null || moveTargetOptions.length === 0"
            @click="confirmMoveBot"
          >
            {{ t('admin.mindbot.move') }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <AdminMindBotConfigDialog
      v-if="isAdmin"
      v-model="dialogVisible"
      v-model:form="form"
      v-model:form-org-id="formOrgId"
      :mode="dialogMode"
      :editing-org-row="editingRow"
      :orgs-without-config="orgsUnderLimit"
      :is-admin="isAdmin"
      :feature-mindbot="featureMindbot"
      :saving="saving"
      :rotating="rotating"
      :dingtalk-secret-replace-mode="dingtalkSecretReplaceMode"
      :dify-api-key-replace-mode="difyApiKeyReplaceMode"
      :manager-school-display-name="managerSchoolDisplayName"
      :school-display-name="mindbotDialogSchoolDisplayName"
      :can-load-usage="canLoadUsage"
      :build-callback-url="buildCallbackUrlByToken"
      @save="save"
      @closed="resetForm"
      @rotate-callback="rotateCallbackUrl"
      @copy-url="copyUrl"
      @replace-dingtalk-secret="startReplaceDingtalkSecret"
      @replace-dify-api-key="startReplaceDifyApiKey"
    />
  </div>
</template>

<style scoped>
.mindbot-pill.el-button {
  border-radius: 9999px;
  font-weight: 500;
  padding-left: 1rem;
  padding-right: 1rem;
}

.mindbot-pill--header.el-button--primary {
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.06);
  --el-button-bg-color: rgb(241 245 249);
  --el-button-border-color: rgb(226 232 240);
  --el-button-text-color: rgb(71 85 105);
  --el-button-hover-bg-color: rgb(226 232 240);
  --el-button-hover-border-color: rgb(203 213 225);
  --el-button-hover-text-color: rgb(51 65 85);
}

html.dark .mindbot-pill--header.el-button--primary {
  --el-button-bg-color: rgb(51 65 85 / 0.55);
  --el-button-border-color: rgb(71 85 105 / 0.7);
  --el-button-text-color: rgb(226 232 240);
  --el-button-hover-bg-color: rgb(71 85 105 / 0.65);
  --el-button-hover-border-color: rgb(100 116 139 / 0.5);
  --el-button-hover-text-color: rgb(248 250 252);
}

.mindbot-pill--table-edit.el-button--primary.is-plain {
  --el-button-bg-color: rgb(248 250 252);
  --el-button-border-color: rgb(226 232 240);
  --el-button-text-color: rgb(100 116 139);
  min-width: 3.5rem;
}

html.dark .mindbot-pill--table-edit.el-button--primary.is-plain {
  --el-button-bg-color: rgb(30 41 59 / 0.35);
  --el-button-border-color: rgb(51 65 85 / 0.5);
  --el-button-text-color: rgb(203 213 225);
}

.mindbot-pill--table-move.el-button--warning.is-plain {
  --el-button-bg-color: rgb(255 251 235);
  --el-button-border-color: rgb(254 240 199);
  --el-button-text-color: rgb(180 83 9);
  min-width: 3.5rem;
}

html.dark .mindbot-pill--table-move.el-button--warning.is-plain {
  --el-button-bg-color: rgb(66 32 6 / 0.35);
  --el-button-border-color: rgb(180 83 9 / 0.35);
  --el-button-text-color: rgb(253 230 138);
}

.mindbot-pill--table-delete.el-button--danger.is-plain {
  --el-button-bg-color: rgb(255 251 251);
  --el-button-border-color: rgb(254 228 228);
  --el-button-text-color: rgb(185 100 100);
  min-width: 3.5rem;
}

html.dark .mindbot-pill--table-delete.el-button--danger.is-plain {
  --el-button-bg-color: rgb(69 10 10 / 0.28);
  --el-button-border-color: rgb(127 29 29 / 0.35);
  --el-button-text-color: rgb(254 202 202 / 0.9);
}
</style>
