/**
 * Registry so AdminFeaturesTab exposes apply action to AdminPage header.
 */
import type { Ref } from 'vue'
import { shallowRef } from 'vue'

export interface AdminFeaturesHeaderToolbarModel {
  saving: Ref<boolean>
  save: () => void | Promise<void>
}

const toolbarModel = shallowRef<AdminFeaturesHeaderToolbarModel | null>(null)

export function registerAdminFeaturesHeaderToolbar(model: AdminFeaturesHeaderToolbarModel): void {
  toolbarModel.value = model
}

export function unregisterAdminFeaturesHeaderToolbar(): void {
  toolbarModel.value = null
}

export function useAdminFeaturesHeaderToolbarModel() {
  return toolbarModel
}
