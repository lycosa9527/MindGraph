<script setup lang="ts">
/**
 * AccountInfoModal - Modal for displaying and editing user account information
 *
 * Design: Swiss Design (Modern Minimalism)
 */
import { computed, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { logPairAudit } from '@/utils/dingtalkPairAuditLog'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'
import { resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'

import ApiTokenModal from './ApiTokenModal.vue'
import AvatarSelectModal from './AvatarSelectModal.vue'
import BindDingTalkAccountModal from './BindDingTalkAccountModal.vue'
import DingTalkPairModal from './DingTalkPairModal.vue'
import ChangePasswordModal from './ChangePasswordModal.vue'
import ChangePhoneModal from './ChangePhoneModal.vue'
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
const { featureMindbot } = useFeatureFlags()
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
const showBindDingTalkModal = ref(false)
const showUnbindPairModal = ref(false)
const dingtalkBindStatus = ref<{
  linked: boolean
  mindbot_available: boolean
  dingtalk_staff_id?: string | null
  rate_limited?: boolean
} | null>(null)
const dingtalkBindLoading = ref(false)
const nameEdit = ref('')
const nameSaving = ref(false)

/** Same-origin API paths; cookies sent for GET (session). */
const openclawSkillZipUrl = '/api/downloads/mindgraph-openclaw-skill'
const chromeExtensionZipUrl = '/api/downloads/mindgraph-chrome-extension'

// Get user data
const userPhone = computed(() => {
  const phone = authStore.user?.phone || ''
  if (phone && phone.length === 11) {
    // Mask middle 4 digits: 13812345678 -> 138****5678
    return `${phone.slice(0, 3)}****${phone.slice(7)}`
  }
  return phone
})
const userOrg = computed(() => authStore.user?.schoolName || '')

const showDingtalkBindSection = computed(
  () => !!authStore.user?.schoolId && featureMindbot.value
)

const canMintDingtalkBind = computed(
  () => dingtalkBindStatus.value?.mindbot_available === true
)

const dingtalkLinked = computed(() => dingtalkBindStatus.value?.linked === true)

const dingtalkStaffMasked = computed(
  () => dingtalkBindStatus.value?.dingtalk_staff_id || ''
)

async function fetchDingtalkBindStatus() {
  if (!authStore.user?.schoolId || !featureMindbot.value) {
    dingtalkBindStatus.value = null
    return
  }
  dingtalkBindLoading.value = true
  const previous = dingtalkBindStatus.value
  try {
    const res = await apiRequest('/api/auth/dingtalk-bind/status', { method: 'GET' })
    if (res.ok) {
      dingtalkBindStatus.value = (await res.json()) as typeof dingtalkBindStatus.value
      return
    }
    if (res.status === 429 && previous) {
      dingtalkBindStatus.value = { ...previous, rate_limited: true }
      return
    }
    dingtalkBindStatus.value = {
      linked: previous?.linked ?? false,
      mindbot_available: previous?.mindbot_available ?? false,
      dingtalk_staff_id: previous?.dingtalk_staff_id,
    }
  } catch {
    if (previous) {
      dingtalkBindStatus.value = previous
      return
    }
    dingtalkBindStatus.value = { linked: false, mindbot_available: false }
  } finally {
    dingtalkBindLoading.value = false
  }
}

function openBindDingTalkModal() {
  if (!canMintDingtalkBind.value) {
    notify.warning(t('auth.dingtalkBindNoMindbot'))
    return
  }
  logPairAudit('account_open_bind', { purpose: 'bind' }, { reportToServer: false })
  void fetchDingtalkBindStatus().then(() => {
    if (canMintDingtalkBind.value) {
      showBindDingTalkModal.value = true
    }
  })
}

function handleDingtalkBindLinked() {
  void fetchDingtalkBindStatus()
  emit('success')
}

function openUnbindPairModal() {
  if (!dingtalkLinked.value) {
    return
  }
  logPairAudit('account_open_unbind', { purpose: 'unbind' }, { reportToServer: false })
  void fetchDingtalkBindStatus().then(() => {
    if (dingtalkLinked.value) {
      showUnbindPairModal.value = true
    }
  })
}

function handleDingtalkUnbindCompleted() {
  void fetchDingtalkBindStatus()
  emit('success')
}

async function unbindDingtalk() {
  openUnbindPairModal()
}
const currentAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))

