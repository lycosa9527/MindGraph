<script setup lang="ts">
/**
 * Per-school MindMate agent branding and optional Dify override.
 * Blank Dify fields on save use global .env credentials.
 */
import { computed, ref, watch } from 'vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage, useNotifications } from '@/composables'
import { resolveSchoolMindmateAvatarUrl } from '@/composables/mindmate/useMindMateBranding'
import {
  useAdminMindmateDifyDefault,
  useProbeAdminOrganizationMindmateDifyHealth,
  useUpdateAdminOrganization,
  useUploadAdminOrganizationMindmateAvatar,
} from '@/composables/queries'
import AdminMindbotSwissSegmented from '@/components/admin/swiss/AdminMindbotSwissSegmented.vue'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

const props = withDefaults(
  defineProps<{
    orgId: number
    difyApiBaseUrl?: string | null
    difyApiKeyMasked?: string | null
    difyApiBaseUrl2?: string | null
    difyApiKey2Masked?: string | null
    difyActiveServer?: number
    difyFailoverEnabled?: boolean
    difyTimeoutSeconds?: number
    dingtalkAiCardStreamingMaxChars?: number
    showChainOfThought?: boolean
    mindmateAgentName?: string | null
    mindmateAgentAvatarUrl?: string | null
    swiss?: boolean
  }>(),
  {
    difyActiveServer: 1,
    difyFailoverEnabled: true,
    difyTimeoutSeconds: 300,
    dingtalkAiCardStreamingMaxChars: 6500,
    showChainOfThought: false,
    swiss: true,
  }
)

const emit = defineEmits<{
  (e: 'saved'): void
}>()

const MINDMATE_AGENT_NAME_MAX_LENGTH = 10
const MAX_AVATAR_BYTES = 1024 * 1024
const ALLOWED_AVATAR_MIME = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/gif',
  'image/webp',
])

const { t } = useLanguage()
const notify = useNotifications()

const updateOrganizationMutation = useUpdateAdminOrganization()
const uploadAvatarMutation = useUploadAdminOrganizationMindmateAvatar()
const probeDifyHealthMutation = useProbeAdminOrganizationMindmateDifyHealth()
const mindmateDifyDefaultQuery = useAdminMindmateDifyDefault({ enabled: false })

const swissFieldLabelClass =
  'mindbot-section-label mindbot-swiss-section-label shrink-0 text-[11px] font-semibold tracking-[0.14em] sm:w-[178px] sm:pr-3 leading-snug'

const selectedServer = ref(1)
const failoverEnabled = ref(true)
const serverOptions = computed(() => [
  { label: t('admin.schoolDifyServer1'), value: 1 },
  { label: t('admin.schoolDifyServer2'), value: 2 },
])
const activeKeyMasked = computed(() =>
  selectedServer.value === 2 ? props.difyApiKey2Masked : props.difyApiKeyMasked
)
const activeBaseUrlProp = computed(() =>
  selectedServer.value === 2 ? props.difyApiBaseUrl2 : props.difyApiBaseUrl
)
const isServerOne = computed(() => selectedServer.value === 1)

const baseUrl = ref('')
const apiKey = ref('')
const difyTimeoutSeconds = ref(300)
const aiCardStreamingMaxChars = ref(6500)
const showChainOfThought = ref(false)
const agentName = ref('')
const agentAvatarUrl = ref<string | null>(null)
const avatarUploading = ref(false)
const avatarInputRef = ref<HTMLInputElement | null>(null)
const avatarPreviewSrc = computed(
  () => resolveSchoolMindmateAvatarUrl(agentAvatarUrl.value) ?? mindmateAvatarMd
)
const keyReplaceMode = ref(false)
const saving = ref(false)
const globalDifyLoading = ref(false)
const globalDifyUrl = ref<string | null>(null)
const globalDifyKeyMasked = ref<string | null>(null)

const difyStatusLoading = ref(false)
const difyStatus = ref<{
  online: boolean
  http_status?: number | null
  error?: string | null
} | null>(null)
const difyAuthVerified = ref(false)
const difyAuthVerifiedFingerprint = ref('')

const hasSchoolOverride = computed(() => Boolean(activeKeyMasked.value))

const globalDifyUnconfigured = computed(
  () =>
    isServerOne.value &&
    !globalDifyLoading.value &&
    !(globalDifyUrl.value ?? '').trim() &&
    !globalDifyKeyMasked.value
)

