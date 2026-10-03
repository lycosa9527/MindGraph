<script setup lang="ts">
/**
 * Change-password fields shared by Settings security and the mobile password card.
 * A successful change revokes sessions and signs the user out.
 */
import { ref, useSlots, watch } from 'vue'

import { Eye, EyeOff, Loader2, RefreshCw } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useTsecCaptcha } from '@/composables/auth/useTsecCaptcha'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'

const props = defineProps<{
  /** Refresh the captcha when the form becomes visible. */
  active: boolean
}>()

const emit = defineEmits<{
  success: []
}>()

const slots = useSlots()
const authStore = useAuthStore()
const featureFlagsStore = useFeatureFlagsStore()
const notify = useNotifications()
const { t } = useLanguage()
const { isTsecCaptcha, showLegacyCaptcha, resolveCaptchaProof } = useTsecCaptcha()

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const captcha = ref('')
const captchaId = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)
const isLoading = ref(false)
const showCurrentPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

function resetForm() {
  currentPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  captcha.value = ''
  captchaId.value = ''
  captchaImage.value = ''
  showCurrentPassword.value = false
  showNewPassword.value = false
  showConfirmPassword.value = false
}

async function refreshCaptcha() {
  if (!featureFlagsStore.flags) {
    await featureFlagsStore.fetchFlags()
  }
  if (isTsecCaptcha.value) {
    return
  }
  captchaLoading.value = true
  try {
    const result = await authStore.fetchCaptcha()
    if (result) {
      captchaId.value = result.captcha_id
      captchaImage.value = result.captcha_image
    } else {
      notify.errorKey('auth.modal.captchaLoadFailed')
    }
  } catch (error) {
    console.error('Captcha error:', error)
    notify.errorKey('auth.modal.captchaNetworkError')
  } finally {
    captchaLoading.value = false
  }
}

watch(
  () => props.active,
  (isActive) => {
    if (!isActive) {
      resetForm()
      return
    }
    void refreshCaptcha()
  },
  { immediate: true }
)

