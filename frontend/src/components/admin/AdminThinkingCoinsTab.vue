<script setup lang="ts">
/**
 * Admin — thinking coin economy (Swiss stone layout + segmented panels).
 */
import { computed, onMounted, ref } from 'vue'

import { ElMessageBox } from 'element-plus'
import { Plus, Trash2 } from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  createAdminThinkingCoinTask,
  deleteAdminThinkingCoinTask,
  fetchAdminThinkingCoinSettings,
  fetchAdminThinkingCoinTasks,
  updateAdminThinkingCoinSettings,
  updateAdminThinkingCoinTask,
  type CreateAdminThinkingCoinTaskBody,
} from '@/composables/auth/useThinkingCoins'
import type { AdminThinkingCoinTask, ThinkingCoinSettings } from '@/types/thinkingCoins'

type AdminPanel = 'tasks' | 'settings' | 'preview'

const PHASE1_HANDLERS = ['auto_login', 'usage_daily', 'client_event', 'navigate', 'custom_cta'] as const

const { t } = useLanguage()
const notify = useNotifications()

const panel = ref<AdminPanel>('tasks')
const tasks = ref<AdminThinkingCoinTask[]>([])
const settings = ref<ThinkingCoinSettings | null>(null)
const loading = ref(true)
const savingSettings = ref(false)
const savingTaskId = ref<number | null>(null)
const showCreateDialog = ref(false)

const createForm = ref<CreateAdminThinkingCoinTaskBody>({
  slug: '',
  title: '',
  subtitle: '',
  reward_amount: 10,
  monthly_cap: null,
  handler_key: 'custom_cta',
  action_config: {},
  sort_order: 100,
  is_active: true,
})

const panelOptions = computed(() => [
  { label: t('thinkingCoins.admin.panelTasks'), value: 'tasks' as const },
  { label: t('thinkingCoins.admin.panelSettings'), value: 'settings' as const },
  { label: t('thinkingCoins.admin.panelPreview'), value: 'preview' as const },
])

const handlerOptions = computed(() =>
  PHASE1_HANDLERS.map((key) => ({
    value: key,
    label: handlerLabel(key),
  }))
)

const activePreviewTasks = computed(() => tasks.value.filter((row) => row.is_active))

function handlerLabel(key: string): string {
  const map: Record<string, string> = {
    auto_login: t('thinkingCoins.admin.handlerAutoLogin'),
    usage_daily: t('thinkingCoins.admin.handlerUsageDaily'),
    client_event: t('thinkingCoins.admin.handlerClientEvent'),
    navigate: t('thinkingCoins.admin.handlerNavigate'),
    custom_cta: t('thinkingCoins.admin.handlerCustomCta'),
    copy_referral_link: t('thinkingCoins.admin.referralLocked'),
  }
  return map[key] ?? key
}

async function loadAll(): Promise<void> {
  loading.value = true
  try {
    const [taskRows, settingRows] = await Promise.all([
      fetchAdminThinkingCoinTasks(),
      fetchAdminThinkingCoinSettings(),
    ])
    tasks.value = taskRows
    settings.value = settingRows
  } finally {
    loading.value = false
  }
}

async function saveTaskRow(task: AdminThinkingCoinTask): Promise<void> {
  savingTaskId.value = task.id
  try {
    await updateAdminThinkingCoinTask(task.id, {
      title: task.title,
      subtitle: task.subtitle,
      reward_amount: task.reward_amount,
      monthly_cap: task.monthly_cap,
      sort_order: task.sort_order,
      is_active: task.is_active,
      action_config: task.action_config,
    })
    notify.success(t('thinkingCoins.admin.save'))
    await loadAll()
  } finally {
    savingTaskId.value = null
  }
}

async function saveSettings(): Promise<void> {
  if (!settings.value) {
    return
  }
  savingSettings.value = true
  try {
    settings.value = await updateAdminThinkingCoinSettings(settings.value)
    notify.success(t('thinkingCoins.admin.save'))
  } finally {
    savingSettings.value = false
  }
}

