<script setup lang="ts">
/**
 * MindBot create/edit modal: phosphor-terminal shell + Swiss red primary, DingTalk + Dify + usage tabs.
 * Latin/UI typography matches UpdateLogModal (JetBrains Mono / Cascadia Code stack).
 */
import { computed, ref, watch } from 'vue'

import { DocumentCopy, MagicStick, Refresh } from '@element-plus/icons-vue'

import AdminMindBotUsagePanel from '@/components/admin/AdminMindBotUsagePanel.vue'
import type {
  MindbotConfigFormState,
  MindbotConfigRow,
  OrgOption,
} from '@/components/admin/mindbotConfigTypes'
import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const visible = defineModel<boolean>({ required: true })
const form = defineModel<MindbotConfigFormState>('form', { required: true })
const formOrgId = defineModel<number | null>('formOrgId', { required: true })

const props = defineProps<{
  mode: 'create' | 'edit'
  editingOrgRow?: MindbotConfigRow
  orgsWithoutConfig: OrgOption[]
  isAdmin: boolean
  featureMindbot: boolean
  saving: boolean
  rotating: boolean
  dingtalkSecretReplaceMode: boolean
  difyApiKeyReplaceMode: boolean
  managerSchoolDisplayName: string
  /** Resolved school display name for the dialog subtitle (钉钉机器人【name】). */
  schoolDisplayName: string
  canLoadUsage: boolean
  buildCallbackUrl: (token: string) => string
}>()

