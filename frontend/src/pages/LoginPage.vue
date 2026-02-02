<script setup lang="ts">
/**
 * Login Page - User authentication
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { t, isZh } = useLanguage()
const notify = useNotifications()

// Form data
const formData = ref({
  phone: '',
  password: '',
  captcha: '',
})

// Captcha state
const captchaId = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)

const isLoading = ref(false)
const showPassword = ref(false)

// Form validation rules
const rules = computed(() => ({
  phone: [
    { required: true, message: t('auth.phone') + ' is required', trigger: 'blur' },
    { min: 11, max: 11, message: '11 digits required', trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('auth.password') + ' is required', trigger: 'blur' },
    { min: 4, max: 100, message: '4-100 characters', trigger: 'blur' },
  ],
  captcha: [
    { required: true, message: t('auth.captcha') + ' is required', trigger: 'blur' },
    { min: 4, max: 4, message: '4 characters required', trigger: 'blur' },
  ],
}))

// Fetch captcha image
async function refreshCaptcha() {
  captchaLoading.value = true
  try {
    const result = await authStore.fetchCaptcha()
    if (result) {
      captchaId.value = result.captcha_id
      captchaImage.value = result.captcha_image
    } else {
      notify.error(isZh.value ? '验证码加载失败' : 'Failed to load captcha')
    }
  } catch (error) {
    console.error('Captcha error:', error)
    notify.error(isZh.value ? '网络错误，验证码加载失败' : 'Network error, failed to load captcha')
  } finally {
    captchaLoading.value = false
  }
}

// Load captcha on mount
onMounted(() => {
  refreshCaptcha()
})

// Handle login
async function handleLogin() {
  if (!formData.value.phone || !formData.value.password) {
    notify.warning(isZh.value ? '请填写所有字段' : 'Please fill in all fields')
    return
  }

  if (!formData.value.captcha || formData.value.captcha.length !== 4) {
    notify.warning(isZh.value ? '请输入4位验证码' : 'Please enter the 4-character captcha')
    return
  }

  if (!captchaId.value) {
    notify.warning(isZh.value ? '请等待验证码加载' : 'Please wait for captcha to load')
    return
  }

  isLoading.value = true

  try {
    const result = await authStore.login({
      phone: formData.value.phone,
      password: formData.value.password,
      captcha: formData.value.captcha,
      captcha_id: captchaId.value,
    })
    const success = result.success

    if (success) {
      const userName = result.user?.username || ''
      notify.success(
        isZh.value
          ? userName
            ? `${userName}，登录成功`
            : '登录成功'
          : userName
            ? `Welcome, ${userName}`
            : 'Login successful'
      )
      // Redirect to intended page or main page
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
    } else {
      notify.error(result.message || (isZh.value ? '登录失败' : 'Login failed'))
      // Refresh captcha on failed login
      formData.value.captcha = ''
      refreshCaptcha()
    }
  } catch (error) {
    console.error('Login error:', error)
    notify.error(isZh.value ? '网络错误，登录失败' : 'Network error, login failed')
    // Refresh captcha on error
    formData.value.captcha = ''
    refreshCaptcha()
  } finally {
    isLoading.value = false
  }
}

// Handle demo login
function goToDemo() {
  router.push('/demo')
}
</script>

<template>
  <div class="login-page">
    <!-- Logo -->
    <div class="text-center mb-8">
      <div
        class="w-16 h-16 bg-primary-500 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-lg shadow-primary-500/30"
      >
        <span class="text-white font-bold text-2xl">MG</span>
      </div>
      <h1 class="text-2xl font-bold text-white mb-2">Welcome Back</h1>
      <p class="text-white/60">Sign in to continue to MindGraph</p>
    </div>

    <!-- Login Form -->
    <el-form
      :model="formData"
      :rules="rules"
      label-position="top"
      @submit.prevent="handleLogin"
    >
      <el-form-item
        :label="t('auth.phone')"
        prop="phone"
      >
        <el-input
          v-model="formData.phone"
          size="large"
          :placeholder="t('auth.phone')"
          prefix-icon="Phone"
          autocomplete="tel"
          maxlength="11"
        />
      </el-form-item>

      <el-form-item
        :label="t('auth.password')"
        prop="password"
      >
        <el-input
          v-model="formData.password"
          size="large"
          :type="showPassword ? 'text' : 'password'"
          :placeholder="t('auth.password')"
          prefix-icon="Lock"
          autocomplete="current-password"
        >
          <template #suffix>
            <el-icon
              class="cursor-pointer"
              @click="showPassword = !showPassword"
            >
              <View v-if="showPassword" />
              <Hide v-else />
            </el-icon>
          </template>
        </el-input>
      </el-form-item>

      <el-form-item
        :label="t('auth.captcha')"
        prop="captcha"
      >
        <div class="captcha-group">
          <el-input
            v-model="formData.captcha"
            size="large"
            :placeholder="t('auth.enterCaptcha')"
            maxlength="4"
            class="captcha-input"
          />
          <div
            class="captcha-image-container"
            @click="refreshCaptcha"
          >
            <img
              v-if="captchaImage"
              :src="captchaImage"
              alt="Captcha"
              class="captcha-image"
              :class="{ 'opacity-50': captchaLoading }"
            />
            <div
              v-else
              class="captcha-placeholder"
            >
              <el-icon
                v-if="captchaLoading"
                class="is-loading"
              >
                <Loading />
              </el-icon>
              <span v-else>Click to load</span>
            </div>
          </div>
        </div>
        <div class="captcha-hint">
          {{ t('auth.clickToRefresh') }}
        </div>
      </el-form-item>

      <el-form-item class="mt-6">
        <el-button
          type="primary"
          size="large"
          :loading="isLoading"
          class="w-full"
          native-type="submit"
        >
          {{ t('auth.login') }}
        </el-button>
      </el-form-item>
    </el-form>

    <!-- Divider -->
    <div class="flex items-center gap-4 my-6">
      <div class="flex-1 h-px bg-white/20" />
      <span class="text-white/40 text-sm">or</span>
      <div class="flex-1 h-px bg-white/20" />
    </div>

    <!-- Demo Login -->
    <el-button
      size="large"
      class="w-full bg-white/10! border-white/20! text-white! hover:bg-white/20!"
      @click="goToDemo"
    >
      Try Demo
    </el-button>
  </div>
</template>

<style scoped>
.login-page {
  width: 100%;
}

.captcha-group {
  display: flex;
  gap: 12px;
  width: 100%;
}

.captcha-input {
  flex: 1;
}

.captcha-image-container {
  flex-shrink: 0;
  width: 120px;
  height: 40px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s;
}

.captcha-image-container:hover {
  opacity: 0.8;
}

.captcha-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.captcha-placeholder {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.captcha-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-top: 4px;
}
</style>
