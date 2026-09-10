<script setup lang="ts">
/**
 * ChangePasswordModal - Modal for changing user password
 *
 * Design: Swiss Design (Modern Minimalism)
 */
import { computed, ref, watch } from 'vue'

import { Eye, EyeOff, KeyRound, Loader2, RefreshCw } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useTsecCaptcha } from '@/composables/auth/useTsecCaptcha'
import { useAuthStore, useFeatureFlagsStore } from '@/stores'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()
const featureFlagsStore = useFeatureFlagsStore()
const notify = useNotifications()
const { t } = useLanguage()
const { isTsecCaptcha, showLegacyCaptcha, resolveCaptchaProof } = useTsecCaptcha()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const formData = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
  captcha: '',
})

const captchaId = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)

const isLoading = ref(false)
const showCurrentPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

function resetForm() {
  formData.value = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
    captcha: '',
  }
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
      notify.error(t('auth.modal.captchaLoadFailed'))
    }
  } catch (error) {
    console.error('Captcha error:', error)
    notify.error(t('auth.modal.captchaNetworkError'))
  } finally {
    captchaLoading.value = false
  }
}

function closeModal() {
  isVisible.value = false
  resetForm()
}

watch(
  () => props.visible,
  (newValue) => {
    if (!newValue) {
      resetForm()
    } else {
      void refreshCaptcha()
    }
  }
)

async function handleSubmit() {
  if (
    !formData.value.currentPassword ||
    !formData.value.newPassword ||
    !formData.value.confirmPassword
  ) {
    notify.warning(t('auth.modal.fillAllFields'))
    return
  }

  if (formData.value.newPassword.length < 8) {
    notify.warning(t('auth.modal.passwordMin8'))
    return
  }

  if (formData.value.newPassword !== formData.value.confirmPassword) {
    notify.warning(t('auth.modal.passwordMismatch'))
    return
  }

  isLoading.value = true

  try {
    const proof = await resolveCaptchaProof(formData.value.captcha, captchaId.value)
    if (!proof) {
      return
    }
    const response = await fetch('/api/auth/change-password', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: formData.value.currentPassword,
        new_password: formData.value.newPassword,
        captcha: proof.captcha,
        captcha_id: proof.captcha_id,
      }),
    })

    const data = await response.json()

    if (response.ok) {
      const msg =
        typeof data.message === 'string' && data.message
          ? data.message
          : t('auth.passwordChangeSuccess')
      notify.success(msg)
      closeModal()
      emit('success')
      // Server revokes refresh tokens and invalidates sessions; clear client state and cookies
      await authStore.logout()
    } else {
      notify.error(typeof data.detail === 'string' ? data.detail : t('auth.passwordChangeFailed'))
      formData.value.captcha = ''
      void refreshCaptcha()
    }
  } catch (error) {
    console.error('Failed to change password:', error)
    notify.error(t('auth.passwordChangeFailed'))
    formData.value.captcha = ''
    void refreshCaptcha()
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.password.ribbon')"
    :title="t('swissGlass.hero.password.title')"
    :line1="t('swissGlass.hero.password.line1')"
    :icon="KeyRound"
    @close="closeModal"
  >
    <form
      class="space-y-5"
      @submit.prevent="handleSubmit"
    >
      <!-- Hidden username field for accessibility and password managers -->
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

      <!-- Current password -->
      <div>
        <label
          class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
          for="change-password-current"
        >
          当前密码
        </label>
        <div class="relative">
          <input
            id="change-password-current"
            v-model="formData.currentPassword"
            :type="showCurrentPassword ? 'text' : 'password'"
            name="change-password-current"
            placeholder="请输入当前密码"
            autocomplete="current-password"
            class="w-full px-4 py-3 pr-11 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
          />
          <button
            type="button"
            class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
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
        </div>
      </div>

      <!-- New password -->
      <div>
        <label
          class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
          for="change-password-new"
        >
          新密码
        </label>
        <div class="relative">
          <input
            id="change-password-new"
            v-model="formData.newPassword"
            :type="showNewPassword ? 'text' : 'password'"
            name="change-password-new"
            placeholder="至少8位字符"
            autocomplete="new-password"
            class="w-full px-4 py-3 pr-11 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
          />
          <button
            type="button"
            class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
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
        </div>
      </div>

      <!-- Confirm password -->
      <div>
        <label
          class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
          for="change-password-confirm"
        >
          确认新密码
        </label>
        <div class="relative">
          <input
            id="change-password-confirm"
            v-model="formData.confirmPassword"
            :type="showConfirmPassword ? 'text' : 'password'"
            name="change-password-confirm"
            placeholder="再次输入新密码"
            autocomplete="new-password"
            class="w-full px-4 py-3 pr-11 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
          />
          <button
            type="button"
            class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
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
        </div>
      </div>

      <!-- Captcha -->
      <div v-if="showLegacyCaptcha">
        <label
          class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
          for="change-password-captcha"
        >
          {{ t('auth.captcha') }}
        </label>
        <div class="captcha-row">
          <input
            id="change-password-captcha"
            v-model="formData.captcha"
            type="text"
            name="change-password-captcha"
            :placeholder="t('auth.modal.captchaPlaceholderShort')"
            maxlength="4"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
            class="captcha-row__input px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
          />
          <img
            v-if="captchaImage && !captchaLoading"
            :src="captchaImage"
            :alt="t('auth.captcha')"
            class="captcha-image"
            :title="t('auth.clickToRefresh')"
            @click="refreshCaptcha"
          />
          <div
            v-else
            class="captcha-placeholder"
            @click="refreshCaptcha"
          >
            <Loader2
              v-if="captchaLoading"
              class="w-5 h-5 text-stone-400 animate-spin"
            />
            <RefreshCw
              v-else
              class="w-5 h-5 text-stone-400"
            />
          </div>
        </div>
      </div>

      <!-- Submit button -->
      <button
        type="submit"
        :disabled="isLoading || captchaLoading"
        class="mind-map-side-rail-btn mind-map-side-rail-btn--primary w-full"
      >
        <Loader2
          v-if="isLoading"
          class="w-4 h-4 animate-spin"
        />
        {{ isLoading ? '修改中...' : '确认修改' }}
      </button>
    </form>
  </SwissGlassCard>
</template>
