/**
 * Parse Excel / Word / WPS table paste for school member batch import.
 * Clipboard from spreadsheet apps uses tab-separated columns and newline-separated rows.
 */

export const MAX_BATCH_MEMBERS = 200
export const MAX_MEMBER_NAME_LENGTH = 200

export type MemberContactType = 'phone' | 'email'

export interface ParsedMemberRow {
  phone?: string
  email?: string
  contactType: MemberContactType
  name: string
  line: number
}

export interface ParsedMemberInvalidRow {
  line: number
  name: string
  contactRaw: string
  errorKey: string
  errorParams?: Record<string, number | string>
}

export interface BatchPasteParseResult {
  rows: ParsedMemberRow[]
  invalidRows?: ParsedMemberInvalidRow[]
  errorKey?: string
  errorParams?: Record<string, number | string>
  skippedHeader?: boolean
  skippedInvalidCount?: number
}

const HEADER_PATTERN = /手机|phone|邮箱|email|姓名|name|mobile|序号|编号|no\.?/i

function splitSpreadsheetLine(line: string): string[] {
  if (line.includes('\t')) {
    return line.split('\t').map((cell) => cell.trim())
  }
  if (line.includes(';')) {
    return line.split(';').map((cell) => cell.trim())
  }
  if (line.includes(',')) {
    const commaParts = line.split(',').map((cell) => cell.trim())
    if (commaParts.length === 2) {
      return commaParts
    }
  }
  return line.split(/\s{2,}/).map((cell) => cell.trim()).filter(Boolean)
}

export function looksLikeEmail(value: string): boolean {
  return value.includes('@')
}

function isContactLikeCell(cell: string): boolean {
  if (isValidMemberPhone(cell) || looksLikeEmail(cell)) {
    return true
  }
  return cell.replace(/\D/g, '').length >= 5
}

function isHeaderCells(cells: string[]): boolean {
  if (cells.length === 0) {
    return false
  }
  const contactLikeCount = cells.filter((cell) => isContactLikeCell(cell)).length
  if (contactLikeCount > 0) {
    return false
  }
  return cells.some((cell) => HEADER_PATTERN.test(cell))
}

function normalizeExcelPhoneCell(raw: string): string {
  const trimmed = raw.trim()
  if (/^[\d.]+[eE][+\-]?\d+$/.test(trimmed)) {
    const numeric = Number(trimmed)
    if (Number.isFinite(numeric) && numeric >= 1_000_000_000 && numeric < 100_000_000_000) {
      return String(Math.round(numeric))
    }
  }
  if (/^\d+\.0+$/.test(trimmed)) {
    return trimmed.split('.')[0] ?? trimmed
  }
  return trimmed
}

export function normalizeMemberPhone(phone: string): string {
  const normalizedCell = normalizeExcelPhoneCell(phone.normalize('NFKC').trim())
  let digits = normalizedCell.replace(/\D/g, '')
  if (digits.length === 13 && digits.startsWith('86')) {
    digits = digits.slice(2)
  }
  return digits
}

export function normalizeMemberEmail(email: string): string {
  return email.normalize('NFKC').trim().toLowerCase()
}

export function isValidMemberPhone(phone: string): boolean {
  const digits = normalizeMemberPhone(phone)
  return digits.length === 11 && digits.startsWith('1')
}

export function isValidMemberEmail(email: string): boolean {
  const normalized = normalizeMemberEmail(email)
  if (!normalized || normalized.length > 255) {
    return false
  }
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)
}

export function isValidMemberContact(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed) {
    return false
  }
  if (looksLikeEmail(trimmed)) {
    return isValidMemberEmail(trimmed)
  }
  return isValidMemberPhone(trimmed)
}

export function isValidMemberName(name: string): boolean {
  const trimmed = name.trim()
  return (
    trimmed.length >= 2 &&
    trimmed.length <= MAX_MEMBER_NAME_LENGTH &&
    !/\d/.test(trimmed)
  )
}

