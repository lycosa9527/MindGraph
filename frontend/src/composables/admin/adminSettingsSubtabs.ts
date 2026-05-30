/**
 * System settings sub-tab definitions (sidebar header + AdminSystemSettingsTab).
 */
import type { Component } from 'vue'

import {
  ChatLineRound,
  Coin,
  Microphone,
  Odometer,
  Reading,
  Setting,
  Ticket,
  UserFilled,
} from '@element-plus/icons-vue'

export interface AdminSettingsSubtabConfig {
  name: string
  labelKey: string
  icon: Component
}

export const ADMIN_SETTINGS_SUBTAB_CONFIG: readonly AdminSettingsSubtabConfig[] = [
  { name: 'features', labelKey: 'admin.featuresTab', icon: Setting },
  { name: 'roles', labelKey: 'admin.roleControl', icon: UserFilled },
  { name: 'tokens', labelKey: 'admin.tokens', icon: Ticket },
  { name: 'library', labelKey: 'admin.library', icon: Reading },
  { name: 'database', labelKey: 'admin.database.tab', icon: Coin },
  { name: 'performance', labelKey: 'admin.performance.tab', icon: Odometer },
  { name: 'gewe', labelKey: 'admin.geweWechat', icon: ChatLineRound },
  { name: 'kitty_llmops', labelKey: 'admin.kittyLlmopsTab', icon: Microphone },
  { name: 'mindbot', labelKey: 'admin.mindbot', icon: Setting },
  { name: 'smart_response', labelKey: 'sidebar.smartResponse', icon: Setting },
  { name: 'teacher_usage', labelKey: 'sidebar.teacherUsage', icon: Setting },
]
