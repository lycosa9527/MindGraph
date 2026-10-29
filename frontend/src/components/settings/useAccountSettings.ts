/**
 * Account, security, and plugin actions for UserSettingsModal.
 * Field saves stay immediate; nested dialogs stay mounted for the life of the shell.
 */
import { type Ref, computed, reactive, ref, watch } from 'vue'

import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useAuthStore } from '@/stores/auth'
import { displayAccountLoginValue, resolveAccountLoginIdentity } from '@/utils/accountLoginIdentity'
import { isBayiSsoPhone } from '@/utils/accountPhone'
import { apiRequest } from '@/utils/apiClient'
import { logPairAudit } from '@/utils/dingtalkPairAuditLog'
import {
  canStartWechatBind,
  shouldShowAccountBindingsSection,
  shouldShowWechatBindRow,
} from '@/utils/oauthLoginUi'
import { resolveUserAvatarEmoji, userAvatarImageSrc } from '@/utils/userAvatarEmoji'

export type AccountSettingsSection = 'account' | 'security' | 'plugins'

type OauthLinks = {
  wechat?: { nickname?: string | null; external_id_masked?: string }
  dingtalk?: { nickname?: string | null; external_id_masked?: string }
  wechat_enabled?: boolean
  dingtalk_enabled?: boolean
}

type DingtalkBindStatus = {
  linked: boolean
  mindbot_available: boolean
  dingtalk_staff_id?: string | null
  rate_limited?: boolean
}

