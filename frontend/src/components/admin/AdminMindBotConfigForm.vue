<script setup lang="ts">
/**
 * MindBot config tabs (DingTalk + Dify + usage) — shared by dialog and school edit modal.
 */
import { computed, ref, watch } from 'vue'

import { DocumentCopy, MagicStick, Refresh } from '@element-plus/icons-vue'

import AdminMindBotUsagePanel from '@/components/admin/AdminMindBotUsagePanel.vue'
import AdminMindbotSwissSegmented from '@/components/admin/swiss/AdminMindbotSwissSegmented.vue'
import type {
  MindbotConfigFormState,
  MindbotConfigRow,
  OrgOption,
} from '@/components/admin/mindbotConfigTypes'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminMindbotStreamingStatus } from '@/composables/queries'

const form = defineModel<MindbotConfigFormState>('form', { required: true })
const formOrgId = defineModel<number | null>('formOrgId', { required: true })

const props = withDefaults(
  defineProps<{
    mode: 'create' | 'edit'
    editingOrgRow?: MindbotConfigRow
    orgsWithoutConfig?: OrgOption[]
    isAdmin?: boolean
    featureMindbot?: boolean
    dingtalkSecretReplaceMode?: boolean
    difyApiKeyReplaceMode?: boolean
    managerSchoolDisplayName?: string
    canLoadUsage?: boolean
    buildCallbackUrl: (token: string) => string
    rotating?: boolean
    /** Hide org picker (school modal already knows the org). */
    hideOrgSelect?: boolean
    /** When set, show one pane only; outer modal supplies tab labels. */
    embeddedPane?: 'dingtalk' | 'log' | 'monitor'
    /** School modal: Dify URL/key/behavior come from MindMate tab. */
    useOrgDifyCredentials?: boolean
  }>(),
  {
    orgsWithoutConfig: () => [],
    isAdmin: true,
    featureMindbot: true,
    dingtalkSecretReplaceMode: false,
    difyApiKeyReplaceMode: false,
    managerSchoolDisplayName: '',
    canLoadUsage: false,
    rotating: false,
    hideOrgSelect: false,
    embeddedPane: undefined,
    useOrgDifyCredentials: false,
  }
)

const emit = defineEmits<{
  rotateCallback: []
  copyUrl: [url: string]
  replaceDingtalkSecret: []
  replaceDifyApiKey: []
}>()

const { t } = useLanguage()
const notify = useNotifications()

const dialogTab = ref<'dingtalk' | 'dify' | 'log' | 'monitor'>('dingtalk')
const aiCardStreamCheckLoading = ref(false)
const aiCardStreamMessage = ref<{ ok: boolean; text: string } | null>(null)
const streamingStatusQueryString = ref('')

const streamingStatusQuery = useAdminMindbotStreamingStatus(
  computed(() => props.editingOrgRow?.id),
  streamingStatusQueryString,
  { enabled: false }
)

const dingtalkFieldLabelClass =
  'mindbot-section-label mindbot-swiss-section-label shrink-0 text-[11px] font-semibold tracking-[0.14em] sm:w-[178px] pt-0.5'

const showSchoolCustomDifyFields = computed(
  () => props.useOrgDifyCredentials && !form.value.use_org_dify_settings
)

type DifySourceChoice = 'org' | 'custom'

/** String values avoid Element Plus radio-button falsy `false` selection bugs. */
const difySourceChoice = computed<DifySourceChoice>({
  get: () => (form.value.use_org_dify_settings ? 'org' : 'custom'),
  set: (choice: DifySourceChoice) => {
    form.value.use_org_dify_settings = choice === 'org'
  },
})

const difySourceOptions = computed(() => [
  { label: t('admin.mindbot.difySourceSchoolDefault'), value: 'org' as const },
  { label: t('admin.mindbot.difySourceCustom'), value: 'custom' as const },
])