export function formatMemberContact(row: Pick<ParsedMemberRow, 'phone' | 'email'>): string {
  return row.email ?? row.phone ?? ''
}

type ClassifiedContact =
  | { kind: 'phone'; value: string }
  | { kind: 'email'; value: string }
  | { kind: 'invalid_phone'; raw: string }
  | { kind: 'invalid_email'; raw: string }

function classifyContactCell(cell: string): ClassifiedContact | null {
  const trimmed = cell.trim()
  if (!trimmed) {
    return null
  }

  if (looksLikeEmail(trimmed)) {
    if (isValidMemberEmail(trimmed)) {
      return { kind: 'email', value: normalizeMemberEmail(trimmed) }
    }
    return { kind: 'invalid_email', raw: trimmed }
  }

  if (isValidMemberPhone(trimmed)) {
    return { kind: 'phone', value: normalizeMemberPhone(trimmed) }
  }

  const digits = trimmed.replace(/\D/g, '')
  if (digits.length >= 5) {
    return { kind: 'invalid_phone', raw: trimmed }
  }

  return null
}

function isContactClassified(cell: string): boolean {
  return classifyContactCell(cell) !== null
}

type ResolveContactResult =
  | {
      ok: true
      row: Omit<ParsedMemberRow, 'line'>
    }
  | {
      ok: false
      invalid: ParsedMemberInvalidRow
    }
  | null

function invalidRowForContact(
  line: number,
  name: string,
  contactRaw: string,
  contactKind: 'phone' | 'email'
): ParsedMemberInvalidRow {
  const errorKey =
    contactKind === 'phone'
      ? 'admin.schoolAddMemberBatchInvalidPhoneForName'
      : 'admin.schoolAddMemberBatchInvalidEmailForName'
  return {
    line,
    name,
    contactRaw,
    errorKey,
    errorParams: { name },
  }
}

function invalidRowForName(line: number, name: string, contactRaw: string): ParsedMemberInvalidRow {
  return {
    line,
    name,
    contactRaw,
    errorKey: 'admin.schoolAddMemberBatchInvalidNameForName',
    errorParams: { name },
  }
}

function invalidRowForLine(line: number, contactRaw: string): ParsedMemberInvalidRow {
  return {
    line,
    name: '',
    contactRaw,
    errorKey: 'admin.schoolAddMemberBatchInvalidContactOnLine',
    errorParams: { line },
  }
}

function resolveContactAndName(cells: string[], line: number): ResolveContactResult {
  const nonEmpty = cells.map((cell) => cell.trim()).filter(Boolean)
  if (nonEmpty.length < 2) {
    return null
  }

  for (let index = 0; index < nonEmpty.length; index += 1) {
    const cell = nonEmpty[index] ?? ''
    const classified = classifyContactCell(cell)
    if (!classified) {
      continue
    }

    const nameCandidates = [
      nonEmpty[index - 1],
      nonEmpty[index + 1],
      ...nonEmpty.filter((_, candidateIndex) => candidateIndex !== index),
    ]

    for (const candidate of nameCandidates) {
      if (!candidate || isContactClassified(candidate)) {
        continue
      }
      const name = candidate.trim()
      if (classified.kind === 'phone') {
        if (!isValidMemberName(name)) {
          return {
            ok: false,
            invalid: invalidRowForName(line, name, classified.value),
          }
        }
        return {
          ok: true,
          row: { phone: classified.value, contactType: 'phone', name },
        }
      }
      if (classified.kind === 'email') {
        if (!isValidMemberName(name)) {
          return {
            ok: false,
            invalid: invalidRowForName(line, name, classified.value),
          }
        }
        return {
          ok: true,
          row: { email: classified.value, contactType: 'email', name },
        }
      }
      if (classified.kind === 'invalid_phone') {
        return {
          ok: false,
          invalid: name
            ? invalidRowForContact(line, name, classified.raw, 'phone')
            : invalidRowForLine(line, classified.raw),
        }
      }
      return {
        ok: false,
        invalid: name
          ? invalidRowForContact(line, name, classified.raw, 'email')
          : invalidRowForLine(line, classified.raw),
      }
    }

    if (classified.kind === 'invalid_phone') {
      return {
        ok: false,
        invalid: invalidRowForLine(line, classified.raw),
      }
    }
    if (classified.kind === 'invalid_email') {
      return {
        ok: false,
        invalid: invalidRowForLine(line, classified.raw),
      }
    }
  }

  return null
}

