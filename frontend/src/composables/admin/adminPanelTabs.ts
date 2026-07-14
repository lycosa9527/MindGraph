/**
 * Shared management panel tab definitions (sidebar + AdminPage).
 */
import type { Component } from 'vue'

import {
  DataAnalysis,
  Document,
  MagicStick,
  Promotion,
  School,
  Setting,
  ShoppingCart,
  User,
} from '@element-plus/icons-vue'

export interface AdminPanelTabConfig {
  name: string
  labelKey: string
  icon: Component
}

export const ADMIN_PANEL_TAB_CONFIG: readonly AdminPanelTabConfig[] = [
  { name: 'data_center', labelKey: 'admin.dataCenter', icon: DataAnalysis },
  { name: 'users', labelKey: 'admin.schoolUsersTitle', icon: User },
  { name: 'organizations', labelKey: 'admin.orgManagement', icon: School },
  { name: 'invites', labelKey: 'admin.inviteUsers', icon: Promotion },
  { name: 'billing', labelKey: 'admin.billing', icon: ShoppingCart },
  { name: 'showcase', labelKey: 'admin.showcase.title', icon: Document },
  { name: 'settings', labelKey: 'admin.systemSettings', icon: Setting },
  { name: 'feature_dev', labelKey: 'admin.featureDevTab', icon: MagicStick },
]
