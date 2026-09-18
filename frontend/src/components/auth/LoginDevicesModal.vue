<script setup lang="ts">
/**
 * LoginDevicesModal — list signed-in browsers and kick one offline.
 */
import { computed, ref, watch } from 'vue'

import { Loader2, Smartphone } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { apiDelete, apiGet } from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t } = useLanguage()
const notify = useNotifications()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

type LoginDeviceRow = {
  device_id: string
  label: string
  ip_address: string
  created_at: string
  is_current: boolean
}

const loading = ref(false)
const kickingId = ref('')
const devices = ref<LoginDeviceRow[]>([])

function formatLastActive(iso: string): string {
  if (!iso) {
    return ''
  }
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) {
    return iso
  }
  return parsed.toLocaleString()
}

async function loadDevices() {
  loading.value = true
  try {
    const res = await apiGet('/api/auth/login-devices')
    if (!res.ok) {
      devices.value = []
      notify.error(t('auth.loginDevicesLoadError'))
      return
    }
    const data = (await res.json()) as { devices?: LoginDeviceRow[] }
    devices.value = Array.isArray(data.devices) ? data.devices : []
  } catch {
    devices.value = []
    notify.error(t('auth.loginDevicesLoadError'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      kickingId.value = ''
      void loadDevices()
    }
  }
)

function closeModal() {
  isVisible.value = false
}

async function kickDevice(row: LoginDeviceRow) {
  if (row.is_current || kickingId.value) {
    return
  }
  kickingId.value = row.device_id
  try {
    const res = await apiDelete(`/api/auth/login-devices/${encodeURIComponent(row.device_id)}`)
    if (!res.ok) {
      notify.error(t('auth.loginDevicesKickError'))
      return
    }
    notify.success(t('auth.loginDevicesKickSuccess'))
    devices.value = devices.value.filter((item) => item.device_id !== row.device_id)
  } catch {
    notify.error(t('auth.loginDevicesKickError'))
  } finally {
    kickingId.value = ''
  }
}
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.loginDevices.ribbon')"
    ribbon-key="swissGlass.hero.loginDevices.ribbon"
    :title="t('swissGlass.hero.loginDevices.title')"
    title-key="swissGlass.hero.loginDevices.title"
    :line1="t('swissGlass.hero.loginDevices.line1')"
    line1-key="swissGlass.hero.loginDevices.line1"
    :icon="Smartphone"
    @close="closeModal"
  >
    <div class="space-y-3">
      <div
        v-if="loading && devices.length === 0"
        class="flex items-center justify-center gap-2 py-6 text-sm text-stone-500"
      >
        <Loader2 class="w-4 h-4 animate-spin" />
        <I18nText k="auth.apiTokenLoading" />
      </div>

      <p
        v-else-if="devices.length === 0"
        class="m-0 py-4 text-sm text-stone-500 text-center"
      >
        <I18nText k="auth.loginDevicesEmpty" />
      </p>

      <ul
        v-else
        class="m-0 p-0 list-none space-y-2"
      >
        <li
          v-for="row in devices"
          :key="row.device_id"
          class="rounded-lg border border-stone-200 bg-stone-50 px-3 py-3"
        >
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div class="min-w-0 space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-medium text-stone-800">
                  <template v-if="row.label">{{ row.label }}</template>
                  <I18nText
                    v-else
                    k="auth.loginDevicesUnknown"
                  />
                </span>
                <span
                  v-if="row.is_current"
                  class="rounded-full bg-stone-200 px-2 py-0.5 text-[11px] font-medium text-stone-600"
                >
                  <I18nText k="auth.loginDevicesCurrent" />
                </span>
              </div>
              <p
                v-if="row.created_at"
                class="m-0 text-xs text-stone-500"
              >
                <I18nText
                  k="auth.loginDevicesLastActive"
                  :params="{ date: formatLastActive(row.created_at) }"
                />
              </p>
              <p
                v-if="row.ip_address"
                class="m-0 text-xs text-stone-500"
              >
                <I18nText
                  k="auth.loginDevicesIp"
                  :params="{ ip: row.ip_address }"
                />
              </p>
            </div>
            <button
              v-if="!row.is_current"
              type="button"
              class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary shrink-0"
              :disabled="Boolean(kickingId)"
              @click="kickDevice(row)"
            >
              <Loader2
                v-if="kickingId === row.device_id"
                class="w-3.5 h-3.5 animate-spin"
              />
              <I18nText
                :k="
                  kickingId === row.device_id ? 'auth.loginDevicesKicking' : 'auth.loginDevicesKick'
                "
              />
            </button>
          </div>
        </li>
      </ul>
    </div>

    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="closeModal"
        >
          <I18nText k="common.close" />
        </button>
      </div>
    </template>
  </SwissGlassCard>
</template>
