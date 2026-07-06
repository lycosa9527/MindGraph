/**
 * Localized labels for thinking coin ledger rows.
 */
import type { ThinkingCoinLedgerItem } from '@/types/thinkingCoins'

type TranslateFn = (key: string) => string

export function resolveLedgerTaskTitle(
  item: Pick<ThinkingCoinLedgerItem, 'task_title' | 'task_title_en'>,
  isZh: boolean
): string {
  if (!isZh && item.task_title_en?.trim()) {
    return item.task_title_en.trim()
  }
  return (item.task_title ?? '').trim()
}

export function ledgerItemLabel(
  item: ThinkingCoinLedgerItem,
  t: TranslateFn,
  isZh: boolean
): string {
  const taskTitle = resolveLedgerTaskTitle(item, isZh)
  if (item.reason === 'task_reward' && taskTitle) {
    return taskTitle
  }
  const key = `thinkingCoins.reason.${item.reason}`
  const translated = t(key)
  return translated === key ? item.reason : translated
}