const effectiveTab = computed({
  get: () => props.embeddedPane ?? dialogTab.value,
  set: (value: 'dingtalk' | 'dify' | 'log' | 'monitor') => {
    if (!props.embeddedPane) {
      dialogTab.value = value
    }
  },
})

const effectiveDingtalkClientId = computed(() => {
  const fromForm = form.value.dingtalk_client_id.trim()
  if (fromForm) {
    return fromForm
  }
  return (props.editingOrgRow?.dingtalk_client_id ?? '').trim()
})

const effectiveAiCardTemplateId = computed(() => {
  const fromForm = form.value.dingtalk_ai_card_template_id.trim()
  if (fromForm) {
    return fromForm
  }
  return (props.editingOrgRow?.dingtalk_ai_card_template_id ?? '').trim()
})

const hasSavedDingtalkClientSecret = computed(() => {
  return Boolean((props.editingOrgRow?.dingtalk_app_secret_masked ?? '').trim())
})

const canRunAiCardProbe = computed(() => {
  if (props.mode !== 'edit' || !props.editingOrgRow || !props.featureMindbot) {
    return false
  }
  if (!hasSavedDingtalkClientSecret.value) {
    return false
  }
  if (!effectiveDingtalkClientId.value) {
    return false
  }
  if (!effectiveAiCardTemplateId.value) {
    return false
  }
  return true
})

const aiCardProbeTooltip = computed(() => {
  if (!props.featureMindbot) {
    return t('admin.mindbot.dingtalkAiCardStreamCheckTooltip')
  }
  if (props.mode !== 'edit' || !props.editingOrgRow) {
    return t('admin.mindbot.dingtalkAiCardStreamCheckNeedEdit')
  }
  if (!hasSavedDingtalkClientSecret.value) {
    return t('admin.mindbot.dingtalkAiCardStreamCheckNeedSavedSecret')
  }
  if (!effectiveDingtalkClientId.value) {
    return t('admin.mindbot.dingtalkAiCardStreamCheckNeedClientId')
  }
  if (!effectiveAiCardTemplateId.value) {
    return t('admin.mindbot.dingtalkAiCardStreamCheckNeedTemplate')
  }
  return t('admin.mindbot.dingtalkAiCardStreamCheckTooltip')
})

watch(
  () => props.mode,
  () => {
    dialogTab.value = 'dingtalk'
    aiCardStreamMessage.value = null
  }
)

watch(
  () => props.editingOrgRow?.id,
  () => {
    if (props.mode !== 'edit' || !props.editingOrgRow) {
      return
    }
    form.value.use_org_dify_settings = props.editingOrgRow.use_org_dify_settings ?? true
  },
  { immediate: true }
)

function orgLabel(org: OrgOption): string {
  const display = org.display_name?.trim()
  if (display) {
    return display
  }
  return org.name
}

async function checkAiCardStreaming(): Promise<void> {
  const configId = props.editingOrgRow?.id
  if (configId == null || !props.featureMindbot) {
    return
  }
  if (!canRunAiCardProbe.value) {
    const msg = aiCardProbeTooltip.value
    notify.warning(msg)
    aiCardStreamMessage.value = { ok: false, text: msg }
    return
  }
  aiCardStreamCheckLoading.value = true
  aiCardStreamMessage.value = null
  try {
    const params = new URLSearchParams()
    const templateId = form.value.dingtalk_ai_card_template_id.trim()
    if (templateId) {
      params.set('template_id', templateId)
    }
    const clientId = form.value.dingtalk_client_id.trim()
    if (clientId) {
      params.set('dingtalk_client_id', clientId)
    }
    const query = params.toString() ? `?${params.toString()}` : ''
    streamingStatusQueryString.value = query
    const result = await streamingStatusQuery.refetch()
    if (result.error) {
      const detail = result.error instanceof Error ? result.error.message : ''
      const errText = detail || t('admin.mindbot.dingtalkAiCardStreamFail')
      notify.error(errText)
      aiCardStreamMessage.value = { ok: false, text: errText }
      return
    }
    const data = (result.data ?? {}) as {
      ok?: boolean
      error?: string
      detail?: string
      friendly_message?: string
      dingtalk_code?: string
    }
    if (data.ok) {
      notify.success(t('admin.mindbot.dingtalkAiCardStreamOk'))
      aiCardStreamMessage.value = { ok: true, text: t('admin.mindbot.dingtalkAiCardStreamOk') }
    } else {
      const base =
        (typeof data.friendly_message === 'string' && data.friendly_message.trim()) ||
        data.error ||
        t('admin.mindbot.dingtalkAiCardStreamFail')
      const codeSuffix = data.dingtalk_code ? ` (${data.dingtalk_code})` : ''
      const errText = `${base}${codeSuffix}`
      notify.error(errText)
      aiCardStreamMessage.value = { ok: false, text: errText }
    }
  } catch {
    const errText = t('admin.mindbot.dingtalkAiCardStreamFail')
    notify.error(errText)
    aiCardStreamMessage.value = { ok: false, text: errText }
  } finally {
    aiCardStreamCheckLoading.value = false
  }
}

