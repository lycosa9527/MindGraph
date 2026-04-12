<script setup lang="ts">
/**
 * Admin — Market (市场): orders, listings, subscriptions.
 */
import { onMounted, ref } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const { t } = useLanguage()
const notify = useNotifications()

const loading = ref(true)
const activeTab = ref<'orders' | 'listings' | 'subscriptions'>('orders')

const stats = ref({
  orders_total: 0,
  orders_paid: 0,
  orders_pending: 0,
})

interface OrderRow {
  id: number
  user_id: number
  user_email_or_phone: string | null
  listing_id: number
  listing_title: string
  out_trade_no: string
  status: string
  amount_minor: number
  currency: string
  alipay_trade_no: string | null
  created_at: string
  paid_at: string | null
}

interface ListingRow {
  id: number
  slug: string
  listing_kind: string
  title: string
  price_minor: number
  currency: string
  is_active: boolean
}

interface SubRow {
  id: number
  user_id: number
  user_email_or_phone: string | null
  listing_id: number
  listing_title: string
  alipay_agreement_id: string | null
  status: string
  current_period_end: string | null
}

const orders = ref<OrderRow[]>([])
const listings = ref<ListingRow[]>([])
const subscriptions = ref<SubRow[]>([])

async function loadAll(): Promise<void> {
  loading.value = true
  try {
    const [resStats, resOrders, resListings, resSubs] = await Promise.all([
      apiRequest('/api/markets/admin/stats'),
      apiRequest('/api/markets/admin/orders?limit=200'),
      apiRequest('/api/markets/admin/listings?limit=500'),
      apiRequest('/api/markets/admin/subscriptions?limit=200'),
    ])
    if (!resStats.ok || !resOrders.ok || !resListings.ok || !resSubs.ok) {
      notify.error(t('admin.markets.loadError'))
      return
    }
    const jStats = (await resStats.json()) as {
      orders_total: number
      orders_paid: number
      orders_pending: number
    }
    stats.value = jStats
    orders.value = (await resOrders.json()) as OrderRow[]
    listings.value = (await resListings.json()) as ListingRow[]
    subscriptions.value = (await resSubs.json()) as SubRow[]
  } catch {
    notify.error(t('admin.markets.loadError'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <div class="admin-markets-tab space-y-6" v-loading="loading">
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-2">{{ t('admin.markets.stats') }}</h2>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div class="text-xs text-gray-500">{{ t('admin.markets.ordersTotal') }}</div>
          <div class="text-2xl font-semibold text-gray-900">{{ stats.orders_total }}</div>
        </div>
        <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div class="text-xs text-gray-500">{{ t('admin.markets.ordersPaid') }}</div>
          <div class="text-2xl font-semibold text-green-700">{{ stats.orders_paid }}</div>
        </div>
        <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div class="text-xs text-gray-500">{{ t('admin.markets.ordersPending') }}</div>
          <div class="text-2xl font-semibold text-amber-700">{{ stats.orders_pending }}</div>
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane :label="t('admin.markets.tabOrders')" name="orders">
        <el-table :data="orders" stripe style="width: 100%" max-height="480">
          <el-table-column prop="id" :label="t('admin.markets.colOrderId')" width="88" />
          <el-table-column prop="user_email_or_phone" :label="t('admin.markets.colUser')" min-width="140" />
          <el-table-column prop="listing_title" :label="t('admin.markets.colListing')" min-width="160" />
          <el-table-column prop="amount_minor" :label="t('admin.markets.colAmount')" width="100" />
          <el-table-column prop="status" :label="t('admin.markets.colStatus')" width="100" />
          <el-table-column prop="out_trade_no" :label="t('admin.markets.colOutTradeNo')" min-width="160" />
          <el-table-column prop="alipay_trade_no" :label="t('admin.markets.colTradeNo')" min-width="160" />
          <el-table-column prop="created_at" :label="t('admin.markets.colCreated')" min-width="160" />
          <el-table-column prop="paid_at" :label="t('admin.markets.colPaid')" min-width="160" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane :label="t('admin.markets.tabListings')" name="listings">
        <el-table :data="listings" stripe style="width: 100%" max-height="480">
          <el-table-column prop="id" width="72" label="ID" />
          <el-table-column prop="slug" :label="t('admin.markets.colSlug')" min-width="140" />
          <el-table-column prop="listing_kind" :label="t('admin.markets.colKind')" width="120" />
          <el-table-column prop="title" :label="t('admin.markets.colTitle')" min-width="200" />
          <el-table-column prop="price_minor" :label="t('admin.markets.colAmount')" width="100" />
          <el-table-column prop="currency" label="CNY" width="72" />
          <el-table-column prop="is_active" :label="t('admin.markets.colActive')" width="88">
            <template #default="{ row }">
              <span>{{ row.is_active ? '✓' : '—' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane :label="t('admin.markets.tabSubscriptions')" name="subscriptions">
        <el-table :data="subscriptions" stripe style="width: 100%" max-height="480">
          <el-table-column prop="id" width="88" label="ID" />
          <el-table-column prop="user_email_or_phone" :label="t('admin.markets.colUser')" min-width="140" />
          <el-table-column prop="listing_title" :label="t('admin.markets.colListing')" min-width="160" />
          <el-table-column prop="status" :label="t('admin.markets.colStatus')" width="100" />
          <el-table-column prop="alipay_agreement_id" label="Agreement" min-width="160" />
          <el-table-column prop="current_period_end" label="Period end" min-width="140" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
