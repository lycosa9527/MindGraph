<script setup lang="ts">
/**
 * Account, security, and plugin tabs. Nested dialogs stay mounted while Settings is open.
 */
import { computed, toRef } from 'vue'

import { Loader2 } from '@lucide/vue'

import ApiTokenModal from '@/components/auth/ApiTokenModal.vue'
import AvatarSelectModal from '@/components/auth/AvatarSelectModal.vue'
import ChangePasswordForm from '@/components/auth/ChangePasswordForm.vue'
import ChangePhoneModal from '@/components/auth/ChangePhoneModal.vue'
import LoginDevicesModal from '@/components/auth/LoginDevicesModal.vue'
import OAuthQrLoginModal from '@/components/auth/OAuthQrLoginModal.vue'
import SetPasswordWithSmsModal from '@/components/auth/SetPasswordWithSmsModal.vue'
import I18nText from '@/components/common/I18nText.vue'

import SettingsAccountBindings from './SettingsAccountBindings.vue'
import { type AccountSettingsSection, useAccountSettings } from './useAccountSettings'

const props = defineProps<{
  open: boolean
  section: AccountSettingsSection
}>()

const emit = defineEmits<{
  success: []
}>()

const form = useAccountSettings(toRef(props, 'open'), () => emit('success'))

const showChangePasswordForm = computed(() => !form.isBayiSsoSubject && !form.needsSetLoginPassword)
</script>

<template>
  <div>
    <div
      v-show="section === 'account'"
      class="space-y-6 user-settings-tab-pad"
    >
      <div>
        <div class="language-settings-swiss__kicker">
          <I18nText k="auth.accountAvatar" />
        </div>
        <div class="flex flex-wrap items-center gap-4">
          <img
            v-if="form.currentAvatarSrc"
            :src="form.currentAvatarSrc"
            alt=""
            class="h-16 w-16 rounded-full object-cover shrink-0"
          />
          <div
            v-else
            class="text-5xl shrink-0 mg-user-avatar-emoji"
          >
            {{ form.currentAvatar }}
          </div>
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary shrink-0"
            @click="form.openAvatarModal"
          >
            <I18nText k="common.edit" />
          </button>
        </div>
      </div>

      <div class="space-y-4">
        <div>
          <label
            class="language-settings-swiss__kicker"
            for="account-info-name"
          >
            <I18nText k="auth.accountDisplayName" />
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <input
              id="account-info-name"
              v-model="form.nameEdit"
              type="text"
              name="account-info-name"
              :placeholder="form.t('auth.accountNamePlaceholder')"
              class="swiss-glass-field__input min-w-0 flex-1"
            />
            <button
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--primary shrink-0"
              :disabled="form.nameSaving"
              @click="form.saveDisplayName"
            >
              <Loader2
                v-if="form.nameSaving"
                class="w-3.5 h-3.5 animate-spin"
              />
              <I18nText k="auth.accountNameSave" />
            </button>
          </div>
        </div>

        <div>
          <label
            class="language-settings-swiss__kicker"
            for="account-info-phone"
          >
            <I18nText k="auth.phone" />
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <input
              id="account-info-phone"
              :value="form.userPhone || form.t('auth.notSet')"
              type="text"
              name="account-info-phone"
              disabled
              class="swiss-glass-field__input min-w-0 flex-1"
            />
            <button
              v-if="!form.isBayiSsoSubject"
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary shrink-0"
              @click="form.openChangePhoneModal"
            >
              <I18nText k="auth.changePhoneButton" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <div
      v-show="section === 'security'"
      class="space-y-6"
    >
      <div
        v-if="!form.isBayiSsoSubject && form.needsSetLoginPassword && form.authStore.user?.phone"
      >
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary w-full"
          @click="form.openSetPasswordSmsModal"
        >
          <I18nText k="auth.setPasswordWithSms" />
        </button>
      </div>
      <ChangePasswordForm
        v-else-if="showChangePasswordForm"
        :active="open && section === 'security'"
      >
        <template #before-actions>
          <SettingsAccountBindings
            v-if="form.showAccountBindingsSection"
            :form="form"
          />
        </template>
        <template #aside>
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
            @click="form.showLoginDevicesModal = true"
          >
            <I18nText k="auth.loginDevicesButton" />
          </button>
        </template>
      </ChangePasswordForm>

      <SettingsAccountBindings
        v-if="form.showAccountBindingsSection && !showChangePasswordForm"
        :form="form"
      />

      <div v-if="form.isBayiSsoSubject || form.needsSetLoginPassword">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
          @click="form.showLoginDevicesModal = true"
        >
          <I18nText k="auth.loginDevicesButton" />
        </button>
      </div>
    </div>

    <div
      v-show="section === 'plugins'"
      class="space-y-4 user-settings-tab-pad"
    >
      <div class="language-settings-swiss__kicker">
        <I18nText k="auth.accountPlugin" />
      </div>
      <div class="flex flex-col gap-2">
        <a
          v-if="form.canUseApiToken"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary w-full"
          :href="form.openclawSkillZipUrl"
          :title="form.t('auth.downloadOpenclawSkillHint')"
          download
        >
          <I18nText k="auth.downloadOpenclawSkill" />
        </a>
        <a
          v-if="form.canUseChromeExtension"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary w-full"
          :href="form.chromeExtensionZipUrl"
          download
        >
          <I18nText k="auth.downloadChromeExtension" />
        </a>
        <a
          v-if="form.featureWordAddin && form.canUseChromeExtension"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary w-full"
          :href="form.wordAddinZipUrl"
          download
        >
          <I18nText k="auth.downloadWordAddin" />
        </a>
        <a
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary w-full"
          :href="form.fileReaderZipUrl"
          :title="form.t('auth.downloadFileReaderHint')"
          download
        >
          <I18nText k="auth.downloadFileReader" />
        </a>
        <button
          v-if="form.canUseApiToken"
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary w-full"
          @click="form.showApiTokenModal = true"
        >
          <I18nText k="auth.apiTokenButton" />
        </button>
      </div>
    </div>

    <AvatarSelectModal
      v-model:visible="form.showAvatarModal"
      @success="form.handleAvatarSuccess"
    />
    <ChangePhoneModal
      v-model:visible="form.showChangePhoneModal"
      @success="form.handlePhoneChangeSuccess"
    />
    <SetPasswordWithSmsModal
      v-model:visible="form.showSetPasswordSmsModal"
      @success="emit('success')"
    />
    <ApiTokenModal
      v-if="form.canUseApiToken"
      v-model:visible="form.showApiTokenModal"
    />
    <LoginDevicesModal v-model:visible="form.showLoginDevicesModal" />
    <OAuthQrLoginModal
      v-model:visible="form.showOAuthBindModal"
      invite-code=""
      mode="bind"
      initial-provider="wechat"
      lock-provider
      @success="form.handleOAuthBindSuccess"
    />
  </div>
</template>
