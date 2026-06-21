<script setup lang="ts">
/**
 * Thinking-coins upgrade landing content: wallet, earn tasks, subscription plans.
 */
import { computed, onMounted, ref } from 'vue'

import { Check, ChevronDown, ChevronRight, Crown, Gift } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { formatThinkingCoinBalance, useThinkingCoins } from '@/composables/auth/useThinkingCoins'
import {
  PERSONAL_PLAN_TIERS,
  type PersonalPlanTier,
  buildUpgradePageTaskCards,
  planBadgeKeys,
  planFeatureKeys,
  taskIcon,
  taskIsActionable,
  taskTheme,
} from '@/composables/auth/thinkingCoinsUpgradeUi'
import { useAuthStore } from '@/stores'
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

const { t } = useLanguage()
const authStore = useAuthStore()
const {
  wallet,
  ledger,
  loading,
  fetchWallet,
  fetchLedger,
  taskTitle,
  handleTaskClick,
} = useThinkingCoins()

const subscriptionTab = ref(false)
const showSubscriptionRef = false
const ledgerOpen = ref(false)
const ledgerPage = ref(1)
const ledgerLoading = ref(false)
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

const taskCards = computed(() => buildUpgradePageTaskCards(earnTasks.value))

const ledgerHasMore = computed(() => {
  if (!ledger.value) {
    return false
  }
  return ledger.value.items.length < ledger.value.total
})

function reasonLabel(reason: string): string {
  const key = `thinkingCoins.reason.${reason}`
  const translated = t(key)
  return translated === key ? reason : translated
}

function taskStatusHint(task: ThinkingCoinEarnTask): string {
  if (task.completed_today && task.handler_key === 'auto_login') {
    return t('thinkingCoins.checkedInToday')
  }
  if (task.completed_today) {
    return t('thinkingCoins.usageDoneToday')
  }
  if (task.slug === 'publish_case') {
    return t('thinkingCoins.casePendingHint')
  }
  return task.status_hint ?? ''
}

function tierLabel(tier: PersonalPlanTier): string {
  return t(`thinkingCoins.tier.${tier}`)
}

function planPrice(tier: PersonalPlanTier): string {
  if (tier === 'trial') {
    return t('thinkingCoins.plan.free')
  }
  if (tier === 'monthly') {
    return t('thinkingCoins.plan.priceMonthly')
  }
  if (tier === 'sub') {
    return t('thinkingCoins.plan.priceSub')
  }
  return t('thinkingCoins.plan.priceAnnual')
}

function planPriceNote(tier: PersonalPlanTier): string {
  if (tier === 'sub') {
    return t('thinkingCoins.plan.priceSubNote')
  }
  if (tier === 'annual') {
    return t('thinkingCoins.plan.priceAnnualNote')
  }
  return ''
}

