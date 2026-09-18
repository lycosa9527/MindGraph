<script setup lang="ts">
/**
 * AccountInfoModal - Modal for displaying and editing user account information
 *
 * Design: Swiss Design (Modern Minimalism)
 */
import { computed, ref, watch } from 'vue'

import { Loader2, UserRound } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'
import {
  canStartWechatBind,
  shouldShowAccountBindingsSection,
  shouldShowWechatBindRow,
} from '@/utils/oauthLoginUi'
import { resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'

import ApiTokenModal from './ApiTokenModal.vue'
import AvatarSelectModal from './AvatarSelectModal.vue'
import ChangePasswordModal from './ChangePasswordModal.vue'
import ChangePhoneModal from './ChangePhoneModal.vue'
import LoginDevicesModal from './LoginDevicesModal.vue'
import OAuthQrLoginModal from './OAuthQrLoginModal.vue'
import SetPasswordWithSmsModal from './SetPasswordWithSmsModal.vue'

const { t } = useLanguage()
const notify = useNotifications()

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()
const { featureWechatLogin, featureWordAddin } = useFeatureFlags()
const { canUseApiToken, canUseChromeExtension, showAccountPlugins } = useSchoolTierFeatures()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const showAvatarModal = ref(false)
const showChangePhoneModal = ref(false)
const showChangePasswordModal = ref(false)
const showSetPasswordSmsModal = ref(false)
const showApiTokenModal = ref(false)
const showLoginDevicesModal = ref(false)
const showOAuthBindModal = ref(false)
const oauthLinksLoading = ref(false)
const oauthLinks = ref<{
  wechat?: { nickname?: string | null; external_id_masked?: string }
  dingtalk?: { nickname?: string | null; external_id_masked?: string }
  wechat_enabled?: boolean
  dingtalk_enabled?: boolean
} | null>(null)
const nameEdit = ref('')
const nameSaving = ref(false)

/** Same-origin API paths; cookies sent for GET (session). */
const openclawSkillZipUrl = '/api/downloads/mindgraph-openclaw-skill'
const chromeExtensionZipUrl = '/api/downloads/mindgraph-chrome-extension'
const wordAddinZipUrl = '/api/downloads/mindgraph-word-addin'

// Get user data
const userPhone = computed(() => {
  const phone = authStore.user?.phone || ''
  if (phone && phone.length === 11) {
    // Mask middle 4 digits: 13812345678 -> 138****5678
    return `${phone.slice(0, 3)}****${phone.slice(7)}`
  }
  return phone
})

const showAccountBindingsSection = computed(() =>
  shouldShowAccountBindingsSection({
    schoolId: authStore.user?.schoolId,
    featureWechatLogin: featureWechatLogin.value,
    wechatAvailable: oauthLinks.value?.wechat_enabled === true,
    wechatLinked: oauthLinks.value?.wechat != null,
  })
)

const showWechatOAuthRow = computed(() =>
  shouldShowWechatBindRow({
    showBindingsSection: showAccountBindingsSection.value,
    featureWechatLogin: featureWechatLogin.value,
    wechatAvailable: oauthLinks.value?.wechat_enabled === true,
    wechatLinked: oauthLinks.value?.wechat != null,
  })
)

const canBindWechat = computed(() =>
  canStartWechatBind({
    featureWechatLogin: featureWechatLogin.value,
    wechatAvailable: oauthLinks.value?.wechat_enabled === true,
  })
)

const wechatOAuthLinked = computed(() => oauthLinks.value?.wechat != null)

const wechatBindingStatus = computed(() => {
  if (!wechatOAuthLinked.value) {
    return t('auth.bindingUnlinked')
  }
  return (
    oauthLinks.value?.wechat?.nickname ||
    oauthLinks.value?.wechat?.external_id_masked ||
    t('auth.oauthLinkedFallback')
  )
})

async function fetchOauthLinks() {
  if (!authStore.user?.schoolId || !featureWechatLogin.value) {
    oauthLinks.value = null
    return
  }
  oauthLinksLoading.value = true
  try {
    const res = await apiRequest('/api/auth/oauth/links', { method: 'GET' })
    if (res.ok) {
      oauthLinks.value = (await res.json()) as typeof oauthLinks.value
    } else {
      oauthLinks.value = {
        wechat_enabled: false,
        dingtalk_enabled: false,
      }
    }
  } catch {
    oauthLinks.value = {
      wechat_enabled: false,
      dingtalk_enabled: false,
    }
  } finally {
    oauthLinksLoading.value = false
  }
}

function openWechatBindModal() {
  showOAuthBindModal.value = true
}

async function unbindWechat() {
  try {
    const res = await apiRequest('/api/auth/oauth/links/wechat', { method: 'DELETE' })
    if (res.ok) {
      notify.success(t('auth.unbindWechatSuccess'))
      await fetchOauthLinks()
      emit('success')
    } else {
      notify.error(t('auth.oauthUnbindError'))
    }
  } catch {
    notify.error(t('auth.oauthUnbindError'))
  }
}

function handleOAuthBindSuccess() {
  void fetchOauthLinks()
  emit('success')
}

const currentAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))