export function useAccountSettings(isOpen: Ref<boolean>, onSuccess: () => void) {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const { featureMindbot, featureWechatLogin, featureWordAddin } = useFeatureFlags()
  const { canUseApiToken, canUseChromeExtension } = useSchoolTierFeatures()

  const showAvatarModal = ref(false)
  const showChangePhoneModal = ref(false)
  const showSetPasswordSmsModal = ref(false)
  const showApiTokenModal = ref(false)
  const showLoginDevicesModal = ref(false)
  const showOAuthBindModal = ref(false)
  const showBindDingTalkModal = ref(false)
  const showUnbindDingTalkModal = ref(false)
  const dingtalkBindLoading = ref(false)
  const dingtalkBindStatus = ref<DingtalkBindStatus | null>(null)
  const oauthLinksLoading = ref(false)
  const oauthLinks = ref<OauthLinks | null>(null)
  const nameEdit = ref('')
  const nameSaving = ref(false)

  /** Same-origin API paths; cookies sent for GET (session). */
  const openclawSkillZipUrl = '/api/downloads/mindgraph-openclaw-skill'
  const wordAddinZipUrl = '/api/downloads/mindgraph-word-addin'
  const fileReaderZipUrl = '/api/downloads/mindgraph-file-reader'

  const accountLogin = computed(() =>
    resolveAccountLoginIdentity({
      phone: authStore.user?.phone,
      email: authStore.user?.email,
    })
  )
  const accountLoginLabelKey = computed(() => accountLogin.value.labelKey)
  const accountLoginValue = computed(() => displayAccountLoginValue(accountLogin.value))
  const canChangePhone = computed(() => accountLogin.value.kind === 'mobile')

  const showDingtalkBindSection = computed(
    () => Boolean(authStore.user?.schoolId) && featureMindbot.value
  )
  const dingtalkLinked = computed(() => dingtalkBindStatus.value?.linked === true)
  const canMintDingtalkBind = computed(() => dingtalkBindStatus.value?.mindbot_available === true)
  const dingtalkStaffMasked = computed(() => dingtalkBindStatus.value?.dingtalk_staff_id || '')
  const dingtalkBindingStatus = computed(() => {
    if (dingtalkLinked.value && dingtalkStaffMasked.value) {
      return t('auth.dingtalkBindLinkedLabel', { staff: dingtalkStaffMasked.value })
    }
    if (dingtalkLinked.value) {
      return t('auth.dingtalkBindLinkedButton')
    }
    return t('auth.bindingUnlinked')
  })

  const showAccountBindingsSection = computed(() =>
    shouldShowAccountBindingsSection({
      schoolId: authStore.user?.schoolId,
      featureWechatLogin: featureWechatLogin.value,
      wechatAvailable: oauthLinks.value?.wechat_enabled === true,
      wechatLinked: oauthLinks.value?.wechat != null,
      featureMindbot: featureMindbot.value,
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
        oauthLinks.value = (await res.json()) as OauthLinks
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

  async function fetchDingtalkBindStatus() {
    if (!authStore.user?.schoolId || !featureMindbot.value) {
      dingtalkBindStatus.value = null
      return
    }
    dingtalkBindLoading.value = true
    const previous = dingtalkBindStatus.value
    try {
      const response = await apiRequest('/api/auth/dingtalk-bind/status', { method: 'GET' })
      if (response.ok) {
        dingtalkBindStatus.value = (await response.json()) as DingtalkBindStatus
        return
      }
      if (response.status === 429 && previous) {
        dingtalkBindStatus.value = { ...previous, rate_limited: true }
        return
      }
      dingtalkBindStatus.value = {
        linked: previous?.linked ?? false,
        mindbot_available: previous?.mindbot_available ?? false,
        dingtalk_staff_id: previous?.dingtalk_staff_id,
      }
    } catch {
      dingtalkBindStatus.value = previous ?? { linked: false, mindbot_available: false }
    } finally {
      dingtalkBindLoading.value = false
    }
  }

  function openBindDingTalkModal() {
    if (!canMintDingtalkBind.value) {
      notify.warningKey('auth.dingtalkBindNoMindbot')
      return
    }
    logPairAudit('account_open_bind', { purpose: 'bind' }, { reportToServer: false })
    void fetchDingtalkBindStatus().then(() => {
      if (canMintDingtalkBind.value) {
        showBindDingTalkModal.value = true
      }
    })
  }

  function openUnbindDingTalkModal() {
    if (!dingtalkLinked.value) {
      return
    }
    logPairAudit('account_open_unbind', { purpose: 'unbind' }, { reportToServer: false })
    void fetchDingtalkBindStatus().then(() => {
      if (dingtalkLinked.value) {
        showUnbindDingTalkModal.value = true
      }
    })
  }

  function handleDingtalkBindCompleted() {
    void fetchDingtalkBindStatus()
  }

  function openWechatBindModal() {
    showOAuthBindModal.value = true
  }

  async function unbindWechat() {
    try {
      const res = await apiRequest('/api/auth/oauth/links/wechat', { method: 'DELETE' })
      if (res.ok) {
        notify.successKey('auth.unbindWechatSuccess')
        await fetchOauthLinks()
        onSuccess()
      } else {
        notify.errorKey('auth.oauthUnbindError')
      }
    } catch {
      notify.errorKey('auth.oauthUnbindError')
    }
  }

  function handleOAuthBindSuccess() {
    void fetchOauthLinks()
    onSuccess()
  }

  const currentAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))
  const currentAvatarSrc = computed(() => userAvatarImageSrc(authStore.user?.avatar))

  /** Bayi jump-in stores a UUID in phone. That id must stay put. */
  const isBayiSsoSubject = computed(() => isBayiSsoPhone(authStore.user?.phone))

  /** Verified profile still has no real name. A cached flag alone does not count. */
  const promptDisplayName = computed(
    () => authStore.isAuthSessionVerified && authStore.user?.needsDisplayName === true
  )

  /** Quick registration: server-only password until user sets one via SMS. */
  const needsSetLoginPassword = computed(() => authStore.user?.loginPasswordSet === false)

  function openAvatarModal() {
    showAvatarModal.value = true
  }

  function handleAvatarSuccess() {
    onSuccess()
  }

  function openChangePhoneModal() {
    showChangePhoneModal.value = true
  }

  function openSetPasswordSmsModal() {
    showSetPasswordSmsModal.value = true
  }

  function handlePhoneChangeSuccess() {
    onSuccess()
  }

  async function saveDisplayName() {
    const trimmed = nameEdit.value.trim()
    if (trimmed.length < 2 || /\d/.test(trimmed)) {
      notify.warningKey('auth.modal.fillRequired')
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
        notify.successKey('auth.accountNameSaveSuccess')
        const current = authStore.user
        if (current) {
          authStore.setUser({ ...current, username: trimmed, needsDisplayName: false })
        }
        await authStore.refreshUserProfile({ bypassThrottle: true })
        onSuccess()
      } else {
        notify.error(
          (typeof data.detail === 'string' && data.detail) || t('auth.accountNameSaveError')
        )
      }
    } catch {
      notify.errorKey('auth.accountNameSaveError')
    } finally {
      nameSaving.value = false
    }
  }

  function resetNameDraft() {
    const username = (authStore.user?.username || '').trim()
    const looksLikeName =
      username.length >= 2 &&
      username.length <= 32 &&
      !/^\d{11}$/.test(username) &&
      !/^\d+$/.test(username)
    nameEdit.value = authStore.user?.needsDisplayName || !looksLikeName ? '' : username
  }

  watch(
    isOpen,
    (open) => {
      if (!open) {
        showOAuthBindModal.value = false
        showBindDingTalkModal.value = false
        showUnbindDingTalkModal.value = false
        return
      }
      resetNameDraft()
    },
    { immediate: true }
  )

  watch(
    () => isOpen.value && featureWechatLogin.value && Boolean(authStore.user?.schoolId),
    (shouldFetch) => {
      if (shouldFetch) {
        void fetchOauthLinks()
      }
    },
    { immediate: true }
  )

  watch(
    () => isOpen.value && featureMindbot.value && Boolean(authStore.user?.schoolId),
    (shouldFetch) => {
      if (shouldFetch) {
        void fetchDingtalkBindStatus()
      }
    },
    { immediate: true }
  )

  return reactive({
    t,
    authStore,
    featureWordAddin,
    canUseApiToken,
    canUseChromeExtension,
    showAvatarModal,
    showChangePhoneModal,
    showSetPasswordSmsModal,
    showApiTokenModal,
    showLoginDevicesModal,
    showOAuthBindModal,
    oauthLinksLoading,
    nameEdit,
    nameSaving,
    openclawSkillZipUrl,
    wordAddinZipUrl,
    fileReaderZipUrl,
    accountLoginLabelKey,
    accountLoginValue,
    canChangePhone,
    showAccountBindingsSection,
    showDingtalkBindSection,
    dingtalkBindLoading,
    dingtalkLinked,
    canMintDingtalkBind,
    dingtalkStaffMasked,
    dingtalkBindingStatus,
    showBindDingTalkModal,
    showUnbindDingTalkModal,
    openBindDingTalkModal,
    openUnbindDingTalkModal,
    handleDingtalkBindCompleted,
    showWechatOAuthRow,
    canBindWechat,
    wechatOAuthLinked,
    wechatBindingStatus,
    openWechatBindModal,
    unbindWechat,
    handleOAuthBindSuccess,
    currentAvatar,
    currentAvatarSrc,
    isBayiSsoSubject,
    promptDisplayName,
    needsSetLoginPassword,
    openAvatarModal,
    handleAvatarSuccess,
    openChangePhoneModal,
    openSetPasswordSmsModal,
    handlePhoneChangeSuccess,
    saveDisplayName,
  })
}
