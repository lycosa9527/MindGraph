<script setup lang="ts">
/**
 * Personal vs school subscription reference tabs on the thinking-coins upgrade page.
 */
import { computed, nextTick, ref } from 'vue'

import { Crown } from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import ThinkingCoinsSchoolSubscriptionPanel from '@/components/auth/ThinkingCoinsSchoolSubscriptionPanel.vue'
import { useLanguage } from '@/composables'
import {
  PERSONAL_PLAN_TIERS,
  type PersonalPlanTier,
  planBadgeKeys,
  planFeatureKeys,
} from '@/composables/auth/thinkingCoinsUpgradeUi'

type SubscriptionPlanTab = 'personal' | 'school'

const { t } = useLanguage()

const subscriptionTab = ref<SubscriptionPlanTab>('personal')
const rootRef = ref<HTMLElement | null>(null)

const subscriptionTabOptions = computed(() => [
  { label: t('thinkingCoins.personalTab'), value: 'personal' as const },
  { label: t('thinkingCoins.schoolTab'), value: 'school' as const },
])

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
  return 'tc-plan-card border-stone-200'
}

async function focusSchoolTab(): Promise<void> {
  subscriptionTab.value = 'school'
  await nextTick()
  rootRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

defineExpose({ focusSchoolTab })
</script>

<template>
  <section
    ref="rootRef"
    class="tc-upgrade-card"
  >
    <div class="tc-subscription-header flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
      <h2 class="text-base font-semibold text-stone-900 sm:text-lg">
        {{ t('thinkingCoins.subscriptionRef') }}
      </h2>

      <AdminSwissSegmented
        v-model="subscriptionTab"
        class="tc-subscription-seg shrink-0"
        equal
        fit
        :options="subscriptionTabOptions"
        :aria-label="t('thinkingCoins.subscriptionRef')"
      />
    </div>

    <div
      v-if="subscriptionTab === 'personal'"
      class="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4"
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

    <ThinkingCoinsSchoolSubscriptionPanel
      v-else
      class="mt-5"
    />
  </section>
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

.tc-subscription-seg {
  border-radius: 0.5rem;
}

.tc-subscription-seg :deep(.admin-swiss-segment) {
  min-height: 1.75rem;
  padding: 0.3125rem 0.625rem;
  font-size: 0.75rem;
}

.tc-plan-card--popular {
  padding-top: 1.75rem;
}
</style>