const urlPlaceholder = computed(() => globalDifyUrl.value || t('admin.schoolDifyUrlPlaceholder'))

const difyStatusLabel = computed(() => {
  if (difyStatusLoading.value) {
    return t('admin.schoolDifyAuthTestRunning')
  }
  return t('admin.schoolDifyAuthTest')
})

function formatDifyAuthError(error: string | null | undefined, httpStatus?: number | null): string {
  const token = (error ?? '').trim()
  if (token === 'api_key_not_configured') {
    return t('admin.schoolDifyAuthErrorNoKey')
  }
  if (token === 'base_url_not_configured') {
    return t('admin.schoolDifyAuthErrorNoUrl')
  }
  if (token === 'timeout') {
    return t('admin.schoolDifyAuthErrorTimeout')
  }
  if (token === 'network') {
    return t('admin.schoolDifyAuthErrorNetwork')
  }
  if (token.startsWith('http_401') || httpStatus === 401) {
    return t('admin.schoolDifyAuthErrorUnauthorized')
  }
  if (token.startsWith('http_403') || httpStatus === 403) {
    return t('admin.schoolDifyAuthErrorForbidden')
  }
  if (token.startsWith('http_404') || httpStatus === 404) {
    return t('admin.schoolDifyAuthErrorNotFound')
  }
  if (token.startsWith('http_')) {
    return t('admin.schoolDifyAuthErrorHttp', { detail: token })
  }
  if (token && !token.startsWith('http_')) {
    return t('admin.schoolDifyAuthErrorDetail', { detail: token })
  }
  return t('admin.schoolDifyAuthTestFailed')
}

const difyStatusTooltip = computed(() => {
  if (difyStatusLoading.value) {
    return t('admin.mindbot.difyServiceTooltip')
  }
  if (!difyStatus.value) {
    return t('admin.schoolDifyAuthTestTooltip')
  }
  if (difyStatus.value.online) {
    return t('admin.mindbot.difyServiceOnline')
  }
  return formatDifyAuthError(difyStatus.value.error, difyStatus.value.http_status)
})

const difyStatusButtonClass = computed(() => {
  if (difyStatusLoading.value || !difyStatus.value) {
    return 'mindbot-dify-status-btn mindbot-dify-status-btn--pending'
  }
  if (difyStatus.value.error === 'api_key_not_configured') {
    return 'mindbot-dify-status-btn mindbot-dify-status-btn--warn'
  }
  if (difyStatus.value.online) {
    return 'mindbot-dify-status-btn mindbot-dify-status-btn--online'
  }
  return 'mindbot-dify-status-btn mindbot-dify-status-btn--offline'
})

function difyFormFingerprint(): string {
  return JSON.stringify({
    server: selectedServer.value,
    url: baseUrl.value.trim(),
    key: apiKey.value.trim(),
    keyReplaceMode: keyReplaceMode.value,
    hasMasked: Boolean(activeKeyMasked.value),
  })
}

function isDifyAuthPassing(): boolean {
  if (!difyStatus.value?.online) {
    return false
  }
  return difyStatus.value.error !== 'api_key_not_configured'
}

const canSave = computed(
  () =>
    difyAuthVerified.value &&
    difyAuthVerifiedFingerprint.value === difyFormFingerprint() &&
    isDifyAuthPassing()
)

function invalidateDifyAuthVerification() {
  difyAuthVerified.value = false
  difyAuthVerifiedFingerprint.value = ''
}

async function loadGlobalDify() {
  globalDifyLoading.value = true
  try {
    const result = await mindmateDifyDefaultQuery.refetch()
    if (result.error) {
      return
    }
    const data = (result.data ?? {}) as {
      dify_api_base_url?: string | null
      dify_api_key_masked?: string | null
    }
    globalDifyUrl.value = data.dify_api_base_url ?? null
    globalDifyKeyMasked.value = data.dify_api_key_masked ?? null
  } catch {
    // Non-blocking.
  } finally {
    globalDifyLoading.value = false
  }
}

function probeBody(): Record<string, string> {
  const body: Record<string, string> = { server: String(selectedServer.value) }
  const url = baseUrl.value.trim()
  const key = apiKey.value.trim()
  if (url) {
    body.dify_api_base_url = url
  }
  if (key) {
    body.dify_api_key = key
  }
  return body
}

