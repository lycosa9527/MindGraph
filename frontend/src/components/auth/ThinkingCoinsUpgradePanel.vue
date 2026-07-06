<script setup lang="ts">
/**
 * Thinking-coins upgrade landing content: wallet, earn tasks, ledger, subscription plans.
 */
import { computed, nextTick, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Check, ChevronDown, ChevronRight, Gift } from '@lucide/vue'

import ThinkingCoinsSubscriptionSection from '@/components/auth/ThinkingCoinsSubscriptionSection.vue'
import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { formatThinkingCoinBalance, useThinkingCoins } from '@/composables/auth/useThinkingCoins'
import {
  buildUpgradePageTaskCards,
  taskIcon,
  taskIsActionable,
  taskTheme,
  type UpgradePageTaskCard,
} from '@/composables/auth/thinkingCoinsUpgradeUi'
import { useAuthStore } from '@/stores'
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

const { t } = useLanguage()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const {
  wallet,
  ledger,
  loading,
  fetchWallet,
  fetchLedger,
  taskTitle,
  ledgerItemLabel,
  handleTaskClick,
} = useThinkingCoins()

const tasksOpen = ref(false)
const ledgerOpen = ref(false)
const ledgerPage = ref(1)
const ledgerLoading = ref(false)
const subscriptionSectionRef = ref<InstanceType<typeof ThinkingCoinsSubscriptionSection> | null>(
  null
)
const LEDGER_PAGE_SIZE = 20

const balanceText = computed(() =>
  formatThinkingCoinBalance(
    wallet.value?.balance ?? authStore.user?.thinkingCoins?.balance ?? 0
  )
)
const isWalletEligible = computed(
  () =>
    wallet.value?.eligible === true || authStore.user?.thinkingCoins?.eligible === true
)
const earnTasks = computed(() => wallet.value?.earn_tasks ?? [])

const COLLAPSED_TASK_PREVIEW_COUNT = 3

const taskCards = computed(() => buildUpgradePageTaskCards(earnTasks.value))

const previewTaskCards = computed(() =>
  taskCards.value.slice(0, COLLAPSED_TASK_PREVIEW_COUNT)
)

function previewCardTitle(card: UpgradePageTaskCard): string {
  if (card.kind === 'task') {
    return taskTitle(card.task)
  }
  return t(card.titleKey)
}

function previewCardReward(card: UpgradePageTaskCard): number {
  if (card.kind === 'task') {
    return card.task.reward_amount
  }
  return card.rewardAmount
}

const ledgerHasMore = computed(() => {
  if (!ledger.value) {
    return false
  }
  return ledger.value.items.length < ledger.value.total
})

function taskStatusHint(task: ThinkingCoinEarnTask): string {
  if (task.completed_today && task.handler_key === 'auto_login') {
    return t('thinkingCoins.checkedInToday')
  }
  if (task.completed_today) {
    return t('thinkingCoins.usageDoneToday')
  }
  if (task.coming_soon || task.slug === 'publish_case') {
    return t('thinkingCoins.comingSoon')
  }
  return task.status_hint ?? ''
}

async function loadWallet() {
  await fetchWallet()
}

async function loadLedgerPage(page: number, append: boolean) {
  await fetchLedger(page, LEDGER_PAGE_SIZE, append)
}

async function toggleLedger() {
  ledgerOpen.value = !ledgerOpen.value
  if (ledgerOpen.value && !ledger.value?.items.length) {
    ledgerPage.value = 1
    await loadLedgerPage(1, false)
  }
}

async function loadMoreLedger() {
  if (ledgerLoading.value || !ledgerHasMore.value) {
    return
  }
  ledgerLoading.value = true
  try {
    ledgerPage.value += 1
    await loadLedgerPage(ledgerPage.value, true)
  } finally {
    ledgerLoading.value = false
  }
}

async function focusSchoolSubscription(): Promise<void> {
  await nextTick()
  await subscriptionSectionRef.value?.focusSchoolTab()
}

function clearSchoolTabQuery(): void {
  if (route.query.tab !== 'school') {
    return
  }
  const nextQuery = { ...route.query }
  delete nextQuery.tab
  void router.replace({ query: nextQuery })
}

async function handleSchoolFocusRequest(): Promise<void> {
  await focusSchoolSubscription()
  clearSchoolTabQuery()
}

