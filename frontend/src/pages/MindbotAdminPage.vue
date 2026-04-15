<script setup lang="ts">
/**
 * Standalone MindBot admin — DingTalk HTTP robot + Dify (per organization).
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { Plus } from '@element-plus/icons-vue'

import AdminMindBotTab from '@/components/admin/AdminMindBotTab.vue'
import { useLanguage } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAuthStore } from '@/stores/auth'
import { apiRequest } from '@/utils/apiClient'

/** Background Dify probe interval (ms). */
const DIFY_HEARTBEAT_MS = 10 * 60 * 1000

const { t } = useLanguage()
const authStore = useAuthStore()
const { featureMindbot } = useFeatureFlags()

const mindbotTabRef = ref<InstanceType<typeof AdminMindBotTab> | null>(null)

const showHeaderAddSchool = computed(
  () => featureMindbot.value && authStore.isAdmin
)

function onHeaderAddSchool(): void {
  mindbotTabRef.value?.openCreate()
}

interface DifyServiceStatusPayload {
  online: boolean
  http_status?: number | null
  error?: string | null
  probe_url?: string | null
}

const difyStatusLoading = ref(false)
const difyStatus = ref<DifyServiceStatusPayload | null>(null)

const difyStatusLabel = computed(() => {
  if (difyStatusLoading.value) {
    return t('admin.mindbot.difyServiceChecking')
  }
  if (!difyStatus.value) {
    return t('admin.mindbot.difyServiceChecking')
  }
  if (difyStatus.value.error === 'api_key_not_configured') {
    return t('admin.mindbot.difyServiceUnconfigured')
  }
  if (difyStatus.value.online) {
    return t('admin.mindbot.difyServiceOnline')
  }
  return t('admin.mindbot.difyServiceOffline')
})

const difyStatusTooltip = computed(() => {
  const err = difyStatus.value?.error
  if (err && err !== 'api_key_not_configured') {
    return t('admin.mindbot.difyServiceTooltipError')
  }
  return t('admin.mindbot.difyServiceTooltip')
})

const difyStatusButtonClass = computed(() => {
  if (difyStatusLoading.value || !difyStatus.value) {
    return 'mindbot-dify-status-btn mindbot-dify-status-btn--pending'
  }
  if (difyStatus.value.error === 'api_key_not_configured') {
    return 'mindbot-dify-status-btn mindbot-dify-status-btn--warn'
  }
  if (difyStatus.value.online) {
    return 'mindbot-dify-status-btn mindbot-dify-status-btn--online'
  }
  return 'mindbot-dify-status-btn mindbot-dify-status-btn--offline'
})

let difyHeartbeatTimer: ReturnType<typeof setInterval> | null = null

async function fetchDifyServiceStatus(silent = false): Promise<void> {
  if (!featureMindbot.value) {
    return
  }
  if (!silent) {
    difyStatusLoading.value = true
  }
  try {
    const res = await apiRequest('/api/mindbot/admin/dify-service-status')
    if (res.ok) {
      difyStatus.value = (await res.json()) as DifyServiceStatusPayload
    } else {
      difyStatus.value = {
        online: false,
        error: `http_${res.status}`,
        probe_url: null,
      }
    }
  } catch {
    difyStatus.value = {
      online: false,
      error: 'network',
      probe_url: null,
    }
  } finally {
    if (!silent) {
      difyStatusLoading.value = false
    }
  }
}

onMounted(() => {
  void fetchDifyServiceStatus(false)
  difyHeartbeatTimer = window.setInterval(() => {
    void fetchDifyServiceStatus(true)
  }, DIFY_HEARTBEAT_MS)
})

onUnmounted(() => {
  if (difyHeartbeatTimer != null) {
    clearInterval(difyHeartbeatTimer)
    difyHeartbeatTimer = null
  }
})
</script>