defineExpose({
  resetTabs: () => {
    dialogTab.value = 'dingtalk'
    aiCardStreamMessage.value = null
  },
})
</script>

<template>
  <component
    :is="embeddedPane ? 'div' : 'el-form'"
    label-position="left"
    label-width="178px"
    class="mindbot-settings-form mindbot-swiss-form mindbot-compact space-y-1"
  >
    <el-tabs
      v-model="effectiveTab"
      class="mindbot-dialog-tabs"
      :class="{ 'mindbot-dialog-tabs--embedded': embeddedPane }"
    >
      <el-tab-pane
        name="dingtalk"
        :label="t('admin.mindbot.tabDingtalk')"
      >
        <div
          v-if="mode === 'edit' && editingOrgRow?.public_callback_token"
          class="mindbot-callback-card mindbot-swiss-inset mb-4 rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] p-3 shadow-none"
        >
          <div
            class="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--mindbot-swiss-muted)] mb-1"
          >
            {{ t('admin.mindbot.schoolCallbackUrl') }}
          </div>
          <p class="mindbot-swiss-hint text-xs mb-3 leading-relaxed">
            {{ t('admin.mindbot.schoolCallbackUrlHint') }}
          </p>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-3">
            <code
              class="mindbot-callback-url mindbot-swiss-code block flex-1 min-w-0 max-w-full break-all rounded-sm border border-[var(--mindbot-swiss-border)] bg-[#050505] px-3 py-2.5 text-xs font-mono leading-snug text-[var(--mindbot-swiss-text)]"
              >{{ buildCallbackUrl(editingOrgRow.public_callback_token) }}</code
            >
            <div class="flex flex-wrap items-center gap-2 shrink-0 sm:self-center">
              <el-button
                type="primary"
                size="small"
                :icon="DocumentCopy"
                class="mindbot-pill mindbot-pill--copy"
                @click="emit('copyUrl', buildCallbackUrl(editingOrgRow.public_callback_token))"
              >
                {{ t('admin.mindbot.copyUrl') }}
              </el-button>
              <el-button
                type="warning"
                size="small"
                plain
                :icon="Refresh"
                :loading="rotating"
                class="mindbot-pill mindbot-pill--rotate"
                @click="emit('rotateCallback')"
              >
                {{ t('admin.mindbot.refreshCallbackUrl') }}
              </el-button>
            </div>
          </div>
        </div>
        <div
          v-else-if="mode === 'create'"
          class="mindbot-config-banner mb-4 rounded-sm border px-3 py-2.5 text-xs font-mono leading-snug text-[var(--mindbot-swiss-text)]"
        >
          {{ t('admin.mindbot.callbackUrlAfterSave') }}
        </div>

        <el-form-item
          v-if="mode === 'create' && isAdmin && !hideOrgSelect"
          :label="t('admin.mindbot.orgSelect')"
          required
        >
          <el-select
            v-model="formOrgId"
            class="mindbot-swiss-select w-full max-w-md"
            filterable
          >
            <el-option
              v-for="org in orgsWithoutConfig"
              :key="org.id"
              :label="orgLabel(org)"
              :value="org.id"
            />
          </el-select>
        </el-form-item>

        <div
          class="mindbot-section-label mindbot-swiss-section-label text-[11px] font-semibold uppercase tracking-[0.14em] mb-1.5 mt-0.5"
        >
          {{ t('admin.mindbot.sectionDingTalk') }}
        </div>
        <div
          class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] mindbot-dingtalk-fields space-y-4"
        >
          <div
            v-if="mode === 'create' && !isAdmin"
            class="flex flex-col gap-2 sm:flex-row sm:items-center"
          >
            <span :class="dingtalkFieldLabelClass">{{ t('admin.mindbot.orgSelect') }}</span>
            <span class="mindbot-swiss-inline-value text-sm font-mono flex-1 min-w-0">{{
              managerSchoolDisplayName
            }}</span>
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
            <span :class="dingtalkFieldLabelClass">{{ t('admin.mindbot.dingtalkClientId') }}</span>
            <el-input
              v-model="form.dingtalk_client_id"
              clearable
              autocomplete="off"
              class="mindbot-swiss-input flex-1 min-w-0 w-full font-mono text-sm"
              :placeholder="t('admin.mindbot.dingtalkClientIdPlaceholder')"
            />
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
            <span :class="dingtalkFieldLabelClass">
              {{ t('admin.mindbot.dingtalkAppSecret') }}
              <span
                v-if="mode === 'create' || dingtalkSecretReplaceMode"
                class="text-[var(--el-color-danger)]"
              >*</span>
            </span>
            <div class="flex-1 min-w-0 w-full">
              <template
                v-if="
                  mode === 'edit' &&
                  editingOrgRow?.dingtalk_app_secret_masked &&
                  !dingtalkSecretReplaceMode
                "
              >
                <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
                  <el-input
                    :model-value="editingOrgRow.dingtalk_app_secret_masked"
                    type="text"
                    readonly
                    class="mindbot-swiss-input font-mono text-sm flex-1 min-w-0 w-full"
                  />
                  <el-button
                    type="primary"
                    plain
                    class="mindbot-pill mindbot-pill--replace shrink-0"
                    size="small"
                    @click="emit('replaceDingtalkSecret')"
                  >
                    {{ t('admin.mindbot.replaceSecret') }}
                  </el-button>
                </div>
              </template>
              <el-input
                v-else
                v-model="form.dingtalk_app_secret"
                type="password"
                show-password
                autocomplete="new-password"
                clearable
                class="mindbot-swiss-input w-full"
              />
            </div>
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
            <span :class="dingtalkFieldLabelClass">{{ t('admin.mindbot.botLabel') }}</span>
            <el-input
              v-model="form.bot_label"
              clearable
              maxlength="64"
              class="mindbot-swiss-input flex-1 min-w-0 w-full"
              :placeholder="t('admin.mindbot.botLabel')"
            />
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
            <span :class="dingtalkFieldLabelClass">
              {{ t('admin.mindbot.dingtalkRobotCode') }}
              <span class="text-[var(--el-color-danger)]">*</span>
            </span>
            <el-input
              v-model="form.dingtalk_robot_code"
              clearable
              class="mindbot-input-robot mindbot-swiss-input flex-1 min-w-0 w-full"
            />
          </div>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
            <span :class="dingtalkFieldLabelClass">{{
              t('admin.mindbot.dingtalkAiCardTemplateId')
            }}</span>
            <div class="flex-1 min-w-0 w-full space-y-2">
              <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                <el-input
                  v-model="form.dingtalk_ai_card_template_id"
                  clearable
                  class="mindbot-swiss-input flex-1 min-w-0 w-full font-mono text-sm"
                  :placeholder="t('admin.mindbot.dingtalkAiCardTemplateIdPlaceholder')"
                />
                <el-tooltip
                  placement="top"
                  :content="aiCardProbeTooltip"
                >
                  <el-button
                    type="primary"
                    plain
                    round
                    size="small"
                    class="mindbot-ai-card-ping shrink-0 !rounded-full !px-3 !font-medium"
                    :loading="aiCardStreamCheckLoading"
                    :disabled="!canRunAiCardProbe || aiCardStreamCheckLoading"
                    @click="checkAiCardStreaming"
                  >
                    <el-icon class="mr-0.5"><MagicStick /></el-icon>
                    {{ t('admin.mindbot.dingtalkAiCardStreamCheck') }}
                  </el-button>
                </el-tooltip>
              </div>
              <p
                v-if="aiCardStreamMessage"
                class="text-xs m-0 leading-relaxed"
                :class="
                  aiCardStreamMessage.ok ? 'mindbot-swiss-msg--ok' : 'mindbot-swiss-msg--err'
                "
              >
                {{ aiCardStreamMessage.text }}
              </p>
            </div>
          </div>
          <template v-if="useOrgDifyCredentials">
            <div
              class="border-t border-[var(--mindbot-swiss-border)] pt-4 space-y-4"
            >
              <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
                <span :class="dingtalkFieldLabelClass">
                  {{ t('admin.mindbot.sectionDifySource') }}
                </span>
                <div class="flex-1 min-w-0 w-full">
                  <AdminMindbotSwissSegmented
                    v-model="difySourceChoice"
                    :options="difySourceOptions"
                    block
                    :aria-label="t('admin.mindbot.sectionDifySource')"
                  />
                </div>
              </div>
              <div
                v-if="showSchoolCustomDifyFields"
                class="space-y-4"
              >
                <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
                  <span :class="dingtalkFieldLabelClass">
                    {{ t('admin.mindbot.difyBaseUrl') }}
                    <span class="text-[var(--el-color-danger)]">*</span>
                  </span>
                  <el-input
                    v-model="form.dify_api_base_url"
                    clearable
                    class="mindbot-swiss-input flex-1 min-w-0 w-full"
                  />
                </div>
                <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
                  <span :class="dingtalkFieldLabelClass">
                    {{ t('admin.mindbot.difyApiKey') }}
                    <span
                      v-if="mode === 'create' || difyApiKeyReplaceMode"
                      class="text-[var(--el-color-danger)]"
                    >*</span>
                  </span>
                  <div class="flex-1 min-w-0 w-full">
                    <template
                      v-if="
                        mode === 'edit' &&
                        editingOrgRow?.dify_api_key_masked &&
                        !difyApiKeyReplaceMode
                      "
                    >
                      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
                        <el-input
                          :model-value="editingOrgRow.dify_api_key_masked"
                          type="text"
                          readonly
                          class="mindbot-swiss-input font-mono text-sm flex-1 min-w-0 w-full"
                        />
                        <el-button
                          type="primary"
                          plain
                          class="mindbot-pill mindbot-pill--replace shrink-0"
                          size="small"
                          @click="emit('replaceDifyApiKey')"
                        >
                          {{ t('admin.mindbot.replaceSecret') }}
                        </el-button>
                      </div>
                    </template>
                    <el-input
                      v-else
                      v-model="form.dify_api_key"
                      type="password"
                      show-password
                      autocomplete="new-password"
                      clearable
                      class="mindbot-swiss-input w-full"
                    />
                  </div>
                </div>
                <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <span :class="dingtalkFieldLabelClass">{{ t('admin.mindbot.difyTimeout') }}</span>
                  <el-input-number
                    v-model="form.dify_timeout_seconds"
                    :min="5"
                    :max="600"
                    class="mindbot-swiss-input-number w-full sm:w-40"
                    controls-position="right"
                  />
                </div>
                <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <span :class="dingtalkFieldLabelClass">{{
                    t('admin.mindbot.dingtalkAiCardStreamingMaxChars')
                  }}</span>
                  <el-input-number
                    v-model="form.dingtalk_ai_card_streaming_max_chars"
                    :min="500"
                    :max="50000"
                    :step="100"
                    class="mindbot-swiss-input-number w-full sm:w-48"
                    controls-position="right"
                  />
                </div>
                <div class="school-dify-cot-row flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-0">
                  <span :class="dingtalkFieldLabelClass">{{
                    t('admin.mindbot.difyShowChainOfThought')
                  }}</span>
                  <el-switch
                    v-model="form.show_chain_of_thought"
                    class="mindbot-cot-switch mindbot-footer-enabled-switch shrink-0"
                  />
                </div>
              </div>
            </div>
          </template>
        </div>
      </el-tab-pane>

      <el-tab-pane
        v-if="!useOrgDifyCredentials"
        name="dify"
        :label="t('admin.mindbot.tabDify')"
      >
        <div
          class="mindbot-section-label mindbot-swiss-section-label text-[11px] font-semibold uppercase tracking-[0.14em] mb-1.5 mt-0.5"
        >
          {{ t('admin.mindbot.sectionDify') }}
        </div>
        <div
          class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)]"
        >
          <el-form-item
            :label="t('admin.mindbot.difyBaseUrl')"
            required
          >
            <el-input
              v-model="form.dify_api_base_url"
              clearable
              class="mindbot-swiss-input w-full max-w-2xl"
            />
          </el-form-item>
          <el-form-item
            :label="t('admin.mindbot.difyApiKey')"
            :required="mode === 'create' || difyApiKeyReplaceMode"
          >
            <template
              v-if="
                mode === 'edit' && editingOrgRow?.dify_api_key_masked && !difyApiKeyReplaceMode
              "
            >
              <div class="max-w-2xl space-y-2">
                <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
                  <el-input
                    :model-value="editingOrgRow.dify_api_key_masked"
                    type="text"
                    readonly
                    class="mindbot-swiss-input font-mono text-sm flex-1 min-w-0"
                  />
                  <el-button
                    type="primary"
                    plain
                    class="mindbot-pill mindbot-pill--replace shrink-0"
                    size="small"
                    @click="emit('replaceDifyApiKey')"
                  >
                    {{ t('admin.mindbot.replaceSecret') }}
                  </el-button>
                </div>
                <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
                  {{ t('admin.mindbot.difyApiKeyMaskedHint') }}
                </p>
              </div>
            </template>
            <template v-else>
              <el-input
                v-model="form.dify_api_key"
                type="password"
                show-password
                autocomplete="new-password"
                clearable
                class="mindbot-swiss-input w-full max-w-2xl"
              />
              <div class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl">
                <template v-if="mode === 'create'">
                  {{ t('admin.mindbot.difyApiKeyHint') }}
                </template>
                <template v-else>
                  {{ t('admin.mindbot.difyApiKeyReplaceHint') }}
                </template>
              </div>
            </template>
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.difyTimeout')">
            <el-input-number
              v-model="form.dify_timeout_seconds"
              :min="5"
              :max="600"
              class="mindbot-swiss-input-number w-full sm:w-40"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item :label="t('admin.mindbot.dingtalkAiCardStreamingMaxChars')">
            <el-input-number
              v-model="form.dingtalk_ai_card_streaming_max_chars"
              :min="500"
              :max="50000"
              :step="100"
              class="mindbot-swiss-input-number w-full sm:w-48"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item
            :label="t('admin.mindbot.difyShowChainOfThought')"
            class="mindbot-cot-form-item"
          >
            <div class="mindbot-cot-field">
              <el-switch
                v-model="form.show_chain_of_thought"
                class="mindbot-cot-switch mindbot-footer-enabled-switch"
              />
            </div>
          </el-form-item>
        </div>
      </el-tab-pane>

      <el-tab-pane
        name="log"
        :label="t('admin.mindbot.tabLog')"
        lazy
      >
        <AdminMindBotUsagePanel
          :organization-id="formOrgId"
          :can-load="canLoadUsage"
          mode="log"
        />
      </el-tab-pane>

      <el-tab-pane
        name="monitor"
        :label="t('admin.mindbot.tabMonitor')"
        lazy
      >
        <AdminMindBotUsagePanel
          :organization-id="formOrgId"
          :can-load="canLoadUsage"
          mode="monitor"
        />
      </el-tab-pane>
    </el-tabs>
  </component>