async function handleSubmit() {
  if (!currentPassword.value || !newPassword.value || !confirmPassword.value) {
    notify.warningKey('auth.modal.fillAllFields')
    return
  }
  if (newPassword.value.length < 8) {
    notify.warningKey('auth.modal.passwordMin8')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    notify.warningKey('auth.modal.passwordMismatch')
    return
  }

  isLoading.value = true
  try {
    const proof = await resolveCaptchaProof(captcha.value, captchaId.value)
    if (!proof) {
      return
    }
    const response = await fetch('/api/auth/change-password', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: currentPassword.value,
        new_password: newPassword.value,
        captcha: proof.captcha,
        captcha_id: proof.captcha_id,
      }),
    })
    const data = (await response.json()) as { message?: string; detail?: string }
    if (response.ok) {
      const msg =
        typeof data.message === 'string' && data.message
          ? data.message
          : t('auth.passwordChangeSuccess')
      notify.success(msg)
      emit('success')
      await authStore.logout()
      return
    }
    notify.error(typeof data.detail === 'string' ? data.detail : t('auth.passwordChangeFailed'))
    captcha.value = ''
    void refreshCaptcha()
  } catch (error) {
    console.error('Failed to change password:', error)
    notify.errorKey('auth.passwordChangeFailed')
    captcha.value = ''
    void refreshCaptcha()
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <form
    class="swiss-glass-stack"
    @submit.prevent="handleSubmit"
  >
    <input
      id="change-password-username"
      type="text"
      name="username"
      :value="authStore.user?.phone || authStore.user?.username || ''"
      autocomplete="username"
      class="sr-only"
      tabindex="-1"
      aria-hidden="true"
      readonly
    />

    <label
      class="swiss-glass-field"
      for="change-password-current"
    >
      <span class="swiss-glass-field__kicker">
        <I18nText k="auth.modal.currentPassword" />
      </span>
      <span class="change-password-field">
        <input
          id="change-password-current"
          v-model="currentPassword"
          :type="showCurrentPassword ? 'text' : 'password'"
          name="change-password-current"
          :placeholder="t('auth.modal.currentPasswordPlaceholder')"
          autocomplete="current-password"
          class="swiss-glass-field__input change-password-field__input"
        />
        <button
          type="button"
          class="change-password-field__toggle"
          @click="showCurrentPassword = !showCurrentPassword"
        >
          <Eye
            v-if="showCurrentPassword"
            class="w-4 h-4"
          />
          <EyeOff
            v-else
            class="w-4 h-4"
          />
        </button>
      </span>
    </label>

    <label
      class="swiss-glass-field"
      for="change-password-new"
    >
      <span class="swiss-glass-field__kicker">
        <I18nText k="auth.modal.newPassword" />
      </span>
      <span class="change-password-field">
        <input
          id="change-password-new"
          v-model="newPassword"
          :type="showNewPassword ? 'text' : 'password'"
          name="change-password-new"
          :placeholder="t('auth.modal.passwordMinPlaceholder')"
          autocomplete="new-password"
          class="swiss-glass-field__input change-password-field__input"
        />
        <button
          type="button"
          class="change-password-field__toggle"
          @click="showNewPassword = !showNewPassword"
        >
          <Eye
            v-if="showNewPassword"
            class="w-4 h-4"
          />
          <EyeOff
            v-else
            class="w-4 h-4"
          />
        </button>
      </span>
    </label>

    <label
      class="swiss-glass-field"
      for="change-password-confirm"
    >
      <span class="swiss-glass-field__kicker">
        <I18nText k="auth.modal.confirmPassword" />
      </span>
      <span class="change-password-field">
        <input
          id="change-password-confirm"
          v-model="confirmPassword"
          :type="showConfirmPassword ? 'text' : 'password'"
          name="change-password-confirm"
          :placeholder="t('auth.modal.confirmPasswordPlaceholder')"
          autocomplete="new-password"
          class="swiss-glass-field__input change-password-field__input"
        />
        <button
          type="button"
          class="change-password-field__toggle"
          @click="showConfirmPassword = !showConfirmPassword"
        >
          <Eye
            v-if="showConfirmPassword"
            class="w-4 h-4"
          />
          <EyeOff
            v-else
            class="w-4 h-4"
          />
        </button>
      </span>
    </label>

    <label
      v-if="showLegacyCaptcha"
      class="swiss-glass-field"
      for="change-password-captcha"
    >
      <span class="swiss-glass-field__kicker">
        <I18nText k="auth.captcha" />
      </span>
      <span class="captcha-row">
        <input
          id="change-password-captcha"
          v-model="captcha"
          type="text"
          name="change-password-captcha"
          :placeholder="t('auth.modal.captchaPlaceholderShort')"
          maxlength="4"
          autocomplete="off"
          autocapitalize="off"
          spellcheck="false"
          class="swiss-glass-field__input captcha-row__input"
        />
        <img
          v-if="captchaImage && !captchaLoading"
          :src="captchaImage"
          :alt="t('auth.captcha')"
          class="captcha-image"
          :title="t('auth.clickToRefresh')"
          @click="refreshCaptcha"
        />
        <button
          v-else
          type="button"
          class="captcha-placeholder"
          @click="refreshCaptcha"
        >
          <Loader2
            v-if="captchaLoading"
            class="w-5 h-5 animate-spin"
          />
          <RefreshCw
            v-else
            class="w-5 h-5"
          />
        </button>
      </span>
    </label>

    <slot name="before-actions" />

    <div :class="{ 'change-password-actions': Boolean(slots.aside) }">
      <slot name="aside" />
      <button
        type="submit"
        :disabled="isLoading || captchaLoading"
        class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
        :class="{ 'w-full': !slots.aside }"
      >
        <Loader2
          v-if="isLoading"
          class="w-4 h-4 animate-spin"
        />
        <I18nText :k="isLoading ? 'auth.modal.changingPassword' : 'auth.modal.confirmChange'" />
      </button>
    </div>
  </form>
</template>

<style scoped>
.change-password-field {
  position: relative;
  display: block;
}

.change-password-field__input {
  padding-inline-end: 2.5rem;
}

.change-password-field__toggle {
  position: absolute;
  inset-inline-end: 0.65rem;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  padding: 0.15rem;
  border: 0;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
}

.change-password-field__toggle:hover {
  color: #57534e;
}

button.captcha-placeholder {
  padding: 0;
  font: inherit;
}
</style>