function validateDifyProbeInputs(): string | null {
  const url = baseUrl.value.trim()
  const key = apiKey.value.trim()
  const hasMasked = Boolean(activeKeyMasked.value)
  if (url && !key && !hasMasked) {
    return t('admin.schoolDifyApiKeyRequired')
  }
  if (key && !url) {
    return t('admin.schoolDifyUrlRequired')
  }
  return null
}

async function fetchDifyHealth(options?: { silent?: boolean }) {
  const silent = options?.silent ?? false
  const validationError = validateDifyProbeInputs()
  if (validationError) {
    difyStatus.value = { online: false, error: 'validation_failed' }
    invalidateDifyAuthVerification()
    if (!silent) {
      notify.warning(validationError)
    }
    return
  }

  difyStatusLoading.value = true
  try {
    const data = (await probeDifyHealthMutation.mutateAsync({
      orgId: props.orgId,
      body: probeBody(),
    })) as typeof difyStatus.value
    difyStatus.value = data
    if (isDifyAuthPassing()) {
      difyAuthVerified.value = true
      difyAuthVerifiedFingerprint.value = difyFormFingerprint()
      if (!silent) {
        notify.success(t('admin.schoolDifyAuthTestPassed'))
      }
      return
    }

    invalidateDifyAuthVerification()
    if (!silent) {
      notify.error(formatDifyAuthError(difyStatus.value?.error, difyStatus.value?.http_status))
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    difyStatus.value = {
      online: false,
      error: message || 'network',
    }
    invalidateDifyAuthVerification()
    if (!silent) {
      notify.error(formatDifyAuthError(difyStatus.value?.error, difyStatus.value?.http_status))
    }
  } finally {
    difyStatusLoading.value = false
  }
}

function onFetchDifyHealthClick() {
  void fetchDifyHealth()
}

function loadSelectedServerCreds() {
  baseUrl.value = (activeBaseUrlProp.value ?? '').trim()
  apiKey.value = ''
  keyReplaceMode.value = !activeKeyMasked.value
  invalidateDifyAuthVerification()
}

watch(
  () =>
    [
      props.orgId,
      props.difyApiBaseUrl,
      props.difyApiKeyMasked,
      props.difyApiBaseUrl2,
      props.difyApiKey2Masked,
      props.difyActiveServer,
      props.difyFailoverEnabled,
      props.difyTimeoutSeconds,
      props.dingtalkAiCardStreamingMaxChars,
      props.showChainOfThought,
    ] as const,
  () => {
    selectedServer.value = props.difyActiveServer === 2 ? 2 : 1
    failoverEnabled.value = Boolean(props.difyFailoverEnabled)
    loadSelectedServerCreds()
    difyTimeoutSeconds.value = props.difyTimeoutSeconds ?? 300
    aiCardStreamingMaxChars.value = props.dingtalkAiCardStreamingMaxChars ?? 6500
    showChainOfThought.value = Boolean(props.showChainOfThought)
  },
  { immediate: true }
)

watch(selectedServer, () => {
  loadSelectedServerCreds()
  difyStatus.value = null
})

watch(
  () => [props.mindmateAgentName, props.mindmateAgentAvatarUrl] as const,
  () => {
    agentName.value = (props.mindmateAgentName ?? '').trim()
    agentAvatarUrl.value = props.mindmateAgentAvatarUrl ?? null
  },
  { immediate: true }
)

watch(
  () => props.orgId,
  () => {
    void loadGlobalDify()
    invalidateDifyAuthVerification()
    difyStatus.value = null
  },
  { immediate: true }
)

watch([baseUrl, apiKey, keyReplaceMode], () => {
  if (difyAuthVerified.value) {
    invalidateDifyAuthVerification()
  }
})

function serverFieldNames(): { urlField: string; keyField: string } {
  return selectedServer.value === 2
    ? { urlField: 'dify_api_base_url_2', keyField: 'dify_api_key_2' }
    : { urlField: 'dify_api_base_url', keyField: 'dify_api_key' }
}

async function clearSchoolDifyOverride() {
  baseUrl.value = ''
  apiKey.value = ''
  keyReplaceMode.value = true
  invalidateDifyAuthVerification()
  saving.value = true
  const { urlField, keyField } = serverFieldNames()
  try {
    await updateOrganizationMutation.mutateAsync({
      orgId: props.orgId,
      body: {
        mindmate_agent_name: agentName.value.trim() || null,
        [urlField]: null,
        [keyField]: null,
      },
    })
    notify.success(t('notification.saved'))
    emit('saved')
    void fetchDifyHealth({ silent: true })
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.trendChartErrors.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function saveSettings() {
  if (!canSave.value) {
    notify.error(t('admin.schoolDifyAuthRequiredBeforeSave'))
    return
  }

  const url = baseUrl.value.trim()
  const key = apiKey.value.trim()
  const hasMasked = Boolean(activeKeyMasked.value)

  if (url && !key && !hasMasked) {
    notify.error(t('admin.schoolDifyApiKeyRequired'))
    return
  }
  if (key && !url) {
    notify.error(t('admin.schoolDifyUrlRequired'))
    return
  }

  const { urlField, keyField } = serverFieldNames()
  const body: Record<string, string | null | number | boolean> = {
    mindmate_agent_name: agentName.value.trim() || null,
    dify_timeout_seconds: difyTimeoutSeconds.value,
    dingtalk_ai_card_streaming_max_chars: aiCardStreamingMaxChars.value,
    show_chain_of_thought: showChainOfThought.value,
    dify_active_server: selectedServer.value,
    dify_failover_enabled: failoverEnabled.value,
  }

  if (!url && !key && !hasMasked) {
    body[urlField] = null
    body[keyField] = null
  } else {
    body[urlField] = url || null
    if (key) {
      body[keyField] = key
    }
  }

  saving.value = true
  try {
    await updateOrganizationMutation.mutateAsync({
      orgId: props.orgId,
      body,
    })
    notify.success(t('notification.saved'))
    apiKey.value = ''
    keyReplaceMode.value = false
    emit('saved')
    void fetchDifyHealth({ silent: true })
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.trendChartErrors.saveFailed'))
  } finally {
    saving.value = false
  }
}

function openAvatarPicker() {
  avatarInputRef.value?.click()
}

function formatAvatarUploadError(detail: string | null | undefined): string {
  const token = (detail ?? '').trim()
  if (token === 'mindmate_avatar_too_large') {
    return t('admin.schoolMindmateAvatarErrorTooLarge')
  }
  if (token === 'mindmate_avatar_unsupported_type') {
    return t('admin.schoolMindmateAvatarErrorType')
  }
  if (token === 'mindmate_avatar_invalid_image') {
    return t('admin.schoolMindmateAvatarErrorInvalid')
  }
  if (token === 'mindmate_avatar_too_small') {
    return t('admin.schoolMindmateAvatarErrorTooSmall')
  }
  if (token === 'mindmate_avatar_gif_too_many_frames') {
    return t('admin.schoolMindmateAvatarErrorGifTooManyFrames')
  }
  if (token) {
    return token
  }
  return t('admin.schoolMindmateAvatarUploadFailed')
}

function validateAvatarFile(file: File): string | null {
  const mime = (file.type || '').toLowerCase()
  if (!ALLOWED_AVATAR_MIME.has(mime)) {
    return t('admin.schoolMindmateAvatarErrorType')
  }
  if (file.size > MAX_AVATAR_BYTES) {
    return t('admin.schoolMindmateAvatarErrorTooLarge')
  }
  if (file.size < 1) {
    return t('admin.schoolMindmateAvatarErrorInvalid')
  }
  return null
}

async function onAvatarSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }

  const validationError = validateAvatarFile(file)
  if (validationError) {
    notify.warning(validationError)
    return
  }

  avatarUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const data = await uploadAvatarMutation.mutateAsync({
      orgId: props.orgId,
      formData,
    })
    agentAvatarUrl.value = (data.mindmate_agent_avatar_url as string | null | undefined) ?? null
    notify.success(t('admin.schoolMindmateAvatarUploaded'))
    emit('saved')
  } catch (err) {
    const detail = err instanceof Error ? err.message : httpErrorDetail({})
    notify.error(formatAvatarUploadError(detail))
  } finally {
    avatarUploading.value = false
  }
}