</template>

<style scoped>
.mindbot-config-banner {
  border-color: rgba(34, 211, 238, 0.28);
  background: linear-gradient(
    105deg,
    rgba(227, 6, 19, 0.12) 0%,
    rgba(34, 211, 238, 0.08) 55%,
    rgba(167, 139, 250, 0.06) 100%
  );
  box-shadow: 0 0 14px rgba(34, 211, 238, 0.08);
}

.mindbot-swiss-msg--ok {
  color: #4ade80;
  text-shadow: 0 0 10px rgba(74, 222, 128, 0.35);
}

.mindbot-swiss-msg--err {
  color: #fb7185;
  text-shadow: 0 0 8px rgba(251, 113, 133, 0.25);
}

.mindbot-swiss-inline-label {
  color: var(--mindbot-swiss-muted);
}

.mindbot-swiss-inline-value {
  color: var(--mindbot-swiss-text);
}

.mindbot-swiss-form.mindbot-settings-form :deep(.el-form-item__label) {
  font-family: var(--geek-ulog-font);
  font-weight: 600;
  font-size: 0.6875rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #e2e8f0;
  line-height: 1.35;
  align-items: flex-start;
  height: auto;
  padding-top: 0.4rem;
}

.mindbot-swiss-form.mindbot-settings-form :deep(.mindbot-cot-form-item .el-form-item__label) {
  align-items: center;
  padding-top: 0;
}

