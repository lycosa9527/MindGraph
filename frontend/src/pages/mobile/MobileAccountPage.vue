<script setup lang="ts">
/**
 * MobileAccountPage — Account settings page for mobile.
 * Shows user info, settings rows (account id, password, avatar, UI version, language), and logout.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  Check,
  ChevronDown,
  ChevronRight,
  Globe,
  Hash,
  Languages,
  Lock,
  LogOut,
  Mail,
  MonitorSmartphone,
  Phone,
  Smile,
} from '@lucide/vue'

import { ChangePasswordModal, ChangePhoneModal } from '@/components/auth'
import AvatarSelectModal from '@/components/auth/AvatarSelectModal.vue'
import SetPasswordWithSmsModal from '@/components/auth/SetPasswordWithSmsModal.vue'
import { useLanguage } from '@/composables'
import { useNotifications } from '@/composables/core/useNotifications'
import { formatGalleryLanguageMenuLabel } from '@/i18n/galleryLanguageMenuLabel'
import {
  PROMPT_LANGUAGE_OPTIONS,
  getLocalesForInterfaceLanguagePicker,
  getPromptLanguageOptionsForPicker,
} from '@/i18n/locales'
import { useAuthStore } from '@/stores'
import { commitClientShell } from '@/stores/clientShellState'
import type { Language, PromptLanguage } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'
import { displayAccountLoginValue, resolveAccountLoginIdentity } from '@/utils/accountLoginIdentity'
import { clientShellLock } from '@/utils/clientShellLock'
import type { ClientShell } from '@/utils/clientShellLock'
import { persistLanguagePreferencesIfAuthenticated } from '@/utils/persistLanguagePreferences'
import { resolveUserAvatarEmoji, userAvatarImageSrc } from '@/utils/userAvatarEmoji'
import { getRolePillStyle } from '@/utils/userRoleDisplay'

const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUIStore()
const { t } = useLanguage()
const notify = useNotifications()

const user = computed(() => authStore.user)
const userAvatar = computed(() => resolveUserAvatarEmoji(user.value?.avatar))
const userAvatarSrc = computed(() => userAvatarImageSrc(user.value?.avatar))
const displayName = computed(() => user.value?.username || '')
const orgName = computed(() => user.value?.schoolName || '')
const userRolePill = computed(() => {
  if (!user.value?.role) {
    return null
  }
  const style = getRolePillStyle(user.value.role, user.value.schoolTier)
  if (!style) {
    return null
  }
  return {
    label: t(style.labelKey),
    labelKey: style.labelKey,
    bgClass: style.bgClass,
    textClass: style.textClass,
    borderClass: style.borderClass,
  }
})

const accountLogin = computed(() =>
  resolveAccountLoginIdentity({
    phone: user.value?.phone,
    email: user.value?.email,
  })
)
const canChangePhone = computed(() => accountLogin.value.kind === 'mobile')
const accountLoginValue = computed(() => displayAccountLoginValue(accountLogin.value) || '—')
const accountLoginIcon = computed(() => {
  if (accountLogin.value.kind === 'email') {
    return Mail
  }
  if (accountLogin.value.kind === 'bayi') {
    return Hash
  }
  return Phone
})

const showChangePhone = ref(false)
const showChangePassword = ref(false)
const showSetPasswordSms = ref(false)
const showAvatarSelect = ref(false)

const needsSetLoginPassword = computed(() => user.value?.loginPasswordSet === false)

const shellExpanded = ref(false)
const shellSaving = ref(false)
const shellSelection = computed<ClientShell>(() => {
  if (clientShellLock.value) return clientShellLock.value
  return uiStore.isMobile ? 'mobile' : 'desktop'
})
const shellLabelKey = computed(() =>
  shellSelection.value === 'mobile' ? 'auth.clientShellMobile' : 'auth.clientShellDesktop'
)

const uiLangExpanded = ref(false)
const presenterLangExpanded = ref(false)
const promptLangExpanded = ref(false)
const promptSearchQuery = ref('')

const allowZhPicker = computed(() => uiStore.languagePolicyAllowZh)

const enabledUiLocales = computed(() =>
  getLocalesForInterfaceLanguagePicker(uiStore.language, allowZhPicker.value)
)

const currentUiLabel = computed(() => {
  const match = enabledUiLocales.value.find((entry) => entry.code === uiStore.language)
  return match?.nativeName ?? uiStore.language
})

const TOP_PROMPT_CODES = ['zh', 'zh-hant', 'en']

const topPromptOptions = computed(() => {
  const opts = getPromptLanguageOptionsForPicker(allowZhPicker.value)
  return opts.filter((opt) => TOP_PROMPT_CODES.includes(opt.code))
})

const filteredPromptOptions = computed(() => {
  const query = promptSearchQuery.value.toLowerCase().trim()
  const allFiltered = getPromptLanguageOptionsForPicker(allowZhPicker.value)
  const nonTop = allFiltered.filter((opt) => !TOP_PROMPT_CODES.includes(opt.code))
  if (!query) return nonTop
  return nonTop.filter(
    (opt) =>
      opt.label.toLowerCase().includes(query) ||
      opt.englishName.toLowerCase().includes(query) ||
      opt.code.toLowerCase().includes(query) ||
      opt.search.some((s: string) => s.toLowerCase().includes(query))
  )
})

const currentPromptLabel = computed(() => {
  const match = PROMPT_LANGUAGE_OPTIONS.find((opt) => opt.code === uiStore.promptLanguage)
  return match?.label ?? uiStore.promptLanguage
})

const currentPresenterLabel = computed(() => {
  const match = enabledUiLocales.value.find((entry) => entry.code === uiStore.presenterUiLocale)
  return match?.nativeName ?? uiStore.presenterUiLocale
})

function selectUiLanguage(code: string) {
  uiStore.setLanguage(code as Language)
  persistLanguagePreferencesIfAuthenticated()
  uiLangExpanded.value = false
}

function selectPresenterLanguage(code: string) {
  uiStore.setPresenterUiLocale(code)
  persistLanguagePreferencesIfAuthenticated()
  presenterLangExpanded.value = false
}

function selectPromptLanguage(code: string) {
  uiStore.setPromptLanguage(code as PromptLanguage)
  uiStore.setMatchPromptToUi(false)
  persistLanguagePreferencesIfAuthenticated()
  promptLangExpanded.value = false
  promptSearchQuery.value = ''
}

function toggleShell() {
  const opening = !shellExpanded.value
  shellExpanded.value = opening
  if (opening) {
    uiLangExpanded.value = false
    presenterLangExpanded.value = false
    promptLangExpanded.value = false
    promptSearchQuery.value = ''
  }
}

async function selectClientShell(shell: ClientShell): Promise<void> {
  if (shellSaving.value || clientShellLock.value === shell) {
    shellExpanded.value = false
    return
  }
  shellSaving.value = true
  const saved = await commitClientShell(shell)
  shellSaving.value = false
  if (!saved) {
    notify.errorKey('auth.clientShellSaveError')
    return
  }
  shellExpanded.value = false
  notify.successKey('auth.clientShellSaved')
}

function toggleUiLang() {
  const opening = !uiLangExpanded.value
  uiLangExpanded.value = opening
  if (opening) {
    shellExpanded.value = false
    presenterLangExpanded.value = false
    promptLangExpanded.value = false
    promptSearchQuery.value = ''
  }
}

function togglePresenterLang() {
  const opening = !presenterLangExpanded.value
  presenterLangExpanded.value = opening
  if (opening) {
    shellExpanded.value = false
    uiLangExpanded.value = false
    promptLangExpanded.value = false
  }
}

function togglePromptLang() {
  const opening = !promptLangExpanded.value
  promptLangExpanded.value = opening
  if (opening) {
    shellExpanded.value = false
    uiLangExpanded.value = false
    presenterLangExpanded.value = false
  } else {
    promptSearchQuery.value = ''
  }
}

async function handleLogout() {
  await authStore.logout()
  router.push('/auth')
}
</script>

<template>
  <div class="mobile-account flex-1 overflow-y-auto">
    <div class="px-4 pt-6 pb-8 max-w-md mx-auto space-y-5 mobile-account-scroll">
      <!-- User profile header -->
      <div class="flex flex-col items-center gap-2 pb-4 border-b border-gray-100">
        <img
          v-if="userAvatarSrc"
          :src="userAvatarSrc"
          alt=""
          class="w-16 h-16 rounded-full object-cover"
        />
        <div
          v-else
          class="flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 text-3xl mg-user-avatar-emoji"
        >
          {{ userAvatar }}
        </div>
        <div class="flex items-center gap-2">
          <div class="text-base font-semibold text-gray-900">
            {{ displayName }}
          </div>
          <span
            v-if="userRolePill"
            class="role-pill text-xs font-medium"
            :class="[userRolePill.bgClass, userRolePill.textClass, userRolePill.borderClass]"
          >
            <I18nText
              v-if="userRolePill.labelKey"
              :k="userRolePill.labelKey"
              dense
              align="center"
            />
            <template v-else>{{ userRolePill.label }}</template>
          </span>
        </div>
        <div
          v-if="orgName"
          class="text-sm text-gray-500"
        >
          {{ orgName }}
        </div>
      </div>

      <!-- Settings list -->
      <div class="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <component
          :is="canChangePhone ? 'button' : 'div'"
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left"
          :class="canChangePhone ? 'active:bg-gray-50 transition-colors' : undefined"
          :type="canChangePhone ? 'button' : undefined"
          @click="canChangePhone ? (showChangePhone = true) : undefined"
        >
          <component
            :is="accountLoginIcon"
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText :k="accountLogin.labelKey" />
            </div>
            <div class="text-xs text-gray-400 mt-0.5">{{ accountLoginValue }}</div>
          </div>
          <ChevronRight
            v-if="canChangePhone"
            :size="18"
            class="text-gray-400 shrink-0"
          />
        </component>

        <div class="border-t border-gray-100 mx-4" />

        <!-- Set login password or change password -->
        <button
          v-if="canChangePhone && needsSetLoginPassword"
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="showSetPasswordSms = true"
        >
          <Lock
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText k="auth.setPasswordWithSms" />
            </div>
          </div>
          <ChevronRight
            :size="18"
            class="text-gray-400 shrink-0"
          />
        </button>
        <button
          v-else-if="!needsSetLoginPassword"
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="showChangePassword = true"
        >
          <Lock
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText k="sidebar.changePassword" />
            </div>
          </div>
          <ChevronRight
            :size="18"
            class="text-gray-400 shrink-0"
          />
        </button>

        <div class="border-t border-gray-100 mx-4" />

        <!-- Change Avatar -->
        <button
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="showAvatarSelect = true"
        >
          <Smile
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText k="sidebar.changeAvatar" />
            </div>
          </div>
          <ChevronRight
            :size="18"
            class="text-gray-400 shrink-0"
          />
        </button>

        <div class="border-t border-gray-100 mx-4" />

        <button
          type="button"
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="toggleShell"
        >
          <MonitorSmartphone
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText k="auth.clientShell" />
            </div>
            <div class="text-xs text-gray-400 mt-0.5">
              <I18nText :k="shellLabelKey" />
            </div>
          </div>
          <ChevronDown
            :size="18"
            class="text-gray-400 shrink-0 transition-transform"
            :class="{ 'rotate-180': shellExpanded }"
          />
        </button>
        <div
          v-if="shellExpanded"
          class="bg-gray-50 px-4 py-2 border-t border-gray-100"
        >
          <button
            type="button"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg active:bg-gray-200 transition-colors"
            :class="shellSelection === 'mobile' ? 'bg-indigo-50' : ''"
            :disabled="shellSaving"
            @click="selectClientShell('mobile')"
          >
            <span class="text-sm text-gray-800">
              <I18nText k="auth.clientShellMobile" />
            </span>
            <Check
              v-if="shellSelection === 'mobile'"
              :size="16"
              class="ml-auto text-indigo-600 shrink-0"
            />
          </button>
          <button
            type="button"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg active:bg-gray-200 transition-colors"
            :class="shellSelection === 'desktop' ? 'bg-indigo-50' : ''"
            :disabled="shellSaving"
            @click="selectClientShell('desktop')"
          >
            <span class="text-sm text-gray-800">
              <I18nText k="auth.clientShellDesktop" />
            </span>
            <Check
              v-if="shellSelection === 'desktop'"
              :size="16"
              class="ml-auto text-indigo-600 shrink-0"
            />
          </button>
          <p class="px-3 pb-2 text-xs text-gray-400">
            <I18nText k="auth.clientShellHint" />
          </p>
        </div>

        <div class="border-t border-gray-100 mx-4" />

        <!-- UI Language -->
        <button
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="toggleUiLang"
        >
          <Globe
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText
                :k="
                  uiStore.bilingualUiEnabled
                    ? 'settings.language.primaryLanguage'
                    : 'mobile.uiLanguage'
                "
              />
            </div>
            <div class="text-xs text-gray-400 mt-0.5">{{ currentUiLabel }}</div>
          </div>
          <ChevronDown
            :size="18"
            class="text-gray-400 shrink-0 transition-transform"
            :class="{ 'rotate-180': uiLangExpanded }"
          />
        </button>

        <!-- UI Language inline selector -->
        <div
          v-if="uiLangExpanded"
          class="bg-gray-50 px-4 py-2 border-t border-gray-100"
        >
          <button
            v-for="locale in enabledUiLocales"
            :key="locale.code"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg active:bg-gray-200 transition-colors"
            :class="uiStore.language === locale.code ? 'bg-indigo-50' : ''"
            @click="selectUiLanguage(locale.code)"
          >
            <span class="text-sm text-gray-800">{{
              formatGalleryLanguageMenuLabel(locale.code, locale.nativeName)
            }}</span>
            <span class="text-xs text-gray-400">{{ locale.englishName }}</span>
            <Check
              v-if="uiStore.language === locale.code"
              :size="16"
              class="ml-auto text-indigo-600 shrink-0"
            />
          </button>
        </div>

        <div class="border-t border-gray-100 mx-4" />

        <button
          v-if="uiStore.bilingualUiEnabled"
          type="button"
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="togglePresenterLang"
        >
          <Languages
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText k="settings.language.secondaryLanguage" />
            </div>
            <div class="text-xs text-gray-400 mt-0.5">{{ currentPresenterLabel }}</div>
          </div>
          <ChevronDown
            :size="18"
            class="text-gray-400 shrink-0 transition-transform"
            :class="{ 'rotate-180': presenterLangExpanded }"
          />
        </button>
        <div
          v-if="uiStore.bilingualUiEnabled && presenterLangExpanded"
          class="bg-gray-50 px-4 py-2 border-t border-gray-100"
        >
          <button
            v-for="locale in enabledUiLocales"
            :key="`presenter-${locale.code}`"
            type="button"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg active:bg-gray-200 transition-colors"
            :class="uiStore.presenterUiLocale === locale.code ? 'bg-indigo-50' : ''"
            @click="selectPresenterLanguage(locale.code)"
          >
            <span class="text-sm text-gray-800">{{
              formatGalleryLanguageMenuLabel(locale.code, locale.nativeName)
            }}</span>
            <span class="text-xs text-gray-400">{{ locale.englishName }}</span>
            <Check
              v-if="uiStore.presenterUiLocale === locale.code"
              :size="16"
              class="ml-auto text-indigo-600 shrink-0"
            />
          </button>
        </div>

        <!-- Prompt Language -->
        <button
          v-else
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="togglePromptLang"
        >
          <Languages
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              <I18nText k="settings.language.prompt" />
            </div>
            <div class="text-xs text-gray-400 mt-0.5">{{ currentPromptLabel }}</div>
          </div>
          <ChevronDown
            :size="18"
            class="text-gray-400 shrink-0 transition-transform"
            :class="{ 'rotate-180': promptLangExpanded }"
          />
        </button>

        <!-- Prompt Language inline selector -->
        <div
          v-if="!uiStore.bilingualUiEnabled && promptLangExpanded"
          class="bg-gray-50 px-4 py-2 border-t border-gray-100"
        >
          <!-- Top languages (zh, zh-hant, en) -->
          <button
            v-for="opt in topPromptOptions"
            :key="opt.code"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg active:bg-gray-200 transition-colors"
            :class="uiStore.promptLanguage === opt.code ? 'bg-indigo-50' : ''"
            @click="selectPromptLanguage(opt.code)"
          >
            <span class="text-sm text-gray-800">{{
              formatGalleryLanguageMenuLabel(opt.code, opt.label)
            }}</span>
            <span class="text-xs text-gray-400">{{ opt.englishName }}</span>
            <Check
              v-if="uiStore.promptLanguage === opt.code"
              :size="16"
              class="ml-auto text-indigo-600 shrink-0"
            />
          </button>

          <!-- Separator -->
          <div class="border-t border-gray-200 my-2" />

          <!-- Search box -->
          <input
            v-model="promptSearchQuery"
            type="text"
            :placeholder="t('languageSettings.searchPromptLanguage', '搜索语言...')"
            class="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300 mb-2"
          />

          <!-- Filtered list -->
          <div class="max-h-48 overflow-y-auto">
            <button
              v-for="opt in filteredPromptOptions"
              :key="opt.code"
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg active:bg-gray-200 transition-colors"
              :class="uiStore.promptLanguage === opt.code ? 'bg-indigo-50' : ''"
              @click="selectPromptLanguage(opt.code)"
            >
              <span class="text-sm text-gray-800">{{
                formatGalleryLanguageMenuLabel(opt.code, opt.label)
              }}</span>
              <span class="text-xs text-gray-400">{{ opt.englishName }}</span>
              <Check
                v-if="uiStore.promptLanguage === opt.code"
                :size="16"
                class="ml-auto text-indigo-600 shrink-0"
              />
            </button>
          </div>
        </div>
      </div>

      <!-- Logout -->
      <button
        class="w-full flex items-center justify-center gap-2 py-3.5 rounded-2xl border border-red-200 bg-white text-red-500 font-medium text-sm active:bg-red-50 transition-colors"
        @click="handleLogout"
      >
        <LogOut :size="18" />
        <I18nText k="sidebar.logout" />
      </button>
    </div>

    <!-- Modals -->
    <ChangePhoneModal
      :visible="showChangePhone"
      @update:visible="showChangePhone = $event"
    />
    <ChangePasswordModal
      :visible="showChangePassword"
      @update:visible="showChangePassword = $event"
    />
    <SetPasswordWithSmsModal v-model:visible="showSetPasswordSms" />
    <AvatarSelectModal
      :visible="showAvatarSelect"
      @update:visible="showAvatarSelect = $event"
    />
  </div>
</template>

<style scoped>
.settings-row + .settings-row {
  border-top: 1px solid #f3f4f6;
}

.mobile-account-scroll {
  padding-bottom: max(2rem, env(safe-area-inset-bottom));
}
</style>
