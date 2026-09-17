<script setup lang="ts">
/**
 * School modal — MindGraph custom AI server (protocol + school URL/key/model).
 */
import { computed, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  probeAdminOrganizationCustomLlmHealth,
  type CustomLlmApiType,
} from '@/composables/queries/adminApi'
import AdminMindbotSwissSegmented from '@/components/admin/swiss/AdminMindbotSwissSegmented.vue'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

const PLATFORM: CustomLlmApiType = 'dashscope_volcengine'

const props = withDefaults(
  defineProps<{
    orgId: number
    readOnly?: boolean
    customLlmApiType?: string | null
    customLlmBaseUrl?: string | null
    customLlmApiKeyMasked?: string | null
    customLlmModel?: string | null
  }>(),
  {
    readOnly: false,
    customLlmApiType: PLATFORM,
    customLlmBaseUrl: null,
    customLlmApiKeyMasked: null,
    customLlmModel: null,
  }
)

const { t } = useLanguage()
const notify = useNotifications()

const labelClass =
  'mindbot-section-label mindbot-swiss-section-label shrink-0 text-[11px] font-semibold tracking-[0.14em] sm:w-[178px]'

const apiType = ref<CustomLlmApiType>(PLATFORM)
const baseUrl = ref('')
const apiKey = ref('')
const modelName = ref('')
const keyMasked = ref<string | null>(null)
const replaceKey = ref(false)
const clearKey = ref(false)
const probing = ref(false)
const probeResult = ref<{ online: boolean; error?: string | null } | null>(null)

const protocolOptions = computed(() => [
  { label: t('admin.customLlm.typePlatform'), value: PLATFORM },
  { label: t('admin.customLlm.typeOpenAiChat'), value: 'openai_chat' },
  { label: t('admin.customLlm.typeOpenAiResponse'), value: 'openai_responses' },
  { label: t('admin.customLlm.typeAnthropic'), value: 'anthropic_messages' },
])

const isCustom = computed(() => apiType.value !== PLATFORM)
const fieldsReadOnly = computed(() => props.readOnly)

function normalizeType(raw: string | null | undefined): CustomLlmApiType {
  if (raw === 'openai_chat' || raw === 'openai_responses' || raw === 'anthropic_messages') {
    return raw
  }
  return PLATFORM
}

function hydrateFromProps(): void {
  apiType.value = normalizeType(props.customLlmApiType)
  baseUrl.value = (props.customLlmBaseUrl ?? '').trim()
  modelName.value = (props.customLlmModel ?? '').trim()
  keyMasked.value = props.customLlmApiKeyMasked ?? null
  apiKey.value = ''
  replaceKey.value = false
  clearKey.value = false
  probeResult.value = null
}

watch(
  () =>
    [
      props.orgId,
      props.customLlmApiType,
      props.customLlmBaseUrl,
      props.customLlmApiKeyMasked,
      props.customLlmModel,
    ] as const,
  () => {
    hydrateFromProps()
  },
  { immediate: true }
)

watch(apiType, (next, prev) => {
  if (next === PLATFORM) {
    probeResult.value = null
  }
  if (prev === PLATFORM && next !== PLATFORM) {
    replaceKey.value = !keyMasked.value
  }
})

function getSavePayload(): Record<string, unknown> {
  if (apiType.value === PLATFORM) {
    return {
      custom_llm_api_type: PLATFORM,
      custom_llm_base_url: null,
      custom_llm_api_key: null,
      custom_llm_model: null,
      clear_custom_llm_api_key: true,
    }
  }
  const body: Record<string, unknown> = {
    custom_llm_api_type: apiType.value,
    custom_llm_base_url: baseUrl.value.trim() || null,
    custom_llm_model: modelName.value.trim() || null,
  }
  if (clearKey.value) {
    body.clear_custom_llm_api_key = true
  } else if (replaceKey.value && apiKey.value.trim()) {
    body.custom_llm_api_key = apiKey.value.trim()
  }
  return body
}

