import { isCnMainlandMobile } from '@/utils/accountPhone'

/** Limits mirror backend SchoolConsultationBody / school_consult_validation.py */

export const SCHOOL_CONSULT_LIMITS = {
  name: 64,
  phone: 32,
  organization: 128,
  note: 500,
} as const

export type SchoolConsultValidationError = 'required' | 'invalidPhone' | 'tooLong'

export interface SchoolConsultFormValues {
  name: string
  phone: string
  organization: string
  note: string
}

const PHONE_ALLOWED_CHARS = /^[\d\s+\-()]+$/

function isDisallowedControl(code: number): boolean {
  return code <= 8 || code === 11 || code === 12 || (code >= 14 && code <= 31) || code === 127
}

function stripDisallowedControls(value: string): string {
  let out = ''
  for (const char of value) {
    if (!isDisallowedControl(char.charCodeAt(0))) {
      out += char
    }
  }
  return out
}

function collapseWhitespace(value: string, keepNewlines: boolean): string {
  if (keepNewlines) {
    return value
      .split('\n')
      .map((line) => line.replace(/[ \t]+/g, ' ').trim())
      .filter((line) => line.length > 0)
      .join('\n')
  }
  return value.replace(/\s+/g, ' ').trim()
}

function sanitizeField(
  value: string,
  maxLen: number,
  keepNewlines: boolean
): { ok: true; value: string } | { ok: false; error: SchoolConsultValidationError } {
  let cleaned = value.trim()
  if (!cleaned) {
    return { ok: false, error: 'required' }
  }
  cleaned = stripDisallowedControls(cleaned)
  cleaned = cleaned.replace(/<@[^>\s]+>/g, '')
  cleaned = collapseWhitespace(cleaned, keepNewlines)
  if (!cleaned) {
    return { ok: false, error: 'required' }
  }
  if (cleaned.length > maxLen) {
    return { ok: false, error: 'tooLong' }
  }
  return { ok: true, value: cleaned }
}

function validatePhone(
  value: string
): { ok: true; value: string } | { ok: false; error: SchoolConsultValidationError } {
  const cleaned = value.trim()
  if (!cleaned) {
    return { ok: false, error: 'required' }
  }
  if (cleaned.length > SCHOOL_CONSULT_LIMITS.phone) {
    return { ok: false, error: 'tooLong' }
  }
  if (!PHONE_ALLOWED_CHARS.test(cleaned)) {
    return { ok: false, error: 'invalidPhone' }
  }
  const digits = cleaned.replace(/\D/g, '')
  if (digits.length < 7 || digits.length > 15) {
    return { ok: false, error: 'invalidPhone' }
  }
  return { ok: true, value: cleaned }
}

export function validateSchoolConsultForm(
  form: SchoolConsultFormValues
):
  | { ok: true; values: SchoolConsultFormValues }
  | { ok: false; error: SchoolConsultValidationError; field: keyof SchoolConsultFormValues } {
  const nameResult = sanitizeField(form.name, SCHOOL_CONSULT_LIMITS.name, false)
  if (!nameResult.ok) {
    return { ok: false, error: nameResult.error, field: 'name' }
  }

  const phoneResult = validatePhone(form.phone)
  if (!phoneResult.ok) {
    return { ok: false, error: phoneResult.error, field: 'phone' }
  }

  const orgResult = sanitizeField(form.organization, SCHOOL_CONSULT_LIMITS.organization, false)
  if (!orgResult.ok) {
    return { ok: false, error: orgResult.error, field: 'organization' }
  }

  const noteTrimmed = form.note.trim()
  let noteValue = ''
  if (noteTrimmed) {
    const noteResult = sanitizeField(noteTrimmed, SCHOOL_CONSULT_LIMITS.note, true)
    if (!noteResult.ok) {
      return { ok: false, error: noteResult.error, field: 'note' }
    }
    noteValue = noteResult.value
  }

  return {
    ok: true,
    values: {
      name: nameResult.value,
      phone: phoneResult.value,
      organization: orgResult.value,
      note: noteValue,
    },
  }
}

export function consultProfileFromAccount(input: {
  username?: string | null
  phone?: string | null
  schoolName?: string | null
}): { name: string; phone: string; organization: string } {
  const username = (input.username || '').trim()
  const storedPhone = (input.phone || '').trim()
  const phone = isCnMainlandMobile(storedPhone) ? storedPhone : ''
  const organization = (input.schoolName || '').trim()
  const looksLikeAccountKey =
    /^\d{7,15}$/.test(username) || (storedPhone !== '' && username === storedPhone)
  const name = looksLikeAccountKey ? '' : username
  return {
    name: name.slice(0, SCHOOL_CONSULT_LIMITS.name),
    phone: phone.slice(0, SCHOOL_CONSULT_LIMITS.phone),
    organization: organization.slice(0, SCHOOL_CONSULT_LIMITS.organization),
  }
}

export function schoolConsultValidationMessageKey(error: SchoolConsultValidationError): string {
  switch (error) {
    case 'required':
      return 'thinkingCoins.school.validationRequired'
    case 'invalidPhone':
      return 'thinkingCoins.school.validationPhone'
    case 'tooLong':
      return 'thinkingCoins.school.validationTooLong'
    default:
      return 'thinkingCoins.school.submitFailed'
  }
}