/** Quick registration: server-only password until user sets one via SMS. */
const needsSetLoginPassword = computed(() => authStore.user?.loginPasswordSet === false)

function closeModal() {
  showBindDingTalkModal.value = false
  showUnbindPairModal.value = false
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
  () => [props.visible, featureMindbot.value] as const,
  ([visible, mindbotEnabled]) => {
    if (visible) {
      const u = (authStore.user?.username || '').trim()
      const looksLikeName =
        u.length >= 2 && u.length <= 32 && !/^\d{11}$/.test(u) && !/^\d+$/.test(u)
      nameEdit.value = looksLikeName ? u : ''
      if (mindbotEnabled && authStore.user?.schoolId) {
        void fetchDingtalkBindStatus()
      }
    }
  }
)
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="closeModal"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]" />

        <!-- Modal -->
        <div class="relative w-full max-w-md">
          <!-- Card -->
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden">
            <!-- Header -->
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100 relative">
              <el-button
                :icon="Close"
                circle
                text
                class="close-btn"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">
                {{ t('auth.accountInfo') }}
              </h2>
            </div>

            <!-- Content -->
            <div class="p-8 space-y-6">
              <!-- Avatar Section -->
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-4"
                >
                  头像
                </label>
                <div class="flex flex-wrap items-center gap-4">
                  <div class="text-5xl shrink-0 mg-user-avatar-emoji">{{ currentAvatar }}</div>
                  <el-button
                    round
                    size="small"
                    class="edit-avatar-btn shrink-0"
                    @click="openAvatarModal"
                  >
                    编辑
                  </el-button>
                </div>
              </div>

              <!-- User Information (Read-only fields) -->
              <div class="space-y-4">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
                    for="account-info-name"
                  >
                    {{ t('auth.accountDisplayName') }}
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
                    <el-button
                      round
                      size="small"
                      class="account-action-btn shrink-0"
                      :loading="nameSaving"
                      @click="saveDisplayName"
                    >
                      {{ t('auth.accountNameSave') }}
                    </el-button>
                  </div>
                </div>

                <div>
                  <label
                    class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
                    for="account-info-phone"
                  >
                    手机号
                  </label>
                  <div class="flex flex-wrap items-center gap-2">
                    <input
                      id="account-info-phone"
                      :value="userPhone || '未设置'"
                      type="text"
                      name="account-info-phone"
                      disabled
                      class="min-w-0 flex-1 px-4 py-3 bg-stone-100 border-0 rounded-lg text-stone-500 cursor-not-allowed"
                    />
                    <div class="flex shrink-0 items-center gap-2">
                      <el-button
                        round
                        size="small"
                        class="account-action-btn"
                        @click="openChangePhoneModal"
                      >
                        {{ t('auth.changePhoneButton') }}
                      </el-button>
                      <el-button
                        v-if="needsSetLoginPassword && authStore.user?.phone"
                        round
                        size="small"
                        class="account-action-btn"
                        @click="openSetPasswordSmsModal"
                      >
                        {{ t('auth.setPasswordWithSms') }}
                      </el-button>
                      <el-button
                        v-else-if="!needsSetLoginPassword"
                        round
                        size="small"
                        class="account-action-btn"
                        @click="openChangePasswordModal"
                      >
                        {{ t('auth.changePassword') }}
                      </el-button>
                    </div>
                  </div>
                </div>

                <div>
                  <label
                    class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
                    for="account-info-org"
                  >
                    组织
                  </label>
                  <input
                    id="account-info-org"
                    :value="userOrg || '未设置组织'"
                    type="text"
                    name="account-info-org"
                    disabled
                    class="w-full px-4 py-3 bg-stone-100 border-0 rounded-lg text-stone-500 cursor-not-allowed"
                  />
                </div>

                <div v-if="showDingtalkBindSection">
                  <label class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2">
                    {{ t('auth.dingtalkBindSection') }}
                  </label>
                  <div class="flex flex-col gap-2">
                    <div class="flex flex-wrap items-center gap-2">
                      <el-button
                        v-if="dingtalkLinked"
                        round
                        size="small"
                        class="account-action-btn account-action-btn--linked shrink-0"
                        disabled
                      >
                        {{ t('auth.dingtalkBindLinkedButton') }}
                      </el-button>
                      <el-button
                        v-else
                        round
                        size="small"
                        class="account-action-btn shrink-0"
                        :loading="dingtalkBindLoading"
                        :disabled="!canMintDingtalkBind"
                        @click="openBindDingTalkModal"
                      >
                        {{ t('auth.dingtalkBindButton') }}
                      </el-button>
                      <el-button
                        v-if="dingtalkLinked"
                        round
                        size="small"
                        class="account-action-btn account-action-btn--unbind shrink-0"
                        @click="unbindDingtalk"
                      >
                        {{ t('auth.dingtalkBindUnbind') }}
                      </el-button>
                    </div>
                    <p
                      v-if="dingtalkLinked && dingtalkStaffMasked"
                      class="text-xs text-stone-500 m-0"
                    >
                      {{ t('auth.dingtalkBindLinkedLabel', { staff: dingtalkStaffMasked }) }}
                    </p>
                    <p
                      v-else-if="!dingtalkBindLoading && !canMintDingtalkBind && !dingtalkLinked"
                      class="text-xs text-stone-500 m-0"
                    >
                      {{ t('auth.dingtalkBindNoMindbot') }}
                    </p>
                  </div>
                </div>

                <div v-if="showAccountPlugins">
                  <label
                    class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
                  >
                    {{ t('auth.accountPlugin') }}
                  </label>
                  <div class="flex flex-wrap items-center gap-2">
                    <a
                      v-if="canUseApiToken"
                      class="account-plugin-pill account-plugin-pill--openclaw"
                      :href="openclawSkillZipUrl"
                      download
                    >
                      {{ t('auth.downloadOpenclawSkill') }}
                    </a>
                    <a
                      v-if="canUseChromeExtension"
                      class="account-plugin-pill account-plugin-pill--chrome"
                      :href="chromeExtensionZipUrl"
                      download
                    >
                      {{ t('auth.downloadChromeExtension') }}
                    </a>
                    <button
                      v-if="canUseApiToken"
                      type="button"
                      class="account-plugin-pill account-plugin-pill--token"
                      @click="showApiTokenModal = true"
                    >
                      {{ t('auth.apiTokenButton') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-8 pb-8 flex justify-end">
              <button
                class="py-2 px-6 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all"
                @click="closeModal"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

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

    <BindDingTalkAccountModal
      v-model="showBindDingTalkModal"
      :linked-staff-id="dingtalkStaffMasked"
      @linked="handleDingtalkBindLinked"
    />

    <DingTalkPairModal
      v-model="showUnbindPairModal"
      mode="unbind"
      :linked-staff-id="dingtalkStaffMasked"
      @completed="handleDingtalkUnbindCompleted"
    />
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95);
}

/* Close button positioning and styling */
.close-btn {
  position: absolute;
  top: 16px;
  inset-inline-end: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
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
  line-height: 1.25;
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

/* Phone / password actions - Swiss Design with dark grey/black theme */
.account-action-btn {
  --el-button-bg-color: #44403c;
  --el-button-text-color: #ffffff;
  --el-button-border-color: #44403c;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-text-color: #ffffff;
  --el-button-hover-border-color: #292524;
  --el-button-active-bg-color: #1c1917;
  --el-button-active-border-color: #1c1917;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.account-action-btn--linked {
  --el-button-bg-color: #e7e5e4;
  --el-button-text-color: #78716c;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #e7e5e4;
  --el-button-hover-text-color: #78716c;
  --el-button-hover-border-color: #d6d3d1;
  --el-button-active-bg-color: #e7e5e4;
  --el-button-active-border-color: #d6d3d1;
  cursor: not-allowed;
}

.account-action-btn--unbind {
  --el-button-bg-color: #ffffff;
  --el-button-text-color: #44403c;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #fafaf9;
  --el-button-hover-text-color: #292524;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #f5f5f4;
  --el-button-active-border-color: #78716c;
}
</style>
