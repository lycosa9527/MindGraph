/**
 * Shared UI helpers for thinking-coins upgrade page and modal.
 */
import type { Component } from 'vue'

import {
  Calendar,
  Camera,
  Download,
  FileText,
  Hammer,
  Languages,
  Share2,
  Sparkles,
  Users,
} from '@lucide/vue'

import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

import { buildSidebarPromoSlides } from '@/composables/sidebar/sidebarThinkingCoinTaskPromo'

export const UPGRADE_PAGE_INVITE_REWARD_DEFAULT = 100

export type UpgradePageTaskCard =
  | { key: string; kind: 'task'; task: ThinkingCoinEarnTask; themeIndex: number }
  | {
      key: string
      kind: 'invite'
      themeIndex: number
      rewardAmount: number
      titleKey: 'thinkingCoins.inviteRegister'
    }

/** All earn tasks from the wallet API, plus invite when referral is inactive. */
export function buildUpgradePageTaskCards(tasks: ThinkingCoinEarnTask[]): UpgradePageTaskCard[] {
  return buildSidebarPromoSlides(tasks).map((slide, themeIndex) => {
    if (slide.kind === 'task') {
      return { ...slide, themeIndex }
    }
    return {
      key: slide.key,
      kind: 'invite',
      themeIndex,
      rewardAmount: UPGRADE_PAGE_INVITE_REWARD_DEFAULT,
      titleKey: 'thinkingCoins.inviteRegister',
    }
  })
}

export const PERSONAL_PLAN_TIERS = ['trial', 'monthly', 'sub', 'annual'] as const

export type PersonalPlanTier = (typeof PERSONAL_PLAN_TIERS)[number]

export type TaskTheme = {
  card: string
  iconWrap: string
  icon: string
  reward: string
}

export const TASK_THEMES: TaskTheme[] = [
  {
    card: 'bg-amber-50 border-amber-100',
    iconWrap: 'bg-amber-400 text-white',
    icon: 'text-white',
    reward: 'text-amber-800',
  },
  {
    card: 'bg-violet-50 border-violet-100',
    iconWrap: 'bg-violet-400 text-white',
    icon: 'text-white',
    reward: 'text-violet-800',
  },
  {
    card: 'bg-emerald-50 border-emerald-100',
    iconWrap: 'bg-emerald-400 text-white',
    icon: 'text-white',
    reward: 'text-emerald-800',
  },
  {
    card: 'bg-sky-50 border-sky-100',
    iconWrap: 'bg-sky-400 text-white',
    icon: 'text-white',
    reward: 'text-sky-800',
  },
  {
    card: 'bg-rose-50 border-rose-100',
    iconWrap: 'bg-rose-400 text-white',
    icon: 'text-white',
    reward: 'text-rose-800',
  },
]

export function taskTheme(index: number): TaskTheme {
  return TASK_THEMES[index % TASK_THEMES.length]
}

export function taskIcon(slug: string): Component {
  if (slug.includes('checkin')) return Calendar
  if (slug.includes('share') || slug.includes('referral')) return Users
  if (slug.includes('export')) return Download
  if (slug.includes('translate')) return Languages
  if (slug.includes('snapshot')) return Camera
  if (slug.includes('workshop')) return Users
  if (slug.includes('learning_sheet')) return Hammer
  if (slug.includes('mindmate')) return Sparkles
  if (slug.includes('diagram')) return Sparkles
  if (slug.includes('case') || slug.includes('publish')) return FileText
  return FileText
}

export function taskIsActionable(task: ThinkingCoinEarnTask): boolean {
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

export function planBadgeKeys(tier: PersonalPlanTier): string[] {
  if (tier === 'monthly') {
    return ['thinkingCoins.plan.badge.monthlyCoins']
  }
  if (tier === 'sub') {
    return ['thinkingCoins.plan.badge.monthlyCoins', 'thinkingCoins.plan.badge.trialMultiplier']
  }
  if (tier === 'annual') {
    return ['thinkingCoins.plan.badge.annualCoins', 'thinkingCoins.plan.badge.annualSave']
  }
  return []
}

export function planFeatureKeys(tier: PersonalPlanTier): string[] {
  const common = [
    'thinkingCoins.plan.feature.nonAi',
    'thinkingCoins.plan.feature.showcase',
  ]
  if (tier === 'trial') {
    return [
      'thinkingCoins.plan.feature.trialCoins',
      'thinkingCoins.plan.feature.trialDiagrams',
      ...common,
    ]
  }
  if (tier === 'monthly' || tier === 'sub') {
    return [
      'thinkingCoins.plan.feature.paidCoins800',
      ...common,
      'thinkingCoins.plan.feature.storage1gb',
    ]
  }
  return [
    'thinkingCoins.plan.feature.paidCoins900',
    ...common,
    'thinkingCoins.plan.feature.storage2gb',
  ]
}