<template>
  <div class="mindbot-admin-page flex-1 flex flex-col bg-gray-50 overflow-hidden">
    <div
      class="mindbot-admin-header h-14 px-4 flex items-center justify-between shrink-0 bg-white border-b border-gray-200 dark:bg-gray-800 dark:border-gray-700"
    >
      <h1 class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate min-w-0 flex-1">
        {{ t('admin.mindbot') }}
      </h1>
      <div
        v-if="featureMindbot"
        class="flex items-center gap-2 shrink-0"
      >
        <el-tooltip
          :content="difyStatusTooltip"
          placement="bottom-end"
          :show-after="400"
        >
          <el-button
            size="small"
            :class="difyStatusButtonClass"
            :loading="difyStatusLoading"
            @click="fetchDifyServiceStatus(false)"
          >
            {{ difyStatusLabel }}
          </el-button>
        </el-tooltip>
        <el-button
          v-if="showHeaderAddSchool"
          size="small"
          class="mindbot-admin-new-school-btn"
          :disabled="mindbotTabRef?.isAddSchoolDisabled ?? true"
          @click="onHeaderAddSchool"
        >
          <el-icon class="mr-1"><Plus /></el-icon>
          {{ t('admin.mindbot.create') }}
        </el-button>
      </div>
    </div>

    <div class="mindbot-admin-body flex-1 overflow-y-auto">
      <div class="px-6 pt-4 pb-6">
        <div class="mindbot-admin-content max-w-[1400px] mx-auto">
          <AdminMindBotTab ref="mindbotTabRef" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mindbot-admin-page {
  min-height: 0;
}

.mindbot-admin-body {
  min-height: 0;
}

.mindbot-dify-status-btn {
  font-weight: 500;
  border-radius: 9999px;
}

.mindbot-dify-status-btn--pending {
  --el-button-bg-color: #f5f5f4;
  --el-button-border-color: #e7e5e4;
  --el-button-text-color: #57534e;
}

.dark .mindbot-dify-status-btn--pending {
  --el-button-bg-color: #374151;
  --el-button-border-color: #4b5563;
  --el-button-text-color: #d1d5db;
}

.mindbot-dify-status-btn--online {
  --el-button-bg-color: #ecfdf5;
  --el-button-border-color: #6ee7b7;
  --el-button-hover-bg-color: #d1fae5;
  --el-button-hover-border-color: #34d399;
  --el-button-hover-text-color: #065f46;
  --el-button-text-color: #047857;
}

.dark .mindbot-dify-status-btn--online {
  --el-button-bg-color: #14532d;
  --el-button-border-color: #16a34a;
  --el-button-hover-bg-color: #166534;
  --el-button-hover-border-color: #22c55e;
  --el-button-hover-text-color: #f8fafc;
  --el-button-text-color: #bbf7d0;
}

.mindbot-dify-status-btn--offline {
  --el-button-bg-color: #fef2f2;
  --el-button-border-color: #fca5a5;
  --el-button-hover-bg-color: #fee2e2;
  --el-button-hover-border-color: #f87171;
  --el-button-hover-text-color: #7f1d1d;
  --el-button-text-color: #b91c1c;
}

.dark .mindbot-dify-status-btn--offline {
  --el-button-bg-color: #450a0a;
  --el-button-border-color: #dc2626;
  --el-button-hover-bg-color: #7f1d1d;
  --el-button-hover-border-color: #ef4444;
  --el-button-hover-text-color: #fef2f2;
  --el-button-text-color: #fecaca;
}

.mindbot-dify-status-btn--warn {
  --el-button-bg-color: #fffbeb;
  --el-button-border-color: #fde68a;
  --el-button-text-color: #92400e;
}

.dark .mindbot-dify-status-btn--warn {
  --el-button-bg-color: #451a03;
  --el-button-border-color: #b45309;
  --el-button-text-color: #fde68a;
}

/* Match MindMate full-page header primary action (New Chat) */
.mindbot-admin-new-school-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-hover-text-color: #1c1917;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

.dark .mindbot-admin-new-school-btn {
  --el-button-bg-color: #4b5563;
  --el-button-border-color: #6b7280;
  --el-button-hover-bg-color: #6b7280;
  --el-button-hover-border-color: #9ca3af;
  --el-button-hover-text-color: #f9fafb;
  --el-button-active-bg-color: #52525b;
  --el-button-active-border-color: #a1a1aa;
  --el-button-text-color: #f9fafb;
}

</style>
