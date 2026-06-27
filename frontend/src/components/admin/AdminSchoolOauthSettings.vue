<script setup lang="ts">
/**
 * Embedded OAuth QR login settings (WeChat toggle + DingTalk keys) for 其他设置 tab.
 */
import { computed, ref, watch } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import {
  fetchAdminOrganizationOauthConfig,
  updateAdminOrganizationOauthConfig,
  type AdminOrganizationOauthConfig,
} from '@/composables/queries/adminApi'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

const props = defineProps<{
  orgId: number
  readOnly?: boolean
  active?: boolean
}>()

const emit = defineEmits<{
  (e: 'saved'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { featureOauthLogin } = useFeatureFlags()

const loading = ref(false)
const saving = ref(false)
const config = ref<AdminOrganizationOauthConfig | null>(null)

const wechatEnabled = ref(false)
const dingtalkEnabled = ref(false)
const dingtalkAppKey = ref('')
const dingtalkCorpId = ref('')
const dingtalkSecret = ref('')
const clearDingtalkSecret = ref(false)
const replaceDingtalkSecret = ref(false)

const labelClass =
  'mindbot-section-label mindbot-swiss-section-label shrink-0 text-[11px] font-semibold tracking-[0.14em] sm:w-[178px]'

const showSection = computed(() => featureOauthLogin.value && props.orgId > 0)

const fieldsReadOnly = computed(() => props.readOnly === true || saving.value)

async function loadConfig(): Promise<void> {
  if (!showSection.value) {
    config.value = null
    return
  }
  loading.value = true
  try {
    const row = await fetchAdminOrganizationOauthConfig(props.orgId)
    config.value = row
    wechatEnabled.value = row.wechat_login_enabled
    dingtalkEnabled.value = row.dingtalk_login_enabled
    dingtalkAppKey.value = row.dingtalk_login_app_key
    dingtalkCorpId.value = row.dingtalk_corp_id
    dingtalkSecret.value = ''
    clearDingtalkSecret.value = false
    replaceDingtalkSecret.value = false
  } catch (err) {
    notify.error(httpErrorDetail(err) || t('admin.oauth.loadError'))
  } finally {
    loading.value = false
  }
}

async function saveConfig(): Promise<boolean> {
  if (!showSection.value || fieldsReadOnly.value || loading.value || !config.value) {
    return true
  }
  saving.value = true
  try {
    const body: Parameters<typeof updateAdminOrganizationOauthConfig>[1] = {
      wechatLoginEnabled: wechatEnabled.value,
      dingtalkLoginEnabled: dingtalkEnabled.value,
      dingtalkLoginAppKey: dingtalkAppKey.value.trim() || undefined,
      dingtalkCorpId: dingtalkCorpId.value.trim() || undefined,
      clearDingtalkSecret: clearDingtalkSecret.value,
    }
    if (replaceDingtalkSecret.value && dingtalkSecret.value.trim()) {
      body.dingtalkLoginAppSecret = dingtalkSecret.value.trim()
    }
    const row = await updateAdminOrganizationOauthConfig(props.orgId, body)
    config.value = row
    dingtalkSecret.value = ''
    clearDingtalkSecret.value = false
    replaceDingtalkSecret.value = false
    emit('saved')
    return true
  } catch (err) {
    notify.error(httpErrorDetail(err) || t('admin.oauth.saveError'))
    return false
  } finally {
    saving.value = false
  }
}

function startReplaceSecret(): void {
  replaceDingtalkSecret.value = true
  clearDingtalkSecret.value = false
  dingtalkSecret.value = ''
}

function clearSecret(): void {
  clearDingtalkSecret.value = true
  replaceDingtalkSecret.value = false
  dingtalkSecret.value = ''
}

watch(
  () => [props.orgId, props.active, featureOauthLogin.value] as const,
  ([orgId, active, enabled]) => {
    if (orgId && active !== false && enabled) {
      void loadConfig()
    }
  },
  { immediate: true }
)

defineExpose({ saveConfig })
</script>

<template>
  <div
    v-if="showSection"
    class="mindbot-section-card mindbot-section-card--compact mindbot-swiss-inset rounded-sm border border-[var(--mindbot-swiss-border)] bg-[var(--mindbot-swiss-inset)] p-3 sm:p-4 space-y-4"
  >
    <div class="flex flex-col gap-1 sm:flex-row sm:items-start">
      <span :class="labelClass">{{ t('admin.oauth.sectionTitle') }}</span>
      <div class="flex-1 min-w-0 max-w-2xl space-y-3">
        <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
          {{ t('admin.oauth.intro') }}
        </p>
        <p class="mindbot-swiss-hint text-xs m-0 leading-relaxed">
          {{ t('admin.oauth.officialDocsHint') }}
        </p>
      </div>
    </div>

    <div
      v-if="loading"
      class="flex items-center gap-2 text-sm mindbot-swiss-hint py-2"
    >
      <Loading class="w-4 h-4 animate-spin" />
      {{ t('common.loading') }}
    </div>

    <template v-else-if="config">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <span :class="labelClass">{{ t('admin.oauth.wechatToggle') }}</span>
        <div class="flex-1 min-w-0 max-w-2xl space-y-1">
          <el-switch
            v-model="wechatEnabled"
            :disabled="fieldsReadOnly"
          />
          <p class="mindbot-swiss-hint text-xs m-0">
            {{ t('admin.oauth.wechatHint') }}
          </p>
          <p
            v-if="config.wechat_app_id"
            class="mindbot-swiss-hint text-xs m-0 break-all"
          >
            AppID: {{ config.wechat_app_id }}
          </p>
        </div>
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span :class="labelClass">{{ t('admin.oauth.dingtalkToggle') }}</span>
        <div class="flex-1 min-w-0 max-w-2xl space-y-3">
          <el-switch
            v-model="dingtalkEnabled"
            :disabled="fieldsReadOnly"
          />

          <div class="space-y-1">
            <label class="block text-xs font-medium mindbot-swiss-hint">
              {{ t('admin.oauth.dingtalkAppKey') }}
            </label>
            <el-input
              v-model="dingtalkAppKey"
              autocomplete="off"
              :disabled="fieldsReadOnly"
              class="mindbot-swiss-input w-full"
            />
          </div>

          <div class="space-y-1">
            <label class="block text-xs font-medium mindbot-swiss-hint">
              {{ t('admin.oauth.dingtalkCorpId') }}
            </label>
            <el-input
              v-model="dingtalkCorpId"
              autocomplete="off"
              :placeholder="t('admin.oauth.dingtalkCorpIdPlaceholder')"
              :disabled="fieldsReadOnly"
              class="mindbot-swiss-input w-full"
            />
          </div>

          <div class="space-y-1">
            <label class="block text-xs font-medium mindbot-swiss-hint">
              {{ t('admin.oauth.dingtalkAppSecret') }}
            </label>
            <p
              v-if="config.dingtalk_login_app_secret_set && !replaceDingtalkSecret"
              class="mindbot-swiss-hint text-xs m-0"
            >
              {{ t('admin.oauth.secretSet') }}
              <button
                v-if="!fieldsReadOnly"
                type="button"
                class="text-stone-700 underline ml-2"
                @click="startReplaceSecret"
              >
                {{ t('admin.oauth.replaceSecret') }}
              </button>
              <button
                v-if="!fieldsReadOnly"
                type="button"
                class="text-red-600 underline ml-2"
                @click="clearSecret"
              >
                {{ t('admin.oauth.clearSecret') }}
              </button>
            </p>
            <el-input
              v-if="!config.dingtalk_login_app_secret_set || replaceDingtalkSecret"
              v-model="dingtalkSecret"
              type="password"
              show-password
              autocomplete="new-password"
              :disabled="fieldsReadOnly"
              class="mindbot-swiss-input w-full"
            />
            <p
              v-if="clearDingtalkSecret"
              class="text-xs text-amber-700 m-0"
            >
              {{ t('admin.oauth.clearSecretPending') }}
            </p>
          </div>
        </div>
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span :class="labelClass">{{ t('admin.oauth.callbackUrls') }}</span>
        <div class="flex-1 min-w-0 max-w-2xl space-y-1 text-xs mindbot-swiss-hint break-all">
          <p class="m-0">
            <span class="font-medium">{{ t('admin.oauth.wechatCallback') }}:</span>
            {{ config.wechat_callback_url || '—' }}
          </p>
          <p class="m-0">
            <span class="font-medium">{{ t('admin.oauth.dingtalkCallback') }}:</span>
            {{ config.dingtalk_callback_url || '—' }}
          </p>
        </div>
      </div>

      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span :class="labelClass">{{ t('admin.oauth.schoolItChecklistTitle') }}</span>
        <p class="flex-1 min-w-0 max-w-2xl text-xs mindbot-swiss-hint m-0 whitespace-pre-line leading-relaxed">
          {{ t('admin.oauth.schoolItChecklist') }}
        </p>
      </div>
    </template>
  </div>
</template>
