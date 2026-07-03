/**
 * Thinking coin (思维币) wallet API composable.
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { loadThinkingCoinsWallet } from '@/composables/auth/fetchThinkingCoinsWallet'
import type {
  AdminThinkingCoinTask,
  ThinkingCoinLedgerResponse,
  ThinkingCoinSettings,
  ThinkingCoinsWallet,
} from '@/types/thinkingCoins'
import { apiRequestJson } from '@/utils/apiClient'

export function formatThinkingCoinBalance(value: number): string {
  return new Intl.NumberFormat(undefined).format(Math.max(0, value))
}

export function useThinkingCoins() {
  const { t, isZh } = useLanguage()
  const notify = useNotifications()
  const router = useRouter()
  const wallet = ref<ThinkingCoinsWallet | null>(null)
  const ledger = ref<ThinkingCoinLedgerResponse | null>(null)
  const loading = ref(false)

  async function fetchWallet(): Promise<ThinkingCoinsWallet | null> {
    loading.value = true
    try {
      const data = await loadThinkingCoinsWallet()
      wallet.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function fetchLedger(page = 1, limit = 20, append = false): Promise<ThinkingCoinLedgerResponse> {
    const data = await apiRequestJson<ThinkingCoinLedgerResponse>(
      `/api/auth/thinking-coins/ledger?page=${page}&limit=${limit}`,
      { method: 'GET' }
    )
    if (append && ledger.value) {
      ledger.value = {
        ...data,
        items: [...ledger.value.items, ...data.items],
      }
    } else {
      ledger.value = data
    }
    return data
  }

  function taskTitle(task: { title: string; title_en?: string | null }): string {
    if (!isZh.value && task.title_en) {
      return task.title_en
    }
    return task.title
  }

  function taskSubtitle(task: { subtitle?: string | null; subtitle_en?: string | null }): string {
    if (!isZh.value && task.subtitle_en) {
      return task.subtitle_en ?? ''
    }
    return task.subtitle ?? ''
  }

  async function handleTaskClick(task: ThinkingCoinsWallet['earn_tasks'][number]): Promise<void> {
    if (task.handler_key === 'navigate') {
      const route = String(task.action_config?.route ?? '/community')
      await router.push(route)
      return
    }
    if (task.handler_key === 'auto_login' && !task.completed_today) {
      await apiRequestJson<{ credited: number; balance: number }>(
        '/api/auth/thinking-coins/check-in',
        {
          method: 'POST',
        }
      )
      notify.success(t('thinkingCoins.checkInSuccess'))
      await fetchWallet()
    }
  }

  return {
    wallet,
    ledger,
    loading,
    fetchWallet,
    fetchLedger,
    taskTitle,
    taskSubtitle,
    handleTaskClick,
    formatBalance: formatThinkingCoinBalance,
  }
}

export async function fetchAdminThinkingCoinTasks(): Promise<AdminThinkingCoinTask[]> {
  const data = await apiRequestJson<{ tasks: AdminThinkingCoinTask[] }>(
    '/api/auth/admin/thinking-coins/tasks',
    { method: 'GET' }
  )
  return data.tasks
}

export async function updateAdminThinkingCoinTask(
  id: number,
  body: Partial<AdminThinkingCoinTask>
): Promise<AdminThinkingCoinTask> {
  const data = await apiRequestJson<{ task: AdminThinkingCoinTask }>(
    `/api/auth/admin/thinking-coins/tasks/${id}`,
    { method: 'PUT', body: JSON.stringify(body) }
  )
  return data.task
}

export async function fetchAdminThinkingCoinSettings(): Promise<ThinkingCoinSettings> {
  return apiRequestJson<ThinkingCoinSettings>('/api/auth/admin/thinking-coins/settings', {
    method: 'GET',
  })
}

export async function updateAdminThinkingCoinSettings(
  body: ThinkingCoinSettings
): Promise<ThinkingCoinSettings> {
  return apiRequestJson<ThinkingCoinSettings>('/api/auth/admin/thinking-coins/settings', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export type CreateAdminThinkingCoinTaskBody = {
  slug: string
  title: string
  subtitle?: string
  title_en?: string
  subtitle_en?: string
  reward_amount: number
  monthly_cap?: number | null
  handler_key: string
  action_config?: Record<string, unknown> | null
  sort_order?: number
  is_active?: boolean
}

export async function createAdminThinkingCoinTask(
  body: CreateAdminThinkingCoinTaskBody
): Promise<AdminThinkingCoinTask> {
  const data = await apiRequestJson<{ task: AdminThinkingCoinTask }>(
    '/api/auth/admin/thinking-coins/tasks',
    { method: 'POST', body: JSON.stringify(body) }
  )
  return data.task
}

export async function deleteAdminThinkingCoinTask(id: number): Promise<void> {
  await apiRequestJson<{ ok: boolean }>(`/api/auth/admin/thinking-coins/tasks/${id}`, {
    method: 'DELETE',
  })
}