/** Quick registration: server-only password until user sets one via SMS. */
const needsSetLoginPassword = computed(() => authStore.user?.loginPasswordSet === false)

function closeModal() {
  showOAuthBindModal.value = false
  isVisible.value = false
}

function openAvatarModal() {
  showAvatarModal.value = true
}

function handleAvatarSuccess() {
  emit('success')
}

function openChangePhoneModal() {
  showChangePhoneModal.value = true
}

function openChangePasswordModal() {
  showChangePasswordModal.value = true
}

function openSetPasswordSmsModal() {
  showSetPasswordSmsModal.value = true
}

function handlePhoneChangeSuccess() {
  emit('success')
}

async function saveDisplayName() {
  const trimmed = nameEdit.value.trim()
  if (trimmed.length < 2 || /\d/.test(trimmed)) {
    notify.warning(t('auth.modal.fillRequired'))
    return
  }
  nameSaving.value = true
  try {
    const res = await apiRequest('/api/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify({ name: trimmed }),
    })
    const data = (await res.json().catch(() => ({}))) as { detail?: string }
    if (res.ok) {
      notify.success(t('auth.accountNameSaveSuccess'))
      await authStore.checkAuth()
      emit('success')
    } else {
      notify.error(
        (typeof data.detail === 'string' && data.detail) || t('auth.accountNameSaveError')
      )
    }
  } catch {
    notify.error(t('auth.accountNameSaveError'))
  } finally {
    nameSaving.value = false
  }
}