async function probeConnection(): Promise<void> {
  if (!isCustom.value || props.orgId <= 0) {
    return
  }
  probing.value = true
  probeResult.value = null
  try {
    const body: Record<string, unknown> = {
      custom_llm_api_type: apiType.value,
      custom_llm_base_url: baseUrl.value.trim(),
      custom_llm_model: modelName.value.trim(),
    }
    if (replaceKey.value && apiKey.value.trim()) {
      body.custom_llm_api_key = apiKey.value.trim()
    }
    const result = await probeAdminOrganizationCustomLlmHealth(props.orgId, body)
    probeResult.value = { online: result.online === true, error: result.error ?? null }
    if (result.online) {
      notify.success(t('admin.customLlm.probeOk'))
    } else {
      notify.error(result.error || t('admin.customLlm.probeFail'))
    }
  } catch (err) {
    const detail = httpErrorDetail(err) || t('admin.customLlm.probeFail')
    probeResult.value = { online: false, error: detail }
    notify.error(detail)
  } finally {
    probing.value = false
  }
}

defineExpose({ getSavePayload })
</script>

<template>
  <div
    class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] p-3 sm:p-4 space-y-4"
  >
    <div class="flex flex-col gap-1 sm:flex-row sm:items-start">
      <span :class="labelClass">{{ t('admin.customLlm.sectionTitle') }}</span>
      <div class="flex-1 min-w-0 max-w-2xl space-y-2">
        <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
          {{ t('admin.customLlm.hint') }}
        </p>
        <AdminMindbotSwissSegmented
          v-model="apiType"
          :options="protocolOptions"
          block
          :aria-label="t('admin.customLlm.sectionTitle')"
        />
      </div>
    </div>

    <template v-if="isCustom">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <span :class="labelClass">{{ t('admin.customLlm.baseUrl') }}</span>
        <el-input
          v-model="baseUrl"
          clearable
          :disabled="fieldsReadOnly"
          :placeholder="t('admin.customLlm.baseUrlPlaceholder')"
          class="mindbot-swiss-input flex-1 min-w-0 max-w-2xl"
        />
      </div>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span :class="labelClass">{{ t('admin.customLlm.apiKey') }}</span>
        <div class="flex-1 min-w-0 max-w-2xl space-y-2">
          <p
            v-if="keyMasked && !replaceKey && !clearKey"
            class="mindbot-swiss-hint text-xs m-0"
          >
            {{ t('admin.customLlm.secretSet', { masked: keyMasked }) }}
          </p>
          <el-input
            v-if="replaceKey || !keyMasked"
            v-model="apiKey"
            type="password"
            show-password
            autocomplete="new-password"
            :disabled="fieldsReadOnly"
            :placeholder="t('admin.customLlm.apiKeyPlaceholder')"
            class="mindbot-swiss-input w-full"
          />
          <div class="flex flex-wrap gap-2">
            <el-button
              v-if="keyMasked && !replaceKey"
              plain
              size="small"
              class="mindbot-pill shrink-0"
              :disabled="fieldsReadOnly"
              @click="replaceKey = true; clearKey = false; apiKey = ''"
            >
              {{ t('admin.oauth.replaceSecret') }}
            </el-button>
            <el-button
              v-if="keyMasked"
              plain
              size="small"
              class="mindbot-pill shrink-0"
              :disabled="fieldsReadOnly"
              @click="clearKey = true; replaceKey = false; apiKey = ''"
            >
              {{ t('admin.oauth.clearSecret') }}
            </el-button>
          </div>
        </div>
      </div>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <span :class="labelClass">{{ t('admin.customLlm.modelName') }}</span>
        <el-input
          v-model="modelName"
          clearable
          :disabled="fieldsReadOnly"
          :placeholder="t('admin.customLlm.modelNamePlaceholder')"
          class="mindbot-swiss-input flex-1 min-w-0 max-w-2xl"
        />
      </div>
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
        <span :class="labelClass" />
        <div class="flex flex-wrap items-center gap-2">
          <el-button
            plain
            size="small"
            class="mindbot-pill shrink-0"
            :loading="probing"
            :disabled="fieldsReadOnly"
            @click="probeConnection"
          >
            {{ t('admin.customLlm.probe') }}
          </el-button>
          <p
            v-if="probeResult"
            class="mindbot-swiss-hint text-xs m-0"
            :class="probeResult.online ? 'text-emerald-700' : 'text-amber-800'"
          >
            {{ probeResult.online ? t('admin.customLlm.probeOk') : probeResult.error }}
          </p>
        </div>
      </div>
    </template>
  </div>
</template>