watch(
  () => route.query.tab,
  (tab) => {
    if (tab === 'school' && route.path === '/thinking-coins/upgrade') {
      void handleSchoolFocusRequest()
    }
  },
  { immediate: true }
)

const offFocusSchool = eventBus.on('thinking_coins:focus_school', () => {
  if (route.path === '/thinking-coins/upgrade') {
    void focusSchoolSubscription()
  }
})

onScopeDispose(offFocusSchool)

onMounted(() => {
  void loadWallet()
})
</script>

<template>
  <div class="tc-upgrade-panel mx-auto w-full max-w-6xl space-y-5 px-4 pb-6 pt-3 sm:px-6 sm:pb-8 sm:pt-4">
    <section class="tc-upgrade-card">
      <h2 class="text-base font-semibold text-stone-900 sm:text-lg">
        {{ t('thinkingCoins.title') }}
      </h2>

      <div
        v-if="loading && !wallet"
        class="py-10 text-center text-sm text-stone-500"
      >
        …
      </div>

      <template v-else-if="isWalletEligible">
        <div class="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span class="text-4xl font-bold tabular-nums tracking-tight text-stone-900 sm:text-5xl">
            {{ balanceText }}
          </span>
          <span class="text-base font-medium text-stone-500">
            {{ t('thinkingCoins.balanceUnit') }}
          </span>
        </div>

        <button
          type="button"
          class="mt-5 flex w-full items-center justify-between gap-3 rounded-xl border border-stone-100 bg-stone-50/80 px-3.5 py-2.5 text-left transition hover:bg-stone-50"
          @click="tasksOpen = !tasksOpen"
        >
          <span class="flex items-center gap-2 text-sm font-medium text-stone-700">
            <component
              :is="tasksOpen ? ChevronDown : ChevronRight"
              class="h-4 w-4 text-stone-400"
            />
            {{ t('thinkingCoins.earnMore') }}
          </span>
          <span
            v-if="!tasksOpen && taskCards.length > COLLAPSED_TASK_PREVIEW_COUNT"
            class="text-xs text-stone-400"
          >
            {{ t('thinkingCoins.tasksExpandHint') }}
          </span>
        </button>

        <button
          v-if="!tasksOpen && previewTaskCards.length"
          type="button"
          class="tc-task-preview-row mt-2 flex w-full gap-2"
          @click="tasksOpen = true"
        >
          <div
            v-for="card in previewTaskCards"
            :key="card.key"
            class="tc-task-preview flex min-w-0 flex-1 items-center gap-1.5 rounded-xl border px-2 py-2"
            :class="taskTheme(card.themeIndex).card"
          >
            <div
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
              :class="taskTheme(card.themeIndex).iconWrap"
            >
              <component
                :is="card.kind === 'task' ? taskIcon(card.task.slug) : Gift"
                class="h-3.5 w-3.5"
              />
            </div>
            <div class="min-w-0 flex-1 truncate text-[11px] font-medium leading-tight text-stone-700">
              {{ previewCardTitle(card) }}
            </div>
            <Check
              v-if="card.kind === 'task' && card.task.completed_today"
              class="h-3 w-3 shrink-0 text-emerald-600"
            />
            <span
              class="shrink-0 text-[11px] font-bold tabular-nums leading-tight"
              :class="taskTheme(card.themeIndex).reward"
            >
              +{{ previewCardReward(card) }}
            </span>
          </div>
        </button>

        <div
          v-if="tasksOpen && taskCards.length"
          class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          <template
            v-for="card in taskCards"
            :key="card.key"
          >
            <button
              v-if="card.kind === 'task'"
              type="button"
              class="tc-task-card flex items-center gap-3 rounded-2xl border p-4 text-left transition hover:-translate-y-px hover:shadow-md"
              :class="[
                taskTheme(card.themeIndex).card,
                taskIsActionable(card.task) ? 'cursor-pointer' : 'cursor-default',
              ]"
              @click="taskIsActionable(card.task) && handleTaskClick(card.task)"
            >
              <div
                class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
                :class="taskTheme(card.themeIndex).iconWrap"
              >
                <component
                  :is="taskIcon(card.task.slug)"
                  class="h-5 w-5"
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-stone-500">
                  {{ taskTitle(card.task) }}
                </div>
                <div
                  class="mt-0.5 text-sm font-bold tabular-nums"
                  :class="taskTheme(card.themeIndex).reward"
                >
                  +{{ card.task.reward_amount }}
                  {{ t('thinkingCoins.balanceUnit') }}
                </div>
                <div
                  v-if="taskStatusHint(card.task)"
                  class="mt-0.5 text-xs text-stone-500"
                >
                  {{ taskStatusHint(card.task) }}
                </div>
              </div>
              <Check
                v-if="card.task.completed_today"
                class="h-4 w-4 shrink-0 text-emerald-600"
              />
            </button>

            <div
              v-else
              class="tc-task-card flex items-center gap-3 rounded-2xl border p-4 transition hover:-translate-y-px hover:shadow-md"
              :class="taskTheme(card.themeIndex).card"
            >
              <div
                class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl"
                :class="taskTheme(card.themeIndex).iconWrap"
              >
                <Gift class="h-5 w-5" />
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-stone-500">
                  {{ t(card.titleKey) }}
                </div>
                <div
                  class="mt-0.5 text-sm font-bold tabular-nums"
                  :class="taskTheme(card.themeIndex).reward"
                >
                  +{{ card.rewardAmount }}
                  {{ t('thinkingCoins.balanceUnit') }}
                </div>
              </div>
            </div>
          </template>
        </div>

        <button
          type="button"
          class="mt-5 flex w-full items-center justify-between gap-3 rounded-xl border border-stone-100 bg-stone-50/80 px-3.5 py-2.5 text-left transition hover:bg-stone-50"
          @click="toggleLedger"
        >
          <span class="flex items-center gap-2 text-sm font-medium text-stone-700">
            <component
              :is="ledgerOpen ? ChevronDown : ChevronRight"
              class="h-4 w-4 text-stone-400"
            />
            {{ t('thinkingCoins.ledgerTitle') }}
          </span>
          <span
            v-if="!ledgerOpen"
            class="text-xs text-rose-500"
          >
            {{ t('thinkingCoins.ledgerExpandHint') }}
          </span>
        </button>

        <div
          v-if="ledgerOpen"
          class="mt-2 overflow-hidden rounded-xl border border-stone-200 bg-white"
        >
          <div
            v-if="!ledger?.items.length"
            class="py-10 text-center text-sm text-stone-400"
          >
            {{ t('thinkingCoins.ledgerEmpty') }}
          </div>
          <ul
            v-else
            class="divide-y divide-stone-100"
          >
            <li
              v-for="item in ledger.items"
              :key="item.id"
              class="flex items-center justify-between gap-3 px-4 py-3 text-sm"
            >
              <span class="truncate text-stone-600">{{ ledgerItemLabel(item) }}</span>
              <span
                class="shrink-0 font-semibold tabular-nums"
                :class="item.delta >= 0 ? 'text-emerald-600' : 'text-stone-800'"
              >
                {{ item.delta >= 0 ? '+' : '' }}{{ item.delta }}
              </span>
            </li>
          </ul>
          <button
            v-if="ledgerHasMore"
            type="button"
            class="w-full border-t border-stone-100 py-3 text-xs font-medium text-stone-600 hover:bg-stone-50 disabled:opacity-50"
            :disabled="ledgerLoading"
            @click="loadMoreLedger"
          >
            {{ ledgerLoading ? t('thinkingCoins.ledgerLoading') : t('thinkingCoins.ledgerLoadMore') }}
          </button>
        </div>
      </template>
    </section>

    <ThinkingCoinsSubscriptionSection
      v-if="isWalletEligible"
      ref="subscriptionSectionRef"
    />
  </div>
</template>

<style scoped>
.tc-upgrade-card {
  border-radius: 1.25rem;
  background: #ffffff;
  padding: 1rem 1.25rem 1.25rem;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 8px 24px rgba(28, 25, 23, 0.06);
}

@media (min-width: 640px) {
  .tc-upgrade-card {
    padding: 1.125rem 1.5rem 1.5rem;
  }
}

.tc-task-preview-row {
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}

.tc-task-preview-row:focus-visible {
  outline: 2px solid #d6d3d1;
  outline-offset: 2px;
  border-radius: 0.75rem;
}

.tc-task-preview {
  pointer-events: none;
}
</style>
