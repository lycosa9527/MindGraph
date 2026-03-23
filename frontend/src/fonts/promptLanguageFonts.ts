/**
 * Lazy Fontsource loaders keyed by script. Eager Latin + SC + TC live in eagerFonts.ts.
 */
export type FontModuleId =
  | 'noto-sans-cyrillic'
  | 'noto-sans-greek'
  | 'noto-sans-vietnamese'
  | 'noto-sans-jp'
  | 'noto-sans-kr'
  | 'noto-sans-thai'
  | 'noto-sans-lao'
  | 'noto-sans-khmer'
  | 'noto-sans-myanmar'
  | 'noto-sans-arabic'
  | 'noto-sans-hebrew'
  | 'noto-sans-devanagari'
  | 'noto-sans-bengali'
  | 'noto-sans-gurmukhi'
  | 'noto-sans-gujarati'
  | 'noto-sans-oriya'
  | 'noto-sans-tamil'
  | 'noto-sans-telugu'
  | 'noto-sans-malayalam'
  | 'noto-sans-kannada'
  | 'noto-sans-sinhala'
  | 'noto-sans-georgian'
  | 'noto-sans-armenian'
  | 'noto-sans-ethiopic'
  | 'noto-serif-tibetan'
  | 'noto-sans-ol-chiki'
  | 'noto-sans-meetei-mayek'

const CYRILLIC_CODES = new Set<string>([
  'ru',
  'uk',
  'bg',
  'mk',
  'sr',
  'be',
  'kk',
  'tg',
  'ba',
  'tt',
  'mn',
])

const ARABIC_SCRIPT_CODES = new Set<string>([
  'ar',
  'acm',
  'ars',
  'arz',
  'apc',
  'acq',
  'prs',
  'aeb',
  'ary',
  'fa',
  'ur',
  'ug',
  'sd',
])

const DEVANAGARI_CODES = new Set<string>([
  'hi',
  'ne',
  'mr',
  'mag',
  'awa',
  'mai',
  'hne',
  'bho',
  'kok',
])

function pair(
  a: () => Promise<unknown>,
  b: () => Promise<unknown>
): Promise<void> {
  return Promise.all([a(), b()]).then(() => undefined)
}

const FONT_LOADERS: Record<FontModuleId, () => Promise<void>> = {
  'noto-sans-cyrillic': () =>
    pair(
      () => import('@fontsource/noto-sans/cyrillic-400.css'),
      () => import('@fontsource/noto-sans/cyrillic-600.css')
    ),
  'noto-sans-greek': () =>
    pair(
      () => import('@fontsource/noto-sans/greek-400.css'),
      () => import('@fontsource/noto-sans/greek-600.css')
    ),
  'noto-sans-vietnamese': () =>
    pair(
      () => import('@fontsource/noto-sans/vietnamese-400.css'),
      () => import('@fontsource/noto-sans/vietnamese-600.css')
    ),
  'noto-sans-jp': () =>
    pair(
      () => import('@fontsource/noto-sans-jp/japanese-400.css'),
      () => import('@fontsource/noto-sans-jp/japanese-600.css')
    ),
  'noto-sans-kr': () =>
    pair(
      () => import('@fontsource/noto-sans-kr/korean-400.css'),
      () => import('@fontsource/noto-sans-kr/korean-600.css')
    ),
  'noto-sans-thai': () =>
    pair(
      () => import('@fontsource/noto-sans-thai/thai-400.css'),
      () => import('@fontsource/noto-sans-thai/thai-600.css')
    ),
  'noto-sans-lao': () =>
    pair(
      () => import('@fontsource/noto-sans-lao/lao-400.css'),
      () => import('@fontsource/noto-sans-lao/lao-600.css')
    ),
  'noto-sans-khmer': () =>
    pair(
      () => import('@fontsource/noto-sans-khmer/khmer-400.css'),
      () => import('@fontsource/noto-sans-khmer/khmer-600.css')
    ),
  'noto-sans-myanmar': () =>
    pair(
      () => import('@fontsource/noto-sans-myanmar/myanmar-400.css'),
      () => import('@fontsource/noto-sans-myanmar/myanmar-600.css')
    ),
  'noto-sans-arabic': () =>
    pair(
      () => import('@fontsource/noto-sans-arabic/arabic-400.css'),
      () => import('@fontsource/noto-sans-arabic/arabic-600.css')
    ),
  'noto-sans-hebrew': () =>
    pair(
      () => import('@fontsource/noto-sans-hebrew/hebrew-400.css'),
      () => import('@fontsource/noto-sans-hebrew/hebrew-600.css')
    ),
  'noto-sans-devanagari': () =>
    pair(
      () => import('@fontsource/noto-sans-devanagari/devanagari-400.css'),
      () => import('@fontsource/noto-sans-devanagari/devanagari-600.css')
    ),
  'noto-sans-bengali': () =>
    pair(
      () => import('@fontsource/noto-sans-bengali/bengali-400.css'),
      () => import('@fontsource/noto-sans-bengali/bengali-600.css')
    ),
  'noto-sans-gurmukhi': () =>
    pair(
      () => import('@fontsource/noto-sans-gurmukhi/gurmukhi-400.css'),
      () => import('@fontsource/noto-sans-gurmukhi/gurmukhi-600.css')
    ),
  'noto-sans-gujarati': () =>
    pair(
      () => import('@fontsource/noto-sans-gujarati/gujarati-400.css'),
      () => import('@fontsource/noto-sans-gujarati/gujarati-600.css')
    ),
  'noto-sans-oriya': () =>
    pair(
      () => import('@fontsource/noto-sans-oriya/oriya-400.css'),
      () => import('@fontsource/noto-sans-oriya/oriya-600.css')
    ),
  'noto-sans-tamil': () =>
    pair(
      () => import('@fontsource/noto-sans-tamil/tamil-400.css'),
      () => import('@fontsource/noto-sans-tamil/tamil-600.css')
    ),
  'noto-sans-telugu': () =>
    pair(
      () => import('@fontsource/noto-sans-telugu/telugu-400.css'),
      () => import('@fontsource/noto-sans-telugu/telugu-600.css')
    ),
  'noto-sans-malayalam': () =>
    pair(
      () => import('@fontsource/noto-sans-malayalam/malayalam-400.css'),
      () => import('@fontsource/noto-sans-malayalam/malayalam-600.css')
    ),
  'noto-sans-kannada': () =>
    pair(
      () => import('@fontsource/noto-sans-kannada/kannada-400.css'),
      () => import('@fontsource/noto-sans-kannada/kannada-600.css')
    ),
  'noto-sans-sinhala': () =>
    pair(
      () => import('@fontsource/noto-sans-sinhala/sinhala-400.css'),
      () => import('@fontsource/noto-sans-sinhala/sinhala-600.css')
    ),
  'noto-sans-georgian': () =>
    pair(
      () => import('@fontsource/noto-sans-georgian/georgian-400.css'),
      () => import('@fontsource/noto-sans-georgian/georgian-600.css')
    ),
  'noto-sans-armenian': () =>
    pair(
      () => import('@fontsource/noto-sans-armenian/armenian-400.css'),
      () => import('@fontsource/noto-sans-armenian/armenian-600.css')
    ),
  'noto-sans-ethiopic': () =>
    pair(
      () => import('@fontsource/noto-sans-ethiopic/ethiopic-400.css'),
      () => import('@fontsource/noto-sans-ethiopic/ethiopic-600.css')
    ),
  'noto-serif-tibetan': () =>
    pair(
      () => import('@fontsource/noto-serif-tibetan/tibetan-400.css'),
      () => import('@fontsource/noto-serif-tibetan/tibetan-600.css')
    ),
  'noto-sans-ol-chiki': () =>
    pair(
      () => import('@fontsource/noto-sans-ol-chiki/ol-chiki-400.css'),
      () => import('@fontsource/noto-sans-ol-chiki/ol-chiki-600.css')
    ),
  'noto-sans-meetei-mayek': () =>
    pair(
      () => import('@fontsource/noto-sans-meetei-mayek/meetei-mayek-400.css'),
      () => import('@fontsource/noto-sans-meetei-mayek/meetei-mayek-600.css')
    ),
}

