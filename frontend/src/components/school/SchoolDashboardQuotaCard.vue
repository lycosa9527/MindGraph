<script setup lang="ts">
/** Re-export — school dashboard quota card uses shared AdminSwissQuotaCard. */
import { type Component } from 'vue'

import AdminSwissQuotaCard from '@/components/admin/swiss/AdminSwissQuotaCard.vue'
import {
  type AdminSwissQuotaAccent,
  type AdminSwissStatTheme,
} from '@/constants/adminSwissStatTheme'

const props = defineProps<{
  title: string
  used: number
  limit: number
  remainingLabel: string
  icon: Component
  theme?: AdminSwissStatTheme
  accent?: AdminSwissQuotaAccent
  limitSuffix?: string
  usedDecimals?: number
  usedDisplayOverride?: string
  limitDisplayOverride?: string
}>()
</script>

<template>
  <AdminSwissQuotaCard v-bind="props" />
</template>
