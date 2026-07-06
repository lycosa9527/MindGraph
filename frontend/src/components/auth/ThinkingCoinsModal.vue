<script setup lang="ts">
/**
 * ThinkingCoinsModal — wallet balance, earn tasks, ledger, subscription reference.
 * Design: Swiss grid + bold typography with Bauhaus-inspired color blocks.
 */
import { computed, ref, watch } from 'vue'

import {
  Calendar,
  Camera,
  Check,
  ChevronDown,
  ChevronRight,
  Coins,
  Download,
  FileText,
  Hammer,
  Languages,
  Share2,
  Sparkles,
  Star,
  Users,
  X,
} from '@lucide/vue'

import { useLanguage } from '@/composables'
import { formatThinkingCoinBalance, useThinkingCoins } from '@/composables/auth/useThinkingCoins'
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

const PERSONAL_TIERS = ['trial', 'monthly', 'sub', 'annual'] as const

type TaskTheme = {
  card: string
  iconWrap: string
  icon: string
  reward: string
}

type TierTheme = {
  stripe: string
  ring: string
}

const props = defineProps<{
  visible: boolean
  initialTab?: 'wallet' | 'subscription'
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t } = useLanguage()
const {
  wallet,
  ledger,
  loading,
  fetchWallet,
  fetchLedger,
  taskTitle,
  taskSubtitle,
  ledgerItemLabel,
  handleTaskClick,
} = useThinkingCoins()

const subscriptionTab = ref(false)
const subscriptionSectionRef = ref<HTMLElement | null>(null)
const ledgerOpen = ref(false)
const ledgerPage = ref(1)
const ledgerLoading = ref(false)
const LEDGER_PAGE_SIZE = 20

const TASK_THEMES: TaskTheme[] = [
  {
    card: 'bg-amber-50 border-amber-200',
    iconWrap: 'bg-amber-500',
    icon: 'text-white',
    reward: 'text-amber-800',
  },
  {
    card: 'bg-sky-50 border-sky-200',
    iconWrap: 'bg-sky-500',
    icon: 'text-white',
    reward: 'text-sky-800',
  },
  {
    card: 'bg-emerald-50 border-emerald-200',
    iconWrap: 'bg-emerald-500',
    icon: 'text-white',
    reward: 'text-emerald-800',
  },
  {
    card: 'bg-rose-50 border-rose-200',
    iconWrap: 'bg-rose-500',
    icon: 'text-white',
    reward: 'text-rose-800',
  },
  {
    card: 'bg-violet-50 border-violet-200',
    iconWrap: 'bg-violet-500',
    icon: 'text-white',
    reward: 'text-violet-800',
  },
]

const TIER_THEMES: Record<(typeof PERSONAL_TIERS)[number], TierTheme> = {
  trial: {
    stripe: 'tc-tier-stripe--stone',
    ring: 'border-stone-200',
  },
  monthly: {
    stripe: 'tc-tier-stripe--amber',
    ring: 'border-amber-200',
  },
  sub: {
    stripe: 'tc-tier-stripe--rose',
    ring: 'border-rose-200',
  },
  annual: {
    stripe: 'tc-tier-stripe--emerald',
    ring: 'border-emerald-200',
  },
}

const ledgerHasMore = computed(() => {
  if (!ledger.value) {
    return false
  }
  return ledger.value.items.length < ledger.value.total
})

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const balanceText = computed(() =>
  formatThinkingCoinBalance(wallet.value?.balance ?? 0)
)

const earnTasks = computed(() => wallet.value?.earn_tasks ?? [])

function taskTheme(index: number): TaskTheme {
  return TASK_THEMES[index % TASK_THEMES.length]
}

function taskIcon(slug: string) {
  if (slug.includes('checkin')) return Calendar
  if (slug.includes('share')) return Share2
  if (slug.includes('export')) return Download
  if (slug.includes('translate')) return Languages
  if (slug.includes('snapshot')) return Camera
  if (slug.includes('workshop')) return Users
  if (slug.includes('learning_sheet')) return Hammer
  if (slug.includes('mindmate')) return Sparkles
  if (slug.includes('diagram')) return Sparkles
  return FileText
}

function taskStatusHint(task: ThinkingCoinEarnTask): string {
  if (task.completed_today && task.handler_key === 'auto_login') {
    return t('thinkingCoins.checkedInToday')
  }
  if (task.completed_today && task.handler_key === 'usage_daily') {
    return t('thinkingCoins.usageDoneToday')
  }
  if (task.completed_today && task.handler_key === 'client_event') {
    return t('thinkingCoins.usageDoneToday')
  }
  if (task.coming_soon || task.slug === 'publish_case') {
    return t('thinkingCoins.comingSoon')
  }
  return task.status_hint ?? ''
}

function taskIsActionable(task: ThinkingCoinEarnTask): boolean {
  if (task.coming_soon || task.slug === 'publish_case') {
    return false
  }
  if (task.handler_key === 'navigate') {
    return true
  }
  if (task.handler_key === 'auto_login') {
    return !task.completed_today
  }
  if (task.handler_key === 'usage_daily') {
    return false
  }
  return false
}

