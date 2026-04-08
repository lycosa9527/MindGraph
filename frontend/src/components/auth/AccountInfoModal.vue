<script setup lang="ts">
/**
 * AccountInfoModal - Modal for displaying and editing user account information
 *
 * Design: Swiss Design (Modern Minimalism)
 */
import { computed, ref } from 'vue'

import { ElButton } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

import ApiTokenModal from './ApiTokenModal.vue'
import AvatarSelectModal from './AvatarSelectModal.vue'
import ChangePasswordModal from './ChangePasswordModal.vue'
import ChangePhoneModal from './ChangePhoneModal.vue'

const { t } = useLanguage()

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const showAvatarModal = ref(false)
const showChangePhoneModal = ref(false)
const showChangePasswordModal = ref(false)
const showApiTokenModal = ref(false)

// Get user data
const userName = computed(() => authStore.user?.username || '')
const userPhone = computed(() => {
  const phone = authStore.user?.phone || ''
  if (phone && phone.length === 11) {
    // Mask middle 4 digits: 13812345678 -> 138****5678
    return `${phone.slice(0, 3)}****${phone.slice(7)}`
  }
  return phone
})
const userOrg = computed(() => authStore.user?.schoolName || '')
const currentAvatar = computed(() => {
  const avatar = authStore.user?.avatar || '🐈‍⬛'
  // Handle legacy avatar_01 format
  if (avatar.startsWith('avatar_')) {
    return '🐈‍⬛'
  }
  return avatar
})

function closeModal() {
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

function handlePhoneChangeSuccess() {
  emit('success')
}
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
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">账户信息</h2>
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
                <div class="flex items-center gap-4">
                  <div class="text-5xl">{{ currentAvatar }}</div>
                  <el-button
                    round
                    size="small"
                    class="edit-avatar-btn"
                    @click="openAvatarModal"
                  >
                    编辑
                  </el-button>
                </div>
              </div>

              <!-- Divider -->
              <div class="border-t border-stone-200" />

              <!-- User Information (Read-only fields) -->
              <div class="space-y-4">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-400 uppercase tracking-wide mb-2"
                    for="account-info-name"
                  >
                    姓名
                  </label>
                  <input
                    id="account-info-name"
                    :value="userName || '未设置'"
                    type="text"
                    name="account-info-name"
                    disabled
                    class="w-full px-4 py-3 bg-stone-100 border-0 rounded-lg text-stone-500 cursor-not-allowed"
                  />
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
              </div>
            </div>

            <!-- Footer -->
            <div class="px-8 pb-8 flex justify-end gap-3">
              <button
                type="button"
                class="py-2 px-5 rounded-full border border-stone-300 text-stone-600 text-sm font-medium hover:border-stone-400 hover:text-stone-800 transition-all"
                @click="showApiTokenModal = true"
              >
                API Token
              </button>
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

    <ApiTokenModal v-model:visible="showApiTokenModal" />
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
</style>
