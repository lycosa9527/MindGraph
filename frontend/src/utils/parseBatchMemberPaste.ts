/**
 * Parse Excel / Word / WPS table paste for school member batch import.
 * Clipboard from spreadsheet apps uses tab-separated columns and newline-separated rows.
 */

export const MAX_BATCH_MEMBERS = 200
export const MAX_MEMBER_NAME_LENGTH = 200

export interface ParsedMemberRow {
  phone: string
  name: string
  line: number
}

export interface BatchPasteParseResult {
  rows: ParsedMemberRow[]
  errorKey?: string
  errorParams?: Record<string, number | string>
  skippedHeader?: boolean
  skippedInvalidCount?: number
}

const HEADER_PATTERN = /手机|phone|姓名|name|mobile|序号|编号|no\.?/i

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

function isHeaderCells(cells: string[]): boolean {
  if (cells.length === 0) {
    return false
  }
  const phoneLikeCount = cells.filter((cell) => isValidMemberPhone(cell)).length
  if (phoneLikeCount > 0) {
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

export function isValidMemberPhone(phone: string): boolean {
  const digits = normalizeMemberPhone(phone)
  return digits.length === 11 && digits.startsWith('1')
}

export function isValidMemberName(name: string): boolean {
  const trimmed = name.trim()
  return (
    trimmed.length >= 2 &&
    trimmed.length <= MAX_MEMBER_NAME_LENGTH &&
    !/\d/.test(trimmed)
  )
}

function resolvePhoneAndName(cells: string[]): { phone: string; name: string } | null {
  const nonEmpty = cells.map((cell) => cell.trim()).filter(Boolean)
  if (nonEmpty.length < 2) {
    return null
  }

  for (let index = 0; index < nonEmpty.length; index += 1) {
    const cell = nonEmpty[index] ?? ''
    if (!isValidMemberPhone(cell)) {
      continue
    }
    const phone = normalizeMemberPhone(cell)
    const nameCandidates = [
      nonEmpty[index - 1],
      nonEmpty[index + 1],
      ...nonEmpty.filter((_, candidateIndex) => candidateIndex !== index),
    ]
    for (const candidate of nameCandidates) {
      if (!candidate || isValidMemberPhone(candidate)) {
        continue
      }
      if (isValidMemberName(candidate)) {
        return { phone, name: candidate.trim() }
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

    const resolved = resolvePhoneAndName(cells)
    if (!resolved || !isValidMemberName(resolved.name)) {
      invalidLineCount += 1
      continue
    }

    rows.push({
      phone: resolved.phone,
      name: resolved.name.trim(),
      line: index + 1,
    })
  }

  if (rows.length === 0 && invalidLineCount > 0) {
    return {
      rows: [],
      errorKey: 'admin.schoolAddMemberBatchInvalidPaste',
      errorParams: { count: invalidLineCount },
      skippedHeader,
      skippedInvalidCount: invalidLineCount,
    }
  }

  if (rows.length > MAX_BATCH_MEMBERS) {
    return {
      rows,
      errorKey: 'admin.schoolAddMemberBatchTooLarge',
      errorParams: { max: MAX_BATCH_MEMBERS, count: rows.length },
      skippedHeader,
      skippedInvalidCount: invalidLineCount > 0 ? invalidLineCount : undefined,
    }
  }

  return {
    rows,
    skippedHeader,
    skippedInvalidCount: invalidLineCount > 0 ? invalidLineCount : undefined,
  }
}

export function dedupeMemberRows(rows: ParsedMemberRow[]): ParsedMemberRow[] {
  const seen = new Set<string>()
  const deduped: ParsedMemberRow[] = []
  for (const row of rows) {
    if (seen.has(row.phone)) {
      continue
    }
    seen.add(row.phone)
    deduped.push(row)
  }
  return deduped
}