/** @deprecated Use parseExcelMemberPaste instead. */
export function splitPasteColumn(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => splitSpreadsheetLine(line)[0] ?? '')
    .filter((line) => line.length > 0)
}

/** @deprecated Use parseExcelMemberPaste instead. */
export function parseBatchMemberPaste(
  phoneColumn: string,
  nameColumn: string
): BatchPasteParseResult {
  if (nameColumn.trim()) {
    const combined = phoneColumn
      .split(/\r?\n/)
      .map((line, index) => {
        const nameLines = nameColumn.split(/\r?\n/)
        const name = (nameLines[index] ?? '').trim()
        return name ? `${line.trim()}\t${name}` : line.trim()
      })
      .join('\n')
    return parseExcelMemberPaste(combined)
  }
  return parseExcelMemberPaste(phoneColumn)
}

export function parseExcelMemberPaste(pasteText: string): BatchPasteParseResult {
  const rawLines = pasteText.split(/\r?\n/)
  const rows: ParsedMemberRow[] = []
  const invalidRows: ParsedMemberInvalidRow[] = []
  let skippedHeader = false
  let invalidLineCount = 0
  let headerSkipped = false

  for (let index = 0; index < rawLines.length; index += 1) {
    const line = rawLines[index]?.trim() ?? ''
    if (!line) {
      continue
    }

    const cells = splitSpreadsheetLine(line)
    if (!headerSkipped && isHeaderCells(cells)) {
      skippedHeader = true
      headerSkipped = true
      continue
    }

    const resolved = resolveContactAndName(cells, index + 1)
    if (!resolved) {
      invalidLineCount += 1
      continue
    }
    if (!resolved.ok) {
      invalidRows.push(resolved.invalid)
      invalidLineCount += 1
      continue
    }

    rows.push({
      ...resolved.row,
      line: index + 1,
    })
  }

  if (rows.length === 0 && invalidLineCount > 0) {
    return {
      rows: [],
      invalidRows,
      errorKey: 'admin.schoolAddMemberBatchInvalidPaste',
      errorParams: { count: invalidLineCount },
      skippedHeader,
      skippedInvalidCount: invalidLineCount,
    }
  }

  if (rows.length > MAX_BATCH_MEMBERS) {
    return {
      rows,
      invalidRows: invalidRows.length > 0 ? invalidRows : undefined,
      errorKey: 'admin.schoolAddMemberBatchTooLarge',
      errorParams: { max: MAX_BATCH_MEMBERS, count: rows.length },
      skippedHeader,
      skippedInvalidCount: invalidLineCount > 0 ? invalidLineCount : undefined,
    }
  }

  return {
    rows,
    invalidRows: invalidRows.length > 0 ? invalidRows : undefined,
    skippedHeader,
    skippedInvalidCount: invalidLineCount > 0 ? invalidLineCount : undefined,
  }
}

function memberContactKey(row: ParsedMemberRow): string {
  return row.email ?? row.phone ?? ''
}

export function dedupeMemberRows(rows: ParsedMemberRow[]): ParsedMemberRow[] {
  const seen = new Set<string>()
  const deduped: ParsedMemberRow[] = []
  for (const row of rows) {
    const key = memberContactKey(row)
    if (!key || seen.has(key)) {
      continue
    }
    seen.add(key)
    deduped.push(row)
  }
  return deduped
}