function planCardClass(tier: PersonalPlanTier): string {
  if (tier === 'sub') {
    return 'tc-plan-card tc-plan-card--popular border-amber-300 ring-1 ring-amber-200'
  }
  if (tier === 'trial') {
    return 'tc-plan-card border-stone-200'
  }
  return 'tc-plan-card border-stone-200'
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

onMounted(() => {
  void loadWallet()
})
</script>

<template>
  <div class="tc-upgrade-panel mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
    <section class="tc-upgrade-card">
      <h2 class="text-lg font-semibold text-stone-900">
        {{ t('thinkingCoins.title') }}
      </h2>

      <div
        v-if="loading && !wallet"
        class="py-16 text-center text-sm text-stone-500"
      >
        …
      </div>

      <template v-else-if="isWalletEligible">
        <div class="mt-4 flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span class="text-4xl font-bold tabular-nums tracking-tight text-stone-900 sm:text-5xl">
            {{ balanceText }}
          </span>
          <span class="text-base font-medium text-stone-500">
            {{ t('thinkingCoins.balanceUnit') }}
          </span>
        </div>

        <div
          v-if="taskCards.length"
          class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
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
          class="mt-6 flex w-full items-center justify-between gap-3 rounded-xl border border-stone-100 bg-stone-50/80 px-4 py-3 text-left transition hover:bg-stone-50"
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
              <span class="truncate text-stone-600">{{ reasonLabel(item.reason) }}</span>
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

    <section
      v-if="showSubscriptionRef"
      class="tc-upgrade-card"
    >
      <h2 class="text-lg font-semibold text-stone-900">
        {{ t('thinkingCoins.subscriptionRef') }}
      </h2>

      <div class="mt-4 flex gap-6 border-b border-stone-200">
        <button
          type="button"
          class="pb-3 text-sm font-medium transition"
          :class="
            !subscriptionTab
              ? 'border-b-2 border-stone-900 text-stone-900'
              : 'text-stone-500 hover:text-stone-800'
          "
          @click="subscriptionTab = false"
        >
          {{ t('thinkingCoins.personalTab') }}
        </button>
        <button
          type="button"
          class="pb-3 text-sm font-medium transition"
          :class="
            subscriptionTab
              ? 'border-b-2 border-stone-900 text-stone-900'
              : 'text-stone-500 hover:text-stone-800'
          "
          @click="subscriptionTab = true"
        >
          {{ t('thinkingCoins.schoolTab') }}
        </button>
      </div>

      <div
        v-if="!subscriptionTab"
        class="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
      >
        <div
          v-for="tier in PERSONAL_PLAN_TIERS"
          :key="tier"
          class="relative flex flex-col rounded-2xl border bg-white p-5"
          :class="planCardClass(tier)"
        >
          <span
            v-if="tier === 'sub'"
            class="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 px-3 py-0.5 text-xs font-semibold text-white"
          >
            {{ t('thinkingCoins.plan.popular') }}
          </span>

          <div class="mb-3 flex items-center gap-2">
            <Crown
              v-if="tier !== 'trial'"
              class="h-5 w-5 text-amber-500"
            />
            <h3 class="text-sm font-semibold text-stone-900">
              {{ tierLabel(tier) }}
            </h3>
          </div>

          <div
            class="mb-1 text-2xl font-bold tabular-nums tracking-tight"
            :class="tier === 'sub' ? 'text-orange-500' : 'text-stone-900'"
          >
            {{ planPrice(tier) }}
          </div>
          <p
            v-if="planPriceNote(tier)"
            class="mb-3 text-xs text-stone-500"
          >
            {{ planPriceNote(tier) }}
          </p>
          <div
            v-else
            class="mb-3 h-4"
          />

          <div
            v-if="planBadgeKeys(tier).length"
            class="mb-4 flex flex-wrap gap-2"
          >
            <span
              v-for="badgeKey in planBadgeKeys(tier)"
              :key="badgeKey"
              class="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-800"
            >
              {{ t(badgeKey) }}
            </span>
          </div>

          <ul class="mb-5 flex-1 space-y-2 text-xs leading-relaxed text-stone-600">
            <li
              v-for="featureKey in planFeatureKeys(tier)"
              :key="featureKey"
              class="flex gap-2"
            >
              <span class="text-stone-400">·</span>
              <span>{{ t(featureKey) }}</span>
            </li>
          </ul>

          <button
            type="button"
            class="w-full rounded-xl py-2.5 text-sm font-medium transition"
            :class="
              tier === 'trial'
                ? 'border border-stone-200 bg-stone-50 text-stone-500 cursor-default'
                : 'bg-stone-900 text-white opacity-60 cursor-not-allowed'
            "
            :disabled="true"
          >
            {{
              tier === 'trial'
                ? t('thinkingCoins.plan.currentPlan')
                : t('thinkingCoins.plan.subscribeNow')
            }}
          </button>
        </div>
      </div>

      <div
        v-else
        class="mt-6 rounded-2xl border border-sky-100 bg-sky-50 px-5 py-5 text-sm leading-relaxed text-sky-900"
      >
        {{ t('thinkingCoins.schoolInfo') }}
      </div>
    </section>
  </div>
</template>

<style scoped>
.tc-upgrade-card {
  border-radius: 1.25rem;
  background: #ffffff;
  padding: 1.5rem 1.75rem;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.04),
    0 8px 24px rgba(28, 25, 23, 0.06);
}

@media (min-width: 640px) {
  .tc-upgrade-card {
    padding: 1.75rem 2rem;
  }
}

.tc-plan-card--popular {
  padding-top: 1.75rem;
}
</style>
