<script setup lang="ts">
/**
 * Per-school MindMate agent branding and optional Dify override.
 * Blank Dify fields on save use global .env credentials.
 */
import { computed, ref, watch } from 'vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage, useNotifications } from '@/composables'
import { resolveSchoolMindmateAvatarUrl } from '@/composables/mindmate/useMindMateBranding'
import { apiRequest } from '@/utils/apiClient'

const props = withDefaults(
  defineProps<{
    orgId: number
    difyApiBaseUrl?: string | null
    difyApiKeyMasked?: string | null
    mindmateAgentName?: string | null
    mindmateAgentAvatarUrl?: string | null
    swiss?: boolean
  }>(),
  { swiss: true }
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

const baseUrl = ref('')
const apiKey = ref('')
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

const hasSchoolOverride = computed(() => Boolean(props.difyApiKeyMasked))

const globalDifyUnconfigured = computed(
  () =>
    !globalDifyLoading.value &&
    !(globalDifyUrl.value ?? '').trim() &&
    !globalDifyKeyMasked.value
)

const urlPlaceholder = computed(
  () => globalDifyUrl.value || t('admin.schoolDifyUrlPlaceholder')
)

const difyStatusLabel = computed(() => {
  if (difyStatusLoading.value) {
    return t('admin.schoolDifyAuthTestRunning')
  }
  return t('admin.schoolDifyAuthTest')
})

function formatDifyAuthError(
  error: string | null | undefined,
  httpStatus?: number | null
): string {
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
    url: baseUrl.value.trim(),
    key: apiKey.value.trim(),
    keyReplaceMode: keyReplaceMode.value,
    hasMasked: Boolean(props.difyApiKeyMasked),
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
    const res = await apiRequest('/api/auth/admin/mindmate/dify-default')
    if (!res.ok) {
      return
    }
    const data = (await res.json()) as {
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
  const body: Record<string, string> = {}
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
  const hasMasked = Boolean(props.difyApiKeyMasked)
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
    const res = await apiRequest(
      `/api/auth/admin/organizations/${props.orgId}/mindmate-dify-health`,
      {
        method: 'POST',
        body: JSON.stringify(probeBody()),
      }
    )
    if (res.ok) {
      difyStatus.value = (await res.json()) as typeof difyStatus.value
    } else {
      const data = (await res.json().catch(() => ({}))) as { detail?: string }
      const detail =
        typeof data.detail === 'string' && data.detail.trim()
          ? data.detail.trim()
          : `http_${res.status}`
      difyStatus.value = {
        online: false,
        error: detail,
        http_status: res.status,
      }
      invalidateDifyAuthVerification()
      if (!silent) {
        notify.error(formatDifyAuthError(detail, res.status))
      }
      return
    }

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
      notify.error(
        formatDifyAuthError(difyStatus.value?.error, difyStatus.value?.http_status)
      )
    }
  } catch {
    difyStatus.value = { online: false, error: 'network' }
    invalidateDifyAuthVerification()
    if (!silent) {
      notify.error(formatDifyAuthError('network'))
    }
  } finally {
    difyStatusLoading.value = false
  }
}

watch(
  () =>
    [props.orgId, props.difyApiBaseUrl, props.difyApiKeyMasked] as const,
  () => {
    baseUrl.value = (props.difyApiBaseUrl ?? '').trim()
    apiKey.value = ''
    keyReplaceMode.value = !props.difyApiKeyMasked
    invalidateDifyAuthVerification()
  },
  { immediate: true }
)

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

async function clearSchoolDifyOverride() {
  baseUrl.value = ''
  apiKey.value = ''
  keyReplaceMode.value = true
  invalidateDifyAuthVerification()
  saving.value = true
  try {
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}`, {
      method: 'PUT',
      body: JSON.stringify({
        mindmate_agent_name: agentName.value.trim() || null,
        dify_api_base_url: null,
        dify_api_key: null,
      }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.saveFailed'))
      return
    }
    notify.success(t('notification.saved'))
    emit('saved')
    void fetchDifyHealth({ silent: true })
  } catch {
    notify.error(t('admin.trendChartErrors.saveFailed'))
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
  const hasMasked = Boolean(props.difyApiKeyMasked)

  if (url && !key && !hasMasked) {
    notify.error(t('admin.schoolDifyApiKeyRequired'))
    return
  }
  if (key && !url) {
    notify.error(t('admin.schoolDifyUrlRequired'))
    return
  }

  const body: Record<string, string | null> = {
    mindmate_agent_name: agentName.value.trim() || null,
  }

  if (!url && !key && !hasMasked) {
    body.dify_api_base_url = null
    body.dify_api_key = null
  } else {
    body.dify_api_base_url = url || null
    if (key) {
      body.dify_api_key = key
    }
  }

  saving.value = true
  try {
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.saveFailed'))
      return
    }
    notify.success(t('notification.saved'))
    apiKey.value = ''
    keyReplaceMode.value = false
    emit('saved')
    void fetchDifyHealth({ silent: true })
  } catch {
    notify.error(t('admin.trendChartErrors.saveFailed'))
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
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}/mindmate-avatar`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) {
      const data = (await res.json().catch(() => ({}))) as { detail?: string }
      notify.error(formatAvatarUploadError(data.detail))
      return
    }
    const data = (await res.json()) as { mindmate_agent_avatar_url?: string | null }
    agentAvatarUrl.value = data.mindmate_agent_avatar_url ?? null
    notify.success(t('admin.schoolMindmateAvatarUploaded'))
    emit('saved')
  } catch {
    notify.error(t('admin.schoolMindmateAvatarUploadFailed'))
  } finally {
    avatarUploading.value = false
  }
}

async function removeAvatar() {
  avatarUploading.value = true
  try {
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}`, {
      method: 'PUT',
      body: JSON.stringify({ mindmate_agent_avatar_url: null }),
    })
    if (!res.ok) {
      const data = (await res.json().catch(() => ({}))) as { detail?: string }
      notify.error(formatAvatarUploadError(data.detail))
      return
    }
    agentAvatarUrl.value = null
    notify.success(t('admin.schoolMindmateAvatarRemoved'))
    emit('saved')
  } catch {
    notify.error(t('admin.schoolMindmateAvatarRemoveFailed'))
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
              v-if="!hasSchoolOverride && !baseUrl"
              class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl m-0"
            >
              {{ t('admin.schoolDifyBlankUsesGlobal', { url: globalDifyUrl || urlPlaceholder }) }}
            </p>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyApiKey')">
            <div class="school-dify-api-key-block max-w-2xl">
              <template v-if="difyApiKeyMasked && !keyReplaceMode">
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
                      @click="fetchDifyHealth"
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
                      @click="fetchDifyHealth"
                    >
                      {{ difyStatusLabel }}
                    </el-button>
                  </el-tooltip>
                </div>
                <div class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed">
                  <template v-if="difyApiKeyMasked">
                    {{ t('admin.mindbot.difyApiKeyReplaceHint') }}
                  </template>
                  <template v-else-if="!hasSchoolOverride && globalDifyKeyMasked">
                    {{ t('admin.schoolDifyApiKeyBlankUsesGlobal', { masked: globalDifyKeyMasked }) }}
                  </template>
                  <template v-else>
                    {{ t('admin.schoolDifyApiKeyHintOptional') }}
                  </template>
                </div>
              </template>
            </div>
          </el-form-item>
        </el-form>
      </div>
    </template>
  </div>
</template>
