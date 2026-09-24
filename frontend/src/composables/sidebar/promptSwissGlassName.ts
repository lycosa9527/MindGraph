/**
 * Swiss glass name prompt shared by archive folders and rename dialogs.
 */
import type { Component } from 'vue'

import { Folder, Pencil } from '@lucide/vue'

import { swissGlassPrompt } from '@/composables/common/useSwissGlassPrompt'

const FOLDER_NAME_MAX_LENGTH = 100
const DEFAULT_NAME_MAX_LENGTH = 200

type TranslateFn = (key: string) => string

export async function promptSwissGlassName(
  t: TranslateFn,
  titleKey: string,
  promptKey: string,
  ribbonKey: string,
  initialValue = '',
  options?: { icon?: Component; maxLength?: number }
): Promise<string | null> {
  try {
    const name = await swissGlassPrompt(t(promptKey), t(titleKey), {
      ribbon: t(ribbonKey),
      ribbonKey,
      titleKey,
      line1Key: promptKey,
      confirmButtonText: t('common.ok'),
      cancelButtonText: t('common.cancel'),
      confirmLabelKey: 'common.ok',
      cancelLabelKey: 'common.cancel',
      inputValue: initialValue,
      inputPattern: /\S+/,
      inputErrorMessage: t('sidebar.diagramHistory.nameRequired'),
      inputMaxLength: options?.maxLength ?? DEFAULT_NAME_MAX_LENGTH,
      icon: options?.icon ?? Pencil,
    })
    return name.trim() || null
  } catch {
    return null
  }
}

export function promptArchiveFolderName(
  t: TranslateFn,
  titleKey: string,
  promptKey: string,
  ribbonKey: string,
  initialValue = ''
): Promise<string | null> {
  return promptSwissGlassName(t, titleKey, promptKey, ribbonKey, initialValue, {
    icon: Folder,
    maxLength: FOLDER_NAME_MAX_LENGTH,
  })
}
