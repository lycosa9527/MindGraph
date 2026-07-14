<script setup lang="ts">
/**
 * Version Update Notification
 * Shows a non-blocking notification (top corner; mirrors for RTL) when a new app version is available.
 * Loads Element Plus overlay + button only when an update is actually available.
 */
import { h, watch } from 'vue'

import { useLanguage, useVersionCheck } from '@/composables'
import {
  getDefaultElNotificationOptions,
  loadElNotification,
} from '@/composables/core/notifications'

const { t } = useLanguage()
const { needsUpdate, currentVersion, serverVersion, forceRefresh, dismissUpdate } =
  useVersionCheck()

type NotificationHandle = { close: () => void }

let notificationInstance: NotificationHandle | null = null
let showGeneration = 0

async function showUpdateNotification() {
  const generation = ++showGeneration
  if (notificationInstance) {
    notificationInstance.close()
    notificationInstance = null
  }

  const [ElNotification, buttonMod, iconsMod] = await Promise.all([
    loadElNotification(),
    import('element-plus/es/components/button/index.mjs'),
    import('@element-plus/icons-vue'),
    import('element-plus/es/components/button/style/css'),
  ])
  if (generation !== showGeneration || !needsUpdate.value) {
    return
  }

  const { ElButton } = buttonMod
  const { Refresh } = iconsMod
  notificationInstance = ElNotification({
    ...getDefaultElNotificationOptions(),
    title: t('notification.newVersionAvailable'),
    message: h('div', { class: 'version-notification-content' }, [
      h('div', { class: 'version-info' }, `${currentVersion.value} → ${serverVersion.value}`),
      h(
        ElButton,
        {
          type: 'primary',
          size: 'small',
          onClick: () => {
            notificationInstance?.close()
            forceRefresh()
          },
        },
        () => t('common.refresh') || '刷新'
      ),
    ]),
    icon: h(Refresh),
    duration: 0,
    onClose: () => {
      dismissUpdate()
      notificationInstance = null
    },
  })
}

watch(
  needsUpdate,
  (newValue) => {
    if (newValue) {
      void showUpdateNotification()
    } else if (notificationInstance) {
      notificationInstance.close()
      notificationInstance = null
    }
  },
  { immediate: true }
)
</script>

<template>
  <!-- This component renders nothing - it uses ElNotification programmatically -->
  <div style="display: none" />
</template>

<style>
/* Global styles for version notification */
.version-notification-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 4px;
}

.version-notification-content .version-info {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.version-notification-content .el-button {
  width: 100%;
}
</style>
