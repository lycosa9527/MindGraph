<script setup lang="ts">
/**
 * ApiTokenModal — generate, display, revoke user API token (WorkBuddy / extensions).
 */
import { computed, ref, watch } from 'vue'

import { ElMessage } from 'element-plus'

import { Key, Loader2 } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables'
import { apiDelete, apiGet, apiPost } from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const { t } = useLanguage()

const isVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

type StatusPayload = {
  exists: boolean
  token: string | null
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
    emit('changed')
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
    emit('changed')
    await loadStatus()
  } finally {
    loading.value = false
  }
}

async function copyToken() {
  const token = rawToken.value || status.value?.token || ''
  if (!token) {
    return
  }
  try {
    await navigator.clipboard.writeText(token)
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
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.apiToken.ribbon')"
    :title="t('swissGlass.hero.apiToken.title')"
    :line1="t('swissGlass.hero.apiToken.line1')"
    :icon="Key"
    @close="closeModal"
  >
    <div class="space-y-4">
      <div
        v-if="loading && !status"
        class="text-center text-stone-500 text-sm"
      >
        加载中…
      </div>

      <template v-else-if="view === 'status'">
        <div
          v-if="status?.exists"
          class="rounded-lg border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600 space-y-2"
        >
          <div>状态：有效</div>
          <div v-if="status.expires_at">到期：{{ status.expires_at }}</div>
          <div v-if="status.last_used_at">上次使用：{{ status.last_used_at }}</div>
          <div
            v-if="status.token"
            class="flex gap-2"
          >
            <input
              :value="status.token"
              type="text"
              readonly
              class="flex-1 min-w-0 px-3 py-2 rounded-lg border border-stone-200 bg-white font-mono text-xs"
            />
            <button
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
              @click="copyToken"
            >
              复制
            </button>
          </div>
          <div
            v-else
            class="text-xs text-stone-500"
          >
            当前令牌无法回显，请重新生成。
          </div>
        </div>
        <div
          v-else
          class="text-sm text-stone-500"
        >
          尚未生成 Token
        </div>

        <div class="flex flex-wrap gap-2 justify-end pt-2">
          <button
            v-if="status?.exists"
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
            :disabled="loading"
            @click="generateToken"
          >
            <Loader2
              v-if="loading"
              class="w-3.5 h-3.5 animate-spin"
            />
            重新生成
          </button>
          <button
            v-else
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
            :disabled="loading"
            @click="generateToken"
          >
            <Loader2
              v-if="loading"
              class="w-3.5 h-3.5 animate-spin"
            />
            生成 Token
          </button>
          <button
            v-if="status?.exists"
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--danger"
            :disabled="loading"
            @click="revokeToken"
          >
            <Loader2
              v-if="loading"
              class="w-3.5 h-3.5 animate-spin"
            />
            吊销
          </button>
        </div>
      </template>

      <template v-else>
        <div
          class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900"
        >
          令牌已保存在账户信息中，可随时再次查看。
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
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
            @click="copyToken"
          >
            复制
          </button>
        </div>
        <div class="flex justify-end pt-2">
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
            @click="doneTokenView"
          >
            完成
          </button>
        </div>
      </template>
    </div>

    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="closeModal"
        >
          {{ t('common.close') }}
        </button>
      </div>
    </template>
  </SwissGlassCard>
</template>
