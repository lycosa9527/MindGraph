<script setup lang="ts">
/**
 * ChangePasswordModal - Modal for changing user password
 *
 * Design: Swiss Design (Modern Minimalism)
 */
import { computed, ref, watch } from 'vue'

import { Close } from '@element-plus/icons-vue'

import { Eye, EyeOff, Loader2 } from 'lucide-vue-next'

import { useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()
const notify = useNotifications()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const formData = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const isLoading = ref(false)
const showCurrentPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

function resetForm() {
  formData.value = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  }
  showCurrentPassword.value = false
  showNewPassword.value = false
  showConfirmPassword.value = false
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
    }
  }
)

async function handleSubmit() {
  if (
    !formData.value.currentPassword ||
    !formData.value.newPassword ||
    !formData.value.confirmPassword
  ) {
    notify.warning('请填写所有字段')
    return
  }

  if (formData.value.newPassword.length < 8) {
    notify.warning('密码至少需要8个字符')
    return
  }

  if (formData.value.newPassword !== formData.value.confirmPassword) {
    notify.warning('两次输入的密码不一致')
    return
  }

  isLoading.value = true

  try {
    // Use credentials (token in httpOnly cookie)
    const response = await fetch('/api/auth/change-password', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: formData.value.currentPassword,
        new_password: formData.value.newPassword,
      }),
    })

    const data = await response.json()

    if (response.ok) {
      notify.success('密码修改成功')
      closeModal()
      emit('success')
    } else {
      notify.error(data.detail || '密码修改失败')
    }
  } catch (error) {
    console.error('Failed to change password:', error)
    notify.error('网络错误，密码修改失败')
  } finally {
    isLoading.value = false
  }
}

function handleBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    closeModal()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click="handleBackdropClick"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]" />

        <!-- Modal -->
        <div class="relative w-full max-w-sm">
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
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">修改密码</h2>
            </div>

            <!-- Form -->
            <form
              class="p-8 space-y-5"
              @submit.prevent="handleSubmit"
            >
              <!-- Hidden username field for accessibility and password managers -->
              <input
                type="text"
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
                >
                  当前密码
                </label>
                <div class="relative">
                  <input
                    v-model="formData.currentPassword"
                    :type="showCurrentPassword ? 'text' : 'password'"
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
                >
                  新密码
                </label>
                <div class="relative">
                  <input
                    v-model="formData.newPassword"
                    :type="showNewPassword ? 'text' : 'password'"
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
                >
                  确认新密码
                </label>
                <div class="relative">
                  <input
                    v-model="formData.confirmPassword"
                    :type="showConfirmPassword ? 'text' : 'password'"
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

              <!-- Submit button -->
              <button
                type="submit"
                :disabled="isLoading"
                class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Loader2
                  v-if="isLoading"
                  class="w-4 h-4 animate-spin"
                />
                {{ isLoading ? '修改中...' : '确认修改' }}
              </button>
            </form>
          </div>
        </div>
      </div>
    </Transition>
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
  right: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}
</style>
