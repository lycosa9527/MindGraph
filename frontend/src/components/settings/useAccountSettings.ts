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
import { apiRequest } from '@/utils/apiClient'
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

export function useAccountSettings(isOpen: Ref<boolean>, onSuccess: () => void) {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const { featureWechatLogin, featureWordAddin } = useFeatureFlags()
  const { canUseApiToken, canUseChromeExtension } = useSchoolTierFeatures()

  const showAvatarModal = ref(false)
  const showChangePhoneModal = ref(false)
  const showSetPasswordSmsModal = ref(false)
  const showApiTokenModal = ref(false)
  const showLoginDevicesModal = ref(false)
  const showOAuthBindModal = ref(false)
  const oauthLinksLoading = ref(false)
  const oauthLinks = ref<OauthLinks | null>(null)
  const nameEdit = ref('')
  const nameSaving = ref(false)

  /** Same-origin API paths; cookies sent for GET (session). */
  const openclawSkillZipUrl = '/api/downloads/mindgraph-openclaw-skill'
  const chromeExtensionZipUrl = '/api/downloads/mindgraph-chrome-extension'
  const wordAddinZipUrl = '/api/downloads/mindgraph-word-addin'
  const fileReaderZipUrl = '/api/downloads/mindgraph-file-reader'

  const userPhone = computed(() => {
    const phone = authStore.user?.phone || ''
    if (phone && phone.length === 11) {
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
  const isBayiSsoSubject = computed(() => {
    const phone = (authStore.user?.phone || '').trim()
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(phone)
  })

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
    chromeExtensionZipUrl,
    wordAddinZipUrl,
    fileReaderZipUrl,
    userPhone,
    showAccountBindingsSection,
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
    needsSetLoginPassword,
    openAvatarModal,
    handleAvatarSuccess,
    openChangePhoneModal,
    openSetPasswordSmsModal,
    handlePhoneChangeSuccess,
    saveDisplayName,
  })
}
