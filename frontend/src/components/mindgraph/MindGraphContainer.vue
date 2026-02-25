<script setup lang="ts">
/**
 * MindGraphContainer - MindGraph mode content area
 * Shows diagram type selection and discovery gallery
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElAvatar, ElButton, ElDialog, ElInput } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'

import DiagramTemplateInput from './DiagramTemplateInput.vue'
import DiagramTypeGrid from './DiagramTypeGrid.vue'
import DiscoveryGallery from './DiscoveryGallery.vue'

const route = useRoute()
const router = useRouter()
const { isZh } = useLanguage()
const authStore = useAuthStore()
const notify = useNotifications()
const username = computed(() => authStore.user?.username || '')

// Join workshop state
const showJoinWorkshopDialog = ref(false)
const joinCode = ref(['', '', '', '', '', '']) // Array for 6 digits
const isJoining = ref(false)
const codeInputRefs = ref<(HTMLInputElement | null)[]>([])

// Handle digit input
function handleDigitInput(index: number, event: Event) {
  const target = event.target as HTMLInputElement
  const value = target.value.replace(/\D/g, '') // Only digits
  
  if (value.length > 0) {
    joinCode.value[index] = value[value.length - 1] // Take last digit if multiple entered
    
    // Move to next input
    if (index < 5 && codeInputRefs.value[index + 1]) {
      codeInputRefs.value[index + 1]?.focus()
    }
  } else {
    joinCode.value[index] = ''
  }
}

// Handle backspace
function handleKeyDown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace' && !joinCode.value[index] && index > 0) {
    // Move to previous input if current is empty
    codeInputRefs.value[index - 1]?.focus()
  }
}

// Handle paste
function handlePaste(event: ClipboardEvent) {
  event.preventDefault()
  const pastedData = event.clipboardData?.getData('text') || ''
  const digits = pastedData.replace(/\D/g, '').slice(0, 6)
  
  digits.split('').forEach((digit, index) => {
    if (index < 6) {
      joinCode.value[index] = digit
    }
  })
  
  // Focus last filled input or next empty
  const nextEmptyIndex = digits.length < 6 ? digits.length : 5
  codeInputRefs.value[nextEmptyIndex]?.focus()
}

// Get formatted code string
function getFormattedCode(): string {
  const code = joinCode.value.join('')
  if (code.length === 6) {
    return `${code.slice(0, 3)}-${code.slice(3, 6)}`
  }
  return code
}

async function joinWorkshop() {
  const code = getFormattedCode()

  if (code.length !== 7) { // xxx-xxx = 7 characters
    notify.warning(
      isZh.value ? '请输入完整的工作坊代码' : 'Please enter the complete workshop code'
    )
    return
  }

  // Validate format (xxx-xxx)
  if (!/^\d{3}-\d{3}$/.test(code)) {
    notify.warning(
      isZh.value
        ? '工作坊代码格式不正确（应为 xxx-xxx）'
        : 'Invalid workshop code format (should be xxx-xxx)'
    )
    return
  }

  isJoining.value = true
  try {
    const response = await authFetch(`/api/workshop/join?code=${code}`, {
      method: 'POST',
    })

    if (response.ok) {
      const data = await response.json()
      notify.success(
        isZh.value
          ? `已加入工作坊：${data.workshop.title}`
          : `Joined workshop: ${data.workshop.title}`
      )
      // Navigate to the diagram
      window.location.href = `/canvas?diagram_id=${data.workshop.diagram_id}`
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(
        error.detail ||
          (isZh.value ? '加入工作坊失败' : 'Failed to join workshop')
      )
    }
  } catch (error) {
    console.error('Failed to join workshop:', error)
    notify.error(
      isZh.value ? '网络错误，加入失败' : 'Network error, failed to join'
    )
  } finally {
    isJoining.value = false
  }
}

// Handle join_workshop query parameter (from QR code scan)
onMounted(() => {
  const joinWorkshopCode = route.query.join_workshop as string | undefined
  if (joinWorkshopCode) {
    // Pre-fill the code
    const digits = joinWorkshopCode.replace(/\D/g, '').slice(0, 6)
    digits.split('').forEach((digit, index) => {
      if (index < 6) {
        joinCode.value[index] = digit
      }
    })
    // Remove query parameter from URL
    const newQuery = { ...route.query }
    delete newQuery.join_workshop
    router.replace({ query: newQuery })
    // Auto-join after a short delay
    setTimeout(() => {
      joinWorkshop()
    }, 500)
  }
})
</script>

<template>
  <div class="mindgraph-container flex flex-col h-full">
    <!-- Header -->
    <header class="h-14 px-4 flex items-center justify-between bg-white border-b border-gray-200">
      <h1 class="text-sm font-semibold text-gray-800">MindGraph</h1>
      <ElButton
        class="join-workshop-btn"
        size="small"
        :icon="Connection"
        @click="showJoinWorkshopDialog = true"
      >
        {{ isZh ? '加入工作坊' : 'Join Workshop' }}
      </ElButton>
    </header>

    <!-- Join Workshop Dialog -->
    <ElDialog
      v-model="showJoinWorkshopDialog"
      :title="isZh ? '加入工作坊' : 'Join Workshop'"
      width="400px"
    >
      <div class="join-workshop-dialog">
        <p class="mb-4 text-gray-600">
          {{
            isZh
              ? '输入工作坊代码，加入其他人的工作坊并一起编辑图示。'
              : 'Enter a workshop code to join someone else\'s workshop and collaborate.'
          }}
        </p>
        <div class="code-input-container">
          <div class="code-input-boxes">
            <input
              v-for="(digit, index) in joinCode.slice(0, 3)"
              :key="index"
              :ref="(el) => { codeInputRefs[index] = el as HTMLInputElement | null }"
              v-model="joinCode[index]"
              type="text"
              inputmode="numeric"
              maxlength="1"
              class="code-input-box"
              @input="handleDigitInput(index, $event)"
              @keydown="handleKeyDown(index, $event)"
              @paste="handlePaste"
            />
            <span class="code-dash">-</span>
            <input
              v-for="(digit, index) in joinCode.slice(3, 6)"
              :key="index + 3"
              :ref="(el) => { codeInputRefs[index + 3] = el as HTMLInputElement | null }"
              v-model="joinCode[index + 3]"
              type="text"
              inputmode="numeric"
              maxlength="1"
              class="code-input-box"
              @input="handleDigitInput(index + 3, $event)"
              @keydown="handleKeyDown(index + 3, $event)"
              @paste="handlePaste"
            />
          </div>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <ElButton @click="showJoinWorkshopDialog = false">
            {{ isZh ? '取消' : 'Cancel' }}
          </ElButton>
          <ElButton
            type="primary"
            :loading="isJoining"
            @click="joinWorkshop"
          >
            {{ isZh ? '加入' : 'Join' }}
          </ElButton>
        </div>
      </div>
    </ElDialog>

    <!-- Scrollable content area -->
    <div class="flex-1 min-h-0 overflow-y-auto">
      <div class="p-5 w-[70%] mx-auto pb-8">
      <!-- Welcome header - above input -->
      <div class="flex flex-col items-center justify-center mb-8">
        <ElAvatar
          :src="mindgraphLogo"
          alt="MindGraph"
          :size="96"
          class="mindgraph-logo mb-4"
        />
        <div class="text-lg text-gray-600">
          {{
            isZh
              ? `${username}你好，我是你的AI思维图示助手`
              : `Hello ${username}, I'm your AI visual thinking assistant`
          }}
        </div>
      </div>

      <!-- Template input -->
      <DiagramTemplateInput />

      <!-- Diagram type grid -->
      <div class="mt-6">
        <DiagramTypeGrid />
      </div>

      <!-- Discovery gallery -->
      <DiscoveryGallery />
      </div>
    </div>
  </div>
</template>

<style scoped>
.mindgraph-logo {
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.mindgraph-logo :deep(img) {
  object-fit: cover;
}

/* Join Workshop button - Swiss Design style (matching MindMate) */
.join-workshop-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

/* Code input boxes - Modern square boxes */
.code-input-container {
  display: flex;
  justify-content: center;
  margin: 20px 0;
}

.code-input-boxes {
  display: flex;
  align-items: center;
  gap: 8px;
}

.code-input-box {
  width: 48px;
  height: 48px;
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  border: 2px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #1f2937;
  transition: all 0.2s ease;
  outline: none;
}

.code-input-box:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  background: #f9fafb;
}


.code-dash {
  font-size: 24px;
  font-weight: 600;
  color: #6b7280;
  margin: 0 4px;
  user-select: none;
}

.dark .code-input-box {
  background: #1f2937;
  border-color: #4b5563;
  color: #f9fafb;
}

.dark .code-input-box:focus {
  border-color: #3b82f6;
  background: #111827;
}

.dark .code-dash {
  color: #9ca3af;
}
</style>
