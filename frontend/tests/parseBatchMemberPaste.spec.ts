import { describe, expect, it } from 'vitest'

import {
  dedupeMemberRows,
  isValidMemberContact,
  isValidMemberEmail,
  isValidMemberPhone,
  MAX_BATCH_MEMBERS,
  normalizeMemberEmail,
  normalizeMemberPhone,
  parseBatchMemberPaste,
  parseExcelMemberPaste,
} from '@/utils/parseBatchMemberPaste'

describe('parseExcelMemberPaste', () => {
  it('parses tab-separated Excel rows', () => {
    const result = parseExcelMemberPaste('13800000001\tAlice\n13800000002\tBob')
    expect(result.rows).toEqual([
      { phone: '13800000001', contactType: 'phone', name: 'Alice', line: 1 },
      { phone: '13800000002', contactType: 'phone', name: 'Bob', line: 2 },
    ])
  })

  it('parses email rows', () => {
    const result = parseExcelMemberPaste('teacher@example.com\tAlice')
    expect(result.rows).toEqual([
      {
        email: 'teacher@example.com',
        contactType: 'email',
        name: 'Alice',
        line: 1,
      },
    ])
  })

  it('skips header row and accepts name-first columns', () => {
    const result = parseExcelMemberPaste('姓名\t手机号\n张三\t13800000001')
    expect(result.skippedHeader).toBe(true)
    expect(result.rows).toEqual([{ phone: '13800000001', contactType: 'phone', name: '张三', line: 2 }])
  })

  it('accepts phone-first or name-first without a header row', () => {
    const phoneFirst = parseExcelMemberPaste('13800000001\t张三')
    const nameFirst = parseExcelMemberPaste('李四\t13800000002')
    expect(phoneFirst.rows).toEqual([{ phone: '13800000001', contactType: 'phone', name: '张三', line: 1 }])
    expect(nameFirst.rows).toEqual([{ phone: '13800000002', contactType: 'phone', name: '李四', line: 1 }])
  })

  it('parses three-column sheets by finding the phone cell', () => {
    const result = parseExcelMemberPaste('1\t张三\t13800000001\n2\t李四\t13800000002')
    expect(result.rows).toHaveLength(2)
    expect(result.rows[0]?.name).toBe('张三')
  })

  it('accepts phones with separators and +86 prefix', () => {
    expect(normalizeMemberPhone('+86 138-0013-8000')).toBe('13800138000')
    expect(isValidMemberPhone('+86 138-0013-8000')).toBe(true)
  })

  it('normalizes email to lowercase', () => {
    expect(normalizeMemberEmail('Teacher@Example.COM')).toBe('teacher@example.com')
    expect(isValidMemberEmail('Teacher@Example.COM')).toBe(true)
  })

  it('accepts Excel scientific notation phone cells', () => {
    const result = parseExcelMemberPaste('1.3800138000E+10\t张三')
    expect(result.rows).toEqual([{ phone: '13800138000', contactType: 'phone', name: '张三', line: 1 }])
  })

  it('accepts Excel trailing .0 phone cells', () => {
    const result = parseExcelMemberPaste('13800138000.0\t张三')
    expect(result.rows).toEqual([{ phone: '13800138000', contactType: 'phone', name: '张三', line: 1 }])
  })

  it('accepts semicolon-separated rows', () => {
    const result = parseExcelMemberPaste('13800000001;Alice\n13800000002;Bob')
    expect(result.rows).toHaveLength(2)
  })

  it('accepts two-part comma-separated rows only', () => {
    const result = parseExcelMemberPaste('13800000001,Alice')
    expect(result.rows).toEqual([{ phone: '13800000001', contactType: 'phone', name: 'Alice', line: 1 }])
  })

  it('falls back to multi-space split when comma line has extra parts', () => {
    const result = parseExcelMemberPaste('13800000001    张三 San')
    expect(result.rows).toEqual([{ phone: '13800000001', contactType: 'phone', name: '张三 San', line: 1 }])
  })

  it('reports invalid paste when rows cannot be parsed', () => {
    const result = parseExcelMemberPaste('only-one-column\nalso-invalid')
    expect(result.rows).toEqual([])
    expect(result.errorKey).toBe('admin.schoolAddMemberBatchInvalidPaste')
  })

  it('records invalid phone format with member name', () => {
    const result = parseExcelMemberPaste('12345\t张三')
    expect(result.rows).toEqual([])
    expect(result.invalidRows).toEqual([
      expect.objectContaining({
        name: '张三',
        errorKey: 'admin.schoolAddMemberBatchInvalidPhoneForName',
      }),
    ])
  })

  it('records invalid email format with member name', () => {
    const result = parseExcelMemberPaste('bad@email\tAlice')
    expect(result.rows).toEqual([])
    expect(result.invalidRows).toEqual([
      expect.objectContaining({
        name: 'Alice',
        errorKey: 'admin.schoolAddMemberBatchInvalidEmailForName',
      }),
    ])
  })

  it('keeps valid rows and counts skipped invalid lines', () => {
    const result = parseExcelMemberPaste('13800000001\t张三\nbad-row\n13800000002\t李四')
    expect(result.rows).toHaveLength(2)
    expect(result.skippedInvalidCount).toBe(1)
  })

  it('rejects batches larger than MAX_BATCH_MEMBERS', () => {
    const lines = Array.from({ length: MAX_BATCH_MEMBERS + 1 }, (_, index) => {
      const suffix = String(index).padStart(8, '0')
      return `138${suffix}\tMember ${String.fromCharCode(65 + (index % 26))}`
    }).join('\n')
    const result = parseExcelMemberPaste(lines)
    expect(result.errorKey).toBe('admin.schoolAddMemberBatchTooLarge')
    expect(result.errorParams?.max).toBe(MAX_BATCH_MEMBERS)
  })

  it('deduplicates by phone or email', () => {
    const rows = dedupeMemberRows([
      { phone: '13800000001', contactType: 'phone', name: 'A', line: 1 },
      { phone: '13800000001', contactType: 'phone', name: 'B', line: 2 },
      { email: 'a@example.com', contactType: 'email', name: 'C', line: 3 },
    ])
    expect(rows).toHaveLength(2)
  })

  it('validates single contact values', () => {
    expect(isValidMemberContact('13800000001')).toBe(true)
    expect(isValidMemberContact('teacher@example.com')).toBe(true)
    expect(isValidMemberContact('bad')).toBe(false)
  })
})

describe('parseBatchMemberPaste legacy wrapper', () => {
  it('still parses tab-separated rows in one field', () => {
    const result = parseBatchMemberPaste('13800000001\tAlice\n13800000002\tBob', '')
    expect(result.rows).toHaveLength(2)
  })
})
