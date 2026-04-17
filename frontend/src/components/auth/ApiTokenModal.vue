<script setup lang="ts">
/**
 * ApiTokenModal — generate, display once, revoke user API token (OpenClaw).
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElMessage } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { apiDelete, apiGet, apiPost } from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

type StatusPayload = {
  exists: boolean
  expires_at: string | null
  last_used_at: string | null
  created_at: string | null
  is_active: boolean
}

const loading = ref(false)
const status = ref<StatusPayload | null>(null)
const view = ref<'status' | 'token'>('status')
const rawToken = ref('')
const tokenExpiresAt = ref('')
const accountHint = ref('')

async function loadStatus() {
  loading.value = true
  try {
    const res = await apiGet('/api/auth/api-token')
    if (!res.ok) {
      status.value = null
      return
    }
    status.value = (await res.json()) as StatusPayload
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      view.value = 'status'
      rawToken.value = ''
      tokenExpiresAt.value = ''
      accountHint.value = ''
      void loadStatus()
    }
  }
)

function closeModal() {
  isVisible.value = false
}

async function generateToken() {
  loading.value = true
  try {
    const res = await apiPost('/api/auth/api-token', {})
    if (!res.ok) {
      const err = await res.text()
      ElMessage.error(err || '生成失败')
      return
    }
    const data = (await res.json()) as { token: string; expires_at: string; account: string }
    rawToken.value = data.token
    tokenExpiresAt.value = data.expires_at
    accountHint.value = data.account
    view.value = 'token'
    await loadStatus()
  } finally {
    loading.value = false
  }
}

async function revokeToken() {
  loading.value = true
  try {
    const res = await apiDelete('/api/auth/api-token')
    if (!res.ok) {
      ElMessage.error('吊销失败')
      return
    }
    ElMessage.success('已吊销')
    view.value = 'status'
    rawToken.value = ''
    await loadStatus()
  } finally {
    loading.value = false
  }
}

async function copyToken() {
  try {
    await navigator.clipboard.writeText(rawToken.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

function doneTokenView() {
  view.value = 'status'
  rawToken.value = ''
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-[60] flex items-center justify-center p-4"
        @click.self="closeModal"
      >
        <div class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]" />
        <div class="relative w-full max-w-md">
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden">
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100 relative">
              <el-button
                :icon="Close"
                circle
                text
                class="close-btn"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">API Token</h2>
              <p class="text-xs text-stone-500 mt-1">用于 OpenClaw 等外部工具，有效期 7 天</p>
            </div>

            <div class="p-8 space-y-4">
              <div
                v-if="loading && !status"
                class="text-center text-stone-500 text-sm"
              >
                加载中…
              </div>

              <template v-else-if="view === 'status'">
                <div
                  v-if="status?.exists"
                  class="rounded-lg border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600 space-y-1"
                >
                  <div>状态：有效</div>
                  <div v-if="status.expires_at">到期：{{ status.expires_at }}</div>
                  <div v-if="status.last_used_at">上次使用：{{ status.last_used_at }}</div>
                </div>
                <div
                  v-else
                  class="text-sm text-stone-500"
                >
                  尚未生成 Token
                </div>

                <div class="flex flex-wrap gap-2 justify-end pt-2">
                  <el-button
                    v-if="status?.exists"
                    round
                    size="small"
                    class="account-action-btn"
                    :loading="loading"
                    @click="generateToken"
                  >
                    重新生成
                  </el-button>
                  <el-button
                    v-else
                    round
                    size="small"
                    type="primary"
                    :loading="loading"
                    @click="generateToken"
                  >
                    生成 Token
                  </el-button>
                  <el-button
                    v-if="status?.exists"
                    round
                    size="small"
                    :loading="loading"
                    @click="revokeToken"
                  >
                    吊销
                  </el-button>
                </div>
              </template>

              <template v-else>
                <div
                  class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900"
                >
                  此 Token 仅显示一次，请立即复制保存；关闭窗口后将无法再次查看完整 Token。
                </div>
                <div
                  v-if="accountHint"
                  class="text-xs text-stone-500"
                >
                  账号：{{ accountHint }}
                </div>
                <div
                  v-if="tokenExpiresAt"
                  class="text-xs text-stone-500"
                >
                  有效期至：{{ tokenExpiresAt }}
                </div>
                <div class="flex gap-2">
                  <input
                    :value="rawToken"
                    type="text"
                    readonly
                    class="flex-1 min-w-0 px-3 py-2 rounded-lg border border-stone-200 bg-stone-50 font-mono text-xs"
                  />
                  <el-button
                    round
                    size="small"
                    @click="copyToken"
                    >复制</el-button
                  >
                </div>
                <div class="flex justify-end pt-2">
                  <el-button
                    round
                    size="small"
                    type="primary"
                    @click="doneTokenView"
                    >完成</el-button
                  >
                </div>
              </template>
            </div>

            <div class="px-8 pb-8 flex justify-end">
              <button
                class="py-2 px-6 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 transition-all"
                @click="closeModal"
              >
                关闭
              </button>
            </div>
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
.close-btn {
  position: absolute;
  top: 16px;
  inset-inline-end: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}
.account-action-btn {
  --el-button-bg-color: #44403c;
  --el-button-text-color: #ffffff;
  --el-button-border-color: #44403c;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-text-color: #ffffff;
  --el-button-hover-border-color: #292524;
  font-weight: 500;
}
</style>
