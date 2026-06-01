/**
 * Shared MindBot admin config state: load, create, update, rotate callback.
 */
import { computed, ref, type Ref } from 'vue'

import { ElMessageBox } from 'element-plus'

import type {
  MindbotConfigFormState,
  MindbotConfigRow,
} from '@/components/admin/mindbotConfigTypes'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import {
  fetchAllAdminMindbotConfigs,
  useCreateAdminMindbotConfig,
  useDeleteAdminMindbotConfig,
  useRotateAdminMindbotCallbackToken,
  useUpdateAdminMindbotConfig,
} from '@/composables/queries'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

export const MINDBOT_BOT_CAP = 5

export function emptyMindbotFormState(): MindbotConfigFormState {
  return {
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
    use_org_dify_settings: true,
  }
}

export type MindbotConfigsFetchResult = {
  configs: MindbotConfigRow[]
  featureDisabled: boolean
}

export async function fetchAllMindbotConfigs(): Promise<MindbotConfigsFetchResult> {
  return fetchAllAdminMindbotConfigs()
}

export function fillMindbotFormFromRow(row: MindbotConfigRow): MindbotConfigFormState {
  return {
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
    use_org_dify_settings: row.use_org_dify_settings ?? true,
  }
}

export function mindbotConfigsForOrg(
  configs: MindbotConfigRow[],
  orgId: number
): MindbotConfigRow[] {
  return configs.filter((row) => row.organization_id === orgId)
}

export function orgMindbotCount(configs: MindbotConfigRow[], orgId: number): number {
  return mindbotConfigsForOrg(configs, orgId).length
}

export function canAddMindbotForOrg(configs: MindbotConfigRow[], orgId: number): boolean {
  return orgMindbotCount(configs, orgId) < MINDBOT_BOT_CAP
}