watch(
  () => [props.visible, featureWechatLogin.value] as const,
  ([visible, wechatEnabled]) => {
    if (visible) {
      const u = (authStore.user?.username || '').trim()
      const looksLikeName =
        u.length >= 2 && u.length <= 32 && !/^\d{11}$/.test(u) && !/^\d+$/.test(u)
      nameEdit.value = looksLikeName ? u : ''
      if (wechatEnabled && authStore.user?.schoolId) {
        void fetchOauthLinks()
      }
    }
  }
)
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.account.ribbon')"
    ribbon-key="swissGlass.hero.account.ribbon"
    :title="t('swissGlass.hero.account.title')"
    title-key="swissGlass.hero.account.title"
    :line1="t('swissGlass.hero.account.line1')"
    line1-key="swissGlass.hero.account.line1"
    :icon="UserRound"
    @close="closeModal"
  >
    <div class="space-y-6">
      <!-- Avatar Section -->
      <div>
        <label class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-4">
          <I18nText k="auth.accountAvatar" />
        </label>
        <div class="flex flex-wrap items-center gap-4">
          <div class="text-5xl shrink-0 mg-user-avatar-emoji">{{ currentAvatar }}</div>
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost shrink-0"
            @click="openAvatarModal"
          >
            <I18nText k="common.edit" />
          </button>
        </div>
      </div>

      <!-- User Information (Read-only fields) -->
      <div class="space-y-4">
        <div>
          <label
            class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
            for="account-info-name"
          >
            <I18nText k="auth.accountDisplayName" />
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <input
              id="account-info-name"
              v-model="nameEdit"
              type="text"
              name="account-info-name"
              :placeholder="t('auth.accountNamePlaceholder')"
              class="min-w-0 flex-1 px-4 py-3 bg-stone-50 border border-stone-200 rounded-lg text-stone-900 text-sm"
            />
            <button
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--primary shrink-0"
              :disabled="nameSaving"
              @click="saveDisplayName"
            >
              <Loader2
                v-if="nameSaving"
                class="w-3.5 h-3.5 animate-spin"
              />
              <I18nText k="auth.accountNameSave" />
            </button>
          </div>
        </div>

        <div>
          <label
            class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
            for="account-info-phone"
          >
            <I18nText k="auth.phone" />
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <input
              id="account-info-phone"
              :value="userPhone || t('auth.notSet')"
              type="text"
              name="account-info-phone"
              disabled
              class="min-w-0 flex-1 px-4 py-3 bg-stone-100 border-0 rounded-lg text-stone-500 cursor-not-allowed"
            />
            <div class="flex shrink-0 items-center gap-2">
              <button
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
                @click="openChangePhoneModal"
              >
                <I18nText k="auth.changePhoneButton" />
              </button>
              <button
                v-if="needsSetLoginPassword && authStore.user?.phone"
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
                @click="openSetPasswordSmsModal"
              >
                <I18nText k="auth.setPasswordWithSms" />
              </button>
              <button
                v-else-if="!needsSetLoginPassword"
                type="button"
                class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
                @click="openChangePasswordModal"
              >
                <I18nText k="auth.changePassword" />
              </button>
            </div>
          </div>
        </div>

        <div
          v-if="showAccountBindingsSection"
          class="space-y-4"
        >
          <label class="block text-xs font-medium text-stone-400 uppercase tracking-wide">
            <I18nText k="auth.accountBindingsSection" />
          </label>

          <div v-if="showWechatOAuthRow">
            <label
              class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
              for="account-binding-wechat"
            >
              <I18nText k="auth.bindingWechat" />
            </label>
            <div class="flex items-center gap-2">
              <input
                id="account-binding-wechat"
                :value="wechatBindingStatus"
                type="text"
                name="account-binding-wechat"
                disabled
                class="min-w-0 flex-1 h-11 px-4 bg-stone-100 border-0 rounded-lg text-stone-500 cursor-not-allowed"
              />
              <button
                v-if="wechatOAuthLinked"
                type="button"
                class="account-binding-action"
                :disabled="oauthLinksLoading"
                @click="unbindWechat"
              >
                <Loader2
                  v-if="oauthLinksLoading"
                  class="w-3.5 h-3.5 animate-spin"
                />
                <I18nText k="auth.unbindWechat" />
              </button>
              <button
                v-else-if="canBindWechat"
                type="button"
                class="account-binding-action"
                :disabled="oauthLinksLoading"
                @click="openWechatBindModal"
              >
                <Loader2
                  v-if="oauthLinksLoading"
                  class="w-3.5 h-3.5 animate-spin"
                />
                <I18nText k="auth.bindWechat" />
              </button>
            </div>
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2">
            <I18nText :k="showAccountPlugins ? 'auth.accountPlugin' : 'auth.loginDevicesButton'" />
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <a
              v-if="canUseApiToken"
              class="account-plugin-pill account-plugin-pill--openclaw"
              :href="openclawSkillZipUrl"
              :title="t('auth.downloadOpenclawSkillHint')"
              download
            >
              <I18nText k="auth.downloadOpenclawSkill" />
            </a>
            <a
              v-if="canUseChromeExtension"
              class="account-plugin-pill account-plugin-pill--chrome"
              :href="chromeExtensionZipUrl"
              download
            >
              <I18nText k="auth.downloadChromeExtension" />
            </a>
            <a
              v-if="featureWordAddin && canUseChromeExtension"
              class="account-plugin-pill account-plugin-pill--word"
              :href="wordAddinZipUrl"
              download
            >
              <I18nText k="auth.downloadWordAddin" />
            </a>
            <button
              v-if="canUseApiToken"
              type="button"
              class="account-plugin-pill account-plugin-pill--token"
              @click="showApiTokenModal = true"
            >
              <I18nText k="auth.apiTokenButton" />
            </button>
            <button
              type="button"
              class="account-plugin-pill account-plugin-pill--devices"
              @click="showLoginDevicesModal = true"
            >
              <I18nText k="auth.loginDevicesButton" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="closeModal"
        >
          <I18nText k="common.close" />
        </button>
      </div>
    </template>
  </SwissGlassCard>

  <!-- Avatar Select Modal -->
  <AvatarSelectModal
    v-model:visible="showAvatarModal"
    @success="handleAvatarSuccess"
  />

  <!-- Change Phone Modal -->
  <ChangePhoneModal
    v-model:visible="showChangePhoneModal"
    @success="handlePhoneChangeSuccess"
  />

  <ChangePasswordModal v-model:visible="showChangePasswordModal" />

  <SetPasswordWithSmsModal
    v-model:visible="showSetPasswordSmsModal"
    @success="emit('success')"
  />

  <ApiTokenModal
    v-if="canUseApiToken"
    v-model:visible="showApiTokenModal"
  />

  <LoginDevicesModal v-model:visible="showLoginDevicesModal" />

  <OAuthQrLoginModal
    v-model:visible="showOAuthBindModal"
    invite-code=""
    mode="bind"
    initial-provider="wechat"
    lock-provider
    @success="handleOAuthBindSuccess"
  />
