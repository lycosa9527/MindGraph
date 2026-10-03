<script setup lang="ts">
/**
 * User chip Settings: account, security, language, and plugins in one dialog.
 * Each tab applies its own changes immediately.
 */
import { computed, ref, watch } from 'vue'

import { Settings } from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import '@/styles/settings-language-swiss.css'

import SettingsAccountPanels from './SettingsAccountPanels.vue'
import SettingsLanguagePanel from './SettingsLanguagePanel.vue'
import { USER_SETTINGS_TAB_KEYS, type UserSettingsTab } from './userSettingsTabs'

const visible = defineModel<boolean>('visible', { required: true })

const props = withDefaults(
  defineProps<{
    initialTab?: UserSettingsTab
  }>(),
  {
    initialTab: 'account',
  }
)

const emit = defineEmits<{
  success: []
}>()

const { t } = useLanguage()
const tab = ref<UserSettingsTab>(props.initialTab)

const tabOptions = computed(() =>
  (['account', 'security', 'language', 'plugins'] as const).map((value) => ({
    value,
    labelKey: USER_SETTINGS_TAB_KEYS[value],
  }))
)

watch(
  () => [visible.value, props.initialTab] as const,
  ([open, initial]) => {
    if (open) {
      tab.value = initial
    }
  }
)

const accountSection = computed(() =>
  tab.value === 'security' || tab.value === 'plugins' ? tab.value : 'account'
)
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('swissGlass.hero.userSettings.ribbon')"
    ribbon-key="swissGlass.hero.userSettings.ribbon"
    :title="t('swissGlass.hero.userSettings.title')"
    title-key="swissGlass.hero.userSettings.title"
    :line1="t('swissGlass.hero.userSettings.line1')"
    line1-key="swissGlass.hero.userSettings.line1"
    :icon="Settings"
    width="min(480px, 92vw)"
    dialog-class="language-settings-swiss user-settings-dialog"
  >
    <AdminSwissSegmented
      v-model="tab"
      class="user-settings-tabs"
      block
      equal
      :aria-label="t('settings.tabs.aria')"
      :options="tabOptions"
    />

    <SettingsLanguagePanel
      v-show="tab === 'language'"
      :open="visible"
    />
    <SettingsAccountPanels
      v-show="tab !== 'language'"
      :open="visible"
      :section="accountSection"
      @success="emit('success')"
    />
  </SwissGlassDialog>
</template>

<style scoped>
.user-settings-tabs {
  margin-bottom: 1.25rem;
}
</style>
