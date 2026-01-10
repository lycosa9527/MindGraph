<script setup lang="ts">
/**
 * Version Update Notification
 * Shows a non-blocking notification in top-right corner when a new app version is available
 * Uses Element Plus ElNotification
 */
import { h, watch } from 'vue'

import { ElButton, ElNotification } from 'element-plus'

import { Refresh } from '@element-plus/icons-vue'

import { useLanguage, useVersionCheck } from '@/composables'

const { t } = useLanguage()
const { needsUpdate, currentVersion, serverVersion, forceRefresh, dismissUpdate } =
  useVersionCheck()

let notificationInstance: ReturnType<typeof ElNotification> | null = null

function showUpdateNotification() {
  // Close existing notification if any
  if (notificationInstance) {
    notificationInstance.close()
  }

  notificationInstance = ElNotification({
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
    position: 'top-right',
    duration: 0, // Don't auto-close
    showClose: true,
    customClass: 'dark-alert-notification',
    onClose: () => {
      dismissUpdate()
      notificationInstance = null
    },
  })
}

// Watch for needsUpdate changes and show notification
watch(
  needsUpdate,
  (newValue) => {
    if (newValue) {
      showUpdateNotification()
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