const emit = defineEmits<{
  save: []
  closed: []
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

/** Effective OpenAPI app key: form overrides saved row. */
const effectiveDingtalkClientId = computed(() => {
  const fromForm = form.value.dingtalk_client_id.trim()
  if (fromForm) {
    return fromForm
  }
  return (props.editingOrgRow?.dingtalk_client_id ?? '').trim()
})

/** Effective template id: form overrides saved row (must match DingTalk published id, e.g. *.schema). */
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

/**
 * Probe calls DingTalk with credentials stored on the server (saved Client Secret).
 * Client ID and template id may be taken from the form or last-saved config.
 */
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

watch(visible, (open) => {
  if (open) {
    dialogTab.value = 'dingtalk'
    aiCardStreamMessage.value = null
  }
})

function orgLabel(org: OrgOption): string {
  const display = org.display_name?.trim()
  if (display) {
    return display
  }
  return org.name
}

async function checkAiCardStreaming(): Promise<void> {
  const oid = formOrgId.value
  if (oid == null || !props.featureMindbot) {
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
    const tid = form.value.dingtalk_ai_card_template_id.trim()
    if (tid) {
      params.set('template_id', tid)
    }
    const cid = form.value.dingtalk_client_id.trim()
    if (cid) {
      params.set('dingtalk_client_id', cid)
    }
    const q = params.toString() ? `?${params.toString()}` : ''
    const res = await apiRequest(`/api/mindbot/admin/configs/${oid}/ai-card-streaming-status${q}`)
    const data = (await res.json()) as {
      ok?: boolean
      error?: string
      detail?: string
      friendly_message?: string
      dingtalk_code?: string
    }
    if (!res.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : ''
      const errText = detail || t('admin.mindbot.dingtalkAiCardStreamFail')
      notify.error(errText)
      aiCardStreamMessage.value = { ok: false, text: errText }
      return
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

function onClose(): void {
  visible.value = false
}

function onDialogClosed(): void {
  emit('closed')
}
</script>

<template>
  <el-dialog
    v-model="visible"
    class="mindbot-settings-dialog mindbot-swiss-dialog"
    width="min(720px, 94vw)"
    destroy-on-close
    append-to-body
    align-center
    modal-class="mindbot-swiss-backdrop"
    :show-close="true"
    @closed="onDialogClosed"
  >
    <template #header>
      <div class="mindbot-swiss-header mindbot-config-header">
        <span class="mindbot-swiss-header__glyph">◇</span>
        <span class="mindbot-swiss-header__title">{{
          mode === 'create' ? t('admin.mindbot.create') : t('admin.mindbot.edit')
        }}</span>
        <span
          class="mindbot-swiss-header__divider"
          aria-hidden="true"
          >·</span
        >
        <span class="mindbot-swiss-header__note">{{
          t('admin.mindbot.dialogHeaderNote', {
            name: (schoolDisplayName || '').trim() || '—',
          })
        }}</span>
      </div>
    </template>
    <div class="mindbot-config-body">
      <div
        class="mindbot-config-scanlines"
        aria-hidden="true"
      />
      <div class="mindbot-swiss-form-wrap">
        <el-form
          label-position="left"
          label-width="178px"
          class="mindbot-settings-form mindbot-swiss-form mindbot-compact space-y-1"
        >
          <el-tabs
            v-model="dialogTab"
            class="mindbot-dialog-tabs"
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
                      @click="
                        emit('copyUrl', buildCallbackUrl(editingOrgRow.public_callback_token))
                      "
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
                v-if="mode === 'create' && isAdmin"
                :label="t('admin.mindbot.orgSelect')"
              >
                <el-select
                  v-model="formOrgId"
                  class="mindbot-swiss-select w-full max-w-md"
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

              <div
                class="mindbot-section-label mindbot-swiss-section-label text-[11px] font-semibold uppercase tracking-[0.14em] mb-1.5 mt-0.5"
              >
                {{ t('admin.mindbot.sectionDingTalk') }}
              </div>
              <div
                class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)]"
              >
                <el-form-item
                  v-if="mode === 'create' && !isAdmin"
                  class="!mb-2"
                >
                  <template #label>
                    <span class="mindbot-swiss-inline-label text-sm font-normal">{{
                      t('admin.mindbot.orgSelect')
                    }}</span>
                  </template>
                  <span class="mindbot-swiss-inline-value text-sm font-mono">{{
                    managerSchoolDisplayName
                  }}</span>
                </el-form-item>
                <el-form-item :label="t('admin.mindbot.dingtalkClientId')">
                  <el-input
                    v-model="form.dingtalk_client_id"
                    clearable
                    autocomplete="off"
                    class="mindbot-swiss-input w-full max-w-2xl font-mono text-sm"
                    :placeholder="t('admin.mindbot.dingtalkClientIdPlaceholder')"
                  />
                  <div class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl">
                    {{ t('admin.mindbot.dingtalkClientIdHint') }}
                  </div>
                </el-form-item>
                <el-form-item :label="t('admin.mindbot.dingtalkAppSecret')">
                  <template
                    v-if="
                      mode === 'edit' &&
                      editingOrgRow?.dingtalk_app_secret_masked &&
                      !dingtalkSecretReplaceMode
                    "
                  >
                    <div class="max-w-2xl space-y-2">
                      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
                        <el-input
                          :model-value="editingOrgRow.dingtalk_app_secret_masked"
                          type="text"
                          readonly
                          class="mindbot-swiss-input font-mono text-sm flex-1 min-w-0"
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
                      <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
                        {{ t('admin.mindbot.dingtalkAppSecretMaskedHint') }}
                      </p>
                    </div>
                  </template>
                  <template v-else>
                    <el-input
                      v-model="form.dingtalk_app_secret"
                      type="password"
                      show-password
                      autocomplete="new-password"
                      clearable
                      class="mindbot-swiss-input w-full max-w-2xl"
                    />
                    <div class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl">
                      <template v-if="mode === 'create'">
                        {{ t('admin.mindbot.dingtalkAppSecretHint') }}
                      </template>
                      <template v-else>
                        {{ t('admin.mindbot.dingtalkAppSecretReplaceHint') }}
                      </template>
                    </div>
                  </template>
                </el-form-item>
                <el-form-item :label="t('admin.mindbot.dingtalkRobotCode')">
                  <el-input
                    v-model="form.dingtalk_robot_code"
                    clearable
                    class="mindbot-input-robot mindbot-swiss-input w-full max-w-md"
                  />
                  <div class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-xl">
                    {{ t('admin.mindbot.dingtalkRobotCodeHint') }}
                  </div>
                </el-form-item>
                <el-form-item :label="t('admin.mindbot.dingtalkAiCardTemplateId')">
                  <div
                    class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3 w-full max-w-2xl"
                  >
                    <el-input
                      v-model="form.dingtalk_ai_card_template_id"
                      clearable
                      class="mindbot-swiss-input flex-1 min-w-0 font-mono text-sm"
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
                    class="text-xs mt-1.5 m-0 leading-relaxed max-w-2xl"
                    :class="
                      aiCardStreamMessage.ok ? 'mindbot-swiss-msg--ok' : 'mindbot-swiss-msg--err'
                    "
                  >
                    {{ aiCardStreamMessage.text }}
                  </p>
                  <p class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl m-0">
                    {{ t('admin.mindbot.dingtalkAiCardTemplateIdHint') }}
                  </p>
                </el-form-item>
              </div>
            </el-tab-pane>

            <el-tab-pane
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
                <el-form-item :label="t('admin.mindbot.difyBaseUrl')">
                  <el-input
                    v-model="form.dify_api_base_url"
                    clearable
                    class="mindbot-swiss-input w-full max-w-2xl"
                  />
                </el-form-item>
                <el-form-item :label="t('admin.mindbot.difyApiKey')">
                  <template
                    v-if="
                      mode === 'edit' &&
                      editingOrgRow?.dify_api_key_masked &&
                      !difyApiKeyReplaceMode
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
                <el-form-item>
                  <el-input
                    v-model="form.dify_inputs_json"
                    type="textarea"
                    :rows="4"
                    class="mindbot-swiss-input font-mono text-sm w-full max-w-2xl"
                  />
                  <div class="mindbot-swiss-hint text-xs mt-1.5 leading-relaxed max-w-2xl">
                    {{ t('admin.mindbot.difyInputsJsonHint') }}
                  </div>
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
                <el-form-item :label="t('admin.mindbot.difyShowChainOfThought')">
                  <div class="mindbot-cot-field max-w-2xl">
                    <el-switch
                      v-model="form.show_chain_of_thought"
                      class="mindbot-cot-switch"
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
        </el-form>
      </div>
    </div>
    <template #footer>
      <div
        class="mindbot-dialog-footer flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="mindbot-footer-enable flex min-w-0 items-center gap-2 sm:gap-2.5">
          <span class="mindbot-footer-enable__label">{{ t('admin.mindbot.enabled') }}</span>
          <el-switch
            v-model="form.is_enabled"
            class="mindbot-footer-enabled-switch shrink-0"
          />
        </div>
        <div
          class="flex shrink-0 flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end sm:gap-2"
        >
          <el-button
            class="mindbot-pill mindbot-pill--footer-cancel"
            @click="onClose"
          >
            {{ t('admin.cancel') }}
          </el-button>
          <el-button
            type="primary"
            class="mindbot-pill mindbot-pill--footer-save"
            :loading="saving"
            @click="emit('save')"
          >
            {{ t('admin.mindbot.save') }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.mindbot-settings-dialog.mindbot-swiss-dialog {
  width: min(92vw, 720px) !important;
  max-width: 100%;
  border-radius: 2px;
  overflow: hidden;
}

.mindbot-settings-dialog.mindbot-swiss-dialog :deep(.el-dialog__footer) {
  padding: 0;
}

.mindbot-config-body {
  position: relative;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

.mindbot-config-scanlines {
  pointer-events: none;
  position: absolute;
  inset: 0;
  z-index: 2;
  border-radius: 2px;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.14) 2px,
    rgba(0, 0, 0, 0.14) 3px
  );
  opacity: 0.3;
}

.mindbot-swiss-form-wrap {
  --mindbot-swiss-red: #e30613;
  --mindbot-geek-cyan: #22d3ee;
  --mindbot-geek-violet: #a78bfa;
  --mindbot-swiss-border: rgba(34, 211, 238, 0.32);
  --mindbot-swiss-inset: rgba(15, 23, 42, 0.72);
  --mindbot-swiss-muted: #a8b7c9;
  --mindbot-swiss-text: #f1f5f9;
  position: relative;
  z-index: 3;
  padding: 0.75rem 1.25rem 0.5rem;
}

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

.mindbot-swiss-hint {
  color: var(--mindbot-swiss-muted);
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

.mindbot-swiss-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem 0.5rem;
  font-family: var(--geek-ulog-font);
}

.mindbot-config-header {
  font-family: var(--geek-ulog-font);
}

.mindbot-swiss-header__glyph {
  color: #22d3ee;
  text-shadow: 0 0 12px rgba(34, 211, 238, 0.55);
  font-weight: 700;
  font-size: 1rem;
  flex-shrink: 0;
  line-height: 1;
}

.mindbot-swiss-header__title {
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #e2e8f0;
  text-shadow:
    0 0 1px rgba(226, 232, 240, 0.85),
    0 0 18px rgba(167, 139, 250, 0.35);
}

.mindbot-swiss-header__divider {
  color: rgba(148, 163, 184, 0.55);
  font-weight: 700;
  user-select: none;
}

.mindbot-swiss-header__note {
  flex: 1 1 10rem;
  min-width: 0;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  line-height: 1.35;
  text-transform: uppercase;
  color: #f9a8d4;
  text-shadow:
    0 0 10px rgba(249, 168, 212, 0.3),
    0 0 16px rgba(167, 139, 250, 0.18);
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

.mindbot-dialog-footer {
  padding: 0.75rem 1.25rem 1rem;
  border-top: 1px solid rgba(34, 211, 238, 0.2);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.85) 0%, #020617 100%);
  box-shadow: inset 0 1px 0 rgba(227, 6, 19, 0.12);
}

.mindbot-footer-enable__label {
  font-family: var(--geek-ulog-font);
  font-weight: 600;
  font-size: 0.6875rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #e2e8f0;
  line-height: 1.35;
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

.mindbot-hint {
  line-height: 1.4;
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
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
  width: 100%;
  max-width: 42rem;
}

.mindbot-cot-switch.el-switch {
  --el-switch-on-color: #22d3ee;
}
</style>

<style>
/*
 * Same monospace stack as UpdateLogModal (`.ulog-header` / `.ulog-md`) — no extra webfont load.
 */
.mindbot-swiss-dialog.el-dialog {
  --geek-ulog-font:
    ui-monospace, 'JetBrains Mono', 'Cascadia Code', 'SFMono-Regular', Consolas, monospace;
  --geek-surface-deep: #020617;
  --geek-surface: #0f172a;
  --geek-elevated: #1e293b;
  --geek-elevated-hover: #334155;
  --geek-text: #f8fafc;
  --geek-text-soft: #e2e8f0;
  --geek-dim: #cbd5e1;
  --geek-cyan: #22d3ee;
  --geek-amber: #fbbf24;
  --geek-amber-text: #fef3c7;
  --geek-swit: #e30613;
  --el-dialog-bg-color: transparent;
  --el-dialog-padding-primary: 0;
  font-family: var(--geek-ulog-font);
  font-variant-numeric: tabular-nums;
  background: linear-gradient(
    165deg,
    var(--geek-surface) 0%,
    var(--geek-surface-deep) 48%,
    #0a0f1a 100%
  );
  border: 1px solid rgba(34, 211, 238, 0.38);
  border-radius: 3px;
  box-shadow:
    0 0 0 1px rgba(167, 139, 250, 0.12),
    0 0 40px rgba(34, 211, 238, 0.12),
    0 0 80px rgba(99, 102, 241, 0.08),
    0 0 32px rgba(227, 6, 19, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
  overflow: hidden;
}

.mindbot-swiss-dialog .el-dialog__header {
  margin: 0;
  padding: 0.85rem 2.85rem 0.65rem 1rem;
  position: relative;
  border-bottom: 1px solid rgba(34, 211, 238, 0.2);
  background: linear-gradient(
    90deg,
    rgba(227, 6, 19, 0.12) 0%,
    rgba(34, 211, 238, 0.08) 38%,
    transparent 62%
  );
}

.mindbot-swiss-dialog .el-dialog__headerbtn {
  top: 0.65rem;
  right: 0.65rem;
  width: 2rem;
  height: 2rem;
}

.mindbot-swiss-dialog .el-dialog__headerbtn .el-dialog__close {
  color: #64748b;
  font-size: 1.1rem;
  transition:
    color 0.15s ease,
    filter 0.15s ease;
}

.mindbot-swiss-dialog .el-dialog__headerbtn:hover .el-dialog__close {
  color: #f472b6;
  filter: drop-shadow(0 0 6px rgba(244, 114, 182, 0.55));
}

.mindbot-swiss-dialog .el-dialog__body {
  padding: 0;
  color: var(--geek-text-soft);
}

.el-overlay.mindbot-swiss-backdrop {
  backdrop-filter: blur(4px);
}

.mindbot-swiss-dialog .el-input__wrapper {
  border-radius: 2px;
  background-color: rgba(15, 23, 42, 0.65);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.18) inset;
  font-family: var(--geek-ulog-font);
  font-size: 0.8125rem;
}

.mindbot-swiss-dialog .el-input__wrapper:hover {
  box-shadow:
    0 0 0 1px rgba(34, 211, 238, 0.45) inset,
    0 0 14px rgba(34, 211, 238, 0.12);
}

.mindbot-swiss-dialog .el-input__inner {
  color: #f1f5f9;
  font-family: var(--geek-ulog-font);
  font-size: 0.8125rem;
  letter-spacing: 0.02em;
}

.mindbot-swiss-dialog .el-input__inner::placeholder,
.mindbot-swiss-dialog .el-textarea__inner::placeholder {
  color: rgba(148, 163, 184, 0.92);
}

.mindbot-swiss-dialog .el-textarea__inner {
  border-radius: 2px;
  background-color: rgba(15, 23, 42, 0.65);
  color: #f1f5f9;
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.18) inset;
  font-family: var(--geek-ulog-font);
  font-size: 0.8125rem;
  line-height: 1.55;
  letter-spacing: 0.02em;
}

.mindbot-swiss-dialog .el-textarea__inner:hover {
  box-shadow:
    0 0 0 1px rgba(227, 6, 19, 0.28) inset,
    0 0 12px rgba(227, 6, 19, 0.08);
}

.mindbot-swiss-dialog .mindbot-swiss-input-number .el-input__wrapper {
  border-radius: 2px;
}

.mindbot-swiss-dialog .el-select .el-select__wrapper {
  border-radius: 2px;
  background-color: rgba(15, 23, 42, 0.65);
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.18) inset;
  font-family: var(--geek-ulog-font);
  font-size: 0.8125rem;
}

.mindbot-swiss-dialog .el-select .el-select__placeholder,
.mindbot-swiss-dialog .el-select .el-select__selected-item {
  color: #f1f5f9;
  font-family: var(--geek-ulog-font);
  font-size: 0.8125rem;
  letter-spacing: 0.02em;
}

.mindbot-swiss-dialog .mindbot-dialog-tabs .el-tabs__header {
  margin: 0 0 0.5rem;
}

.mindbot-swiss-dialog .mindbot-dialog-tabs .el-tabs__nav-wrap::after {
  display: none;
}

.mindbot-swiss-dialog .mindbot-dialog-tabs .el-tabs__nav {
  display: flex;
  gap: 0.35rem;
  padding: 0.35rem;
  width: 100%;
  border-radius: 2px;
  background: rgba(30, 41, 59, 0.72);
  border: 1px solid rgba(34, 211, 238, 0.22);
}

.mindbot-swiss-dialog .mindbot-dialog-tabs .el-tabs__item {
  flex: 1;
  justify-content: center;
  height: 2.25rem;
  line-height: 2.25rem;
  padding: 0 0.65rem;
  border-radius: 2px;
  font-family: var(--geek-ulog-font);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid transparent;
  color: var(--geek-dim);
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.mindbot-swiss-dialog .mindbot-dialog-tabs .el-tabs__item:hover {
  color: var(--geek-text);
  background: rgba(34, 211, 238, 0.1);
  border-color: rgba(34, 211, 238, 0.18);
}

.mindbot-swiss-dialog .mindbot-dialog-tabs .el-tabs__item.is-active {
  color: #ffffff !important;
  font-weight: 700;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
  background: linear-gradient(165deg, #b91c1c 0%, var(--geek-swit) 52%, #7f1d1d 100%);
  border: 1px solid rgba(252, 165, 165, 0.35);
  box-shadow:
    0 0 0 1px rgba(34, 211, 238, 0.22),
    0 0 18px rgba(34, 211, 238, 0.14);
}

.mindbot-swiss-dialog .mindbot-dialog-tabs .el-tabs__active-bar {
  display: none;
}

.mindbot-swiss-dialog .mindbot-pill--footer-cancel.el-button {
  border-radius: 2px;
  font-family: var(--geek-ulog-font);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  --el-button-bg-color: var(--geek-elevated);
  --el-button-border-color: rgba(148, 163, 184, 0.45);
  --el-button-text-color: var(--geek-text);
  --el-button-hover-bg-color: var(--geek-elevated-hover);
  --el-button-hover-border-color: rgba(34, 211, 238, 0.5);
  --el-button-hover-text-color: #ffffff;
  --el-button-active-bg-color: var(--geek-elevated-hover);
  --el-button-active-border-color: rgba(34, 211, 238, 0.45);
  --el-button-active-text-color: #ffffff;
}

.mindbot-swiss-dialog .mindbot-pill--footer-cancel.el-button:hover {
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.12);
}

.mindbot-swiss-dialog .mindbot-pill--footer-save.el-button--primary {
  border-radius: 2px;
  --el-button-bg-color: #e30613;
  --el-button-border-color: #c50512;
  --el-button-text-color: #ffffff;
  --el-button-hover-bg-color: #ff1a1f;
  --el-button-hover-border-color: #e30613;
  --el-button-hover-text-color: #ffffff;
  font-family: var(--geek-ulog-font);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  box-shadow:
    0 0 0 1px rgba(34, 211, 238, 0.15),
    0 0 20px rgba(227, 6, 19, 0.25);
}

.mindbot-swiss-dialog .mindbot-pill--copy.el-button--primary,
.mindbot-swiss-dialog .mindbot-pill--replace.el-button--primary.is-plain {
  border-radius: 2px;
  font-family: var(--geek-ulog-font);
  font-size: 0.75rem;
  font-weight: 600;
  --el-button-bg-color: var(--geek-elevated);
  --el-button-border-color: rgba(34, 211, 238, 0.42);
  --el-button-text-color: var(--geek-text);
  --el-button-hover-bg-color: var(--geek-elevated-hover);
  --el-button-hover-border-color: rgba(34, 211, 238, 0.65);
  --el-button-hover-text-color: #ffffff;
  --el-button-active-bg-color: var(--geek-elevated-hover);
  --el-button-active-border-color: rgba(34, 211, 238, 0.55);
  --el-button-active-text-color: #ffffff;
}

.mindbot-swiss-dialog .mindbot-pill--rotate.el-button--warning.is-plain {
  border-radius: 2px;
  font-family: var(--geek-ulog-font);
  font-size: 0.75rem;
  font-weight: 600;
  --el-button-bg-color: rgba(69, 26, 3, 0.65);
  --el-button-border-color: rgba(251, 191, 36, 0.45);
  --el-button-text-color: var(--geek-amber-text);
  --el-button-hover-bg-color: rgba(120, 53, 15, 0.55);
  --el-button-hover-border-color: rgba(251, 191, 36, 0.72);
  --el-button-hover-text-color: #fffbeb;
  --el-button-active-bg-color: rgba(120, 53, 15, 0.65);
  --el-button-active-border-color: rgba(251, 191, 36, 0.72);
}

.mindbot-swiss-dialog .mindbot-ai-card-ping {
  border-radius: 2px !important;
  font-family: var(--geek-ulog-font);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  --el-button-bg-color: var(--geek-surface);
  --el-button-border-color: rgba(34, 211, 238, 0.5);
  --el-button-text-color: #ecfeff;
  --el-button-hover-bg-color: var(--geek-elevated);
  --el-button-hover-border-color: rgba(227, 6, 19, 0.55);
  --el-button-hover-text-color: #ffffff;
}

.mindbot-swiss-dialog .mindbot-footer-enabled-switch.el-switch {
  --el-switch-on-color: var(--geek-swit);
}
</style>