const loadedModules = new Set<FontModuleId>()

export function fontModulesForPromptLanguageCode(code: string): FontModuleId[] {
  const c = code.trim().toLowerCase()
  if (CYRILLIC_CODES.has(c)) {
    return ['noto-sans-cyrillic']
  }
  if (c === 'el') {
    return ['noto-sans-greek']
  }
  if (c === 'vi') {
    return ['noto-sans-vietnamese']
  }
  if (c === 'ja') {
    return ['noto-sans-jp']
  }
  if (c === 'ko') {
    return ['noto-sans-kr']
  }
  if (c === 'th') {
    return ['noto-sans-thai']
  }
  if (c === 'lo') {
    return ['noto-sans-lao']
  }
  if (c === 'km') {
    return ['noto-sans-khmer']
  }
  if (c === 'my') {
    return ['noto-sans-myanmar']
  }
  if (ARABIC_SCRIPT_CODES.has(c)) {
    return ['noto-sans-arabic']
  }
  if (c === 'he' || c === 'ydd') {
    return ['noto-sans-hebrew']
  }
  if (DEVANAGARI_CODES.has(c)) {
    return ['noto-sans-devanagari']
  }
  if (c === 'bn' || c === 'as') {
    return ['noto-sans-bengali']
  }
  if (c === 'pa') {
    return ['noto-sans-gurmukhi']
  }
  if (c === 'gu') {
    return ['noto-sans-gujarati']
  }
  if (c === 'or') {
    return ['noto-sans-oriya']
  }
  if (c === 'ta') {
    return ['noto-sans-tamil']
  }
  if (c === 'te') {
    return ['noto-sans-telugu']
  }
  if (c === 'ml') {
    return ['noto-sans-malayalam']
  }
  if (c === 'kn') {
    return ['noto-sans-kannada']
  }
  if (c === 'si') {
    return ['noto-sans-sinhala']
  }
  if (c === 'ka') {
    return ['noto-sans-georgian']
  }
  if (c === 'hy') {
    return ['noto-sans-armenian']
  }
  if (c === 'am') {
    return ['noto-sans-ethiopic']
  }
  if (c === 'bo') {
    return ['noto-serif-tibetan']
  }
  if (c === 'sat') {
    return ['noto-sans-ol-chiki']
  }
  if (c === 'mni') {
    return ['noto-sans-meetei-mayek']
  }
  return []
}

async function loadFontModule(id: FontModuleId): Promise<void> {
  if (loadedModules.has(id)) {
    return
  }
  const loader = FONT_LOADERS[id]
  await loader()
  loadedModules.add(id)
}

/**
 * Loads Fontsource CSS for the given prompt output language code (lazy, cached).
 */
export async function ensureFontsForLanguageCode(code: string): Promise<void> {
  const modules = fontModulesForPromptLanguageCode(code)
  if (modules.length === 0) {
    if (typeof document !== 'undefined' && document.fonts?.ready) {
      await document.fonts.ready
    }
    return
  }
  await Promise.all(modules.map((id) => loadFontModule(id)))
  if (typeof document !== 'undefined' && document.fonts?.ready) {
    await document.fonts.ready
  }
}
