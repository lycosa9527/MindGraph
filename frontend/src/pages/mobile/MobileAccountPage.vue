<script setup lang="ts">
/**
 * MobileAccountPage — Account settings page for mobile.
 * Shows user info, settings rows (phone, password, avatar, UI/prompt language), and logout.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  Check,
  ChevronDown,
  ChevronRight,
  Globe,
  Languages,
  Lock,
  LogOut,
  Phone,
  Smile,
} from 'lucide-vue-next'

import { ChangePasswordModal, ChangePhoneModal } from '@/components/auth'
import AvatarSelectModal from '@/components/auth/AvatarSelectModal.vue'
import { useLanguage } from '@/composables'
import { PROMPT_LANGUAGE_OPTIONS, getLocalesForInterfaceLanguagePicker } from '@/i18n/locales'
import { useAuthStore } from '@/stores'
import type { Language, PromptLanguage } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUIStore()
const { t } = useLanguage()

const user = computed(() => authStore.user)
const userAvatar = computed(() => {
  const avatar = user.value?.avatar || '👤'
  return avatar.startsWith('avatar_') ? '👤' : avatar
})
const displayName = computed(() => user.value?.username || '')
const orgName = computed(() => user.value?.schoolName || '')

const maskedPhone = computed(() => {
  const phone = user.value?.phone || ''
  if (phone.length >= 7) {
    return `${phone.slice(0, 3)}****${phone.slice(-4)}`
  }
  return phone || '—'
})

const showChangePhone = ref(false)
const showChangePassword = ref(false)
const showAvatarSelect = ref(false)

const uiLangExpanded = ref(false)
const promptLangExpanded = ref(false)
const promptSearchQuery = ref('')

const enabledUiLocales = computed(() => getLocalesForInterfaceLanguagePicker(uiStore.language))

const currentUiLabel = computed(() => {
  const match = enabledUiLocales.value.find((entry) => entry.code === uiStore.language)
  return match?.nativeName ?? uiStore.language
})

const TOP_PROMPT_CODES = ['zh', 'zh-hant', 'en']

const topPromptOptions = computed(() =>
  PROMPT_LANGUAGE_OPTIONS.filter((opt) => TOP_PROMPT_CODES.includes(opt.code))
)

const filteredPromptOptions = computed(() => {
  const query = promptSearchQuery.value.toLowerCase().trim()
  const nonTop = PROMPT_LANGUAGE_OPTIONS.filter((opt) => !TOP_PROMPT_CODES.includes(opt.code))
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

function selectUiLanguage(code: string) {
  uiStore.setLanguage(code as Language)
  uiStore.setUiLanguageExplicit(true)
  void authStore.saveLanguagePreferences(code as Language, uiStore.promptLanguage)
  uiLangExpanded.value = false
}

function selectPromptLanguage(code: string) {
  uiStore.setPromptLanguage(code as PromptLanguage)
  uiStore.setMatchPromptToUi(false)
  void authStore.saveLanguagePreferences(uiStore.language, code as PromptLanguage)
  promptLangExpanded.value = false
  promptSearchQuery.value = ''
}

function toggleUiLang() {
  const opening = !uiLangExpanded.value
  uiLangExpanded.value = opening
  if (opening) {
    promptLangExpanded.value = false
    promptSearchQuery.value = ''
  }
}

function togglePromptLang() {
  const opening = !promptLangExpanded.value
  promptLangExpanded.value = opening
  if (opening) {
    uiLangExpanded.value = false
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
    <div class="px-4 pt-6 pb-8 max-w-md mx-auto space-y-5">
      <!-- User profile header -->
      <div class="flex flex-col items-center gap-2 pb-4 border-b border-gray-100">
        <div class="flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 text-3xl">
          {{ userAvatar }}
        </div>
        <div class="text-base font-semibold text-gray-900">
          {{ displayName }}
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
        <!-- Change Phone -->
        <button
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="showChangePhone = true"
        >
          <Phone
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              {{ t('sidebar.changePhone', '修改手机号') }}
            </div>
            <div class="text-xs text-gray-400 mt-0.5">{{ maskedPhone }}</div>
          </div>
          <ChevronRight
            :size="18"
            class="text-gray-400 shrink-0"
          />
        </button>

        <div class="border-t border-gray-100 mx-4" />

        <!-- Change Password -->
        <button
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="showChangePassword = true"
        >
          <Lock
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              {{ t('sidebar.changePassword', '修改密码') }}
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
              {{ t('sidebar.changeAvatar', '修改头像') }}
            </div>
          </div>
          <ChevronRight
            :size="18"
            class="text-gray-400 shrink-0"
          />
        </button>

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
              {{ t('mobile.uiLanguage', '界面语言') }}
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
            <span class="text-sm text-gray-800">{{ locale.nativeName }}</span>
            <span class="text-xs text-gray-400">{{ locale.englishName }}</span>
            <Check
              v-if="uiStore.language === locale.code"
              :size="16"
              class="ml-auto text-indigo-600 shrink-0"
            />
          </button>
        </div>

        <div class="border-t border-gray-100 mx-4" />

        <!-- Prompt Language -->
        <button
          class="settings-row w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-gray-50 transition-colors"
          @click="togglePromptLang"
        >
          <Languages
            :size="20"
            class="text-gray-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900">
              {{ t('settings.language.prompt') }}
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
          v-if="promptLangExpanded"
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
            <span class="text-sm text-gray-800">{{ opt.label }}</span>
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
              <span class="text-sm text-gray-800">{{ opt.label }}</span>
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
        {{ t('sidebar.logout', '退出登录') }}
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
</style>