.mindbot-settings-form :deep(.el-tabs__content) {
  padding-top: 0.35rem;
}

.mindbot-section-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mindbot-section-label::before {
  content: '';
  width: 0.25rem;
  height: 0.85rem;
  border-radius: 9999px;
  background: linear-gradient(180deg, rgb(203 213 225), rgb(226 232 240));
  flex-shrink: 0;
}

html.dark .mindbot-section-label::before {
  background: linear-gradient(180deg, rgb(71 85 105 / 0.7), rgb(100 116 139 / 0.5));
}

.mindbot-section-label.mindbot-swiss-section-label {
  color: #e2e8f0;
}

.mindbot-section-label.mindbot-swiss-section-label::before {
  width: 3px;
  height: 0.75rem;
  border-radius: 0;
  background: linear-gradient(180deg, #e30613 0%, #22d3ee 100%);
  box-shadow:
    0 0 10px rgba(227, 6, 19, 0.45),
    0 0 14px rgba(34, 211, 238, 0.25);
}

.mindbot-dingtalk-fields :deep(.el-input) {
  width: 100%;
}

.mindbot-section-card--compact {
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.mindbot-settings-form.mindbot-compact :deep(.el-form-item) {
  margin-bottom: 0.5rem;
}

.mindbot-settings-form.mindbot-compact :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.mindbot-callback-url {
  max-height: 5.5rem;
  overflow: auto;
}

.mindbot-input-robot :deep(.el-input__wrapper) {
  font-family: var(--geek-ulog-font);
}

.mindbot-cot-field {
  display: flex;
  align-items: center;
  line-height: 1;
  width: 100%;
  max-width: 42rem;
}

.mindbot-cot-switch.el-switch {
  --el-switch-on-color: #22d3ee;
}

.mindbot-dialog-tabs--embedded :deep(.el-tabs__header) {
  display: none;
}

.mindbot-dialog-tabs--embedded :deep(.el-tabs__content) {
  padding-top: 0;
}
</style>