</template>

<style scoped>
.account-binding-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  height: 2.75rem;
  padding: 0 1rem;
  border-radius: 10px;
  border: 1px solid var(--swiss-border-strong, #d6d3d1);
  background: var(--swiss-surface, #ffffff);
  color: var(--swiss-body, #44403c);
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  line-height: 1;
  white-space: normal;
  text-align: start;
  flex-shrink: 0;
  height: auto;
  min-height: 2.75rem;
  cursor: pointer;
  font-family: inherit;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    opacity 0.15s ease,
    color 0.15s ease;
}

.account-binding-action:hover:not(:disabled) {
  border-color: var(--swiss-body, #44403c);
  background: var(--swiss-hover, #f5f5f4);
}

.account-binding-action:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/*
 * Plugin row — light Swiss tones: cool mist, soft blue-gray, warm sand.
 * Dark text on pale fills; subtle border; hover deepens slightly.
 */
.account-plugin-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.9rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  border: 1px solid;
  text-decoration: none;
  cursor: pointer;
  font-family: inherit;
  line-height: 1.2;
  white-space: normal;
  text-align: start;
  height: auto;
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease;
}

.account-plugin-pill--openclaw {
  color: #3f3f3c;
  background: #ecebe8;
  border-color: #d4d0c8;
}

.account-plugin-pill--openclaw:hover {
  background: #e3e1dc;
  border-color: #c4bfb5;
  color: #292524;
}

.account-plugin-pill--chrome {
  color: #334155;
  background: #e8eef2;
  border-color: #c4d0e0;
}

.account-plugin-pill--chrome:hover {
  background: #dde6ec;
  border-color: #a8b8cc;
  color: #1e293b;
}

.account-plugin-pill--word {
  color: #1e3a5f;
  background: #e8f0f8;
  border-color: #b8cce0;
}

.account-plugin-pill--word:hover {
  background: #dce8f4;
  border-color: #9ab4d0;
  color: #0f2744;
}

.account-plugin-pill--token {
  color: #44403c;
  background: #f0ebe6;
  border-color: #d9cfc4;
}

.account-plugin-pill--token:hover {
  background: #e8e0d8;
  border-color: #ccc0b8;
  color: #1c1917;
}

.account-plugin-pill--devices {
  color: #3f3f46;
  background: #ececf0;
  border-color: #d4d4d8;
}

.account-plugin-pill--devices:hover {
  background: #e4e4e7;
  border-color: #c4c4cc;
  color: #18181b;
}
</style>
