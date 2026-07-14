<script setup lang="ts">
/**
 * Admin-only warning when GeoLite2-Country.mmdb is missing on the server.
 */
import { h, watch } from 'vue'

import { AlertTriangle } from '@lucide/vue'

import { useLanguage } from '@/composables'
import {
  getDefaultElNotificationOptions,
  loadElNotification,
} from '@/composables/core/notifications'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'

const STORAGE_KEY = 'mindgraph_geolite_missing_dismissed'

const FALLBACK_DOWNLOAD_URL =
  'https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/?lang=en'

const authStore = useAuthStore()
const { t } = useLanguage()

type NotificationHandle = { close: () => void }

let notificationInstance: NotificationHandle | null = null

function closeNotification() {
  if (notificationInstance) {
    notificationInstance.close()
    notificationInstance = null
  }
}

async function checkAndNotify() {
  if (!authStore.isAdmin) {
    closeNotification()
    return
  }
  try {
    const res = await apiRequest('/api/auth/admin/system/geolite')
    if (!res.ok) {
      return
    }
    const data = (await res.json()) as {
      geolite_country_mmdb_present: boolean
      expected_path: string
      download_url: string
    }
    if (data.geolite_country_mmdb_present) {
      try {
        localStorage.removeItem(STORAGE_KEY)
      } catch {
        // ignore
      }
      closeNotification()
      return
    }
    let dismissed = false
    try {
      dismissed = localStorage.getItem(STORAGE_KEY) === '1'
    } catch {
      dismissed = false
    }
    if (dismissed) {
      return
    }
    await showNotification(data)
  } catch {
    // ignore
  }
}

async function showNotification(data: { expected_path: string; download_url: string }) {
  if (notificationInstance) {
    return
  }
  const url = data.download_url || FALLBACK_DOWNLOAD_URL
  const ElNotification = await loadElNotification()
  notificationInstance = ElNotification({
    ...getDefaultElNotificationOptions(),
    title: t('notification.geoLiteMissingTitle'),
    type: 'warning',
    duration: 0,
    icon: h(AlertTriangle, { size: 20 }),
    message: h('div', { class: 'geolite-missing-notification' }, [
      h('p', { style: { margin: '0 0 8px 0' } }, t('notification.geoLiteMissingIntro')),
      h('p', { style: { margin: '0 0 8px 0', wordBreak: 'break-all' } }, [
        t('notification.geoLiteMissingPathLabel'),
        ' ',
        data.expected_path,
      ]),
      h(
        'a',
        {
          href: url,
          target: '_blank',
          rel: 'noopener noreferrer',
          style: { color: 'var(--el-color-primary)' },
        },
        t('notification.geoLiteMissingLink')
      ),
    ]),
    onClose: () => {
      notificationInstance = null
      try {
        localStorage.setItem(STORAGE_KEY, '1')
      } catch {
        // ignore
      }
    },
  })
}

watch(
  () => authStore.isAdmin,
  (isAdmin) => {
    if (isAdmin) {
      setTimeout(() => {
        void checkAndNotify()
      }, 1500)
    } else {
      closeNotification()
    }
  },
  { immediate: true }
)
</script>

<template>
  <div style="display: none" />
</template>
