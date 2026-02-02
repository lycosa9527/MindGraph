<script setup lang="ts">
/**
 * Gewe WeChat Login Component
 *
 * Simple login workflow:
 * 1. Configure token and region
 * 2. Generate QR code
 * 3. Display QR code
 * 4. Poll for login status
 * 5. Show login status
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'

import { ChatLineRound, CircleCheck, CircleClose, Loading, RefreshLeft } from '@element-plus/icons-vue'

import { useNotifications } from '@/composables'
import apiClient from '@/utils/apiClient'

const notify = useNotifications()

// Region code mapping
const regionOptions = [
  { value: '110000', label: '北京市' },
  { value: '120000', label: '天津市' },
  { value: '130000', label: '河北省' },
  { value: '140000', label: '山西省' },
  { value: '150000', label: '内蒙古' },
  { value: '210000', label: '辽宁省' },
  { value: '220000', label: '吉林省' },
  { value: '230000', label: '黑龙江省' },
  { value: '310000', label: '上海市' },
  { value: '320000', label: '江苏省' },
  { value: '330000', label: '浙江省' },
  { value: '340000', label: '安徽省' },
  { value: '350000', label: '福建省' },
  { value: '360000', label: '江西省' },
  { value: '370000', label: '山东省' },
  { value: '410000', label: '河南省' },
  { value: '420000', label: '湖北省' },
  { value: '430000', label: '湖南省' },
  { value: '440000', label: '广东省' },
  { value: '450000', label: '广西省' },
  { value: '460000', label: '海南省' },
  { value: '500000', label: '重庆市' },
  { value: '510000', label: '四川省' },
  { value: '520000', label: '贵州省' },
  { value: '530000', label: '云南省' },
  { value: '540000', label: '西藏' },
  { value: '610000', label: '陕西省' },
  { value: '620000', label: '甘肃省' },
  { value: '630000', label: '青海省' },
  { value: '640000', label: '宁夏' },
  { value: '650000', label: '新疆' },
]

// Device type options
const deviceTypeOptions = [
  { value: 'ipad', label: 'iPad' },
  { value: 'mac', label: 'Mac' },
]

// Configuration state
const geweToken = ref<string>('')
const selectedRegionId = ref<string>('110000') // Default to 北京市
const selectedDeviceType = ref<string>('ipad') // Default to iPad

// Login state
const qrCodeBase64 = ref<string>('')
const uuid = ref<string>('')
const appId = ref<string>('')
const appIdMasked = ref<string>('')
const isGeneratingQr = ref(false)
const isLoggedIn = ref(false)
const loginInfo = ref<{ app_id: string; wxid: string } | null>(null)
const loginInfoMasked = ref<{ app_id: string; wxid: string } | null>(null)
const checkInterval = ref<number | null>(null)
const expiredTime = ref<number>(0) // Remaining seconds from API
const countdownInterval = ref<number | null>(null)
const countdownSeconds = ref<number>(0) // Display countdown
const isResettingDeviceId = ref(false)

// Helper function to mask a value
function maskValue(value: string, showChars: number = 4): string {
  if (!value) return ''
  if (value.length <= showChars * 2) {
    return '*'.repeat(value.length)
  }
  return `${value.slice(0, showChars)}...${value.slice(-showChars)}`
}

// Load saved configuration from backend and localStorage
async function loadSavedConfig() {
  try {
    // Try to load from backend first
    try {
      const response = await apiClient.get('/api/gewe/preferences')
      if (response.ok) {
        const data = await response.json()
        if (data.region_id) {
          selectedRegionId.value = data.region_id
        }
        if (data.device_type) {
          selectedDeviceType.value = data.device_type
        }
      }
    } catch (error) {
      // Fallback to localStorage if backend fails
      console.debug('Failed to load preferences from backend, using localStorage:', error)
      const savedRegionId = localStorage.getItem('gewe_region_id')
      const savedDeviceType = localStorage.getItem('gewe_device_type')
      if (savedRegionId) {
        selectedRegionId.value = savedRegionId
      }
      if (savedDeviceType) {
        selectedDeviceType.value = savedDeviceType
      }
    }

    // Load appId from localStorage for display (will be overwritten by backend if available)
    const savedAppId = localStorage.getItem('gewe_app_id')
    if (savedAppId) {
      appId.value = savedAppId
      appIdMasked.value = maskValue(savedAppId)
    }
  } catch (error) {
    console.error('Failed to load saved config:', error)
  }
}

// Save configuration to backend (called automatically on change)
async function saveConfig(silent = true) {
  try {
    const response = await apiClient.post('/api/gewe/preferences/save', {
      regionId: selectedRegionId.value,
      deviceType: selectedDeviceType.value,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '保存配置失败' }))
      throw new Error(error.detail || error.msg || '保存配置失败')
    }

    // Also save to localStorage as backup
    if (selectedRegionId.value) {
      localStorage.setItem('gewe_region_id', selectedRegionId.value)
    }
    if (selectedDeviceType.value) {
      localStorage.setItem('gewe_device_type', selectedDeviceType.value)
    }

    if (!silent) {
      notify.success('配置已保存')
    }
  } catch (error: any) {
    console.error('Failed to save config:', error)
    if (!silent) {
      notify.error(error.message || '保存配置失败')
    }
  }
}

// Save appId to localStorage
function saveAppId(newAppId: string) {
  try {
    if (newAppId) {
      localStorage.setItem('gewe_app_id', newAppId)
    }
  } catch (error) {
    console.error('Failed to save appId:', error)
  }
}

// Load config status (token and app_id)
async function loadConfigStatus() {
  try {
    const response = await apiClient.get('/api/gewe/config/status')
    if (response.ok) {
      const data = await response.json()
      if (data.token_masked) {
        geweToken.value = data.token_masked
      }
      if (data.app_id) {
        appId.value = data.app_id
        appIdMasked.value = data.app_id_masked || maskValue(data.app_id)
        saveAppId(data.app_id)
      } else if (data.app_id_masked) {
        appIdMasked.value = data.app_id_masked
      }
    } else {
      // If token is not configured, show empty
      geweToken.value = ''
    }
  } catch (error) {
    console.error('Failed to load config status:', error)
    geweToken.value = ''
  }
}

// Load saved login info on mount
async function loadSavedLoginInfo() {
  try {
    const response = await apiClient.get('/api/gewe/login/info')
    if (!response.ok) {
      isLoggedIn.value = false
      return
    }
    const data = await response.json()
    if (data.app_id && data.wxid) {
      loginInfo.value = {
        app_id: data.app_id,
        wxid: data.wxid,
      }
      loginInfoMasked.value = {
        app_id: maskValue(data.app_id),
        wxid: maskValue(data.wxid),
      }
      appId.value = data.app_id
      appIdMasked.value = maskValue(data.app_id)
      saveAppId(data.app_id)
      isLoggedIn.value = true
    } else {
      isLoggedIn.value = false
    }
  } catch (error) {
    console.error('Failed to load saved login info:', error)
    isLoggedIn.value = false
  }
}

// Generate QR code
async function generateQrCode() {
  isGeneratingQr.value = true
  qrCodeBase64.value = ''
  uuid.value = ''
  isLoggedIn.value = false
  stopCountdown()
  expiredTime.value = 0
  countdownSeconds.value = 0

  try {
    const response = await apiClient.post('/api/gewe/login/qrcode', {
      appId: appId.value || '',
      regionId: selectedRegionId.value,
      deviceType: selectedDeviceType.value,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '生成二维码失败' }))
      throw new Error(error.detail || error.msg || '生成二维码失败')
    }

    const data = await response.json()
    if (data.ret === 200 && data.data) {
      // Handle qrImgBase64 - check if it already has data URL prefix
      const qrImg = data.data.qrImgBase64 || ''
      if (qrImg.startsWith('data:')) {
        qrCodeBase64.value = qrImg
      } else {
        qrCodeBase64.value = `data:image/png;base64,${qrImg}`
      }
      uuid.value = data.data.uuid
      const newAppId = data.data.appId || appId.value
      appId.value = newAppId
      appIdMasked.value = maskValue(newAppId)
      saveAppId(newAppId)

      notify.success('二维码已生成，请使用微信扫码登录')
      startPollingLoginStatus()
    } else {
      throw new Error(data.msg || '生成二维码失败')
    }
  } catch (error: any) {
    notify.error(error.message || '生成二维码失败')
  } finally {
    isGeneratingQr.value = false
  }
}

// Check login status
async function checkLoginStatus() {
  if (!uuid.value || !appId.value) {
    return
  }

  try {
    // iPad login requires autoSliding: false
    // Mac login can use autoSliding: true (auto verification) or false (manual app verification)
    const autoSliding = selectedDeviceType.value === 'mac' ? true : false

    const response = await apiClient.post('/api/gewe/login/check', {
      appId: appId.value,
      uuid: uuid.value,
      autoSliding: autoSliding,
    })

    if (!response.ok) {
      return // Don't show error for polling failures
    }

    const result = await response.json()
    if (result.ret === 200 && result.data) {
      const data = result.data

      // Update expiredTime from API response
      if (typeof data.expiredTime === 'number') {
        expiredTime.value = data.expiredTime
        // If QR code expired (expiredTime <= 0), stop polling
        if (data.expiredTime <= 0) {
          stopPollingLoginStatus()
          stopCountdown()
          qrCodeBase64.value = ''
          countdownSeconds.value = 0
          notify.warning('二维码已过期，请重新生成')
          return
        }
        // Sync countdown value with API response (this ensures countdown stays accurate)
        countdownSeconds.value = data.expiredTime
        // Start countdown if not already running
        if (countdownInterval.value === null && qrCodeBase64.value) {
          startCountdown()
        }
      }

      // status: 0=未扫码, 1=已扫码未登录, 2=登录成功
      if (data.status === 2) {
        // Login successful
        const loginInfoData = data.loginInfo || {}
        const wxid = loginInfoData.wxid || data.wxid || data.Wxid
        const finalAppId = data.appId || appId.value

        if (wxid && finalAppId) {
          stopPollingLoginStatus()
          isLoggedIn.value = true
          loginInfo.value = {
            app_id: finalAppId,
            wxid: wxid,
          }
          loginInfoMasked.value = {
            app_id: maskValue(finalAppId),
            wxid: maskValue(wxid),
          }
          appId.value = finalAppId
          appIdMasked.value = maskValue(finalAppId)
          saveAppId(finalAppId)
          qrCodeBase64.value = '' // Clear QR code after successful login
          stopCountdown()
          notify.success('登录成功！')
        }
      } else if (data.status === 1) {
        // Scanned but not logged in yet - might need face verification
        // Show face verification QR code if available
        if (data.qrImgBase64) {
          const qrImg = data.qrImgBase64
          if (qrImg.startsWith('data:')) {
            qrCodeBase64.value = qrImg
          } else {
            qrCodeBase64.value = `data:image/png;base64,${qrImg}`
          }
        }
      }
      // status === 0 means not scanned yet, continue polling
    }
  } catch (error: any) {
    console.debug('Login check:', error.message)
  }
}

// Start polling for login status
function startPollingLoginStatus() {
  // Clear any existing interval
  stopPollingLoginStatus()

  // Poll every 5 seconds (as per API docs)
  checkInterval.value = window.setInterval(() => {
    checkLoginStatus()
  }, 5000)

  // Also check immediately
  checkLoginStatus()
}

// Stop polling
function stopPollingLoginStatus() {
  if (checkInterval.value !== null) {
    clearInterval(checkInterval.value)
    checkInterval.value = null
  }
}

// Start countdown timer
function startCountdown() {
  // Clear existing countdown
  stopCountdown()

  // Update countdown every second
  countdownInterval.value = window.setInterval(() => {
    if (countdownSeconds.value > 0) {
      countdownSeconds.value--
    } else {
      stopCountdown()
      stopPollingLoginStatus()
      qrCodeBase64.value = ''
      notify.warning('二维码已过期，请重新生成')
    }
  }, 1000)
}

// Stop countdown timer
function stopCountdown() {
  if (countdownInterval.value !== null) {
    clearInterval(countdownInterval.value)
    countdownInterval.value = null
  }
}

// Cleanup on unmount
onUnmounted(() => {
  stopPollingLoginStatus()
  stopCountdown()
  if (saveTimeout) {
    clearTimeout(saveTimeout)
  }
})

// Auto-save preferences when they change (debounced)
let saveTimeout: ReturnType<typeof setTimeout> | null = null
watch([selectedRegionId, selectedDeviceType], () => {
  // Clear existing timeout
  if (saveTimeout) {
    clearTimeout(saveTimeout)
  }
  // Debounce: only save after user stops changing for 500ms
  saveTimeout = setTimeout(() => {
    saveConfig(true) // Silent save
  }, 500)
}, { deep: true })

// Reset device ID
async function resetDeviceId() {
  isResettingDeviceId.value = true
  try {
    const response = await apiClient.post('/api/gewe/device/reset')
    if (response.ok) {
      // Clear local state
      appId.value = ''
      appIdMasked.value = ''
      loginInfo.value = null
      loginInfoMasked.value = null
      isLoggedIn.value = false
      // Clear localStorage
      localStorage.removeItem('gewe_app_id')
      // Reload config status to refresh display
      await loadConfigStatus()
      notify.success('设备ID已重置，已保存的 app_id 和 wxid 已清除。下次登录时将生成新的 app_id 和 wxid')
    } else {
      const error = await response.json().catch(() => ({ detail: '重置设备ID失败' }))
      throw new Error(error.detail || error.msg || '重置设备ID失败')
    }
  } catch (error: any) {
    console.error('Failed to reset device ID:', error)
    notify.error(error.message || '重置设备ID失败')
  } finally {
    isResettingDeviceId.value = false
  }
}

// Load saved info on mount
onMounted(async () => {
  await loadSavedConfig()
  loadConfigStatus()
  loadSavedLoginInfo()
})
</script>

<template>
  <div class="gewe-login-component">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <el-icon><ChatLineRound /></el-icon>
            <span>Gewe 微信登录</span>
          </div>
          <!-- Login Status Badge -->
          <div class="flex items-center gap-2">
            <el-icon
              v-if="isLoggedIn"
              class="text-green-500"
            >
              <CircleCheck />
            </el-icon>
            <el-icon
              v-else
              class="text-gray-400"
            >
              <CircleClose />
            </el-icon>
            <span
              :class="isLoggedIn ? 'text-green-600 dark:text-green-400' : 'text-gray-500'"
              class="text-sm font-medium"
            >
              {{ isLoggedIn ? '已登录' : '未登录' }}
            </span>
          </div>
        </div>
      </template>

      <!-- Configuration Section -->
      <div class="mb-6 space-y-4">
        <el-form
          :model="{ token: geweToken, regionId: selectedRegionId }"
          label-width="120px"
        >
          <el-form-item label="Gewe 令牌">
            <el-input
              v-model="geweToken"
              :placeholder="geweToken || '未在后端配置 (.env)'"
              readonly
              disabled
            >
              <template #prefix>
                <el-icon><ChatLineRound /></el-icon>
              </template>
            </el-input>
            <div class="text-xs text-gray-500 mt-1">
              <span v-if="geweToken">Token 已在后端环境变量 GEWE_TOKEN 中配置（已脱敏）</span>
              <span v-else class="text-red-500">Token 未配置 - 请在后端 .env 文件中设置 GEWE_TOKEN</span>
            </div>
          </el-form-item>

          <el-form-item label="App ID (设备ID)">
            <div class="flex gap-2">
              <el-input
                v-model="appIdMasked"
                :placeholder="appIdMasked || '由后端自动管理（首次登录留空）'"
                readonly
                disabled
                style="flex: 1"
              >
                <template #prefix>
                  <el-icon><CircleCheck /></el-icon>
                </template>
              </el-input>
              <el-button
                :loading="isResettingDeviceId"
                :disabled="!appId && !appIdMasked"
                @click="resetDeviceId"
              >
                <el-icon><RefreshLeft /></el-icon>
                <span class="ml-1">重置</span>
              </el-button>
            </div>
            <div class="text-xs text-gray-500 mt-1 space-y-1">
              <div>• 由后端管理 - 自动从登录响应中设置</div>
              <div>• 首次登录：留空，系统会自动创建设备</div>
              <div>• 重新登录：使用上次登录返回的 appId（避免重复创建设备触发风控）</div>
              <div>• 重置设备ID：清除已保存的设备ID，下次登录将创建新设备</div>
            </div>
          </el-form-item>

          <el-form-item label="设备与地区">
            <div class="flex gap-2">
              <el-select
                v-model="selectedRegionId"
                placeholder="选择地区"
                filterable
                style="flex: 1"
              >
                <el-option
                  v-for="option in regionOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <el-select
                v-model="selectedDeviceType"
                placeholder="选择设备"
                filterable
                style="width: 150px"
              >
                <el-option
                  v-for="option in deviceTypeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </div>
            <div class="text-xs text-gray-500 mt-1">
              <div v-if="selectedDeviceType === 'ipad'">
                • iPad登录：需要人脸识别App进行二次验证（仅支持iOS，使用苹果自带浏览器打开下载）
              </div>
              <div v-else>
                • Mac登录：支持自动验证（约10秒，90%通过率）或手动滑块App验证
              </div>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <!-- Login Info Display -->
      <div
        v-if="isLoggedIn && loginInfoMasked"
        class="mb-6 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800"
      >
        <div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
          <p><strong>设备 ID:</strong> {{ loginInfoMasked.app_id }}</p>
          <p><strong>微信 ID:</strong> {{ loginInfoMasked.wxid }}</p>
        </div>
      </div>

      <!-- QR Code Display -->
      <div
        v-if="!isLoggedIn"
        class="text-center mb-6"
      >
        <div
          v-if="qrCodeBase64"
          class="inline-block p-4 bg-white rounded-lg shadow-lg"
        >
          <img
            :src="qrCodeBase64"
            alt="微信登录二维码"
            class="w-64 h-64"
          />
        </div>
        <div
          v-else
          class="w-64 h-64 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center mx-auto"
        >
          <el-icon
            v-if="isGeneratingQr"
            :size="48"
            class="is-loading text-gray-400"
          >
            <Loading />
          </el-icon>
          <span
            v-else
            class="text-gray-400"
          >暂无二维码</span>
        </div>
        <!-- Countdown Display -->
        <div
          v-if="qrCodeBase64 && countdownSeconds > 0"
          class="mt-4 text-lg font-medium"
          :class="countdownSeconds <= 30 ? 'text-red-500' : 'text-gray-600 dark:text-gray-300'"
        >
          倒计时 {{ countdownSeconds }} 秒
        </div>
      </div>

      <!-- Status Message -->
      <div
        v-if="!isLoggedIn && qrCodeBase64"
        class="text-center mb-6"
      >
        <el-alert
          type="info"
          :closable="false"
          show-icon
        >
          <template #title>
            <div class="flex items-center gap-2">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>等待扫码... 请使用微信扫描二维码</span>
            </div>
          </template>
        </el-alert>
      </div>

      <!-- Actions -->
      <div class="flex justify-center">
        <el-button
          v-if="!isLoggedIn"
          type="primary"
          :loading="isGeneratingQr"
          @click="generateQrCode"
        >
          {{ qrCodeBase64 ? '重新生成二维码' : '生成二维码' }}
        </el-button>
        <el-button
          v-else
          type="success"
          disabled
        >
          <el-icon><CircleCheck /></el-icon>
          <span class="ml-2">已登录</span>
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.gewe-login-component {
  max-width: 800px;
  margin: 0 auto;
}
</style>
