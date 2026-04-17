/**
 * Compare first N UI locales' message values to English — report % "translated"
 * (value !== English value for that key). English locale is the baseline (skipped).
 *
 * "Translated" here means the string differs from `en` (materialized stubs are 0%).
 *
 * Run: npx tsx scripts/check-ui-translation-coverage.ts
 */
import { INTERFACE_LANGUAGE_PICKER_CODES } from '../src/i18n/locales'
import { SUPPORTED_UI_LOCALES } from '../src/i18n/supportedUiLocales'

const ENGLISH_NAME_BY_CODE = new Map(
  SUPPORTED_UI_LOCALES.map((e) => [e.code, e.englishName] as const)
)

const NS_FILES = [
  'admin',
  'auth',
  'canvas',
  'common',
  'community',
  'knowledge',
  'mindmate',
  'notification',
  'sidebar',
  'workshop',
] as const

type Messages = Record<string, string>

async function loadMessages(code: string, ns: string): Promise<Messages> {
  const mod = (await import(`../src/locales/messages/${code}/${ns}.ts`)) as {
    default: Messages
  }
  return mod.default
}

function compareNamespace(en: Messages, loc: Messages): { total: number; translated: number } {
  let translated = 0
  let total = 0
  for (const key of Object.keys(en)) {
    total += 1
    if (Object.prototype.hasOwnProperty.call(loc, key) && loc[key] !== en[key]) {
      translated += 1
    }
  }
  return { total, translated }
}

/** Keys in auth related to SMS/email OTP, captcha send, region hybrid (subset for quick audit). */
const AUTH_SMS_EMAIL_KEY =
  /sms|Sms|email|Email|sesLogin|verification|Verification|codeSent|sendSms|sendEmail|resend|networkSms|networkEmail|enter6Digit|hybridRegister|mainland|educationEmail|registrationEmail|acknowledgeOverseas|loginPhoneOrEmail|forgotPhoneOrEmail|detectingRegion|waitRegion/

function compareAuthSmsEmailSubset(
  en: Messages,
  loc: Messages
): { total: number; translated: number } {
  let translated = 0
  let total = 0
  for (const key of Object.keys(en)) {
    if (!AUTH_SMS_EMAIL_KEY.test(key)) {
      continue
    }
    total += 1
    if (Object.prototype.hasOwnProperty.call(loc, key) && loc[key] !== en[key]) {
      translated += 1
    }
  }
  return { total, translated }
}

async function main(): Promise<void> {
  const codes = [...INTERFACE_LANGUAGE_PICKER_CODES]

  console.log(
    `Tier-27 / interface-picker UI locales (${INTERFACE_LANGUAGE_PICKER_CODES.length} codes, see locales.ts):`
  )
  console.log(codes.join(', '))
  console.log('')

  const enMaps: Record<string, Messages> = {}
  for (const ns of NS_FILES) {
    enMaps[ns] = await loadMessages('en', ns)
  }

  for (const code of codes) {
    if (code === 'en') {
      console.log(`[${code}] (source — skipped)\n`)
      continue
    }

    let totalKeys = 0
    let totalTranslated = 0
    const nsPct: Record<string, number> = {}
    const locMaps: Record<string, Messages> = {}

    for (const ns of NS_FILES) {
      const en = enMaps[ns]
      const loc = await loadMessages(code, ns)
      locMaps[ns] = loc
      const { total, translated } = compareNamespace(en, loc)
      totalKeys += total
      totalTranslated += translated
      nsPct[ns] = total === 0 ? 100 : Math.round((translated / total) * 1000) / 10
    }

    const overall = totalKeys === 0 ? 0 : Math.round((totalTranslated / totalKeys) * 1000) / 10
    const otpSub = compareAuthSmsEmailSubset(enMaps.auth, locMaps.auth)
    const otpPct =
      otpSub.total === 0 ? 0 : Math.round((otpSub.translated / otpSub.total) * 1000) / 10

    const englishName = ENGLISH_NAME_BY_CODE.get(code) ?? code
    console.log(
      `[${code}] ${englishName}: ${overall}% keys differ from English (${totalTranslated}/${totalKeys})`
    )
    console.log(
      `  auth (SMS/email/OTP-related key subset): ${otpPct}% (${otpSub.translated}/${otpSub.total} keys)`
    )
    console.log(`  by namespace: ${NS_FILES.map((ns) => `${ns}:${nsPct[ns]}%`).join(' | ')}`)
    console.log('')
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
