<script setup lang="ts">
/**
 * Admin — Market (市场): orders, listings, subscriptions.
 */
import { computed, ref } from 'vue'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import { useLanguage } from '@/composables'
import {
  useAdminMarketsListings,
  useAdminMarketsOrders,
  useAdminMarketsStats,
  useAdminMarketsSubscriptions,
} from '@/composables/queries'

const { t } = useLanguage()

const activeTab = ref<'orders' | 'listings' | 'subscriptions'>('orders')

const statsQuery = useAdminMarketsStats()
const ordersQuery = useAdminMarketsOrders(200)
const listingsQuery = useAdminMarketsListings(500)
const subscriptionsQuery = useAdminMarketsSubscriptions(200)

const loading = computed(
  () =>
    statsQuery.isFetching.value ||
    ordersQuery.isFetching.value ||
    listingsQuery.isFetching.value ||
    subscriptionsQuery.isFetching.value
)

const stats = computed(() => ({
  orders_total: statsQuery.data.value?.orders_total ?? 0,
  orders_paid: statsQuery.data.value?.orders_paid ?? 0,
  orders_pending: statsQuery.data.value?.orders_pending ?? 0,
}))

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

const orders = computed(() => (ordersQuery.data.value ?? []) as OrderRow[])
const listings = computed(() => (listingsQuery.data.value ?? []) as ListingRow[])
const subscriptions = computed(() => (subscriptionsQuery.data.value ?? []) as SubRow[])
</script>

<template>
  <div
    v-loading="loading"
    class="admin-markets-tab space-y-6"
  >
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-2">
        <I18nText k="admin.markets.stats" />
      </h2>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <AdminSwissKpiCard
          :title="t('admin.markets.ordersTotal')"
          :value="stats.orders_total"
          theme="neutral"
        />
        <AdminSwissKpiCard
          :title="t('admin.markets.ordersPaid')"
          :value="stats.orders_paid"
          theme="success"
        />
        <AdminSwissKpiCard
          :title="t('admin.markets.ordersPending')"
          :value="stats.orders_pending"
          theme="warn"
        />
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane name="orders">
        <template #label>
          <I18nText k="admin.markets.tabOrders" />
        </template>
        <el-table
          :data="orders"
          stripe
          style="width: 100%"
          max-height="480"
        >
          <el-table-column
            prop="id"
            width="88"
          >
            <template #header>
              <I18nText k="admin.markets.colOrderId" />
            </template>
          </el-table-column>
          <el-table-column
            prop="user_email_or_phone"
            min-width="140"
          >
            <template #header>
              <I18nText k="admin.markets.colUser" />
            </template>
          </el-table-column>
          <el-table-column
            prop="listing_title"
            min-width="160"
          >
            <template #header>
              <I18nText k="admin.markets.colListing" />
            </template>
          </el-table-column>
          <el-table-column
            prop="amount_minor"
            width="100"
          >
            <template #header>
              <I18nText k="admin.markets.colAmount" />
            </template>
          </el-table-column>
          <el-table-column
            prop="status"
            width="100"
          >
            <template #header>
              <I18nText k="admin.markets.colStatus" />
            </template>
          </el-table-column>
          <el-table-column
            prop="out_trade_no"
            min-width="160"
          >
            <template #header>
              <I18nText k="admin.markets.colOutTradeNo" />
            </template>
          </el-table-column>
          <el-table-column
            prop="alipay_trade_no"
            min-width="160"
          >
            <template #header>
              <I18nText k="admin.markets.colTradeNo" />
            </template>
          </el-table-column>
          <el-table-column
            prop="created_at"
            min-width="160"
          >
            <template #header>
              <I18nText k="admin.markets.colCreated" />
            </template>
          </el-table-column>
          <el-table-column
            prop="paid_at"
            min-width="160"
          >
            <template #header>
              <I18nText k="admin.markets.colPaid" />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane name="listings">
        <template #label>
          <I18nText k="admin.markets.tabListings" />
        </template>
        <el-table
          :data="listings"
          stripe
          style="width: 100%"
          max-height="480"
        >
          <el-table-column
            prop="id"
            width="72"
            label="ID"
          />
          <el-table-column
            prop="slug"
            min-width="140"
          >
            <template #header>
              <I18nText k="admin.markets.colSlug" />
            </template>
          </el-table-column>
          <el-table-column
            prop="listing_kind"
            width="120"
          >
            <template #header>
              <I18nText k="admin.markets.colKind" />
            </template>
          </el-table-column>
          <el-table-column
            prop="title"
            min-width="200"
          >
            <template #header>
              <I18nText k="admin.markets.colTitle" />
            </template>
          </el-table-column>
          <el-table-column
            prop="price_minor"
            width="100"
          >
            <template #header>
              <I18nText k="admin.markets.colAmount" />
            </template>
          </el-table-column>
          <el-table-column
            prop="currency"
            label="CNY"
            width="72"
          />
          <el-table-column
            prop="is_active"
            width="88"
          >
            <template #header>
              <I18nText k="admin.markets.colActive" />
            </template>
            <template #default="{ row }">
              <span>{{ row.is_active ? '✓' : '—' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane name="subscriptions">
        <template #label>
          <I18nText k="admin.markets.tabSubscriptions" />
        </template>
        <el-table
          :data="subscriptions"
          stripe
          style="width: 100%"
          max-height="480"
        >
          <el-table-column
            prop="id"
            width="88"
            label="ID"
          />
          <el-table-column
            prop="user_email_or_phone"
            min-width="140"
          >
            <template #header>
              <I18nText k="admin.markets.colUser" />
            </template>
          </el-table-column>
          <el-table-column
            prop="listing_title"
            min-width="160"
          >
            <template #header>
              <I18nText k="admin.markets.colListing" />
            </template>
          </el-table-column>
          <el-table-column
            prop="status"
            width="100"
          >
            <template #header>
              <I18nText k="admin.markets.colStatus" />
            </template>
          </el-table-column>
          <el-table-column
            prop="alipay_agreement_id"
            label="Agreement"
            min-width="160"
          />
          <el-table-column
            prop="current_period_end"
            label="Period end"
            min-width="140"
          />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
