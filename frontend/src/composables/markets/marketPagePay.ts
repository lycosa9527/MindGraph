/**
 * Alipay PC page-pay checkout for Market listings (电脑网站支付).
 */
import { apiRequest, parseApiErrorDetail } from '@/utils/apiClient'

export const MARKET_PAY_NEED_LOGIN = 'MARKET_PAY_NEED_LOGIN'

export interface MarketOrderSnapshot {
  id: number
  listing_id: number
  out_trade_no: string
  status: string
  amount_minor: number
  currency: string
}

export function formatListingYuan(priceMinor: number): string {
  return `¥${(priceMinor / 100).toFixed(2)}`
}

export function parseAlipayReturnOrderId(query: Record<string, unknown>): number | null {
  const raw = query.order_id
  const value = Array.isArray(raw) ? raw[0] : raw
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1) {
    return null
  }
  return parsed
}

export function isAlipayReturnQuery(query: Record<string, unknown>): boolean {
  return query.alipay === 'return' || parseAlipayReturnOrderId(query) !== null
}

export function writeAlipayPagePayForm(html: string): void {
  document.open()
  document.write(html)
  document.close()
}

export async function createMarketOrder(listingId: number): Promise<MarketOrderSnapshot> {
  const response = await apiRequest('/api/markets/orders', {
    method: 'POST',
    body: JSON.stringify({ listing_id: listingId }),
  })
  if (response.status === 401) {
    throw new Error(MARKET_PAY_NEED_LOGIN)
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, '无法创建订单'))
  }
  return (await response.json()) as MarketOrderSnapshot
}

export async function fetchMarketOrder(orderId: number): Promise<MarketOrderSnapshot> {
  const response = await apiRequest(`/api/markets/orders/${orderId}`)
  if (response.status === 401) {
    throw new Error(MARKET_PAY_NEED_LOGIN)
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, '无法查询订单'))
  }
  return (await response.json()) as MarketOrderSnapshot
}

export async function startMarketPagePay(
  listingId: number,
  renderForm: (html: string) => void = writeAlipayPagePayForm
): Promise<void> {
  const order = await createMarketOrder(listingId)
  const response = await apiRequest(`/api/markets/orders/${order.id}/pay`, { method: 'POST' })
  if (response.status === 401) {
    throw new Error(MARKET_PAY_NEED_LOGIN)
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, '无法发起支付宝支付'))
  }
  const html = await response.text()
  if (!html.includes('<form')) {
    throw new Error('支付宝未返回支付表单')
  }
  renderForm(html)
}