async function removeAvatar() {
  avatarUploading.value = true
  try {
    await updateOrganizationMutation.mutateAsync({
      orgId: props.orgId,
      body: { mindmate_agent_avatar_url: null },
    })
    agentAvatarUrl.value = null
    notify.success(t('admin.schoolMindmateAvatarRemoved'))
    emit('saved')
  } catch (err) {
    const detail = err instanceof Error ? err.message : httpErrorDetail({})
    notify.error(formatAvatarUploadError(detail))
  } finally {
    avatarUploading.value = false
  }
}

defineExpose({
  canSave,
  saving,
  saveSettings,
})
</script>

<template>
  <div :class="swiss ? 'school-dify-tab' : 'space-y-3'">
    <template v-if="swiss">
      <div
        class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] p-3 sm:p-4 mb-4"
      >
        <div
          class="mindbot-section-label mindbot-swiss-section-label text-[11px] font-semibold uppercase tracking-[0.14em] mb-3"
        >
          {{ t('admin.schoolMindmateAgentSection') }}
        </div>
        <el-form
          label-position="left"
          label-width="178px"
          class="mindbot-swiss-form"
        >
          <el-form-item :label="t('admin.schoolMindmateAgentName')">
            <el-input
              v-model="agentName"
              clearable
              :maxlength="MINDMATE_AGENT_NAME_MAX_LENGTH"
              show-word-limit
              class="mindbot-swiss-input w-full max-w-2xl"
            />
          </el-form-item>
          <el-form-item :label="t('admin.schoolMindmateAgentAvatar')">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center max-w-2xl">
              <img
                :src="avatarPreviewSrc"
                alt=""
                class="h-16 w-16 rounded-full object-cover border border-[var(--mindbot-swiss-border)] bg-white"
              />
              <div class="flex flex-wrap gap-2">
                <el-button
                  type="primary"
                  plain
                  class="mindbot-pill mindbot-pill--replace"
                  size="small"
                  :loading="avatarUploading"
                  @click="openAvatarPicker"
                >
                  {{ t('admin.schoolMindmateAgentAvatarUpload') }}
                </el-button>
                <el-button
                  v-if="agentAvatarUrl"
                  class="mindbot-pill mindbot-pill--footer-cancel"
                  size="small"
                  :loading="avatarUploading"
                  @click="removeAvatar"
                >
                  {{ t('admin.schoolMindmateAgentAvatarRemove') }}
                </el-button>
              </div>
            </div>
            <input
              ref="avatarInputRef"
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
              class="hidden"
              @change="onAvatarSelected"
            />
            <p class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl m-0">
              {{ t('admin.schoolMindmateAgentAvatarHint') }}
            </p>
          </el-form-item>
        </el-form>
      </div>

      <div
        class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] p-3 sm:p-4"
      >
        <div
          class="mindbot-section-label mindbot-swiss-section-label text-[11px] font-semibold uppercase tracking-[0.14em] mb-3 flex flex-wrap items-center justify-between gap-2"
        >
          <span>{{ t('admin.mindbot.sectionDify') }}</span>
          <el-button
            v-if="hasSchoolOverride"
            type="warning"
            plain
            size="small"
            class="mindbot-pill shrink-0"
            :loading="saving"
            @click="clearSchoolDifyOverride"
          >
            {{ t('admin.schoolDifyClearOverride') }}
          </el-button>
        </div>
        <div class="school-dify-server-toolbar flex flex-col gap-3 mb-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="flex flex-col gap-1">
            <span class="mindbot-swiss-hint text-[11px] font-semibold uppercase tracking-[0.12em]">
              {{ t('admin.schoolDifyActiveServer') }}
            </span>
            <AdminMindbotSwissSegmented
              v-model="selectedServer"
              :options="serverOptions"
              block
              :aria-label="t('admin.schoolDifyActiveServer')"
            />
          </div>
          <div class="school-dify-failover-row flex items-center gap-2">
            <span class="mindbot-swiss-hint text-[11px] font-semibold uppercase tracking-[0.12em]">
              {{ t('admin.schoolDifyFailover') }}
            </span>
            <el-switch
              v-model="failoverEnabled"
              class="mindbot-footer-enabled-switch shrink-0"
            />
          </div>
        </div>
        <p class="mindbot-swiss-hint text-xs mb-3 leading-relaxed m-0">
          {{ t('admin.schoolDifyDualServerHint') }}
        </p>
        <p
          v-if="globalDifyUnconfigured"
          class="mindbot-swiss-hint text-xs mb-3 leading-relaxed m-0 text-amber-800"
          role="status"
        >
          {{ t('admin.schoolDifyGlobalUnconfigured') }}
        </p>
        <el-form
          label-position="left"
          label-width="178px"
          class="mindbot-swiss-form"
          @submit.prevent="saveSettings"
        >
          <el-form-item :label="t('admin.mindbot.difyBaseUrl')">
            <el-input
              v-model="baseUrl"
              clearable
              :placeholder="urlPlaceholder"
              class="mindbot-swiss-input w-full max-w-2xl"
            />
            <p
              v-if="isServerOne && !hasSchoolOverride && !baseUrl"
              class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl m-0"
            >
              {{ t('admin.schoolDifyBlankUsesGlobal', { url: globalDifyUrl || urlPlaceholder }) }}
            </p>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyApiKey')">
            <div class="school-dify-api-key-block max-w-2xl">
              <template v-if="activeKeyMasked && !keyReplaceMode">
                <div class="school-dify-api-key-input-line">
                  <el-input
                    :model-value="difyApiKeyMasked"
                    type="text"
                    readonly
                    class="mindbot-swiss-input font-mono text-sm school-dify-api-key-input"
                  />
                  <el-button
                    type="primary"
                    plain
                    class="mindbot-pill mindbot-pill--replace shrink-0"
                    size="small"
                    @click="keyReplaceMode = true"
                  >
                    {{ t('admin.mindbot.replaceSecret') }}
                  </el-button>
                  <el-tooltip
                    :content="difyStatusTooltip"
                    placement="top"
                    :show-after="400"
                  >
                    <el-button
                      size="small"
                      :class="[difyStatusButtonClass, 'shrink-0']"
                      :loading="difyStatusLoading"
                      @click="onFetchDifyHealthClick"
                    >
                      {{ difyStatusLabel }}
                    </el-button>
                  </el-tooltip>
                </div>
                <p class="mindbot-swiss-hint text-xs mt-1.5 m-0 leading-relaxed">
                  {{ t('admin.mindbot.difyApiKeyMaskedHint') }}
                </p>
              </template>
              <template v-else>
                <div class="school-dify-api-key-input-line">
                  <el-input
                    v-model="apiKey"
                    type="password"
                    show-password
                    autocomplete="new-password"
                    clearable
                    class="mindbot-swiss-input school-dify-api-key-input"
                  />
                  <el-tooltip
                    :content="difyStatusTooltip"
                    placement="top"
                    :show-after="400"
                  >
                    <el-button
                      size="small"
                      :class="[difyStatusButtonClass, 'shrink-0']"
                      :loading="difyStatusLoading"
                      @click="onFetchDifyHealthClick"
                    >
                      {{ difyStatusLabel }}
                    </el-button>
                  </el-tooltip>
                </div>
                <div class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed">
                  <template v-if="activeKeyMasked">
                    {{ t('admin.mindbot.difyApiKeyReplaceHint') }}
                  </template>
                  <template v-else-if="isServerOne && !hasSchoolOverride && globalDifyKeyMasked">
                    {{
                      t('admin.schoolDifyApiKeyBlankUsesGlobal', { masked: globalDifyKeyMasked })
                    }}
                  </template>
                  <template v-else>
                    {{ t('admin.schoolDifyApiKeyHintOptional') }}
                  </template>
                </div>
              </template>
            </div>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyTimeout')">
            <el-input-number
              v-model="difyTimeoutSeconds"
              :min="5"
              :max="600"
              class="mindbot-swiss-input-number w-full sm:w-40"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.dingtalkAiCardStreamingMaxChars')">
            <el-input-number
              v-model="aiCardStreamingMaxChars"
              :min="500"
              :max="50000"
              :step="100"
              class="mindbot-swiss-input-number w-full sm:w-48"
              controls-position="right"
            />
          </el-form-item>
          <div class="school-dify-cot-row flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-0">
            <span :class="swissFieldLabelClass">{{ t('admin.mindbot.difyShowChainOfThought') }}</span>
            <el-switch
              v-model="showChainOfThought"
              class="mindbot-cot-switch mindbot-footer-enabled-switch shrink-0"
            />
          </div>
        </el-form>
      </div>
    </template>
  </div>
</template>
