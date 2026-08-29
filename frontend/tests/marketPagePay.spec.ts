import { describe, expect, it } from 'vitest'

import {
  formatListingYuan,
  isAlipayReturnQuery,
  parseAlipayReturnOrderId,
} from '@/composables/markets/marketPagePay'
import { listingRowToTemplate } from '@/composables/markets/templateCatalog'

describe('marketPagePay', () => {
  it('formats fen as yuan', () => {
    expect(formatListingYuan(1990)).toBe('¥19.90')
    expect(formatListingYuan(1)).toBe('¥0.01')
  })

  it('reads order_id from Alipay return query', () => {
    expect(parseAlipayReturnOrderId({ order_id: '42' })).toBe(42)
    expect(parseAlipayReturnOrderId({ order_id: ['7'] })).toBe(7)
    expect(parseAlipayReturnOrderId({ order_id: 'nope' })).toBeNull()
    expect(parseAlipayReturnOrderId({})).toBeNull()
  })

  it('detects the return landing query', () => {
    expect(isAlipayReturnQuery({ alipay: 'return' })).toBe(true)
    expect(isAlipayReturnQuery({ order_id: '3' })).toBe(true)
    expect(isAlipayReturnQuery({})).toBe(false)
  })
})

describe('listingRowToTemplate', () => {
  it('maps a market listing to a catalog card', () => {
    const row = listingRowToTemplate({
      id: 9,
      title: '演示模板',
      product_type: 'MindMate',
      scene: '教学通用',
      subject: '语文',
      price_minor: 990,
    })
    expect(row.listingId).toBe(9)
    expect(row.priceMinor).toBe(990)
    expect(row.type).toBe('MindMate')
  })
})