export function useAdminMindBotConfig(options?: {
  organizationId?: Ref<number | null | undefined>
  useOrgDifySettings?: boolean
}) {
  const { t } = useLanguage()
  const notify = useNotifications()
  const { publicSiteUrl } = usePublicSiteUrl()

  const loading = ref(false)
  const saving = ref(false)
  const rotating = ref(false)
  const configs = ref<MindbotConfigRow[]>([])
  const dialogMode = ref<'create' | 'edit'>('create')
  const formOrgId = ref<number | null>(null)
  const editingConfigId = ref<number | null>(null)
  const dingtalkSecretReplaceMode = ref(false)
  const difyApiKeyReplaceMode = ref(false)
  const form = ref<MindbotConfigFormState>(emptyMindbotFormState())
  const featureDisabled = ref(false)
  let loadConfigsPromise: Promise<void> | null = null
  let configsHydrated = false

  const createConfigMutation = useCreateAdminMindbotConfig()
  const updateConfigMutation = useUpdateAdminMindbotConfig()
  const rotateTokenMutation = useRotateAdminMindbotCallbackToken()
  const deleteConfigMutation = useDeleteAdminMindbotConfig()

  const apiMindbotBase = computed(() => {
    const origin = publicSiteUrl.value.replace(/\/$/, '')
    return `${origin}/api/mindbot`
  })

  function buildCallbackUrlByToken(token: string): string {
    const tok = token.trim()
    return `${apiMindbotBase.value}/dingtalk/callback/t/${encodeURIComponent(tok)}`
  }

  const editingRow = computed(() => {
    const configId = editingConfigId.value
    if (configId == null) {
      return undefined
    }
    return configs.value.find((row) => row.id === configId)
  })

  const canLoadUsage = computed(() => dialogMode.value === 'edit' && editingConfigId.value != null)

  function resetForm(): void {
    form.value = emptyMindbotFormState()
    formOrgId.value = null
    editingConfigId.value = null
    dingtalkSecretReplaceMode.value = false
    difyApiKeyReplaceMode.value = false
  }

  function fillForm(row: MindbotConfigRow): void {
    form.value = fillMindbotFormFromRow(row)
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

  function beginCreateForOrg(orgId: number): void {
    dialogMode.value = 'create'
    resetForm()
    formOrgId.value = orgId
  }

  function beginEditRow(row: MindbotConfigRow): void {
    dialogMode.value = 'edit'
    fillForm(row)
  }

  async function loadConfigs(force = false): Promise<void> {
    if (loadConfigsPromise) {
      await loadConfigsPromise
      return
    }
    if (!force && configsHydrated) {
      return
    }
    loading.value = true
    loadConfigsPromise = (async () => {
      try {
        const result = await fetchAllMindbotConfigs()
        configs.value = result.configs
        featureDisabled.value = result.featureDisabled
        configsHydrated = true
      } catch {
        notify.error(t('admin.mindbot.loadError'))
        configs.value = []
        featureDisabled.value = false
      } finally {
        loading.value = false
        loadConfigsPromise = null
      }
    })()
    await loadConfigsPromise
  }

  async function loadConfigsForOrg(orgId: number, preferredConfigId?: number | null): Promise<void> {
    await loadConfigs()
    if (featureDisabled.value) {
      return
    }
    const orgRows = mindbotConfigsForOrg(configs.value, orgId)
    if (orgRows.length === 0) {
      beginCreateForOrg(orgId)
      return
    }
    const preferred =
      preferredConfigId != null ? orgRows.find((row) => row.id === preferredConfigId) : undefined
    beginEditRow(preferred ?? orgRows[0])
  }

  function buildSavePayload(isCreate: boolean): Record<string, unknown> | null {
    const oid = formOrgId.value
    if (oid == null) {
      return null
    }
    const schoolSession = options?.useOrgDifySettings === true
    const useOrgDify = schoolSession ? form.value.use_org_dify_settings : false
    const payload: Record<string, unknown> = {
      bot_label: form.value.bot_label.trim() || null,
      dingtalk_robot_code: form.value.dingtalk_robot_code.trim(),
      dingtalk_client_id: form.value.dingtalk_client_id.trim() || null,
      dingtalk_ai_card_template_id: form.value.dingtalk_ai_card_template_id.trim() || null,
      dingtalk_ai_card_param_key: form.value.dingtalk_ai_card_param_key.trim() || null,
      is_enabled: form.value.is_enabled,
    }
    if (schoolSession) {
      payload.use_org_dify_settings = form.value.use_org_dify_settings
    }
    if (!useOrgDify) {
      payload.dify_api_base_url = form.value.dify_api_base_url.trim()
      payload.dify_timeout_seconds = form.value.dify_timeout_seconds
      payload.show_chain_of_thought_oto = form.value.show_chain_of_thought
      payload.show_chain_of_thought_internal_group = form.value.show_chain_of_thought
      payload.show_chain_of_thought_cross_org_group = form.value.show_chain_of_thought
      payload.chain_of_thought_max_chars = form.value.chain_of_thought_max_chars
      payload.dingtalk_ai_card_streaming_max_chars = form.value.dingtalk_ai_card_streaming_max_chars
    }
    if (isCreate) {
      if (!form.value.dingtalk_app_secret.trim()) {
        return null
      }
      if (!useOrgDify && !form.value.dify_api_base_url.trim()) {
        return null
      }
      if (!useOrgDify && !form.value.dify_api_key.trim()) {
        return null
      }
      payload.organization_id = oid
      payload.dingtalk_app_secret = form.value.dingtalk_app_secret.trim()
      if (!useOrgDify) {
        payload.dify_api_key = form.value.dify_api_key.trim()
      }
      return payload
    }
    if (dingtalkSecretReplaceMode.value) {
      const secret = form.value.dingtalk_app_secret.trim()
      if (secret) {
        payload.dingtalk_app_secret = secret
      }
    }
    if (!useOrgDify && difyApiKeyReplaceMode.value) {
      const key = form.value.dify_api_key.trim()
      if (key) {
        payload.dify_api_key = key
      }
    }
    return payload
  }

  async function createConfig(): Promise<boolean> {
    const payload = buildSavePayload(true)
    if (payload == null) {
      notify.error(t('admin.mindbot.saveError'))
      return false
    }
    saving.value = true
    try {
      const saved = await createConfigMutation.mutateAsync(payload)
      notify.success(t('admin.mindbot.saved'))
      await loadConfigs(true)
      const row = configs.value.find((item) => item.id === saved.id) ?? saved
      fillForm(row)
      dialogMode.value = 'edit'
      return true
    } catch (err) {
      const detail = err instanceof Error ? err.message : ''
      notify.error(detail || t('admin.mindbot.saveError'))
      return false
    } finally {
      saving.value = false
    }
  }

  async function updateConfig(): Promise<boolean> {
    const configId = editingConfigId.value
    if (configId == null) {
      notify.error(t('admin.mindbot.saveError'))
      return false
    }
    const payload = buildSavePayload(false)
    if (payload == null) {
      notify.error(t('admin.mindbot.saveError'))
      return false
    }
    saving.value = true
    try {
      const saved = await updateConfigMutation.mutateAsync({ configId, body: payload })
      notify.success(t('admin.mindbot.saved'))
      await loadConfigs(true)
      const row = configs.value.find((item) => item.id === saved.id) ?? saved
      fillForm(row)
      dialogMode.value = 'edit'
      return true
    } catch (err) {
      const detail = err instanceof Error ? err.message : ''
      notify.error(detail || t('admin.mindbot.saveError'))
      return false
    } finally {
      saving.value = false
    }
  }

  async function saveConfig(): Promise<boolean> {
    if (dialogMode.value === 'create') {
      return createConfig()
    }
    return updateConfig()
  }

  async function rotateCallbackUrl(): Promise<void> {
    const configId = editingConfigId.value
    if (configId == null) {
      return
    }
    try {
      await ElMessageBox.confirm(
        t('admin.mindbot.rotateConfirm'),
        t('admin.mindbot.rotateConfirmTitle'),
        {
          type: 'warning',
          customClass: 'mindbot-swiss-message-box mindbot-swiss-msg--rotate',
          modalClass: 'mindbot-swiss-backdrop',
          cancelButtonClass: 'mindbot-pill mindbot-pill--footer-cancel',
          showClose: true,
        }
      )
    } catch {
      return
    }
    rotating.value = true
    try {
      const row = await rotateTokenMutation.mutateAsync(configId)
      const idx = configs.value.findIndex((item) => item.id === configId)
      if (idx >= 0) {
        configs.value[idx] = row as unknown as MindbotConfigRow
      }
      fillForm(row as unknown as MindbotConfigRow)
      notify.success(t('admin.mindbot.callbackRotated'))
    } catch {
      notify.error(t('admin.mindbot.loadError'))
    } finally {
      rotating.value = false
    }
  }

  async function deleteConfig(row: MindbotConfigRow): Promise<boolean> {
    try {
      await ElMessageBox.confirm(
        t('admin.mindbot.deleteConfirm'),
        t('admin.mindbot.deleteConfirmTitle'),
        {
          type: 'warning',
          customClass: 'mindbot-swiss-message-box mindbot-swiss-msg--delete',
          modalClass: 'mindbot-swiss-backdrop',
          cancelButtonClass: 'mindbot-pill mindbot-pill--footer-cancel',
          showClose: true,
        }
      )
    } catch {
      return false
    }
    try {
      await deleteConfigMutation.mutateAsync(row.id)
      notify.success(t('admin.mindbot.deleted'))
      await loadConfigs(true)
      return true
    } catch (err) {
      const detail = err instanceof Error ? err.message : httpErrorDetail({})
      notify.error(detail || t('admin.mindbot.deleteError'))
      return false
    }
  }

  async function copyUrl(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text)
      notify.success(t('admin.mindbot.copied'))
    } catch {
      notify.error(t('admin.mindbot.saveError'))
    }
  }

  const orgConfigs = computed(() => {
    const orgId = options?.organizationId?.value
    if (orgId == null) {
      return []
    }
    return mindbotConfigsForOrg(configs.value, orgId)
  })

  return {
    loading,
    saving,
    rotating,
    configs,
    orgConfigs,
    dialogMode,
    formOrgId,
    editingConfigId,
    editingRow,
    dingtalkSecretReplaceMode,
    difyApiKeyReplaceMode,
    form,
    canLoadUsage,
    featureDisabled,
    buildCallbackUrlByToken,
    resetForm,
    fillForm,
    beginCreateForOrg,
    beginEditRow,
    startReplaceDingtalkSecret,
    startReplaceDifyApiKey,
    loadConfigs,
    loadConfigsForOrg,
    saveConfig,
    rotateCallbackUrl,
    deleteConfig,
    copyUrl,
  }
}

export type AdminMindBotOrgSession = ReturnType<typeof useAdminMindBotConfig>

const orgSessions = new Map<number, AdminMindBotOrgSession>()

export function getAdminMindBotOrgSession(orgId: number): AdminMindBotOrgSession {
  if (!orgSessions.has(orgId)) {
    const orgIdRef = ref(orgId)
    orgSessions.set(
      orgId,
      useAdminMindBotConfig({ organizationId: orgIdRef, useOrgDifySettings: true })
    )
  }
  return orgSessions.get(orgId) as AdminMindBotOrgSession
}

export function clearAdminMindBotOrgSession(orgId: number): void {
  orgSessions.delete(orgId)
}