function tierLabel(tier: (typeof PERSONAL_TIERS)[number]): string {
  return t(`thinkingCoins.tier.${tier}`)
}

function tierTheme(tier: (typeof PERSONAL_TIERS)[number]): TierTheme {
  return TIER_THEMES[tier]
}

async function loadData() {
  await fetchWallet()
  if (ledgerOpen.value) {
    await fetchLedger(ledgerPage.value)
  }
}

watch(
  () => props.visible,
  (open) => {
    if (open) {
      subscriptionTab.value = false
      void loadData().then(() => {
        if (props.initialTab === 'subscription' && subscriptionSectionRef.value) {
          subscriptionSectionRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      })
    }
  }
)

watch(ledgerOpen, (open) => {
  if (open && props.visible) {
    ledgerPage.value = 1
    void fetchLedger(1, LEDGER_PAGE_SIZE, false)
  }
})

async function loadMoreLedger(): Promise<void> {
  if (ledgerLoading.value || !ledgerHasMore.value) {
    return
  }
  ledgerLoading.value = true
  try {
    ledgerPage.value += 1
    await fetchLedger(ledgerPage.value, LEDGER_PAGE_SIZE, true)
  } finally {
    ledgerLoading.value = false
  }
}

function closeModal() {
  isVisible.value = false
}

function onUpgradeClick() {
  subscriptionTab.value = true
  subscriptionSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="fixed inset-0 z-[2000] flex items-center justify-center p-4"
    >
      <div
        class="absolute inset-0 bg-stone-900/45 backdrop-blur-[2px]"
        @click="closeModal"
      />

      <div
        class="tc-modal relative z-10 flex w-full max-w-2xl max-h-[90vh] flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        :aria-label="t('thinkingCoins.title')"
      >
        <div class="tc-modal-stripe shrink-0" aria-hidden="true" />

        <div class="tc-modal-header shrink-0 flex items-center justify-between border-b border-stone-100 px-6 py-4">
          <div class="flex items-center gap-3 min-w-0">
            <div class="tc-modal-icon-wrap shrink-0">
              <Coins class="h-5 w-5 text-amber-700" />
            </div>
            <h2 class="text-base font-semibold tracking-tight text-stone-900 truncate">
              {{ t('thinkingCoins.title') }}
            </h2>
          </div>
          <button
            type="button"
            class="rounded-lg p-1.5 text-stone-400 transition hover:bg-stone-100 hover:text-stone-700"
            :aria-label="t('common.close')"
            @click="closeModal"
          >
            <X class="h-5 w-5" />
          </button>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto">
          <div
            v-if="loading && !wallet"
            class="p-10 text-center text-sm text-stone-500"
          >
            …
          </div>

          <template v-else-if="wallet?.eligible">
            <section class="border-b border-stone-100 px-6 py-5">
              <div class="tc-balance-hero rounded-xl border border-stone-200 bg-stone-50 p-5">
                <div class="flex items-end justify-between gap-4">
                  <div class="min-w-0">
                    <p class="text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-500">
                      {{ t('thinkingCoins.balanceUnit') }}
                    </p>
                    <p class="mt-1 text-4xl font-bold tabular-nums tracking-tight text-stone-900">
                      {{ balanceText }}
                    </p>
                  </div>
                  <button
                    type="button"
                    class="tc-upgrade-btn shrink-0"
                    @click="onUpgradeClick"
                  >
                    <Star class="h-3.5 w-3.5 fill-current" />
                    {{ t('thinkingCoins.upgrade') }}
                  </button>
                </div>
              </div>

              <h3 class="mt-5 mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-500">
                {{ t('thinkingCoins.earnMore') }}
              </h3>

              <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <button
                  v-for="(task, index) in earnTasks"
                  :key="task.id"
                  type="button"
                  class="tc-task-card flex items-center gap-3 rounded-xl border p-3 text-left transition"
                  :class="[
                    taskTheme(index).card,
                    taskIsActionable(task)
                      ? 'hover:-translate-y-px hover:shadow-md cursor-pointer'
                      : 'opacity-90 cursor-default',
                  ]"
                  :disabled="!taskIsActionable(task)"
                  @click="taskIsActionable(task) && handleTaskClick(task)"
                >
                  <div
                    class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                    :class="taskTheme(index).iconWrap"
                  >
                    <component
                      :is="taskIcon(task.slug)"
                      class="h-5 w-5"
                      :class="taskTheme(index).icon"
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-semibold text-stone-800">
                      {{ taskTitle(task) }}
                    </div>
                    <div class="truncate text-xs text-stone-500">
                      {{ taskSubtitle(task) }}
                    </div>
                    <div
                      v-if="taskStatusHint(task)"
                      class="mt-0.5 text-xs text-stone-400"
                    >
                      {{ taskStatusHint(task) }}
                    </div>
                  </div>
                  <div class="flex shrink-0 items-center gap-1">
                    <Check
                      v-if="task.completed_today"
                      class="h-4 w-4 text-emerald-600"
                    />
                    <span
                      class="text-sm font-bold tabular-nums"
                      :class="taskTheme(index).reward"
                    >
                      +{{ task.reward_amount }}
                    </span>
                  </div>
                </button>
              </div>

              <button
                type="button"
                class="mt-4 flex w-full items-center gap-2 rounded-lg border border-stone-200 px-3 py-2 text-sm font-medium text-stone-600 transition hover:border-stone-300 hover:bg-stone-50 hover:text-stone-800"
                @click="ledgerOpen = !ledgerOpen"
              >
                <component
                  :is="ledgerOpen ? ChevronDown : ChevronRight"
                  class="h-4 w-4 shrink-0 text-stone-400"
                />
                <span>{{ t('thinkingCoins.ledgerTitle') }}</span>
              </button>

              <div
                v-if="ledgerOpen"
                class="mt-2 overflow-hidden rounded-xl border border-stone-200 bg-white"
              >
                <div
                  v-if="!ledger?.items.length"
                  class="py-8 text-center text-sm text-stone-400"
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
                    class="flex items-center justify-between gap-3 px-4 py-2.5 text-sm"
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
                  class="w-full border-t border-stone-100 py-2.5 text-xs font-medium text-stone-600 transition hover:bg-stone-50 disabled:opacity-50"
                  :disabled="ledgerLoading"
                  @click="loadMoreLedger"
                >
                  {{ ledgerLoading ? t('thinkingCoins.ledgerLoading') : t('thinkingCoins.ledgerLoadMore') }}
                </button>
              </div>
            </section>

            <section
              ref="subscriptionSectionRef"
              class="px-6 py-5"
            >
              <h3 class="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-500">
                {{ t('thinkingCoins.subscriptionRef') }}
              </h3>

              <div class="mb-4 inline-flex rounded-full border border-stone-200 bg-stone-50 p-0.5">
                <button
                  type="button"
                  class="rounded-full px-4 py-1.5 text-sm font-medium transition"
                  :class="
                    !subscriptionTab
                      ? 'bg-stone-900 text-white shadow-sm'
                      : 'text-stone-600 hover:text-stone-900'
                  "
                  @click="subscriptionTab = false"
                >
                  {{ t('thinkingCoins.personalTab') }}
                </button>
                <button
                  type="button"
                  class="rounded-full px-4 py-1.5 text-sm font-medium transition"
                  :class="
                    subscriptionTab
                      ? 'bg-stone-900 text-white shadow-sm'
                      : 'text-stone-600 hover:text-stone-900'
                  "
                  @click="subscriptionTab = true"
                >
                  {{ t('thinkingCoins.schoolTab') }}
                </button>
              </div>

              <div
                v-if="!subscriptionTab"
                class="grid grid-cols-1 gap-3 sm:grid-cols-2"
              >
                <div
                  v-for="tier in PERSONAL_TIERS"
                  :key="tier"
                  class="tc-tier-card overflow-hidden rounded-xl border bg-white"
                  :class="tierTheme(tier).ring"
                >
                  <div
                    class="tc-tier-stripe h-1.5"
                    :class="tierTheme(tier).stripe"
                  />
                  <div class="p-4">
                    <div class="mb-2 text-sm font-semibold text-stone-800">
                      {{ tierLabel(tier) }}
                    </div>
                    <div class="mb-2 text-xl font-bold text-stone-400 blur-[6px] select-none">
                      ¥ ··
                    </div>
                    <div class="mb-3 text-xs text-stone-500">
                      {{ t('thinkingCoins.pricePending') }}
                    </div>
                    <button
                      type="button"
                      disabled
                      class="w-full cursor-not-allowed rounded-lg border border-stone-200 py-2 text-xs font-medium text-stone-400"
                    >
                      {{ t('thinkingCoins.comingSoon') }}
                    </button>
                  </div>
                </div>
              </div>

              <div
                v-else
                class="rounded-xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm leading-relaxed text-sky-900"
              >
                {{ t('thinkingCoins.schoolInfo') }}
              </div>
            </section>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.tc-modal-stripe {
  height: 4px;
  background: linear-gradient(
    90deg,
    #ef4444 0%,
    #ef4444 25%,
    #f59e0b 25%,
    #f59e0b 50%,
    #3b82f6 50%,
    #3b82f6 75%,
    #1c1917 75%,
    #1c1917 100%
  );
}

.tc-modal-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.625rem;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 1px solid #fde68a;
}

.tc-upgrade-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 9999px;
  padding: 0.5rem 1rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%);
  box-shadow: 0 1px 2px rgba(234, 88, 12, 0.25);
  transition:
    transform 0.12s ease,
    box-shadow 0.12s ease;
}

.tc-upgrade-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(234, 88, 12, 0.28);
}

.tc-tier-stripe--stone {
  background: #78716c;
}

.tc-tier-stripe--amber {
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
}

.tc-tier-stripe--rose {
  background: linear-gradient(90deg, #f43f5e, #fb7185);
}

.tc-tier-stripe--emerald {
  background: linear-gradient(90deg, #10b981, #34d399);
}
</style>