async function confirmDeleteTask(task: AdminThinkingCoinTask): Promise<void> {
  if (task.is_system) {
    return
  }
  try {
    await ElMessageBox.confirm(t('thinkingCoins.admin.deleteConfirm'), {
      type: 'warning',
      confirmButtonText: t('thinkingCoins.admin.deleteTask'),
    })
    await deleteAdminThinkingCoinTask(task.id)
    notify.success(t('thinkingCoins.admin.save'))
    await loadAll()
  } catch {
    /* cancelled */
  }
}

function resetCreateForm(): void {
  createForm.value = {
    slug: '',
    title: '',
    subtitle: '',
    reward_amount: 10,
    monthly_cap: null,
    handler_key: 'custom_cta',
    action_config: {},
    sort_order: 100,
    is_active: true,
  }
}

async function submitCreateTask(): Promise<void> {
  const body = { ...createForm.value }
  if (body.handler_key === 'usage_daily') {
    body.action_config = {
      request_type: String(body.action_config?.request_type ?? 'mindmate'),
    }
  } else if (body.handler_key === 'client_event') {
    body.action_config = {
      event_key: String(body.action_config?.event_key ?? ''),
    }
  } else if (body.handler_key === 'navigate') {
    body.action_config = {
      route: String(body.action_config?.route ?? '/community'),
    }
  } else {
    body.action_config = null
  }
  await createAdminThinkingCoinTask(body)
  notify.success(t('thinkingCoins.admin.save'))
  showCreateDialog.value = false
  resetCreateForm()
  await loadAll()
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <div class="admin-thinking-coins p-4 max-w-5xl space-y-5">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-stone-900 tracking-tight">
        {{ t('thinkingCoins.admin.tab') }}
      </h2>
      <AdminSwissSegmented
        v-model="panel"
        :options="panelOptions"
        equal
        fit
        :aria-label="t('thinkingCoins.admin.tab')"
      />
    </header>

    <div
      v-if="loading"
      class="text-sm text-stone-500 py-8 text-center"
    >
      …
    </div>

    <template v-else>
      <!-- Tasks -->
      <section v-if="panel === 'tasks'">
        <div class="admin-swiss-toolbar admin-swiss-toolbar--header mb-3 flex-wrap">
          <p class="text-xs text-stone-500 flex-1 min-w-[12rem]">
            {{ t('thinkingCoins.admin.tasksTitle') }}
          </p>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-800"
            @click="showCreateDialog = true"
          >
            <Plus class="h-3.5 w-3.5" />
            {{ t('thinkingCoins.admin.addTask') }}
          </button>
        </div>

        <div class="overflow-x-auto rounded-xl border border-stone-200 bg-white">
          <table class="min-w-full text-sm">
            <thead class="bg-stone-50 text-stone-600 text-xs uppercase tracking-wide">
              <tr>
                <th class="px-3 py-2.5 text-left">{{ t('thinkingCoins.admin.slug') }}</th>
                <th class="px-3 py-2.5 text-left">{{ t('thinkingCoins.admin.tasksTitle') }}</th>
                <th class="px-3 py-2.5 text-left">{{ t('thinkingCoins.admin.reward') }}</th>
                <th class="px-3 py-2.5 text-left">{{ t('thinkingCoins.admin.monthlyCap') }}</th>
                <th class="px-3 py-2.5 text-left">{{ t('thinkingCoins.admin.handler') }}</th>
                <th class="px-3 py-2.5 text-left">{{ t('thinkingCoins.admin.sortOrder') }}</th>
                <th class="px-3 py-2.5 text-left">{{ t('thinkingCoins.admin.active') }}</th>
                <th class="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="task in tasks"
                :key="task.id"
                class="border-t border-stone-100 hover:bg-stone-50/80"
              >
                <td class="px-3 py-2 font-mono text-xs text-stone-500">
                  {{ task.slug }}
                  <span
                    v-if="task.is_system"
                    class="ml-1 rounded bg-stone-100 px-1 py-0.5 text-[10px] text-stone-500"
                  >
                    {{ t('thinkingCoins.admin.systemTask') }}
                  </span>
                </td>
                <td class="px-3 py-2">
                  <input
                    v-model="task.title"
                    type="text"
                    class="w-full min-w-[8rem] rounded border border-stone-200 px-2 py-1 text-sm"
                  >
                </td>
                <td class="px-3 py-2">
                  <input
                    v-model.number="task.reward_amount"
                    type="number"
                    min="0"
                    class="w-20 rounded border border-stone-200 px-2 py-1"
                  >
                </td>
                <td class="px-3 py-2">
                  <input
                    v-model.number="task.monthly_cap"
                    type="number"
                    min="0"
                    placeholder="—"
                    class="w-20 rounded border border-stone-200 px-2 py-1"
                  >
                </td>
                <td class="px-3 py-2 text-xs text-stone-500 whitespace-nowrap">
                  {{ handlerLabel(task.handler_key) }}
                </td>
                <td class="px-3 py-2">
                  <input
                    v-model.number="task.sort_order"
                    type="number"
                    class="w-16 rounded border border-stone-200 px-2 py-1"
                  >
                </td>
                <td class="px-3 py-2 text-center">
                  <input
                    v-model="task.is_active"
                    type="checkbox"
                    :disabled="task.slug === 'referral_register'"
                  >
                </td>
                <td class="px-3 py-2 whitespace-nowrap">
                  <button
                    type="button"
                    class="text-xs font-medium text-stone-700 hover:text-stone-900 disabled:opacity-40"
                    :disabled="savingTaskId === task.id"
                    @click="saveTaskRow(task)"
                  >
                    {{ t('thinkingCoins.admin.save') }}
                  </button>
                  <button
                    v-if="!task.is_system"
                    type="button"
                    class="ml-2 inline-flex text-stone-400 hover:text-red-600"
                    :title="t('thinkingCoins.admin.deleteTask')"
                    @click="confirmDeleteTask(task)"
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Settings -->
      <section v-else-if="panel === 'settings' && settings">
        <h3 class="swiss-stat-card-group__title mb-3">
          {{ t('thinkingCoins.admin.settingsTitle') }}
        </h3>
        <div class="rounded-xl border border-stone-200 bg-white p-4 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl">
          <label class="text-sm text-stone-700">
            {{ t('thinkingCoins.admin.signupGrant') }}
            <input
              v-model.number="settings.signup_grant"
              type="number"
              min="0"
              class="mt-1 block w-full rounded-lg border border-stone-200 px-3 py-2"
            >
          </label>
          <label class="text-sm text-stone-700">
            {{ t('thinkingCoins.admin.dailyEarnCap') }}
            <input
              v-model.number="settings.daily_earn_cap"
              type="number"
              min="0"
              class="mt-1 block w-full rounded-lg border border-stone-200 px-3 py-2"
            >
            <span class="mt-1 block text-xs text-stone-500">
              {{ t('thinkingCoins.admin.dailyEarnCapHint') }}
            </span>
          </label>
          <label class="text-sm text-stone-700">
            {{ t('thinkingCoins.admin.costMindmate') }}
            <input
              v-model.number="settings.cost_mindmate_turn"
              type="number"
              min="0"
              class="mt-1 block w-full rounded-lg border border-stone-200 px-3 py-2"
            >
          </label>
          <label class="text-sm text-stone-700">
            {{ t('thinkingCoins.admin.costDiagram') }}
            <input
              v-model.number="settings.cost_diagram_gen"
              type="number"
              min="0"
              class="mt-1 block w-full rounded-lg border border-stone-200 px-3 py-2"
            >
          </label>
          <label class="text-sm text-stone-700">
            {{ t('thinkingCoins.admin.costCanvas') }}
            <input
              v-model.number="settings.cost_canvas_assist"
              type="number"
              min="0"
              class="mt-1 block w-full rounded-lg border border-stone-200 px-3 py-2"
            >
          </label>
        </div>
        <button
          type="button"
          class="mt-4 rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          :disabled="savingSettings"
          @click="saveSettings"
        >
          {{ t('thinkingCoins.admin.save') }}
        </button>
      </section>

      <!-- Preview -->
      <section v-else-if="panel === 'preview'">
        <h3 class="swiss-stat-card-group__title mb-3">
          {{ t('thinkingCoins.admin.previewTitle') }}
        </h3>
        <div class="flex flex-wrap gap-2">
          <div
            v-for="task in activePreviewTasks"
            :key="`preview-${task.id}`"
            class="rounded-xl border border-amber-100 bg-gradient-to-br from-amber-50 to-orange-50 px-4 py-3 text-sm min-w-[10rem]"
          >
            <div class="font-medium text-stone-800">{{ task.title }}</div>
            <div class="text-xs text-stone-500 mt-0.5">{{ handlerLabel(task.handler_key) }}</div>
            <div class="mt-1 font-semibold text-amber-700">+{{ task.reward_amount }}</div>
          </div>
        </div>
      </section>
    </template>

    <el-dialog
      v-model="showCreateDialog"
      :title="t('thinkingCoins.admin.createTaskTitle')"
      width="480px"
      destroy-on-close
      @closed="resetCreateForm"
    >
      <div class="space-y-3 text-sm">
        <label class="block">
          {{ t('thinkingCoins.admin.slug') }}
          <input
            v-model="createForm.slug"
            type="text"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2 font-mono text-sm"
            placeholder="my_custom_task"
          >
        </label>
        <label class="block">
          {{ t('thinkingCoins.admin.tasksTitle') }}
          <input
            v-model="createForm.title"
            type="text"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2"
          >
        </label>
        <label class="block">
          {{ t('thinkingCoins.admin.reward') }}
          <input
            v-model.number="createForm.reward_amount"
            type="number"
            min="0"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2"
          >
        </label>
        <label class="block">
          {{ t('thinkingCoins.admin.handler') }}
          <select
            v-model="createForm.handler_key"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2 bg-white"
          >
            <option
              v-for="opt in handlerOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </label>
        <label
          v-if="createForm.handler_key === 'usage_daily'"
          class="block"
        >
          {{ t('thinkingCoins.admin.requestType') }}
          <input
            :value="String(createForm.action_config?.request_type ?? 'mindmate')"
            type="text"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2 font-mono text-sm"
            @input="createForm.action_config = { request_type: ($event.target as HTMLInputElement).value }"
          >
        </label>
        <label
          v-if="createForm.handler_key === 'client_event'"
          class="block"
        >
          {{ t('thinkingCoins.admin.eventKey') }}
          <input
            :value="String(createForm.action_config?.event_key ?? '')"
            type="text"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2 font-mono text-sm"
            @input="createForm.action_config = { event_key: ($event.target as HTMLInputElement).value }"
          >
        </label>
        <label
          v-if="createForm.handler_key === 'navigate'"
          class="block"
        >
          {{ t('thinkingCoins.admin.route') }}
          <input
            :value="String(createForm.action_config?.route ?? '/community')"
            type="text"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2 font-mono text-sm"
            @input="createForm.action_config = { route: ($event.target as HTMLInputElement).value }"
          >
        </label>
        <label class="block">
          {{ t('thinkingCoins.admin.sortOrder') }}
          <input
            v-model.number="createForm.sort_order"
            type="number"
            class="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2"
          >
        </label>
      </div>
      <template #footer>
        <button
          type="button"
          class="rounded-lg border border-stone-200 px-4 py-2 text-sm text-stone-600 hover:bg-stone-50"
          @click="showCreateDialog = false"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="ml-2 rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800"
          @click="submitCreateTask"
        >
          {{ t('thinkingCoins.admin.save') }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>
